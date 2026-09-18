"""Palette parity, radii, named shader fields, and bounded live resources."""
from pathlib import Path
import os
import bpy
import numpy as np
from bleMD import bleMDLive as live
from bleMD.bleMDTree import starter_tree
from bleMD.bleMDFields import SCALAR, VECTOR, COLOR
from bleMD.bleMDPalette import ITEMS, stops, sample, apply_ramp
from bleMD.bleMDShader import create_group
from bleMD.bleMDPipeline import evaluate_tree

ROOT = Path(__file__).resolve().parents[1]
scene = bpy.context.scene
live.suspended = True
scene.frame_set(0)
tree = starter_tree(); tree.scene = scene
tree.automatic_updates = False
source = next(n for n in tree.nodes if n.bl_idname == 'BleMDFileSource')
output = next(n for n in tree.nodes if n.bl_idname == 'BleMDParticleOutput')
color = next(n for n in tree.nodes if n.bl_idname == 'BleMDColorMap')
source.filepath = str(ROOT / 'tests/fixtures/tiny.dump')
obj = evaluate_tree(tree, scene)

# Every legacy palette fits in Blender's native ramp and agrees with particle
# mapping at both endpoints and interior samples; shader changes need no OVITO.
group = create_group()
x = np.array([0., .125, .5, .875, 1.])
for name, _, _ in ITEMS:
    color.palette = name
    group.bleMD_palette = name
    ramp = group.nodes['bleMD Palette'].color_ramp
    assert len(ramp.elements) <= 32
    expected = sample(name, x)
    actual = np.array([ramp.evaluate(float(t))[:3] for t in x])
    np.testing.assert_allclose(actual, expected, atol=2e-6, err_msg=name)
    positions, colors = stops(name)
    assert positions[0] == 0 and positions[-1] == 1, name
color.palette = 'viridis'
evaluate_tree(tree, scene)
expected = sample('viridis', np.array([0,.5,1]))
np.testing.assert_allclose([v.color[:3] for v in obj.data.color_attributes['bleMD Color'].data], expected, atol=1e-6)

# Absolute per-particle radii with a scale, used by the same Mesh-to-Points
# node for both viewport spheres and rendered particles.
tree.links.new(source.outputs['c_energy'], output.inputs['Radius'])
output.radius_scale = 2
evaluate_tree(tree, scene)
np.testing.assert_allclose([v.value for v in obj.data.attributes['bleMD Radius'].data], [.2,.4,.6], atol=1e-6)
bpy.context.view_layer.update()
mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
ids = np.empty(len(mesh.vertices), dtype=np.int32); mesh.attributes['Particle Identifier'].data.foreach_get('value',ids)
positions = np.empty(len(mesh.vertices)*3); mesh.vertices.foreach_get('co',positions)
centers = np.array([v.co[:] for v in obj.data.vertices])[ids-1]
np.testing.assert_allclose(np.linalg.norm(positions.reshape(-1,3)-centers, axis=1), np.array([.2,.4,.6])[ids-1], atol=1e-6)

# Export multiple independently named fields even with a restrictive data filter.
for kind, name, field in ((SCALAR,'Energy','c_energy'), (SCALAR,'Atom','Atom ID'),
                          (VECTOR,'Coordinates','Position'), (COLOR,'Tint',None)):
    socket = output.inputs.new(kind, 'Shader field')
    socket['bleMD_export_name'] = name
    tree.links.new(source.outputs[field] if field else color.outputs['Color'], socket)
