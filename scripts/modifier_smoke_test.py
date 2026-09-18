"""Catalog coverage plus native OVITO parity and persistence of modifier nodes."""
from pathlib import Path
import os

import bpy
import numpy as np
import ovito.modifiers as modifiers
from ovito.io import import_file
from ovito.pipeline import Modifier, ModifierInterface

from bleMD.bleMDModifiers import CATALOG, append_modifier, member, parameter_value, set_member
from bleMD.bleMDPipeline import build_pipeline, evaluate_tree, TREE_TYPE, SOURCE_TYPE, OUTPUT_TYPE

ROOT = Path(__file__).resolve().parents[1]
FILE = str(ROOT / 'tests/fixtures/tiny.dump')
expected = set()
for name in dir(modifiers):
    cls = getattr(modifiers, name)
    if isinstance(cls, type) and issubclass(cls, (Modifier, ModifierInterface)):
        try:
            cls()
        except TypeError:
            continue
        expected.add(cls.__name__)
assert set(CATALOG) == expected

all_tree = bpy.data.node_groups.new('All OVITO modifiers', TREE_TYPE)
all_tree.use_fake_user = True
controls = 0
for name, record in CATALOG.items():
    node = all_tree.nodes.new('BleMD_' + name)
    assert node.bl_label == record['label']
    if issubclass(record['cls'], Modifier):
        native = record['cls']()
        assert record['category'] == native._ovito_class.class_metadata('ModifierCategory')
    else:
        native = record['cls']()
    # Every exposed parameter must roundtrip through Blender's serialized RNA
    # and be accepted by its corresponding native OVITO property setter.
    for spec in record['parameters']:
        original = record['cls']()
        original_value = original
        for part in spec.path:
            original_value = member(original_value, part)
        try:
            set_member(original, spec.path, original_value)
        except Exception:
            # Some native defaults are uninitialized sentinels (e.g. an empty
            # voxel-grid selector). They are not legal user overrides.
            assert not getattr(node, 'use_' + spec.storage_key)
            continue
        try:
            set_member(native, spec.path, parameter_value(node, spec.storage_key, spec))
        except Exception as error:
            raise AssertionError(f'{name}.{spec.key}: {error}') from error
        controls += 1
    pipeline = import_file(FILE, sort_particles=True)
    append_modifier(node, pipeline, all_tree)
    assert len(pipeline.modifiers) == 1, name


def new_tree(*names):
    tree = bpy.data.node_groups.new('Modifier test', TREE_TYPE)
    source = tree.nodes.new(SOURCE_TYPE)
    source.filepath = FILE
    previous = source
    nodes = []
    for name in names:
        node = tree.nodes.new('BleMD_' + name)
        node.expose_dataset = True
        tree.links.new(previous.outputs[0], node.inputs[0])
        nodes.append(node)
        previous = node
    output = tree.nodes.new(OUTPUT_TYPE)
    tree.links.new(previous.outputs[0], output.inputs[0])
    return tree, nodes, output


def set_parameter(node, key, value):
    spec = next(p for p in CATALOG[node.modifier_name]['parameters'] if p.key == key)
    setattr(node, 'value_' + spec.storage_key, value)
    assert getattr(node, 'use_' + spec.storage_key)


def parity(name, settings):
    tree, (node,), _ = new_tree(name)
    native = getattr(modifiers, name)()
    for key, value in settings.items():
        set_parameter(node, key, value)
        spec = next(p for p in CATALOG[name]['parameters'] if p.key == key)
        set_member(native, spec.path, parameter_value(node, spec.storage_key, spec))
    expected_pipeline = import_file(FILE, sort_particles=True)
    expected_pipeline.modifiers.append(native)
    actual_pipeline, _ = build_pipeline(tree)
    for frame in (0, 1):
        actual = actual_pipeline.compute(frame)
        reference = expected_pipeline.compute(frame)
        assert set(actual.particles.keys()) == set(reference.particles.keys()), name
        for prop in actual.particles.keys():
            np.testing.assert_allclose(np.asarray(actual.particles[prop]), np.asarray(reference.particles[prop]), rtol=1e-5, atol=1e-6, err_msg=f'{name}.{prop}')
        assert set(actual.tables.keys()) == set(reference.tables.keys()), name
        for key in actual.tables.keys():
            np.testing.assert_allclose(actual.tables[key].xy(), reference.tables[key].xy(), rtol=1e-5, atol=1e-6)
    return tree, node


