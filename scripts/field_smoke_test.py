"""Typed DAG parity, identity joins, visualization, persistence, and failures."""
from pathlib import Path
import os
import bpy
import numpy as np
from ovito.io import import_file
from ovito.modifiers import AtomicStrainModifier

from bleMD.bleMDFields import SCALAR, VECTOR, TENSOR, COLOR, ANALYSIS_OUTPUTS, migrate_tree
from bleMD.bleMDModifiers import CATALOG
from bleMD.bleMDPipeline import TREE_TYPE, SOCKET_TYPE, evaluate_tree
from bleMD.bleMDGraph import Graph

ROOT = Path(__file__).resolve().parents[1]
FILE = str(ROOT / 'tests/fixtures/strain.dump')
scene = bpy.context.scene
scene.frame_set(1)
tree = bpy.data.node_groups.new('Typed strain graph', TREE_TYPE)
tree.use_fake_user = True
source = tree.nodes.new('BleMDFileSource'); source.filepath = FILE
analysis = tree.nodes.new('BleMD_AtomicStrainModifier')
color = tree.nodes.new('BleMDColorMap'); color.maximum = .2
output = tree.nodes.new('BleMDParticleOutput')
component = tree.nodes.new('BleMDFieldComponent')
link = tree.links.new
link(source.outputs[0], analysis.inputs[0])
link(source.outputs[0], output.inputs[0])
link(analysis.outputs['Shear Strain'], color.inputs['Value'])
link(color.outputs[0], output.inputs['Color'])
link(analysis.outputs['Strain Tensor'], component.inputs['Tensor / Quaternion'])
link(component.outputs[0], output.inputs['Value'])
assert not any(s.bl_idname == SOCKET_TYPE for s in analysis.outputs)
assert analysis.outputs['Strain Tensor'].bl_idname == TENSOR


def attr(obj, name):
    attribute = obj.data.attributes[name]
    field, width = {'FLOAT': ('value', 1), 'INT': ('value', 1),
                    'FLOAT_VECTOR': ('vector', 3), 'FLOAT_COLOR': ('color', 4)}[attribute.data_type]
    values = np.empty(len(attribute.data) * width)
    attribute.data.foreach_get(field, values)
    return values if width == 1 else values.reshape(-1, width)


def parameter(node, key, value):
    spec = next(p for p in CATALOG[node.modifier_name]['parameters'] if p.key == key)
    setattr(node, 'value_' + spec.storage_key, value)


native = import_file(FILE, sort_particles=True)
native.modifiers.append(AtomicStrainModifier(output_strain_tensors=True))
data = native.compute(1)
strain = np.asarray(data.particles['Shear Strain'])
assert np.all(strain > 0)
obj = evaluate_tree(tree, scene)
np.testing.assert_allclose(attr(obj, 'bleMD Value'), np.asarray(data.particles['Strain Tensor'])[:,0], atol=1e-6)
np.testing.assert_allclose(attr(obj, 'bleMD Color Value'), strain, atol=1e-6)
expected = ((1-strain[:,None]/color.maximum)*np.asarray(color.low_color)
            + strain[:,None]/color.maximum*np.asarray(color.high_color))
np.testing.assert_allclose(attr(obj, 'bleMD Color')[:,:3], expected, atol=1e-6)
assert obj.data.attributes['bleMD Color'].data_type == 'FLOAT_COLOR'
assert any(n.type == 'ATTRIBUTE' and n.attribute_name == 'bleMD Color' for n in output.material.node_tree.nodes)
# Geometry branch remains unmodified; the branch compiler reuses analysis work.
graph = Graph(tree)
geometry, _ = graph.output_pipeline()
assert 'Shear Strain' not in geometry.compute(1).particles
assert graph.field(analysis.outputs['Shear Strain']).pipeline is graph.field(analysis.outputs['Strain Tensor']).pipeline

