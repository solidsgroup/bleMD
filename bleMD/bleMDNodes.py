import bpy

def create_geonodes():
    obj = bpy.data.objects["MD_Object"]
        
    geo_nodes = obj.modifiers.get("build_geonode")
    if geo_nodes:
        return
        
    geo_nodes = obj.modifiers.new("build_geonode", "NODES")

    node_group = create_group()
    geo_nodes.node_group = node_group


def create_group(name="geonode_object"):
    group = bpy.data.node_groups.get(name)
    # check if a group already exists
    if group:
        return

    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    #group.inputs.new('NodeSocketGeometry', "Geometry")
    #group.outputs.new('NodeSocketGeometry', "Geometry")
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

    bpy.data.node_groups[name].nodes["Mesh to Points"].inputs[3].default_value = 1
    bpy.data.node_groups["geonode_object"].nodes["Set Material"].inputs[2].default_value = bpy.data.materials["my_mat"]

    group.links.new(input_node.outputs[0], mesh_to_points.inputs[0])
    group.links.new(mesh_to_points.outputs[0], set_material.inputs[0])
    group.links.new(set_material.outputs[0], output_node.inputs[0])

    return group


def create_material():
    mat = bpy.data.materials.get("my_mat")
    if mat:
        return
        
    mat = bpy.data.materials.new("my_mat")
    obj = bpy.data.objects["MD_Object"]
    obj.data.materials.append(mat)

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
    Math1.location = (-700, 250)
    bpy.data.materials["my_mat"].node_tree.nodes["Math"].operation = 'SUBTRACT'
    Math2 = mat_nodes.new('ShaderNodeMath',)    
    Math2.location = (-550, 250)
    bpy.data.materials["my_mat"].node_tree.nodes["Math.001"].operation = 'DIVIDE'
        
    color_ramp = mat_nodes.new('ShaderNodeValToRGB')
    color_ramp.location = (-350, 250)

    mat.node_tree.links.new(attribute.outputs[2], Math1.inputs[0])
    mat.node_tree.links.new(Math1.outputs[0], Math2.inputs[0])
    mat.node_tree.links.new(Math2.outputs[0], color_ramp.inputs[0])
    mat.node_tree.links.new(color_ramp.outputs[0], principled.inputs[0])
    mat.node_tree.links.new(principled.outputs[0], material_output.inputs[0])
    
    
def updateDefaultShader():
    my_shader = bpy.context.scene.bleMD_props.my_shader
    my_normalhigh = bpy.context.scene.bleMD_props.my_normalhigh
    my_normallow = bpy.context.scene.bleMD_props.my_normallow
    my_range = my_normalhigh - my_normallow
    
    bpy.data.materials["my_mat"].node_tree.nodes["Attribute"].attribute_name = my_shader
    
    bpy.data.materials["my_mat"].node_tree.nodes["Math"].inputs[1].default_value = my_normallow
    bpy.data.materials["my_mat"].node_tree.nodes["Math.001"].inputs[1].default_value = my_range
    
    return my_shader


def setup():
    create_material()
    create_geonodes()
    for scene in bpy.data.scenes:
        scene.render.engine = 'CYCLES'   

    print("Hello")
