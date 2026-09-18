"""Native shader groups with the same palette presets as bleMD Color Map."""
import bpy
from bpy.props import EnumProperty
from .bleMDPalette import ITEMS, apply_ramp


def changed(group, context):
    ramp = group.nodes.get('bleMD Palette')
    if ramp:
        apply_ramp(ramp.color_ramp, group.bleMD_palette)


def create_group(palette='viridis'):
    group = bpy.data.node_groups.new('bleMD Color Map', 'ShaderNodeTree')
    group['bleMD_palette_group'] = True
    for name, default in (('Value', 0.), ('Minimum', 0.), ('Maximum', 1.)):
        socket = group.interface.new_socket(name, in_out='INPUT', socket_type='NodeSocketFloat')
        socket.default_value = default
    group.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    inp = group.nodes.new('NodeGroupInput'); inp.location = (-500,0)
    mapping = group.nodes.new('ShaderNodeMapRange'); mapping.location = (-280,0)
    mapping.clamp = True
    for a,b in (('Value','Value'),('Minimum','From Min'),('Maximum','From Max')):
        group.links.new(inp.outputs[a], mapping.inputs[b])
    ramp = group.nodes.new('ShaderNodeValToRGB'); ramp.name = 'bleMD Palette'; ramp.location = (-40,0)
    out = group.nodes.new('NodeGroupOutput'); out.location = (260,0)
    group.links.new(mapping.outputs['Result'], ramp.inputs[0])
    group.links.new(ramp.outputs['Color'], out.inputs['Color'])
    group.bleMD_palette = palette
    changed(group, None)
    return group


class BLEMD_OT_shader_colormap(bpy.types.Operator):
    bl_idname = 'blemd.shader_colormap'
    bl_label = 'bleMD Color Map'
    bl_description = 'Add a shader Color Map using the bleMD palette library; choose presets in the bleMD sidebar'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.space_data and context.space_data.type == 'NODE_EDITOR'
                and context.space_data.tree_type == 'ShaderNodeTree' and context.space_data.edit_tree)

    def execute(self, context):
        tree = context.space_data.edit_tree
        for n in tree.nodes:
            n.select = False
        node = tree.nodes.new('ShaderNodeGroup')
        node.node_tree = create_group()
        node.label = 'bleMD Color Map'
        node.location = context.space_data.cursor_location
        node.select = True
        tree.nodes.active = node
        return {'FINISHED'}


class BLEMD_PT_shader(bpy.types.Panel):
    bl_label = 'bleMD Color Map'
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'bleMD'

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        tree = context.space_data.edit_tree
        node = tree.nodes.active if tree else None
        group = getattr(node, 'node_tree', None)
        if group and group.get('bleMD_palette_group'):
            layout.prop(group, 'bleMD_palette', text='Colorbar')
        layout.operator('blemd.shader_colormap')
        layout.label(text='Read exported fields with Attribute nodes.')
        obj = context.object
        if obj and obj.type == 'MESH' and obj.data.get('bleMD_object'):
            for attr in obj.data.attributes:
                if not attr.name.startswith('.') and attr.name != 'position':
                    layout.label(text=attr.name)


def menu(self, context):
    if context.space_data.tree_type == 'ShaderNodeTree':
        self.layout.operator('blemd.shader_colormap', icon='COLOR')


def register():
    bpy.types.ShaderNodeTree.bleMD_palette = EnumProperty(name='Colorbar', items=ITEMS, default='viridis', update=changed)
    bpy.utils.register_class(BLEMD_OT_shader_colormap)
    bpy.utils.register_class(BLEMD_PT_shader)
    bpy.types.NODE_MT_add.append(menu)


def unregister():
    bpy.types.NODE_MT_add.remove(menu)
    bpy.utils.unregister_class(BLEMD_PT_shader)
    bpy.utils.unregister_class(BLEMD_OT_shader_colormap)
    del bpy.types.ShaderNodeTree.bleMD_palette