# Every advertised optional Atomic Strain result is produced on demand.
for name, kind, flag in ANALYSIS_OUTPUTS['AtomicStrainModifier']:
    consumer = tree.nodes.new('BleMDFieldComponent') if kind == TENSOR else tree.nodes.new('BleMDColorMap')
    edge = link(analysis.outputs[name], consumer.inputs['Tensor / Quaternion'] if kind == TENSOR else consumer.inputs[0])
    graph = Graph(tree)
    field = graph.field(analysis.outputs[name])
    actual_data, values, _ = graph.field_values(field, 1)
    modifier = AtomicStrainModifier()
    if flag:
        setattr(modifier, flag, True)
    ref = import_file(FILE, sort_particles=True); ref.modifiers.append(modifier)
    np.testing.assert_allclose(values, np.asarray(ref.compute(1).particles[name]), atol=1e-8)
    tree.nodes.remove(consumer)

# Keep artist materials and shader edits, and honor explicit field connections
# even when dataset attributes have been restricted.
material = output.material
material.node_tree.nodes.new('ShaderNodeMath').label = 'Artist edit'
output.attributes = 'Particle Identifier'
evaluate_tree(tree, scene)
assert output.material == material
assert any(n.label == 'Artist edit' for n in material.node_tree.nodes)
assert 'bleMD Color' in obj.data.attributes and 'bleMD Value' in obj.data.attributes
output.attributes = ''

# Join a full analysis to filtered and reversed particle geometry by ID.
script = tree.nodes.new('BleMDOvitoScript')
text = bpy.data.texts.new('Filtered geometry')
text.write('''import numpy as np
from ovito.modifiers import ExpressionSelectionModifier, DeleteSelectedModifier
pipeline.modifiers.append(ExpressionSelectionModifier(expression="ParticleIdentifier > 10"))
pipeline.modifiers.append(DeleteSelectedModifier())
def reverse(frame, data):
    for name in list(data.particles.keys()):
        data.particles_.create_property(name, data=np.asarray(data.particles[name])[::-1].copy())
pipeline.modifiers.append(reverse)
''')
script.script = text
link(source.outputs[0], script.inputs[0]); link(script.outputs[0], output.inputs[0])
obj = evaluate_tree(tree, scene)
ids = attr(obj, 'Particle Identifier').astype(int)
assert len(ids) == 10 and ids[0] == 10
np.testing.assert_allclose(attr(obj, 'bleMD Value'), np.asarray(data.particles['Strain Tensor'])[ids-1,0], atol=1e-6)

# Vector outputs and component extraction from displacements.
displacement = tree.nodes.new('BleMD_CalculateDisplacementsModifier')
link(source.outputs[0], displacement.inputs[0])
link(displacement.outputs['Displacement'], output.inputs['Vector'])
evaluate_tree(tree, scene)
np.testing.assert_allclose(attr(obj, 'bleMD Vector'),
    np.asarray(native.source.compute(1).particles.positions)[ids-1] - np.asarray(native.source.compute(0).particles.positions)[ids-1], atol=1e-6)

# Interpolation applies ID matching to field arrays as well as positions.
link(source.outputs[0], output.inputs[0])
source.timesteps_per_frame = 2
obj = evaluate_tree(tree, scene)
np.testing.assert_allclose(attr(obj, 'bleMD Value'), .5*np.asarray(data.particles['Strain Tensor'])[:,0], atol=1e-6)
source.timesteps_per_frame = 1


def failure(fragment):
    old_mesh = output.target.data
    try:
        evaluate_tree(tree, scene)
    except ValueError as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError('Expected: ' + fragment)
    assert output.target.data == old_mesh

# Type mismatch, ambiguous component input, disabled analyses, range errors and mismatched sources.
link(analysis.outputs['Strain Tensor'], color.inputs[0]); failure('needs')
link(analysis.outputs['Shear Strain'], color.inputs[0])
link(component.outputs[0], color.inputs[0])
link(color.outputs[0], component.inputs['Vector']); failure('exactly one')
tree.links.remove(component.inputs['Tensor / Quaternion'].links[0]); failure('needs')
tree.links.remove(component.inputs['Vector'].links[0])
link(analysis.outputs['Strain Tensor'], component.inputs['Tensor / Quaternion'])
link(analysis.outputs['Shear Strain'], color.inputs[0])
analysis.enabled = False; failure('Enable analysis'); analysis.enabled = True
color.maximum = 0; failure('Maximum'); color.maximum = .2
other = tree.nodes.new('BleMDFileSource'); other.filepath = FILE
link(other.outputs[0], analysis.inputs[0]); failure('same File Source')
link(source.outputs[0], analysis.inputs[0])

