"""Round viewport particles and Workbench color-attribute support for Blender 4.2."""
import bpy
from bpy.app.handlers import persistent

COLOR = 'bleMD Color'
MARKER = 'bleMD_viewport_version'
DETAILS = {'LOW': (8, 4), 'MEDIUM': (16, 8), 'HIGH': (24, 12)}
DETAIL_ITEMS = [
    ('AUTO', 'Adaptive spheres', 'Round spheres for small systems; coarse spheres above 5,000 atoms to reduce memory'),
    ('LOW', 'Coarse spheres', '8 segments, 4 rings; lowest mesh cost'),
    ('MEDIUM', 'Round spheres', '16 segments, 8 rings'),
    ('HIGH', 'Smooth spheres', '24 segments, 12 rings; more viewport memory'),
    ('POINTS', 'Native points', 'Blender point-cloud preview; useful for very large datasets'),
]


def enable_solid_colors():
    # Workbench's color source is a viewport setting, not a per-object setting.
    # Include inactive VIEW_3D spaces so switching back from the node editor works.
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.color_type = 'VERTEX'


def activate_color(mesh):
    if COLOR not in mesh.color_attributes:
        return
    if mesh.color_attributes.active_color_name != COLOR:
        mesh.color_attributes.active_color_name = COLOR
    if mesh.color_attributes.default_color_name != COLOR:
        mesh.color_attributes.default_color_name = COLOR


def ensure_preview(obj, detail='AUTO'):
    """Extend the stock geometry graph in place, retaining radius and material nodes."""
    modifier = obj.modifiers.get('build_geonode')
    if not modifier or not modifier.node_group:
        return
    group = modifier.node_group
    nodes, links = group.nodes, group.links
    points = nodes.get('Mesh to Points')
    material = nodes.get('Set Material')
    if points is None or material is None:
        return
    if not group.get(MARKER):
        incoming = material.inputs['Geometry'].links
        # Only migrate our original point display connection. User-authored
        # geometry between these nodes is not replaced.
        if len(incoming) != 1 or incoming[0].from_node != points:
            return
        sphere = nodes.new('GeometryNodeMeshUVSphere')
        sphere.name = 'bleMD Viewport Sphere'
        sphere.label = 'Round viewport atoms'
        sphere.inputs['Radius'].default_value = 1
        sphere.location = (-300, -250)
        smooth = nodes.new('GeometryNodeSetShadeSmooth')
        smooth.name = 'bleMD Viewport Smooth'
        smooth.location = (-60, -250)
        links.new(sphere.outputs['Mesh'], smooth.inputs['Geometry'])
        radius = nodes.new('GeometryNodeInputRadius')
        radius.name = 'bleMD Viewport Radius'
        radius.location = (-300, -450)
        scale = nodes.new('ShaderNodeCombineXYZ')
        scale.name = 'bleMD Viewport Scale'
        scale.location = (-60, -450)
        for socket in scale.inputs:
            links.new(radius.outputs[0], socket)
        instances = nodes.new('GeometryNodeInstanceOnPoints')
        instances.name = 'bleMD Viewport Instances'
        instances.location = (180, -220)
        links.new(points.outputs['Points'], instances.inputs['Points'])
        links.new(smooth.outputs['Geometry'], instances.inputs['Instance'])
        links.new(scale.outputs[0], instances.inputs['Scale'])
        realize = nodes.new('GeometryNodeRealizeInstances')
        realize.name = 'bleMD Viewport Realize'
        realize.location = (420, -220)
        links.new(instances.outputs['Instances'], realize.inputs['Geometry'])
        viewport = nodes.new('GeometryNodeIsViewport')
        viewport.name = 'bleMD Is Viewport'
        viewport.location = (420, 100)
        switch = nodes.new('GeometryNodeSwitch')
        switch.input_type = 'GEOMETRY'
        switch.name = 'bleMD Viewport Switch'
        switch.label = 'Viewport spheres / render points'
        switch.location = (630, 50)
        links.new(points.outputs['Points'], switch.inputs['False'])
        links.new(realize.outputs['Geometry'], switch.inputs['True'])
        links.new(switch.outputs[0], material.inputs['Geometry'])
        material.location = (860, 50)
        for node in nodes:
            if node.bl_idname == 'NodeGroupOutput':
                node.location = (1090, 50)
        group[MARKER] = 1
    sphere = nodes.get('bleMD Viewport Sphere')
    switch = nodes.get('bleMD Viewport Switch')
    viewport = nodes.get('bleMD Is Viewport')
    # Do not reconstruct nodes an artist has removed from an upgraded group.
    if sphere is None or switch is None or viewport is None:
        return
    effective = ('LOW' if len(obj.data.vertices) > 5000 else 'MEDIUM') if detail == 'AUTO' else detail
    segments, rings = DETAILS.get(effective, DETAILS['MEDIUM'])
    if sphere.inputs['Segments'].default_value != segments:
        sphere.inputs['Segments'].default_value = segments
    if sphere.inputs['Rings'].default_value != rings:
        sphere.inputs['Rings'].default_value = rings
    control = switch.inputs['Switch']
    if detail == 'POINTS':
        for link in list(control.links):
            links.remove(link)
        control.default_value = False
    elif not control.is_linked:
        links.new(viewport.outputs[0], control)
    activate_color(obj.data)
    if COLOR in obj.data.color_attributes:
        enable_solid_colors()


