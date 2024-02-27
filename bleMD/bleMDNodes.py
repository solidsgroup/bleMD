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

    geonode_object = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = name)
    
    #initialize geonode_object nodes
    #geonode_object interface
    #Socket My Input
    my_input_socket = geonode_object.interface.new_socket(name = "My Input", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    my_input_socket.attribute_domain = 'POINT'
    
    #Socket My Output
    my_output_socket = geonode_object.interface.new_socket(name = "My Output", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    my_output_socket.attribute_domain = 'POINT'
    
    
    #node Mesh to Points
    mesh_to_points = geonode_object.nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.name = "Mesh to Points"
    mesh_to_points.mode = 'VERTICES'
    #Selection
    mesh_to_points.inputs[1].default_value = True
    #Position
    mesh_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
    #Radius
    bpy.data.node_groups[name].nodes["Mesh to Points"].inputs["Radius"].default_value = mytool.my_radius
    
    #node Group Input
    group_input = geonode_object.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    
    #node Set Material
    set_material = geonode_object.nodes.new("GeometryNodeSetMaterial")
    set_material.name = "Set Material"
    #Selection
    set_material.inputs[1].default_value = True
    if mytool.mat_selection in bpy.data.materials.keys():
        bpy.data.node_groups[name].nodes["Set Material"].inputs[2].default_value = bpy.data.materials[mytool.mat_selection]
    
    #node Delete Geometry
    delete_geometry = geonode_object.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry.name = "Delete Geometry"
    delete_geometry.domain = 'POINT'
    delete_geometry.mode = 'ALL'
    
    #node Math.011
    math_011 = geonode_object.nodes.new("ShaderNodeMath")
    math_011.name = "Plane Thickness"
    math_011.operation = 'GREATER_THAN'
    math_011.use_clamp = False
    #Value_001
    math_011.inputs[1].default_value = 0
    #Value_002
    math_011.inputs[2].default_value = 0.5
    
    #node Position
    position = geonode_object.nodes.new("GeometryNodeInputPosition")
    position.name = "Position"
    
    #node Vector
    vector = geonode_object.nodes.new("FunctionNodeInputVector")
    vector.name = "Plane Vector"
    vector.vector = (0.0, 0.0, 0.0)
    
    #node Vector Math.002
    vector_math_002 = geonode_object.nodes.new("ShaderNodeVectorMath")
    vector_math_002.name = "Vector Math.002"
    vector_math_002.operation = 'DOT_PRODUCT'
    #Vector_002
    vector_math_002.inputs[2].default_value = (0.0, 0.0, 0.0)
    #Scale
    vector_math_002.inputs[3].default_value = 1.0
    
    #node Value.003
    value_003 = geonode_object.nodes.new("ShaderNodeValue")
    value_003.name = "Plane Distance"
    
    value_003.outputs[0].default_value = 0.0
    #node Math.001
    math_001 = geonode_object.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'ADD'
    math_001.use_clamp = False
    #Value_002
    math_001.inputs[2].default_value = 0.5
    
    #node Math.002
    math_002 = geonode_object.nodes.new("ShaderNodeMath")
    math_002.name = "Math.002"
    math_002.operation = 'DIVIDE'
    math_002.use_clamp = False
    #Value_002
    math_002.inputs[2].default_value = 0.5
    
    #node Math
    math = geonode_object.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'ABSOLUTE'
    math.use_clamp = False
    #Value_001
    math.inputs[1].default_value = 0.5
    #Value_002
    math.inputs[2].default_value = 0.5
    
    #node Vector Math.003
    vector_math_003 = geonode_object.nodes.new("ShaderNodeVectorMath")
    vector_math_003.name = "Vector Math.003"
    vector_math_003.operation = 'LENGTH'
    #Vector_001
    vector_math_003.inputs[1].default_value = (0.0, 0.0, 0.0)
    #Vector_002
    vector_math_003.inputs[2].default_value = (0.0, 0.0, 0.0)
    #Scale
    vector_math_003.inputs[3].default_value = 1.0
    
    #node Group Output
    group_output = geonode_object.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    
    
    
    
    #Set locations
    mesh_to_points.location = (-280.04180908203125, 655.4263305664062)
    group_input.location = (-494.1868591308594, 605.1441040039062)
    set_material.location = (747.50146484375, 696.5126342773438)
    delete_geometry.location = (527.167236328125, 682.7308959960938)
    math_011.location = (324.61688232421875, 522.8726196289062)
    position.location = (-614.8848266601562, 385.8265380859375)
    vector.location = (-614.8453369140625, 306.63885498046875)
    vector_math_002.location = (-422.0212097167969, 415.8225402832031)
    value_003.location = (-420.03375244140625, 274.6254577636719)
    math_001.location = (-250.7779998779297, 414.654541015625)
    math_002.location = (115.44991302490234, 449.82379150390625)
    math.location = (-87.7671890258789, 410.32568359375)
    vector_math_003.location = (-419.2497253417969, 155.30636596679688)
    group_output.location = (967.5928955078125, 676.5765991210938)
    
    #Set dimensions
    mesh_to_points.width, mesh_to_points.height = 140.0, 100.0
    group_input.width, group_input.height = 140.0, 100.0
    set_material.width, set_material.height = 140.0, 100.0
    delete_geometry.width, delete_geometry.height = 140.0, 100.0
    math_011.width, math_011.height = 140.0, 100.0
    position.width, position.height = 140.0, 100.0
    vector.width, vector.height = 140.0, 100.0
    vector_math_002.width, vector_math_002.height = 140.0, 100.0
    value_003.width, value_003.height = 140.0, 100.0
    math_001.width, math_001.height = 140.0, 100.0
    math_002.width, math_002.height = 140.0, 100.0
    math.width, math.height = 140.0, 100.0
    vector_math_003.width, vector_math_003.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    
    #Set geonode_object links
    geonode_object.links.new(group_input.outputs[0], mesh_to_points.inputs[0])
    geonode_object.links.new(set_material.outputs[0], group_output.inputs[0])
    geonode_object.links.new(delete_geometry.outputs[0], set_material.inputs[0])
    geonode_object.links.new(mesh_to_points.outputs[0], delete_geometry.inputs[0])
    geonode_object.links.new(math_011.outputs[0], delete_geometry.inputs[1])
    geonode_object.links.new(position.outputs[0], vector_math_002.inputs[0])
    geonode_object.links.new(vector.outputs[0], vector_math_002.inputs[1])
    geonode_object.links.new(vector_math_002.outputs[1], math_001.inputs[0])
    geonode_object.links.new(value_003.outputs[0], math_001.inputs[1])
    geonode_object.links.new(math_001.outputs[0], math.inputs[0])
    geonode_object.links.new(vector.outputs[0], vector_math_003.inputs[0])
    geonode_object.links.new(math.outputs[0], math_002.inputs[0])
    geonode_object.links.new(vector_math_003.outputs[1], math_002.inputs[1])
    geonode_object.links.new(math_002.outputs[0], math_011.inputs[0])

    return geonode_object


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