# General reader validates shape; works on arbitrary imported properties.
reader = tree.nodes.new('BleMDReadProperty'); reader.property_name = 'Particle Identifier'
link(source.outputs[0], reader.inputs[0]); link(reader.outputs[0], output.inputs['Value'])
obj = evaluate_tree(tree, scene)
np.testing.assert_array_equal(attr(obj, 'bleMD Value'), np.arange(1,28))
reader.property_name = 'Position'; failure('does not match')
reader.field_type = 'VECTOR'; link(reader.outputs[0], output.inputs['Vector'])
obj = evaluate_tree(tree, scene)
np.testing.assert_allclose(attr(obj, 'bleMD Vector'), np.asarray(data.particles.positions), atol=1e-6)
link(component.outputs[0], output.inputs['Value'])

# Missing and duplicate IDs must leave the previous output intact.
link(source.outputs[0], output.inputs[0])
link(script.outputs[0], analysis.inputs[0])
failure('missing particle identifiers')
link(source.outputs[0], analysis.inputs[0])
text.clear()
text.write("import numpy as np\ndef duplicates(frame, data):\n    data.particles_.create_property('Particle Identifier', data=np.ones(data.particles.count, dtype=np.int64))\npipeline.modifiers.append(duplicates)\n")
link(script.outputs[0], output.inputs[0]); failure('must be unique')
text.clear()
text.write("def no_ids(frame, data):\n    del data.particles_['Particle Identifier']\npipeline.modifiers.append(no_ids)\n")
failure('requires Particle Identifier')
link(source.outputs[0], output.inputs[0])

# Model an older saved chain: pipeline-only analysis output and legacy sink.
legacy_tree = bpy.data.node_groups.new('Legacy migration', TREE_TYPE)
legacy_tree.use_fake_user = True
legacy_source = legacy_tree.nodes.new('BleMDFileSource'); legacy_source.filepath = FILE
legacy = legacy_tree.nodes.new('BleMD_CentroSymmetryModifier')
legacy.outputs.clear(); legacy.outputs.new(SOCKET_TYPE, 'Pipeline')
legacy_output = legacy_tree.nodes.new('BleMDParticleOutput')
for socket in list(legacy_output.inputs)[1:]:
    legacy_output.inputs.remove(socket)
legacy_tree.links.new(legacy_source.outputs[0], legacy.inputs[0])
legacy_tree.links.new(legacy.outputs[0], legacy_output.inputs[0])
# Migration retains the original socket and links, then adds field outputs.
migrate_tree(legacy_tree)
assert legacy.expose_dataset and legacy.outputs[0].name == 'Pipeline'
assert legacy.outputs[0].is_linked
assert legacy.outputs['Centrosymmetry'].bl_idname == SCALAR
assert legacy_output.inputs['Color'].bl_idname == COLOR
evaluate_tree(legacy_tree, scene)

# Save/reopen with typed nodes and pointer references intact.
evaluate_tree(tree, scene)
path = Path(os.environ['BLENDER_USER_CONFIG']) / 'fields-roundtrip.blend'
name = tree.name
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
tree = bpy.data.node_groups[name]
obj = evaluate_tree(tree, bpy.context.scene)
assert obj.data.attributes['bleMD Color'].data_type == 'FLOAT_COLOR'
# Disable/re-enable with an evaluated graph still open. Recipe associations
# and field links survive; native evaluated copies are released before teardown.
import addon_utils
for _ in range(2):
    addon_utils.disable('bleMD', default_set=False)
    addon_utils.enable('bleMD', default_set=False)
    tree = bpy.data.node_groups[name]
    obj = evaluate_tree(tree, bpy.context.scene)
    assert obj.bleMD_node_tree == tree
    assert obj.data.attributes['bleMD Color'].data_type == 'FLOAT_COLOR'
print('PASS: typed analysis DAG, native strain parity, optional outputs, ID joins, colors, vectors, interpolation, errors, migration and persistence')
