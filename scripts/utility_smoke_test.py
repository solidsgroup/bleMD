"""Compare utilities with Blender's evaluator, then exercise particle graphs."""
from pathlib import Path
import os
import bpy
import numpy as np
from bleMD import bleMDUtilities as util, bleMDLive as live
from bleMD.bleMDFields import SCALAR, VECTOR, COLOR
from bleMD.bleMDTree import starter_tree
from bleMD.bleMDPipeline import evaluate_tree

ROOT=Path(__file__).resolve().parents[1]
for tree in bpy.data.node_groups:
    if tree.bl_idname=='BleMDNodeTree': tree.automatic_updates=False
live.invalidate();live.suspended=True
scene=bpy.context.scene;scene.frame_set(0)
# The reference is an actual Geometry Nodes evaluation of Blender's native
# nodes on varying per-vertex attributes, including zeros and negative inputs.
a=np.array([-3.5,-2,-1.5,-1,-.5,0,.1,.5,1,1.5,2,3.5],dtype=np.float32)
b=np.array([2,0,-2,1,-1,0,.5,2,3,1.5,4,-1.5],dtype=np.float32)
c=np.array([.2,0,-1,2,.5,1,.1,.5,2,0,3,.01],dtype=np.float32)
v1=np.column_stack((a,a*.5,np.ones(len(a))));v1[0]=0
v2=np.column_stack((b,np.ones(len(a)),b*.25));v2[1]=0
v3=np.column_stack((c,-c,c*.5))
mesh=bpy.data.meshes.new('Native utility inputs');mesh.vertices.add(len(a))
obj=bpy.data.objects.new('Native utility test',mesh);scene.collection.objects.link(obj)
for name,values in [('A',a),('B',b),('C',c),('V1',v1),('V2',v2),('V3',v3)]:
    attr=mesh.attributes.new(name,'FLOAT' if values.ndim==1 else 'FLOAT_VECTOR','POINT')
    attr.data.foreach_set('value' if values.ndim==1 else 'vector',values.ravel())
