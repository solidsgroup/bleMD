"""A dedicated bleMD mode in Blender's Node Editor."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories

from .bleMDPipeline import TREE_TYPE, SOURCE_TYPE, SCRIPT_TYPE, OUTPUT_TYPE, SOCKET_TYPE, evaluate_tree
from .bleMDNodes import create_field_material
from . import bleMDModifiers, bleMDFields, bleMDViewport, bleMDSource, bleMDLive, bleMDWorkspace, bleMDShader, bleMDScene, bleMDPlayback, bleMDUtilities
from bpy.app.handlers import persistent


class BleMDNodeTree(bpy.types.NodeTree):
    bl_idname = TREE_TYPE
    bl_label = "bleMD"
    bl_icon = 'NODETREE'

    automatic_updates: BoolProperty(name="Automatic Updates", default=True,
        description="Evaluate node edits and timeline changes automatically; disable for large datasets")
    scene: PointerProperty(type=bpy.types.Scene, name="Scene")
    # Retained for migration of older saved trees; playback is now per source.
    start_frame: IntProperty(name="Start Frame", default=0)
    frame_stride: IntProperty(name="Frames per Simulation Step", default=1, min=1)
    interpolation: EnumProperty(name="Between Steps", items=[
        ('HOLD', "Hold", "Keep the preceding simulation frame"),
        ('LINEAR', "Linear", "Interpolate positions and floating-point attributes using particle IDs"),
    ], default='HOLD')
    frame_count: IntProperty(default=0)
    last_message: StringProperty(default="Choose a simulation file to start")
    has_error: BoolProperty(default=False)


class BleMDPipelineSocket(bpy.types.NodeSocket):
    bl_idname = SOCKET_TYPE
    bl_label = "Particle Dataset"

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    @classmethod
    def draw_color_simple(cls):
        return (0.2, 0.65, 0.85, 1.0)


class BleMDNode:
    @classmethod
    def poll(cls, tree):
        return tree.bl_idname == TREE_TYPE


class BleMDFileSource(BleMDNode, bpy.types.Node):
    bl_idname = SOURCE_TYPE
    bl_label = "File Source"
    bl_icon = 'FILE_FOLDER'
    filepath: StringProperty(name="File", subtype='FILE_PATH', update=bleMDSource.source_changed)
    start_frame: IntProperty(name="Start Frame", default=0,
        description="Blender timeline frame corresponding to the first saved MD frame")
    timesteps_per_frame: IntProperty(name="Timesteps per Frame", default=1, min=1,
        description="Blender frames between consecutive saved MD frames; values above one interpolate smoothly")
    channels_loaded: BoolProperty(default=False)
    channels_error: BoolProperty(default=False)
    channels_message: StringProperty(default='Choose a file to discover particle fields')

    def init(self, context):
        self.width = 260
        self.outputs.new(SOCKET_TYPE, "Data")
        self['bleMD_timing_version'] = 1
        bleMDSource.ensure_atom_id(self)

    def draw_buttons(self, context, layout):
        layout.prop(self, "filepath", text="")
        layout.prop(self, 'start_frame')
        layout.prop(self, 'timesteps_per_frame')
        if self.timesteps_per_frame > 1:
            layout.label(text='Smooth interpolation between MD frames')
        layout.operator('blemd.refresh_source_fields', text='Refresh Fields', icon='FILE_REFRESH').node_name = self.name
        layout.label(text='Field discovery failed; refresh for details' if self.channels_error else self.channels_message,
                     icon='ERROR' if self.channels_error else 'INFO')


class BleMDOvitoScript(BleMDNode, bpy.types.Node):
    bl_idname = SCRIPT_TYPE
    bl_label = "OVITO Script"
    bl_icon = 'TEXT'
    enabled: BoolProperty(name="Enabled", default=True)
    script: PointerProperty(type=bpy.types.Text, name="Script")

    def init(self, context):
        self.width = 240
        self.inputs.new(SOCKET_TYPE, "Data")
        self.outputs.new(SOCKET_TYPE, "Data")

    def draw_buttons(self, context, layout):
        layout.prop(self, "enabled")
        col = layout.column()
        col.prop(self, "script", text="")
        col.operator("blemd.new_script", text="New Script", icon='ADD').node_name = self.name


class BleMDParticleOutput(BleMDNode, bpy.types.Node):
    bl_idname = OUTPUT_TYPE
    bl_label = "Particle Output"
    bl_icon = 'OUTLINER_OB_POINTCLOUD'
    target: PointerProperty(type=bpy.types.Object)
    radius: FloatProperty(name="Radius", default=1.0, min=0.0, get=bleMDFields.radius_get, set=bleMDFields.radius_set)
    radius_scale: FloatProperty(name="Radius Scale", default=1.0, min=0.0)
    color_mode: EnumProperty(name="Color", items=[('AUTO', 'From data / fallback', 'Use native OVITO Color if available; otherwise use the specified color'), ('UNIFORM', 'Uniform', 'Use the specified color when no Color field is connected')], default='AUTO')
    color: FloatVectorProperty(name="Color", subtype='COLOR', size=3, min=0, max=1, default=(.6,.6,.6), get=bleMDFields.color_get, set=bleMDFields.color_set)
    viewport_detail: EnumProperty(name="Viewport", items=bleMDViewport.DETAIL_ITEMS, default="AUTO", update=bleMDViewport.change_detail)
    material: PointerProperty(type=bpy.types.Material, name="Material")
    attributes: StringProperty(name="Attributes", description="Comma-separated particle properties; empty transfers all supported numeric properties")

    def init(self, context):
        self.width = 260
        self.inputs.new(SOCKET_TYPE, "Data")
        for name, kind in (("Radius", bleMDFields.SCALAR), ("Color", bleMDFields.COLOR), ("Value", bleMDFields.SCALAR), ("Vector", bleMDFields.VECTOR)):
            self.inputs.new(kind, name)
        self.inputs['Radius'].default_value = 1.
        self['bleMD_socket_defaults'] = 1

    def draw_buttons(self, context, layout):
        if self.inputs.get('Radius') and self.inputs['Radius'].is_linked:
            layout.prop(self, "radius_scale")
        if not self.inputs['Color'].is_linked:
            layout.prop(self, 'color_mode', text='')
        layout.prop(self, "viewport_detail", text="")
        layout.prop(self, "material", text="")
        layout.operator("blemd.new_material", text="New Material", icon='ADD').node_name = self.name
        if self.inputs.get("Color") and self.inputs["Color"].is_linked:
            layout.label(text="Shader attribute: bleMD Color")
        if self.inputs.get("Value") and self.inputs["Value"].is_linked:
            layout.label(text="Scalar attribute: bleMD Value")
        for socket in self.inputs:
            if 'bleMD_export_name' in socket:
                row = layout.row(align=True)
                row.prop(socket, '["bleMD_export_name"]', text=socket.name)
                op = row.operator('blemd.remove_shader_field', text='', icon='X')
                op.node_name, op.socket_id = self.name, socket.identifier
        row = layout.row(align=True)
        for kind, label in (('SCALAR','+ Value'), ('VECTOR','+ Vector'), ('COLOR','+ Color')):
            op = row.operator('blemd.add_shader_field', text=label)
            op.node_name, op.kind = self.name, kind
        layout.prop(self, "attributes")
        layout.label(text="Empty = all numeric properties")
        if self.target:
            layout.label(text=self.target.name, icon='OBJECT_DATA')
            layout.operator("blemd.select_output", text="Select Output")
        layout.operator("blemd.update_pipeline", text="Update", icon='FILE_REFRESH')


def current_tree(context):
    space = context.space_data
    if space and space.type == 'NODE_EDITOR' and space.tree_type == TREE_TYPE:
        return space.edit_tree or space.node_tree
    return None


def starter_tree(tree=None):
    if getattr(bpy.context, 'scene', None) is not None:
        bleMDScene.ensure_defaults(bpy.context.scene)
    tree = tree or bpy.data.node_groups.new("bleMD Pipeline", TREE_TYPE)
    tree.use_fake_user = True
    source = tree.nodes.new(SOURCE_TYPE)
    source.location = (-600, 180)
    color = tree.nodes.new('BleMDColorMap')
    color.location = (-250, -50)
    color.label = 'Color by Atom ID'
    color.range_mode = 'FIRST_FRAME'
    output = tree.nodes.new(OUTPUT_TYPE)
    output.location = (80, 180)
    tree.links.new(source.outputs[0], output.inputs[0])
    tree.links.new(bleMDSource.ensure_atom_id(source), color.inputs['Value'])
    tree.links.new(color.outputs['Color'], output.inputs['Color'])
    return tree


class BLEMD_OT_add_shader_field(bpy.types.Operator):
    bl_idname = 'blemd.add_shader_field'
    bl_label = 'Add Shader Field'
    bl_description = 'Add a named particle field accessible in shaders with an Attribute node'
    bl_options = {'REGISTER', 'UNDO'}
    node_name: StringProperty()
    kind: EnumProperty(items=[('SCALAR','Value',''), ('VECTOR','Vector',''), ('COLOR','Color','')])

    def execute(self, context):
        tree = current_tree(context)
        node = tree.nodes.get(self.node_name) if tree else None
        if node is None or node.bl_idname != OUTPUT_TYPE:
            return {'CANCELLED'}
        socket = node.inputs.new(bleMDFields.TYPE_IDS[self.kind], 'Shader ' + self.kind.title())
        used = {s.get('bleMD_export_name') for s in node.inputs}
        index = 1
        while f'Field {index}' in used:
            index += 1
        socket['bleMD_export_name'] = f'Field {index}'
        return {'FINISHED'}


class BLEMD_OT_remove_shader_field(bpy.types.Operator):
    bl_idname = 'blemd.remove_shader_field'
    bl_label = 'Remove Shader Field'
    bl_options = {'REGISTER', 'UNDO'}
    node_name: StringProperty()
    socket_id: StringProperty()

    def execute(self, context):
        tree = current_tree(context)
        node = tree.nodes.get(self.node_name) if tree else None
        if node:
            socket = next((s for s in node.inputs if s.identifier == self.socket_id and 'bleMD_export_name' in s), None)
            if socket:
                node.inputs.remove(socket)
                return {'FINISHED'}
        return {'CANCELLED'}


class BLEMD_OT_new_pipeline(bpy.types.Operator):
    bl_idname = "blemd.new_pipeline"
    bl_label = "New Pipeline"
    bl_description = "Create a File Source, Atom ID Color Map, and Particle Output"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'NODE_EDITOR' and context.space_data.tree_type == TREE_TYPE

    def execute(self, context):
        tree = current_tree(context)
        context.space_data.node_tree = starter_tree(tree if tree and not tree.nodes else None)
        context.space_data.node_tree.scene = context.scene
        region = next((region for region in context.area.regions if region.type == 'WINDOW'), None)
        if region is not None:
            with context.temp_override(region=region):
                bpy.ops.node.view_all()
        return {'FINISHED'}


class BleMDTreeOperator:
    @classmethod
    def poll(cls, context):
        return current_tree(context) is not None


class BLEMD_OT_refresh_source_fields(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = 'blemd.refresh_source_fields'
    bl_label = 'Refresh Source Fields'
    bl_description = 'Read the first simulation frame and expose its particle properties as outputs'
    bl_options = {'REGISTER', 'UNDO'}
    node_name: StringProperty()

    def execute(self, context):
        node = current_tree(context).nodes.get(self.node_name)
        if node is None or node.bl_idname != SOURCE_TYPE:
            return {'CANCELLED'}
        bleMDLive.invalidate(node.id_data)
        if not bleMDSource.inspect_source(node):
            self.report({'ERROR'}, node.channels_message)
            return {'CANCELLED'}
        self.report({'INFO'}, node.channels_message)
        return {'FINISHED'}


class BLEMD_OT_update_pipeline(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = "blemd.update_pipeline"
    bl_label = "Update"
    bl_description = "Evaluate the pipeline at the current Blender frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        tree = current_tree(context)
        try:
            bleMDLive.evaluate(tree, context.scene, force=True)
        except Exception as error:
            tree.has_error = True
            tree.last_message = str(error)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, tree.last_message)
        return {'FINISHED'}


class BLEMD_OT_new_script(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = "blemd.new_script"
    bl_label = "New OVITO Script"
    bl_options = {'REGISTER', 'UNDO'}
    node_name: StringProperty()

    def execute(self, context):
        node = current_tree(context).nodes.get(self.node_name)
        if node is None or node.bl_idname != SCRIPT_TYPE:
            return {'CANCELLED'}
        script = bpy.data.texts.new("bleMD OVITO Script")
        script.write('# Configure the input "pipeline" here. This runs when the recipe changes or on manual Update.\n'
                     '# Edit this text in Blender\'s Text Editor.\n\n'
                     '# from ovito.modifiers import CentroSymmetryModifier\n'
                     '# pipeline.modifiers.append(CentroSymmetryModifier(num_neighbors=12))\n')
        node.script = script
        node.enabled = True
        return {'FINISHED'}


class BLEMD_OT_new_material(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = "blemd.new_material"
    bl_label = "New bleMD Material"
    bl_options = {'REGISTER', 'UNDO'}
    node_name: StringProperty()

    def execute(self, context):
        node = current_tree(context).nodes.get(self.node_name)
        if node is None or node.bl_idname != OUTPUT_TYPE:
            return {'CANCELLED'}
        node.material = create_field_material()
        return {'FINISHED'}


class BLEMD_OT_modifier_configuration(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = "blemd.modifier_configuration"
    bl_label = "New Modifier Configuration"
    bl_options = {'REGISTER', 'UNDO'}
    node_name: StringProperty()

    def execute(self, context):
        node = current_tree(context).nodes.get(self.node_name)
        if node is None or not bleMDModifiers.is_modifier_node(node):
            return {'CANCELLED'}
        script = bpy.data.texts.new(node.bl_label + " Configuration")
        script.write('# Runs after this modifier is appended to the pipeline.\n'
                     '# Available: modifier (this node), pipeline (upstream plus this node).\n'
                     '# Use for advanced parameters and methods, e.g.:\n'
                     '# modifier.some_parameter = value\n')
        node.configuration = script
        return {'FINISHED'}


class BLEMD_OT_select_output(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = "blemd.select_output"
    bl_label = "Select Output"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        outputs = [node for node in current_tree(context).nodes if node.bl_idname == OUTPUT_TYPE]
        if len(outputs) != 1 or outputs[0].target is None:
            return {'CANCELLED'}
        obj = outputs[0].target
        if obj.name not in context.view_layer.objects:
            self.report({'ERROR'}, "The output is not in the current view layer")
            return {'CANCELLED'}
        for selected in context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class BLEMD_OT_fit_timeline(BleMDTreeOperator, bpy.types.Operator):
    bl_idname = "blemd.fit_timeline"
    bl_label = "Fit Timeline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        tree = current_tree(context)
        if not tree.frame_count:
            self.report({'ERROR'}, "Update the pipeline first")
            return {'CANCELLED'}
        bleMDPlayback.fit(context.scene, tree)
        return {'FINISHED'}


class BLEMD_PT_pipeline(bpy.types.Panel):
    bl_label = "bleMD Pipeline"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "bleMD"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == TREE_TYPE

    def draw(self, context):
        layout = self.layout
        tree = current_tree(context)
        if tree is None or not tree.nodes:
            layout.operator("blemd.new_pipeline")
            return
        layout.operator("blemd.layout", icon='WORKSPACE')
        layout.prop(tree, "automatic_updates")
        layout.prop(context.scene, "frame_current", text="Current Frame")
        layout.label(text="Playback timing: File Source node")
        layout.operator("blemd.update_pipeline", icon='FILE_REFRESH')
        layout.operator("blemd.fit_timeline")
        if tree.frame_count:
            layout.label(text=f"{tree.frame_count} simulation frames")
        if not tree.automatic_updates:
            layout.label(text="Paused: click Update to evaluate", icon='PAUSE')
        box = layout.box()
        box.alert = tree.has_error
        # Keep long OVITO exceptions readable in the sidebar.
        import textwrap
        for line in textwrap.wrap(tree.last_message, width=40):
            box.label(text=line)


class BleMDNodeCategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == TREE_TYPE


def draw_header(self, context):
    if context.space_data.tree_type == TREE_TYPE:
        self.layout.operator("blemd.layout", text="bleMD Layout", icon='WORKSPACE')
        self.layout.operator("blemd.new_pipeline", icon='ADD')
        row = self.layout.row()
        row.enabled = current_tree(context) is not None
        row.operator("blemd.update_pipeline", icon='FILE_REFRESH')


CLASSES = (
    BleMDNodeTree, BleMDPipelineSocket, *bleMDFields.SOCKET_CLASSES,
    *bleMDFields.NODE_CLASSES, *bleMDUtilities.NODE_CLASSES, BleMDFileSource, BleMDOvitoScript,
    BleMDParticleOutput, BLEMD_OT_new_pipeline, BLEMD_OT_update_pipeline,
    BLEMD_OT_new_script, BLEMD_OT_new_material, BLEMD_OT_select_output,
    BLEMD_OT_fit_timeline, BLEMD_PT_pipeline,
    BLEMD_OT_modifier_configuration, BLEMD_OT_refresh_source_fields,
    BLEMD_OT_add_shader_field, BLEMD_OT_remove_shader_field,
)


@persistent
def migrate_fields(_):
    for tree in getattr(bpy.data, 'node_groups', ()):
        if tree.bl_idname == TREE_TYPE:
            bleMDFields.migrate_tree(tree)
    bleMDViewport.refresh_saved_outputs()
    if hasattr(bpy.data, 'workspaces'):
        bleMDWorkspace.migrate_views()


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bleMDModifiers.register()
    bleMDWorkspace.register()
    bleMDShader.register()
    bleMDScene.register()
    bleMDViewport.register()
    bpy.types.Object.bleMD_node_tree = PointerProperty(type=bpy.types.NodeTree)
    categories = [BleMDNodeCategory("BLEMD_PIPELINE", "Input / Output / Scripts", items=[
        NodeItem(SOURCE_TYPE), NodeItem(SCRIPT_TYPE), NodeItem(OUTPUT_TYPE),
    ])]
    categories.append(BleMDNodeCategory("BLEMD_FIELDS", "Particle Fields",
        items=[NodeItem(cls.bl_idname) for cls in bleMDFields.NODE_CLASSES]))
    categories.append(BleMDNodeCategory("BLEMD_UTILITIES", "Utilities",
        items=[NodeItem(cls.bl_idname) for cls in bleMDUtilities.NODE_CLASSES]))
    categories.append(BleMDNodeCategory("BLEMD_LAYOUT", "Layout",
        items=[NodeItem('NodeFrame'), NodeItem('NodeReroute')]))
    catalog = bleMDModifiers.CATALOG
    order = list(bleMDModifiers.CATEGORY_ORDER)
    order += sorted({record['category'] for record in catalog.values()} - set(order))
    for index, category in enumerate(order):
        names = sorted((name for name in catalog if catalog[name]['category'] == category),
                       key=lambda name: catalog[name]['label'].casefold())
        if names:
            categories.append(BleMDNodeCategory(f"BLEMD_MODIFIERS_{index}", category,
                              items=[NodeItem(f"BleMD_{name}") for name in names]))
    register_node_categories("BLEMD_NODES", categories)
    bpy.types.NODE_HT_header.append(draw_header)
    bpy.app.handlers.load_post.append(migrate_fields)
    migrate_fields(None)
    bleMDLive.register()


def unregister():
    bleMDLive.unregister()
    bleMDWorkspace.unregister()
    bleMDShader.unregister()
    bleMDScene.unregister()
    # Blender 4.2 unregisters custom node types only in the main database.
    # Evaluated copies reached through Object.bleMD_node_tree otherwise retain
    # freed native type pointers. Drop those dependencies and flush evaluation
    # while the node types are still alive, then restore the saved recipe links.
    bindings = [(obj, obj.bleMD_node_tree) for obj in bpy.data.objects if obj.bleMD_node_tree]
    try:
        for obj, tree in bindings:
            obj.bleMD_node_tree = None
            obj.update_tag()
        if bindings:
            # update_tag() alone does not rebuild ID-pointer dependencies.
            # A temporary collection relation requests a full graph rebuild.
            marker = bpy.data.collections.new('bleMD unregister dependency refresh')
            try:
                for scene in bpy.data.scenes:
                    scene.collection.children.link(marker)
                    scene.collection.children.unlink(marker)
                    for layer in scene.view_layers:
                        layer.update()
            finally:
                bpy.data.collections.remove(marker)
    finally:
        for obj, tree in bindings:
            obj.bleMD_node_tree = tree
    bleMDViewport.unregister()
    bpy.app.handlers.load_post.remove(migrate_fields)
    bpy.types.NODE_HT_header.remove(draw_header)
    unregister_node_categories("BLEMD_NODES")
    bleMDModifiers.unregister()
    del bpy.types.Object.bleMD_node_tree
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
