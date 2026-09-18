"""Exercise the custom editor and its actual OVITO/Blender evaluation path."""

from pathlib import Path
import os

import bpy
import numpy as np

from bleMD.bleMDPipeline import evaluate_tree, pipeline_chain
from bleMD.bleMDTree import TREE_TYPE, SOURCE_TYPE, SCRIPT_TYPE, OUTPUT_TYPE

ROOT = Path(__file__).resolve().parents[1]
area = bpy.context.screen.areas[0]
area.ui_type = TREE_TYPE
with bpy.context.temp_override(area=area):
    assert bpy.ops.blemd.new_pipeline() == {'FINISHED'}
tree = area.spaces.active.node_tree
assert area.type == 'NODE_EDITOR' and area.ui_type == TREE_TYPE
source = next(n for n in tree.nodes if n.bl_idname == SOURCE_TYPE)
assert not any(n.bl_idname == SCRIPT_TYPE for n in tree.nodes)
color = next(n for n in tree.nodes if n.bl_idname == 'BleMDColorMap')
assert color.range_mode == 'FIRST_FRAME'
script = tree.nodes.new(SCRIPT_TYPE)
script.enabled = False
output = next(n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE)
# This suite still tests scripted geometry chains. Typed source coloring has
# dedicated tests, so remove that branch from this legacy playback exercise.
tree.nodes.remove(color)
tree.links.new(source.outputs[0], script.inputs[0])
tree.links.new(script.outputs[0], output.inputs[0])
source.filepath = str(ROOT / 'tests' / 'fixtures' / 'tiny.dump')
scene = bpy.context.scene
scene.frame_set(0)
active_before = bpy.context.view_layer.objects.active
with bpy.context.temp_override(area=area):
    assert bpy.ops.blemd.update_pipeline() == {'FINISHED'}
obj = output.target
assert obj.bleMD_node_tree == tree
assert bpy.context.view_layer.objects.active == active_before
assert len(obj.data.vertices) == 3
assert tuple(obj.data.vertices[0].co) == (1, 1, 1)
assert obj.data.attributes['Particle Identifier'].data_type == 'INT'
assert obj.data.attributes['Particle Type'].data_type == 'INT'
assert obj.data.attributes['c_energy'].data_type == 'FLOAT'
assert obj.modifiers['build_geonode'].node_group is not None
with bpy.context.temp_override(area=area):
    assert bpy.ops.blemd.new_material(node_name=output.name) == {'FINISHED'}
    assert bpy.ops.blemd.new_script(node_name=script.name) == {'FINISHED'}
script.script.clear()
script.script.write('from ovito.modifiers import ComputePropertyModifier\n'
                    'pipeline.modifiers.append(ComputePropertyModifier(output_property="TwiceEnergy", expressions=["2*c_energy"]))\n')
script.enabled = True
output.radius = 0.4
output.attributes = 'TwiceEnergy, Particle Type'
evaluate_tree(tree, scene)
assert output.target == obj
assert np.isclose(obj.data.attributes['TwiceEnergy'].data[0].value, 0.2)
assert 'c_energy' not in obj.data.attributes
assert obj.data.materials[0] == output.material
assert np.isclose(obj.modifiers['build_geonode'].node_group.nodes['Mesh to Points'].inputs['Radius'].default_value, 0.4)

# Frame mapping, endpoint clamping and float/discrete attribute behavior.
source.start_frame = 10
source.timesteps_per_frame = 2
scene.frame_set(11)
evaluate_tree(tree, scene)
assert tuple(obj.data.vertices[0].co) == (2, 1, 1)
assert np.isclose(obj.data.attributes['TwiceEnergy'].data[0].value, 0.4)
assert obj.data.attributes['Particle Type'].data[0].value == 1
with bpy.context.temp_override(area=area):
    assert bpy.ops.blemd.fit_timeline() == {'FINISHED'}