@persistent
def update_evaluated_colors(scene, depsgraph=None):
    if depsgraph is None:
        return
    if depsgraph.mode != 'VIEWPORT':
        return
    for obj in scene.objects:
        if obj.type != 'MESH' or COLOR not in obj.data.color_attributes:
            continue
        modifier = obj.modifiers.get('build_geonode')
        if not modifier or not modifier.node_group or not modifier.node_group.get(MARKER):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        # Realize Instances in 4.2 keeps color values but drops the active/default
        # color names. Workbench reads these names from the evaluated mesh.
        # Repair only display metadata on the transient result; never write
        # geometry, rerun OVITO, or tag original IDs from this handler.
        if evaluated.type == 'MESH' and evaluated.data != obj.data:
            activate_color(evaluated.data)


def change_detail(node, context):
    if node.target is not None:
        ensure_preview(node.target, node.viewport_detail)


def refresh_saved_outputs():
    for obj in getattr(bpy.data, 'objects', ()):
        if obj.type != 'MESH' or not obj.data.get('bleMD_object'):
            continue
        tree = getattr(obj, 'bleMD_node_tree', None)
        output = next((n for n in tree.nodes if n.bl_idname == 'BleMDParticleOutput' and n.target == obj), None) if tree else None
        ensure_preview(obj, output.viewport_detail if output else 'AUTO')
    # File loading can build the initial dependency graph without firing the
    # update_post handler. Repair that first evaluated result explicitly too.
    if getattr(bpy.context, 'view_layer', None) is not None:
        update_evaluated_colors(bpy.context.scene, bpy.context.evaluated_depsgraph_get())


def register():
    bpy.app.handlers.depsgraph_update_post.append(update_evaluated_colors)
    bpy.app.handlers.frame_change_post.append(update_evaluated_colors)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(update_evaluated_colors)
    bpy.app.handlers.frame_change_post.remove(update_evaluated_colors)


def configure_radius(obj, output):
    group = obj.modifiers['build_geonode'].node_group
    socket = group.nodes['Mesh to Points'].inputs['Radius']
    name = 'bleMD Radius Attribute'
    attribute = group.nodes.get(name)
    linked = output.inputs.get('Radius') and output.inputs['Radius'].is_linked
    if linked:
        if attribute is None:
            attribute = group.nodes.new('GeometryNodeInputNamedAttribute')
            attribute.name = name
            attribute.data_type = 'FLOAT'
            attribute.inputs['Name'].default_value = 'bleMD Radius'
            attribute.location = (-550,-100)
        if not socket.links or socket.links[0].from_node != attribute:
            group.links.new(attribute.outputs['Attribute'], socket)
    else:
        # Remove only our own connection; retain artist-authored geometry fields.
        for link in list(socket.links):
            if link.from_node == attribute:
                group.links.remove(link)
        if socket.default_value != output.radius:
            socket.default_value = output.radius