group=bpy.data.node_groups.new('Native utility parity','GeometryNodeTree')
group.interface.new_socket('Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
group.interface.new_socket('Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
inp=group.nodes.new('NodeGroupInput');out=group.nodes.new('NodeGroupOutput')
store=group.nodes.new('GeometryNodeStoreNamedAttribute');store.inputs['Name'].default_value='Result'
group.links.new(inp.outputs['Geometry'],store.inputs['Geometry']);group.links.new(store.outputs['Geometry'],out.inputs['Geometry'])
mod=obj.modifiers.new('Reference','NODES');mod.node_group=group
readers={}
for name in ('A','B','C','V1','V2','V3'):
    reader=group.nodes.new('GeometryNodeInputNamedAttribute')
    reader.data_type='FLOAT_VECTOR' if name.startswith('V') else 'FLOAT'
    reader.inputs['Name'].default_value=name;readers[name]=reader
custom_tree=bpy.data.node_groups.new('Utility controls','BleMDNodeTree')
custom_tree.automatic_updates=False

def reference(native,output=0,vector=False):
    store.data_type='FLOAT_VECTOR' if vector else 'FLOAT'
    group.links.new(native.outputs[output],store.inputs['Value'])
    bpy.context.view_layer.update()
    result=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.attributes['Result']
    values=np.empty(len(a)*(3 if vector else 1),dtype=np.float32)
    result.data.foreach_get('vector' if vector else 'value',values)
    return values.reshape(-1,3) if vector else values

native=group.nodes.new('ShaderNodeMath');node=custom_tree.nodes.new('BleMDMath')
for i,name in enumerate(('A','B','C')): group.links.new(readers[name].outputs['Attribute'],native.inputs[i])
for op,_,_ in util.MATH_ITEMS:
    native.operation=op;node.operation=op
    values=[a,b,c][:len(util.input_indices(node))]
    expected=reference(native)
    actual=util.evaluate(node,0,values,len(a))
    np.testing.assert_allclose(actual,expected,rtol=3e-5,atol=2e-6,err_msg=op)
native.operation=node.operation='MULTIPLY';native.use_clamp=node.use_clamp=True
np.testing.assert_allclose(util.evaluate(node,0,[a,b],len(a)),reference(native),atol=1e-6)
node=custom_tree.nodes.new('BleMDVectorMath');native=group.nodes.new('ShaderNodeVectorMath')
for i,name in enumerate(('V1','V2','V3','B')): group.links.new(readers[name].outputs['Attribute'],native.inputs[i])
for op,_,_ in util.VECTOR_ITEMS:
    native.operation=node.operation=op
    vector=op not in util.VECTOR_SCALAR;index=0 if vector else 1
    values=[[v1,v2,v3,b][i] for i in util.input_indices(node)]
    expected=reference(native,index,vector)
    # Blender vector modulo produces NaN for zero divisors. bleMD follows
    # scalar Math's safe-zero behavior so particle attributes stay finite.
    if op=='MODULO': expected=np.nan_to_num(expected,nan=0)
    actual=util.evaluate(node,index,values,len(a))
    np.testing.assert_allclose(actual,expected,rtol=3e-5,atol=2e-6,err_msg=op)
node=custom_tree.nodes.new('BleMDMapRange');native=group.nodes.new('ShaderNodeMapRange')
group.links.new(readers['A'].outputs['Attribute'],native.inputs['Value'])
for mode in ('LINEAR','STEPPED','SMOOTHSTEP','SMOOTHERSTEP'):
    native.interpolation_type=node.interpolation_type=mode
    for clamp in (False,True):
        native.clamp=node.clamp=clamp
        for lo,hi in ((-1.,2.),(2.,-1.),(1.,1.)):
            vals=[a]+[np.full(len(a),v) for v in (lo,hi,4.,-2.,3.)]
            for i,v in enumerate((lo,hi,4.,-2.,3.),1):native.inputs[i].default_value=v
            expected=reference(native)
            actual=util.evaluate(node,0,vals[:len(util.input_indices(node))],len(a))
            np.testing.assert_allclose(actual,expected,rtol=3e-5,atol=2e-6,err_msg=f'{mode} {clamp} {lo} {hi}')
node=custom_tree.nodes.new('BleMDClamp');native=group.nodes.new('ShaderNodeClamp')
for i,name in enumerate(('A','B','C')):group.links.new(readers[name].outputs['Attribute'],native.inputs[i])
for mode in ('MINMAX','RANGE'):
    native.clamp_type=node.clamp_type=mode
    np.testing.assert_allclose(util.evaluate(node,0,[a,b,c],len(a)),reference(native),atol=1e-6)

# The particle graph uses field identity and constant broadcasting, not vertex
# index assumptions. Arithmetic results drive radius, color, and named fields.
tree=starter_tree();tree.scene=scene;tree.automatic_updates=False
source=next(n for n in tree.nodes if n.bl_idname=='BleMDFileSource')
output=next(n for n in tree.nodes if n.bl_idname=='BleMDParticleOutput')
color=next(n for n in tree.nodes if n.bl_idname=='BleMDColorMap')
source.filepath=str(ROOT/'tests/fixtures/tiny.dump')
particles=evaluate_tree(tree,scene)
math=tree.nodes.new('BleMDMath');math.operation='MULTIPLY'
math.inputs[1].default_value=2
tree.links.new(source.outputs['c_energy'],math.inputs[0])
tree.links.new(math.outputs[0],output.inputs['Radius'])
value=tree.nodes.new('BleMDValue');value.value=.1
add=tree.nodes.new('BleMDMath');tree.links.new(math.outputs[0],add.inputs[0]);tree.links.new(value.outputs[0],add.inputs[1])
extra=output.inputs.new(SCALAR,'Shader');extra['bleMD_export_name']='Computed'
tree.links.new(add.outputs[0],extra)
tree.links.new(add.outputs[0],color.inputs['Value'])
evaluate_tree(tree,scene)
np.testing.assert_allclose([v.value for v in particles.data.attributes['bleMD Radius'].data],[.2,.4,.6],atol=1e-6)
np.testing.assert_allclose([v.value for v in particles.data.attributes['Computed'].data],[.3,.5,.7],atol=1e-6)
separate=tree.nodes.new('BleMDSeparateXYZ');combine=tree.nodes.new('BleMDCombineXYZ')
tree.links.new(source.outputs['Position'],separate.inputs[0])
tree.links.new(separate.outputs['Z'],combine.inputs['X']);tree.links.new(separate.outputs['X'],combine.inputs['Z'])
combine.inputs['Y'].default_value=7
tree.links.new(combine.outputs[0],output.inputs['Vector'])
evaluate_tree(tree,scene)
np.testing.assert_allclose([v.vector[:] for v in particles.data.attributes['bleMD Vector'].data],[[1,7,1],[2,7,2],[3,7,3]])
# Native reroutes work on both Data and typed fields; Frame is purely layout.
route=tree.nodes.new('NodeReroute');tree.links.new(source.outputs['Data'],route.inputs[0]);tree.links.new(route.outputs[0],output.inputs['Data'])
field_route=tree.nodes.new('NodeReroute');tree.links.new(add.outputs[0],field_route.inputs[0]);tree.links.new(field_route.outputs[0],extra)
frame=tree.nodes.new('NodeFrame');add.parent=frame
source.timesteps_per_frame=2;scene.frame_set(1);evaluate_tree(tree,scene)
np.testing.assert_allclose([v.value for v in particles.data.attributes['Computed'].data],[.5,.7,.9],atol=1e-6)

# Reorder one input branch, then combine with an unmodified field by ID.
scene.frame_set(0)
script=tree.nodes.new('BleMDOvitoScript');script.script=bpy.data.texts.new('Reverse utility input')
script.script.write('import numpy as np\ndef reverse(frame,data):\n    for name in list(data.particles.keys()):\n        data.particles_.create_property(name,data=np.asarray(data.particles[name]).copy()[::-1])\npipeline.modifiers.append(reverse)\n')
read=tree.nodes.new('BleMDReadProperty');read.property_name='c_energy'
tree.links.new(source.outputs['Data'],script.inputs[0]);tree.links.new(script.outputs[0],read.inputs[0])
tree.links.new(source.outputs['c_energy'],add.inputs[0]);tree.links.new(read.outputs[0],add.inputs[1])
evaluate_tree(tree,scene)
np.testing.assert_allclose([v.value for v in particles.data.attributes['Computed'].data],[.2,.4,.6],atol=1e-6)
# Constant expressions broadcast on either branch, including when the constant
# is the first operand. A constant's default dataset must not dictate identity.
tree.links.new(value.outputs[0],add.inputs[0])
evaluate_tree(tree,scene)
np.testing.assert_allclose([v.value for v in particles.data.attributes['Computed'].data],[.2,.3,.4],atol=1e-6)

# Mix RGB and separate/combine color channels into an actual Color field.
rgb=tree.nodes.new('BleMDRGB');rgb.value=(1,0,0)
mix=tree.nodes.new('BleMDMix');mix.data_type='COLOR';mix.inputs[0].default_value=.25
mix.inputs[6].default_value=(0,0,1);tree.links.new(rgb.outputs[0],mix.inputs[5])
sep=tree.nodes.new('BleMDSeparateColor');comb=tree.nodes.new('BleMDCombineColor')
tree.links.new(mix.outputs['Color'],sep.inputs[0])
for i in range(3):tree.links.new(sep.outputs[i],comb.inputs[i])
tree.links.new(comb.outputs[0],output.inputs['Color']);evaluate_tree(tree,scene)
np.testing.assert_allclose([v.color[:3] for v in particles.data.color_attributes['bleMD Color'].data],[[.75,0,.25]]*3,atol=1e-6)

# Real cycle and cross-source errors preserve geometry. Hidden inputs are not
# evaluated, and switching back to a binary operation exposes the cycle.
def fails(fragment):
    previous=particles.data
    try:evaluate_tree(tree,scene)
    except ValueError as error:assert fragment in str(error),str(error)
    else:raise AssertionError(fragment)
    assert particles.data==previous
other=tree.nodes.new('BleMDFileSource');other.filepath=source.filepath
tree.links.new(other.outputs['Atom ID'],add.inputs[0]);fails('same File Source')
tree.links.new(value.outputs[0],add.inputs[0])
tree.links.new(add.outputs[0],add.inputs[1]);fails('cycle')
add.operation='ABSOLUTE';evaluate_tree(tree,scene)
add.operation='ADD';fails('cycle')
tree.links.new(read.outputs[0],add.inputs[1]);evaluate_tree(tree,scene)

# Live edits reuse OVITO pipelines, while field expressions recompute. Multiple
# consumers share expression results within a frame; caches are released after it.
live.suspended=False;tree.automatic_updates=True;live.invalidate();live.tick()
graph=live._states[tree.as_pointer()]['graph']
value.value=.4;live.tick()
assert not tree.has_error,tree.last_message
assert live._states[tree.as_pointer()]['graph'] is graph
np.testing.assert_allclose([v.value for v in particles.data.attributes['Computed'].data],[.5,.6,.7],atol=1e-6)
assert not graph.samples and not graph.expression_values
name=tree.name
path=str(Path(os.environ['BLENDER_USER_CONFIG'])/'utilities-roundtrip.blend')
bpy.ops.wm.save_as_mainfile(filepath=path);bpy.ops.wm.open_mainfile(filepath=path)
tree=bpy.data.node_groups[name];live.tick();assert not tree.has_error,tree.last_message
assert any(n.bl_idname=='BleMDMath' and n.operation=='MULTIPLY' for n in tree.nodes)
assert any(n.bl_idname=='NodeReroute' for n in tree.nodes)
print(f'PASS: {len(util.MATH_ITEMS)} Math and {len(util.VECTOR_ITEMS)} Vector Math operations against native Blender, Map Range/Clamp parity, constants, expressions, ID joins, reroutes, cycles, live edits and persistence')