assert (scene.frame_start, scene.frame_end) == (10, 12)
scene.frame_set(100)
evaluate_tree(tree, scene)
assert tuple(obj.data.vertices[0].co) == (3, 1, 1)
scene.frame_set(0)
evaluate_tree(tree, scene)
assert tuple(obj.data.vertices[0].co) == (1, 1, 1)

# Output references and script text persist through saving and reopening.
roundtrip = Path(os.environ['BLENDER_USER_CONFIG']) / 'node-roundtrip.blend'
tree_name = tree.name
obj_name = obj.name
bpy.ops.wm.save_as_mainfile(filepath=str(roundtrip))
bpy.ops.wm.open_mainfile(filepath=str(roundtrip))
tree = bpy.data.node_groups[tree_name]
source, script, output = pipeline_chain(tree)
scene = bpy.context.scene
obj = bpy.data.objects[obj_name]
assert output.target == obj and obj.bleMD_node_tree == tree
assert script.script and script.enabled
assert source.timesteps_per_frame == 2 and source.start_frame == 10
evaluate_tree(tree, scene)
assert np.isclose(obj.data.attributes['TwiceEnergy'].data[0].value, 0.2)

# Copying a recipe must create a separate output, not overwrite the first.
copy = tree.copy()
copy_output = next(n for n in copy.nodes if n.bl_idname == OUTPUT_TYPE)
copy_obj = evaluate_tree(copy, scene)
assert copy_obj != obj
assert copy_obj.bleMD_node_tree == copy
assert output.target == obj


def expect_error(fragment):
    mesh = obj.data
    try:
        evaluate_tree(tree, scene)
    except ValueError as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError(f'Expected: {fragment}')
    assert obj.data == mesh, 'A failed update changed the output mesh'


# Invalid graphs and scripts report errors before replacing existing output.
link = script.inputs[0].links[0]
tree.links.remove(link)
expect_error("Connect 'Data'")
tree.links.new(script.outputs[0], script.inputs[0])
expect_error('cycle')
tree.links.remove(script.inputs[0].links[0])
tree.links.new(source.outputs[0], script.inputs[0])
script.script.clear()
script.script.write('raise RuntimeError("test error")')
expect_error('test error')
extra = tree.nodes.new(OUTPUT_TYPE)
expect_error('exactly one Particle Output')
tree.nodes.remove(extra)

# Frame-dependent filtering changes particle counts. Exact saved frames work,
# while interpolated frames reject mismatched membership.
script.script.clear()
script.script.write('from ovito.modifiers import ExpressionSelectionModifier, DeleteSelectedModifier\n'
                    'pipeline.modifiers.append(ExpressionSelectionModifier(expression="Position.X > 3.5"))\n'
                    'pipeline.modifiers.append(DeleteSelectedModifier())\n')
output.attributes = ''
scene.frame_set(11)
expect_error('membership changes')
scene.frame_set(12)
evaluate_tree(tree, scene)
assert len(obj.data.vertices) == 1
scene.frame_set(10)
evaluate_tree(tree, scene)
assert len(obj.data.vertices) == 3

# Reorder particles differently each frame: interpolation must match IDs.
script.script.clear()
script.script.write('import numpy as np\n'
                    'def reorder(frame, data):\n'
                    '    if frame == 1:\n'
                    '        for name in list(data.particles.keys()):\n'
                    '            values = np.asarray(data.particles[name]).copy()[::-1]\n'
                    '            data.particles_.create_property(name, data=values)\n'
                    'pipeline.modifiers.append(reorder)\n')
scene.frame_set(11)
evaluate_tree(tree, scene)
assert tuple(obj.data.vertices[0].co) == (2, 1, 1)
assert tuple(obj.data.vertices[2].co) == (4, 3, 3)

# Deleting the output object permits a clean recreation on Update.
bpy.data.objects.remove(obj, do_unlink=True)
assert output.target is None
obj = evaluate_tree(tree, scene)
assert len(obj.data.vertices) == 3
print('PASS: bleMD node editor, script, attributes, playback, save/reopen, copying, errors, changing counts, ID matching')
