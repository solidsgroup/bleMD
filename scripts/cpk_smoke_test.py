"""CPK colors through actual OVITO import, field joins and Blender attributes."""
import os
from pathlib import Path
import bpy
import numpy as np
from bleMD import bleMDLive as live
from bleMD.bleMDTree import starter_tree
from bleMD.bleMDPipeline import evaluate_tree
from bleMD.bleMDFields import COLOR

ROOT=Path(__file__).resolve().parents[1]
for tree in bpy.data.node_groups:
    if tree.bl_idname=='BleMDNodeTree':tree.automatic_updates=False
live.invalidate();live.suspended=True
scene=bpy.context.scene;scene.frame_set(0)
tree=starter_tree();tree.scene=scene;tree.automatic_updates=False
source=next(n for n in tree.nodes if n.bl_idname=='BleMDFileSource')
output=next(n for n in tree.nodes if n.bl_idname=='BleMDParticleOutput')
source.filepath=str(ROOT/'tests/fixtures/elements.xyz')
obj=evaluate_tree(tree,scene)
cpk=tree.nodes.new('BleMDCPKColor')
tree.links.new(source.outputs['Atom Type'],cpk.inputs[0])
tree.links.new(cpk.outputs[0],output.inputs['Color'])
extra=output.inputs.new(COLOR,'Chemical color');extra['bleMD_export_name']='Chemical color'
tree.links.new(cpk.outputs[0],extra)

def rgb(hex_color):
    srgb=np.array([int(hex_color[i:i+2],16)/255 for i in (0,2,4)])
    return np.where(srgb<=.04045,srgb/12.92,((srgb+.055)/1.055)**2.4)

expected=np.array([rgb(c) for c in ('FFFFFF','909090','3050F8','FF0D0D','FFFF30','1FF01F','E06633','FF00FF')])
def check(wanted):
    evaluate_tree(tree,scene)
    for name in ('bleMD Color','Chemical color'):
        np.testing.assert_allclose([p.color[:3] for p in obj.data.color_attributes[name].data],wanted,atol=1e-6)
    assert obj.data.materials[0].node_tree.nodes.get('Attribute') is not None

# Metadata comes from species names; numeric type IDs are assigned by the reader
# in first-seen order (oxygen is type 1, not hydrogen).
check(expected)
source.timesteps_per_frame=2;scene.frame_set(1);check(expected)
assert abs(obj.data.vertices[0].co.y-.5)<1e-6
scene.frame_set(0)
# Exact override takes precedence over a known element name.
cpk.type_mapping='1=C';changed=expected.copy();changed[3]=rgb('909090');check(changed)
cpk.type_mapping=''
# Color utility consumers can use CPK just like Color Map.
mix=tree.nodes.new('BleMDMix');mix.data_type='COLOR';mix.inputs[0].default_value=.5
mix.inputs[6].default_value=(0,0,0);tree.links.new(cpk.outputs[0],mix.inputs[5]);tree.links.new(mix.outputs['Color'],output.inputs['Color'])
evaluate_tree(tree,scene)
np.testing.assert_allclose([p.color[:3] for p in obj.data.color_attributes['bleMD Color'].data],expected*.5,atol=1e-6)
tree.links.new(cpk.outputs[0],output.inputs['Color'])
# Read a downstream reordered type property, including its type-name metadata.
script=tree.nodes.new('BleMDOvitoScript');script.script=bpy.data.texts.new('CPK reorder')
script.script.write('import numpy as np\ndef reorder(frame,data):\n    for name in list(data.particles.keys()):\n        data.particles_.make_mutable(data.particles[name])[...] = np.asarray(data.particles[name]).copy()[::-1]\npipeline.modifiers.append(reorder)\n')
read=tree.nodes.new('BleMDReadProperty');read.property_name='Particle Type'
tree.links.new(source.outputs['Data'],script.inputs[0]);tree.links.new(script.outputs[0],read.inputs[0]);tree.links.new(read.outputs[0],cpk.inputs[0]);check(expected)
# Explicit atomic numbers are opt-in, and can arrive through arithmetic nodes.
cpk.input_mode='ATOMIC_NUMBER'
math=tree.nodes.new('BleMDMath');math.inputs[1].default_value=0
tree.links.new(source.outputs['Z'],math.inputs[0]);tree.links.new(math.outputs[0],cpk.inputs[0]);check(expected)
cpk.fallback_color=(.2,.4,.6);changed=expected.copy();changed[-1]=(.2,.4,.6);check(changed)
# Numeric LAMMPS types have no implied periodic-table meaning.
source.filepath=str(ROOT/'tests/fixtures/tiny.dump');cpk.input_mode='TYPES';cpk.type_mapping=''
tree.links.new(source.outputs['Atom Type'],cpk.inputs[0]);check(np.tile((.2,.4,.6),(3,1)))
cpk.type_mapping='1=C, 2=O';mapped=np.array([rgb('909090'),rgb('FF0D0D'),rgb('909090')]);check(mapped)

def fails(fragment):
    previous=obj.data
    try:evaluate_tree(tree,scene)
    except ValueError as error:assert fragment in str(error),str(error)
    else:raise AssertionError(fragment)
    assert obj.data==previous
for text,fragment in [('1=Carbon','element mappings'),('1=C, 1=O','duplicate'),('1=ZZ','element mappings')]:
    cpk.type_mapping=text;fails(fragment)
cpk.type_mapping='1=C, 2=O'
tree.links.new(source.outputs['c_energy'],cpk.inputs[0]);fails('finite integer')
tree.links.new(source.outputs['Atom Type'],cpk.inputs[0])
cpk.mute=True;fails('Unmute');cpk.mute=False
route=tree.nodes.new('NodeReroute');tree.links.new(source.outputs['Atom Type'],route.inputs[0]);tree.links.new(route.outputs[0],cpk.inputs[0]);check(mapped)
# Live edits are appearance-only and reuse native pipelines.
live.suspended=False;tree.automatic_updates=True;live.invalidate();live.tick()
graph=live._states[tree.as_pointer()]['graph'];cpk.type_mapping='1=H, 2=O';live.tick()
assert not tree.has_error,tree.last_message
assert live._states[tree.as_pointer()]['graph'] is graph
np.testing.assert_allclose(obj.data.color_attributes['bleMD Color'].data[0].color[:3],(1,1,1))
assert not graph.samples and not graph.expression_values
name=tree.name
path=str(Path(os.environ['BLENDER_USER_CONFIG'])/'cpk-roundtrip.blend')
bpy.ops.wm.save_as_mainfile(filepath=path);bpy.ops.wm.open_mainfile(filepath=path)
tree=bpy.data.node_groups[name];live.tick();assert not tree.has_error,tree.last_message
cpk=next(n for n in tree.nodes if n.bl_idname=='BleMDCPKColor');assert cpk.type_mapping=='1=H, 2=O'
assert cpk.inputs[0].is_linked and cpk.outputs[0].is_linked
print('PASS: CPK element names, numeric type mappings, atomic numbers, linear RGB, unknown fallback, ID joins, interpolation, color utilities, attributes, validation, live caching and persistence')
