"""Source discovery, stable socket identities, and the default colored graph."""
from pathlib import Path
import os
import bpy
import numpy as np

from bleMD.bleMDTree import starter_tree
from bleMD.bleMDPipeline import evaluate_tree, SOURCE_TYPE, OUTPUT_TYPE, SCRIPT_TYPE
from bleMD.bleMDFields import SCALAR, VECTOR, TENSOR, COLOR
from bleMD.bleMDSource import channel, AVAILABLE, inspect_source, sync_channels
from ovito.data import DataCollection

ROOT = Path(__file__).resolve().parents[1]
TINY = str(ROOT / 'tests/fixtures/tiny.dump')
FIELDS = str(ROOT / 'tests/fixtures/fields.xyz')
scene = bpy.context.scene
scene.frame_set(0)
tree = starter_tree()
source = next(n for n in tree.nodes if n.bl_idname == SOURCE_TYPE)
color = next(n for n in tree.nodes if n.bl_idname == 'BleMDColorMap')
output = next(n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE)
assert len(tree.nodes) == 3 and not any(n.bl_idname == SCRIPT_TYPE for n in tree.nodes)
assert output.inputs['Data'].links[0].from_node == source
assert color.inputs['Value'].links[0].from_socket == source.outputs['Atom ID']
assert output.inputs['Color'].links[0].from_node == color
identifier = source.outputs['Atom ID'].identifier
source.filepath = TINY
inspect_source(source)
assert source.channels_loaded and not source.channels_error
assert source.outputs['Atom ID'].identifier == identifier
assert source.outputs['Atom Type'].bl_idname == SCALAR
assert source.outputs['Position'].bl_idname == VECTOR
assert source.outputs['c_energy'].bl_idname == SCALAR
assert len(tree.links) == 3
obj = evaluate_tree(tree, scene)
assert color.minimum == 1 and color.maximum == 3


def colors():
    return np.array([c.color[:3] for c in obj.data.color_attributes['bleMD Color'].data])


def values(name):
    return np.array([p.value for p in obj.data.attributes[name].data])


np.testing.assert_allclose(colors()[0], color.low_color, atol=1e-6)
np.testing.assert_allclose(colors()[-1], color.high_color, atol=1e-6)
assert not np.allclose(colors()[0], colors()[-1])
initial = colors().copy()
scene.frame_set(1); evaluate_tree(tree, scene)
np.testing.assert_allclose(colors(), initial, atol=1e-6)

# A source channel drives coloring directly. Automatic range is derived from
# frame 0, rather than changing as c_energy increases at frame 1.
tree.links.new(source.outputs['c_energy'], color.inputs['Value'])
evaluate_tree(tree, scene)
assert np.isclose(color.minimum, .1) and np.isclose(color.maximum, .3)
np.testing.assert_allclose(colors(), np.tile(color.high_color,(3,1)), atol=1e-6)
color.range_mode = 'FIXED'; color.minimum = 0; color.maximum = 1
evaluate_tree(tree, scene)
assert not np.allclose(colors()[0], colors()[-1])

# Repeat discovery without losing a linked field's socket or consumers.
energy = source.outputs['c_energy']
ptr = energy.as_pointer()
for _ in range(2):
    assert inspect_source(source)
    assert source.outputs['c_energy'].as_pointer() == ptr
    assert color.inputs['Value'].links[0].from_socket == energy

# Missing fields keep their existing links and fail before replacing the mesh.
source.filepath = FIELDS
inspect_source(source)
assert energy.is_linked and not energy.get(AVAILABLE)
previous_mesh = obj.data
try:
    evaluate_tree(tree, scene)
except ValueError as error:
    assert 'c_energy' in str(error) and 'missing' in str(error)
else:
    raise AssertionError('Missing field should fail')
assert obj.data == previous_mesh
source.filepath = TINY
inspect_source(source)
assert energy.as_pointer() == ptr and energy.get(AVAILABLE)
evaluate_tree(tree, scene)