parity('ExpressionSelectionModifier', {'expression': 'ParticleIdentifier == 2'})
parity('SelectTypeModifier', {'property': 'Particle Type', 'types': '[2]'})
parity('AssignColorModifier', {'color': (0.2, 0.4, 0.6), 'keep_selection': True})
parity('SliceModifier', {'normal': (1.0, 0.0, 0.0), 'distance': 2.5, 'select': True})
parity('ComputePropertyModifier', {'output_property': 'TwiceEnergy', 'expressions': '2*c_energy'})
parity('HistogramModifier', {'property': 'c_energy', 'bin_count': 4})
parity('CoordinationAnalysisModifier', {'cutoff': 2.0, 'number_of_bins': 8})
parity('CentroSymmetryModifier', {'num_neighbors': 2})
parity('CommonNeighborAnalysisModifier', {'mode': 'FixedCutoff', 'cutoff': 2.0})
parity('CreateBondsModifier', {'cutoff': 2.0})
parity('ReplicateModifier', {'num_x': 2})
matrix = (1., 0., 0., 1., 0., 1., 0., 2., 0., 0., 1., 3.)
parity('AffineTransformationModifier', {'transformation': matrix})

# Actual node-chain evaluation, disabled modifiers, and output replacement.
tree, (select, delete), output = new_tree('ExpressionSelectionModifier', 'DeleteSelectedModifier')
set_parameter(select, 'expression', 'ParticleIdentifier == 2')
bpy.context.scene.frame_set(0)
obj = evaluate_tree(tree, bpy.context.scene)
assert len(obj.data.vertices) == 2
delete.enabled = False
evaluate_tree(tree, bpy.context.scene)
assert len(obj.data.vertices) == 3
delete.enabled = True
delete.mute = True
evaluate_tree(tree, bpy.context.scene)
assert len(obj.data.vertices) == 3
delete.mute = False

# Secondary file sources and references are real OVITO FileSource objects.
tree2, (combine,), _ = new_tree('CombineDatasetsModifier')
combine.secondary_file = FILE
pipeline, _ = build_pipeline(tree2)
assert pipeline.compute().particles.count == 6
tree3, (displacements,), _ = new_tree('CalculateDisplacementsModifier')
displacements.secondary_file = FILE
pipeline, _ = build_pipeline(tree3)
assert 'Displacement' in pipeline.compute(1).particles

# A Python modifier runs for each evaluated frame, unlike a pipeline script.
tree4, (python_node,), _ = new_tree('PythonModifier')
python_node.function_text = bpy.data.texts.new('Frame function')
python_node.function_text.write('def modify(frame, data):\n    data.particles_.create_property("FrameValue", data=[frame]*data.particles.count)\n')
pipeline, _ = build_pipeline(tree4)
assert np.all(np.asarray(pipeline.compute(1).particles['FrameValue']) == 1)

# Configure advanced native methods directly, e.g. pairwise bond cutoffs.
tree5, (bonds,), _ = new_tree('CreateBondsModifier')
bonds.configuration = bpy.data.texts.new('Bond configuration')
bonds.configuration.write('from ovito.modifiers import CreateBondsModifier\nmodifier.mode = CreateBondsModifier.Mode.Pairwise\nmodifier.set_pairwise_cutoff(1, 2, 2.0)\n')
pipeline, _ = build_pipeline(tree5)
assert pipeline.compute().particles.bonds is not None

# Manual selection records particle IDs in OVITO's native selection modifier.
tree6, (manual,), _ = new_tree('ManualSelectionModifier')
manual.selection_ids = '2'
pipeline, _ = build_pipeline(tree6)
for frame in (0,1):
    data = pipeline.compute(frame)
    selected = np.asarray(data.particles.identifiers)[np.asarray(data.particles.selection) != 0]
    assert selected.tolist() == [2]

# Coloring can feed downstream modifiers without dropping RGB data.
tree7, (color,), _ = new_tree('ColorCodingModifier')
set_parameter(color, 'property', 'c_energy')
color.gradient_name = 'Viridis'
pipeline, _ = build_pipeline(tree7)
assert np.asarray(pipeline.compute().particles.colors).shape == (3,3)

# Save all native node types plus a working chain, then reopen and evaluate.
all_name, tree_name, expr_name = all_tree.name, tree.name, select.name
bpy.ops.wm.save_as_mainfile(filepath=str(Path(os.environ['BLENDER_USER_CONFIG']) / 'modifiers.blend'))
bpy.ops.wm.open_mainfile(filepath=str(Path(os.environ['BLENDER_USER_CONFIG']) / 'modifiers.blend'))
assert len(bpy.data.node_groups[all_name].nodes) == len(CATALOG)
tree = bpy.data.node_groups[tree_name]
obj = evaluate_tree(tree, bpy.context.scene)
assert len(obj.data.vertices) == 2
print(f'PASS: {len(CATALOG)} OVITO modifier node types, {controls} native parameter controls, category parity, computation parity, sources, scripts, selections, persistence')
