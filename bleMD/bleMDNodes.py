import bpy

def create_geonodes():
    obj = bpy.context.object

    if not "bleMD_object" in obj.data.keys():
        return

    #geo_nodes = obj.modifiers["build_geonode"]
    if not "build_geonode" in obj.modifiers.keys():
        geo_nodes = obj.modifiers.new("build_geonode", "NODES")
        node_group = create_group("meshtopoints")
        geo_nodes.node_group = node_group

def create_group(name="geonode_object"):
    obj = bpy.context.object
    mytool = bpy.context.object.bleMD_props
    
    group = bpy.data.node_groups.get(name)

    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    name = group.name
    group.interface.new_socket('My Output',in_out='INPUT',socket_type='NodeSocketGeometry')
    group.interface.new_socket('My Input',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    
    input_node = group.nodes.new('NodeGroupInput')
    output_node = group.nodes.new('NodeGroupOutput')
    output_node.is_active_output = True
    input_node.location.x = -300
    output_node.location.x = 350

    mesh_to_points = group.nodes.new('GeometryNodeMeshToPoints')
    set_material = group.nodes.new('GeometryNodeSetMaterial')
    mesh_to_points.location.x = -75
    set_material.location.x = 125

    bpy.data.node_groups[name].nodes["Mesh to Points"].inputs["Radius"].default_value = mytool.my_radius

    if mytool.mat_selection in bpy.data.materials.keys():
        bpy.data.node_groups[name].nodes["Set Material"].inputs[2].default_value = bpy.data.materials[mytool.mat_selection]

    group.links.new(input_node.outputs[0], mesh_to_points.inputs[0])
    group.links.new(mesh_to_points.outputs[0], set_material.inputs[0])
    group.links.new(set_material.outputs[0], output_node.inputs[0])

    return group


def create_material():
    mat = bpy.data.materials.new("bleMD_default")
    mat.use_nodes = True
    mat_nodes = mat.node_tree.nodes
    material_output = mat.node_tree.nodes.get('Material Output')
    default_BSDF = mat.node_tree.nodes.get('Principled BSDF')
    mat.node_tree.nodes.remove(default_BSDF)
    principled = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled.location.y = 350

    attribute = mat_nodes.new('ShaderNodeAttribute')
    attribute.location = (-900, 250)
        
    Math1 = mat_nodes.new('ShaderNodeMath',)
    Math1.name="bleMD_MathNode1"
    Math1.location = (-700, 250)
    Math1.operation = 'SUBTRACT'
    Math2 = mat_nodes.new('ShaderNodeMath',)    
    Math2.name="bleMD_MathNode2"
    Math2.location = (-550, 250)
    Math2.operation = 'DIVIDE'
        
    color_ramp = mat_nodes.new('ShaderNodeValToRGB')
    color_ramp.location = (-350, 250)

    mat.node_tree.links.new(attribute.outputs[2], Math1.inputs[0])
    mat.node_tree.links.new(Math1.outputs[0], Math2.inputs[0])
    mat.node_tree.links.new(Math2.outputs[0], color_ramp.inputs[0])
    mat.node_tree.links.new(color_ramp.outputs[0], principled.inputs[0])
    mat.node_tree.links.new(principled.outputs[0], material_output.inputs[0])

    mat.bleMD = True

    return mat

    #obj = bpy.context.object
    #if "bleMD_object" in obj.data.keys():
    #    obj.data.materials.append(mat)
    
def updateDefaultShader():
    my_normalhigh = bpy.context.object.bleMD_props.my_normalhigh
    my_normallow = bpy.context.object.bleMD_props.my_normallow
    my_range = my_normalhigh - my_normallow
    
    bpy.data.materials["my_mat"].node_tree.nodes["bleMD_MathNode1"].inputs[1].default_value = my_normallow
    bpy.data.materials["my_mat"].node_tree.nodes["bleMD_MathNode2"].inputs[1].default_value = my_range
    
def defaultSettings():

    for scene in bpy.data.scenes:
        scene.render.engine = 'CYCLES'
        
    #bpy.context.window.workspace = bpy.data.workspaces['Shading']
    for n in range(3,11): # This whole bit of code is hacky
        for area in bpy.data.screens[n].areas: 
           if area.type == 'VIEW_3D':
               for space in area.spaces: 
                   if space.type == 'VIEW_3D':
                      space.shading.type = 'RENDERED'
                      
    #bpy.context.space_data.context = 'OBJECT'


def makeSun():
    lamp = bpy.data.objects.get('Sun')
    if lamp:
        return
    lamp = bpy.ops.object.light_add(type='SUN', radius=1, align='WORLD', location=(0, 0, 1000), scale=(1, 1, 1))


def setup():
    create_geonodes()
    defaultSettings()
    #makeSun()