# Invalid paths preserve wiring and show a discovery error on the source.
source.filepath = str(ROOT / 'tests/fixtures/does-not-exist.dump')
inspect_source(source)
assert source.channels_error and energy.is_linked
source.filepath = FIELDS
inspect_source(source)
assert not source.channels_error
assert source.outputs['vel'].bl_idname == VECTOR
assert source.outputs['Stress Tensor'].bl_idname == TENSOR
assert source.outputs['Color'].bl_idname == COLOR
pair = next(s for s in source.outputs if channel(s) == ('pair', SCALAR, 0))
assert pair.name == 'pair.1'
# Original imported fields may be tensors; explicit Value/Vector/Color channels
# are transferred independently of the supported-property dataset filter.
tree.links.new(pair, output.inputs['Value'])
tree.links.new(source.outputs['vel'], output.inputs['Vector'])
tree.links.new(source.outputs['Color'], output.inputs['Color'])
evaluate_tree(tree, scene)
np.testing.assert_array_equal(values('bleMD Value'), [4,5])
np.testing.assert_allclose(colors(), [[1,0,0],[0,1,0]], atol=1e-6)
np.testing.assert_allclose([p.vector[:] for p in obj.data.attributes['bleMD Vector'].data], [[1,2,3],[2,3,4]], atol=1e-6)

# Constant scalar fields produce the midpoint, avoiding a divide-by-zero.
tree.links.new(source.outputs['Charge'], color.inputs['Value'])
tree.links.new(color.outputs[0], output.inputs['Color'])
color.range_mode = 'FIRST_FRAME'
evaluate_tree(tree, scene)
np.testing.assert_allclose(colors(), np.tile((np.array(color.low_color)+np.array(color.high_color))*.5,(2,1)), atol=1e-6)

# A scalar property changing to a vector gets a new socket; the connected old
# socket is retained as unavailable and is never silently retyped.
changing = Path(os.environ['BLENDER_USER_CONFIG']) / 'changing.xyz'
changing.write_text('2\nProperties=id:I:1:pos:R:3:custom:R:1\n1 0 0 0 2\n2 1 1 1 3\n')
source.filepath = str(changing)
inspect_source(source)
custom = source.outputs['custom']
tree.links.new(custom, color.inputs['Value'])
changing.write_text('2\nProperties=id:I:1:pos:R:3:custom:R:3\n1 0 0 0 2 3 4\n2 1 1 1 3 4 5\n')
assert inspect_source(source)
assert custom.is_linked and not custom.get(AVAILABLE)
assert any(channel(s) == ('custom',VECTOR,-1) for s in source.outputs)
previous_mesh = obj.data
try:
    evaluate_tree(tree, scene)
except ValueError as error:
    assert 'does not match' in str(error), str(error)
else:
    raise AssertionError('Changed field type should fail')
assert obj.data == previous_mesh
# Restore a working graph for save/reopen, including compound component fields.
source.filepath = FIELDS
inspect_source(source)
tree.links.new(source.outputs['Atom ID'], color.inputs['Value'])
evaluate_tree(tree, scene)
# Non-particle datasets retain their Data output for downstream scripts.
nonparticle = tree.nodes.new(SOURCE_TYPE)
sync_channels(nonparticle, DataCollection())
assert len(nonparticle.outputs) == 1 and nonparticle.outputs[0].name == 'Data'
source_name, tree_name = source.name, tree.name
path = Path(os.environ['BLENDER_USER_CONFIG']) / 'source-roundtrip.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
tree = bpy.data.node_groups[tree_name]
source = tree.nodes[source_name]
assert source.outputs['Atom ID'].identifier == identifier
obj = evaluate_tree(tree, bpy.context.scene)
np.testing.assert_array_equal(values('bleMD Value'), [4,5])
assert len([n for n in tree.nodes if n.bl_idname == SCRIPT_TYPE]) == 0
print('PASS: source channels, default ID colors, first-frame range, scalar/vector/tensor/RGB/component fields, stable links, missing/changed fields, constant values, persistence')