output.attributes = 'Particle Identifier'
evaluate_tree(tree, scene)
assert set(['Energy','Atom','Coordinates','Tint','bleMD Color Value','bleMD Radius']) <= set(obj.data.attributes.keys())
assert 'c_energy' not in obj.data.attributes
assert obj.data.attributes['Tint'].data_type == 'FLOAT_COLOR'
np.testing.assert_allclose([v.value for v in obj.data.attributes['Energy'].data],[.1,.2,.3], atol=1e-6)
np.testing.assert_allclose([v.vector[:] for v in obj.data.attributes['Coordinates'].data],[v.co[:] for v in obj.data.vertices])
# These fields survive realization, where the material actually reads them.
bpy.context.view_layer.update()
mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
assert set(['Energy','Atom','Coordinates','Tint']) <= set(mesh.attributes.keys())
mat = output.material
attribute = mat.node_tree.nodes.new('ShaderNodeAttribute'); attribute.attribute_name = 'Energy'
shader = mat.node_tree.nodes.new('ShaderNodeGroup'); shader.node_tree = group
mat.node_tree.links.new(attribute.outputs['Fac'],shader.inputs['Value'])
mat.node_tree.links.new(shader.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
evaluate_tree(tree,scene)
assert output.material == mat and shader.inputs['Value'].is_linked

# Unconnected Color has a specified fallback, while a field takes precedence.
output.color_mode = 'UNIFORM'; output.color = (.1,.3,.8)
tree.links.remove(output.inputs['Color'].links[0])
evaluate_tree(tree, scene)
np.testing.assert_allclose([v.color[:3] for v in obj.data.color_attributes['bleMD Color'].data], [[.1,.3,.8]]*3, atol=1e-6)
tree.links.new(color.outputs['Color'],output.inputs['Color'])
evaluate_tree(tree,scene)
np.testing.assert_allclose(obj.data.color_attributes['bleMD Color'].data[0].color[:3], expected[0], atol=1e-6)
tree.links.remove(output.inputs['Radius'].links[0]); output.radius = .25
evaluate_tree(tree,scene)
assert 'bleMD Radius' not in obj.data.attributes
assert not obj.modifiers['build_geonode'].node_group.nodes['Mesh to Points'].inputs['Radius'].is_linked

# Invalid exports and negative radii fail before replacing the last valid mesh.
socket = next(s for s in output.inputs if s.get('bleMD_export_name') == 'Atom')
socket['bleMD_export_name'] = 'Energy'
previous = obj.data
try:
    evaluate_tree(tree, scene)
except ValueError as e:
    assert 'unique' in str(e)
else:
    raise AssertionError('Duplicate export accepted')
assert obj.data == previous
socket['bleMD_export_name'] = 'Atom'
script = tree.nodes.new('BleMDOvitoScript')
script.script = bpy.data.texts.new('Invalid radius')
script.script.write("from ovito.modifiers import ComputePropertyModifier\npipeline.modifiers.append(ComputePropertyModifier(output_property='bad_radius',expressions=['-1']))")
tree.links.new(source.outputs['Data'],script.inputs['Data'])
read = tree.nodes.new('BleMDReadProperty'); read.property_name = 'bad_radius'
tree.links.new(script.outputs['Data'],read.inputs['Data'])
tree.links.new(read.outputs['Field'],output.inputs['Radius'])
try:
    evaluate_tree(tree,scene)
except ValueError as e:
    assert 'nonnegative' in str(e), str(e)
else:
    raise AssertionError('Negative radius accepted')
assert obj.data == previous
tree.links.remove(output.inputs['Radius'].links[0]); tree.nodes.remove(read); tree.nodes.remove(script)

# Resource counts stay bounded, and palette/export edits reuse native pipelines.
for old in bpy.data.node_groups:
    if old.bl_idname == 'BleMDNodeTree': old.automatic_updates = False
live.suspended = False; tree.automatic_updates = True
live.invalidate(); live.tick()
graph = live._states[tree.as_pointer()]['graph']
pipelines = tuple(graph.pipelines.values())
counts = len(bpy.data.meshes),len(bpy.data.materials),len(bpy.data.node_groups)
for frame in range(30):
    scene.frame_set(frame % 2)
    color.palette = 'plasma' if frame % 2 else 'viridis'
    live.tick()
    assert not tree.has_error,tree.last_message
    assert live._states[tree.as_pointer()]['graph'] is graph
    assert tuple(graph.pipelines.values()) == pipelines
    assert not graph.samples
assert counts == (len(bpy.data.meshes),len(bpy.data.materials),len(bpy.data.node_groups))
socket['bleMD_export_name'] = 'Renamed Atom'
live.tick()
assert 'Renamed Atom' in obj.data.attributes and 'Atom' not in obj.data.attributes

# Dynamic socket names, palette choices, shaders and radius settings persist.
name=tree.name
path=str(Path(os.environ['BLENDER_USER_CONFIG'])/'appearance-roundtrip.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
tree=bpy.data.node_groups[name]
output=next(n for n in tree.nodes if n.bl_idname=='BleMDParticleOutput')
live.tick()
assert any(s.get('bleMD_export_name')=='Renamed Atom' for s in output.inputs)
assert 'Renamed Atom' in output.target.data.attributes
assert any(n.bl_idname=='ShaderNodeGroup' and n.node_tree.get('bleMD_palette_group') for n in output.material.node_tree.nodes)
print(f'PASS: {len(ITEMS)} palette presets and shader parity, per-particle radii, fallback color, named shader fields, validation, bounded caches/resources and persistence')
