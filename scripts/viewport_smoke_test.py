"""Actual evaluated viewport geometry, per-particle colors, and render separation."""
from pathlib import Path
import os
import bpy
import numpy as np
from mathutils import Vector

from bleMD.bleMDPipeline import TREE_TYPE, evaluate_tree
from bleMD.bleMDViewport import refresh_saved_outputs, update_evaluated_colors
from bleMD.bleMDNodes import create_group

ROOT = Path(__file__).resolve().parents[1]
scene = bpy.context.scene
scene.frame_set(0)
tree = bpy.data.node_groups.new('Viewport colors', TREE_TYPE)
tree.use_fake_user = True
source = tree.nodes.new('BleMDFileSource')
source.filepath = str(ROOT / 'tests/fixtures/tiny.dump')
reader = tree.nodes.new('BleMDReadProperty'); reader.property_name = 'c_energy'
color = tree.nodes.new('BleMDColorMap'); color.minimum = .1; color.maximum = .3
output = tree.nodes.new('BleMDParticleOutput'); output.radius = .4
for a, b in ((source.outputs[0], reader.inputs[0]), (reader.outputs[0], color.inputs[0]),
             (source.outputs[0], output.inputs[0]), (color.outputs[0], output.inputs['Color'])):
    tree.links.new(a, b)
obj = evaluate_tree(tree, scene)


def evaluated_mesh():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    return obj.evaluated_get(dg).data


mesh = evaluated_mesh()
assert len(obj.data.vertices) == 3, 'The stored particle data must remain one vertex per atom'
assert len(mesh.polygons) > 0, 'Viewport output still contains only points'
assert mesh.color_attributes.active_color_name == 'bleMD Color'
assert mesh.color_attributes.default_color_name == 'bleMD Color'
assert all(p.use_smooth for p in mesh.polygons)
assert output.material in [m.original for m in mesh.materials if m], [(m.name if m else None) for m in mesh.materials]
count = len(mesh.vertices)
ids = np.empty(count, dtype=np.int32)
mesh.attributes['Particle Identifier'].data.foreach_get('value', ids)
colors = np.empty(count*4)
mesh.color_attributes['bleMD Color'].data.foreach_get('color', colors)
original_colors = np.array([tuple(c.color) for c in obj.data.color_attributes['bleMD Color'].data])
np.testing.assert_allclose(colors.reshape(-1,4), original_colors[ids-1], atol=1e-6)
assert not np.allclose(original_colors[0], original_colors[2]), 'Fixture must have distinct colors'
positions = np.empty(count*3); mesh.vertices.foreach_get('co', positions)
centers = np.array([tuple(v.co) for v in obj.data.vertices])[ids-1]
np.testing.assert_allclose(np.linalg.norm(positions.reshape(-1,3)-centers, axis=1), .4, atol=1e-6)
assert all(s.shading.color_type == 'VERTEX' for screen in bpy.data.screens for area in screen.areas for s in area.spaces if s.type=='VIEW_3D')

# Detail changes affect only the viewport and do not rerun OVITO or replace data.
original_mesh = obj.data
output.viewport_detail = 'LOW'
assert len(evaluated_mesh().vertices) < count
output.viewport_detail = 'HIGH'
assert len(evaluated_mesh().vertices) > count
output.viewport_detail = 'POINTS'
assert len(evaluated_mesh().polygons) == 0
output.viewport_detail = 'MEDIUM'
assert len(evaluated_mesh().vertices) == count
assert obj.data == original_mesh

# Upgrading the original geometry graph retains the material, radius and shaders.
old = obj.modifiers['build_geonode'].node_group
obj.modifiers['build_geonode'].node_group = create_group('Original point display', obj)
group = obj.modifiers['build_geonode'].node_group
group.nodes['Mesh to Points'].inputs['Radius'].default_value = .4
group.nodes['Set Material'].inputs['Material'].default_value = output.material
shader = output.material.node_tree.nodes.new('ShaderNodeMath'); shader.label = 'Keep artist edits'
refresh_saved_outputs()
assert len(evaluated_mesh().vertices) == count
assert any(n.label == 'Keep artist edits' for n in output.material.node_tree.nodes)
assert group.nodes['Set Material'].inputs['Material'].default_value == output.material
assert np.isclose(group.nodes['Mesh to Points'].inputs['Radius'].default_value,.4)

# Request an actual RENDER dependency graph through a minimal render engine.
# It inspects geometry without involving lighting or image-comparison noise.
seen_render = []
class BLEMD_TEST_Render(bpy.types.RenderEngine):
    bl_idname = 'BLEMD_TEST_RENDER'
    bl_label = 'bleMD render geometry test'
    def render(self, dg):
        evaluated = obj.evaluated_get(dg)
        seen_render.append((dg.mode, len(evaluated.data.polygons)))
        result = self.begin_result(0, 0, 32, 32)
        self.end_result(result)
bpy.utils.register_class(BLEMD_TEST_Render)
old_engine = scene.render.engine
previous_hidden = [(o, o.hide_render) for o in scene.objects]
for other, _ in previous_hidden:
    other.hide_render = other != obj
camera_data = bpy.data.cameras.new('Viewport test camera')
camera = bpy.data.objects.new('Viewport test camera', camera_data)
scene.collection.objects.link(camera)
camera.location = (2,-8,8)
camera.rotation_euler = (Vector((2,2,2))-camera.location).to_track_quat('-Z','Y').to_euler()
old_camera = scene.camera
scene.camera = camera
scene.render.engine = 'BLEMD_TEST_RENDER'
scene.render.resolution_x = 32; scene.render.resolution_y = 32; scene.render.resolution_percentage = 100
try:
    bpy.ops.render.render()
    assert seen_render == [('RENDER', 0)], seen_render
finally:
    scene.render.engine = old_engine
    bpy.utils.unregister_class(BLEMD_TEST_Render)
    scene.camera = old_camera
    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    for other, hidden in previous_hidden:
        other.hide_render = hidden

# Native OVITO Color is also displayed without requiring a typed Color branch.
for edge in list(output.inputs['Color'].links):
    tree.links.remove(edge)
script = tree.nodes.new('BleMDOvitoScript')
text = bpy.data.texts.new('OVITO color test')
text.write('from ovito.modifiers import AssignColorModifier\npipeline.modifiers.append(AssignColorModifier(color=(0.2,0.7,0.1)))\n')
script.script = text
output.material = None
tree.links.new(source.outputs[0], script.inputs[0]); tree.links.new(script.outputs[0], output.inputs[0])
evaluate_tree(tree, scene)
np.testing.assert_allclose(obj.data.color_attributes['bleMD Color'].data[0].color[:3], [.2,.7,.1], atol=1e-6)
assert evaluated_mesh().color_attributes.active_color_name == 'bleMD Color'

name, obj_name = tree.name, obj.name
path = Path(os.environ['BLENDER_USER_CONFIG']) / 'viewport-roundtrip.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
tree = bpy.data.node_groups[name]; obj = bpy.data.objects[obj_name]
assert len(evaluated_mesh().polygons) > 0
assert evaluated_mesh().color_attributes.active_color_name == 'bleMD Color'
assert bpy.app.handlers.depsgraph_update_post.count(update_evaluated_colors) == 1
print('PASS: round viewport geometry, per-atom colors and radius, detail switching, migration, shader preservation, native OVITO color, render separation and save/reopen')
