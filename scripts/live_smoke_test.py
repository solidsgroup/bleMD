"""Timeline handlers and the same timer callback used by the interactive UI."""
from pathlib import Path
import bpy
import numpy as np
from bleMD import bleMDLive as live
from bleMD.bleMDTree import starter_tree
from bleMD.bleMDPipeline import SOURCE_TYPE, OUTPUT_TYPE, SCRIPT_TYPE

ROOT = Path(__file__).resolve().parents[1]
for old in bpy.data.node_groups:
    if old.bl_idname == 'BleMDNodeTree':
        old.automatic_updates = False
live.invalidate()
scene = bpy.context.scene
scene.frame_set(0)
tree = starter_tree()
tree.scene = scene
source = next(n for n in tree.nodes if n.bl_idname == SOURCE_TYPE)
output = next(n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE)
color = next(n for n in tree.nodes if n.bl_idname == 'BleMDColorMap')
assert tree.automatic_updates
source.filepath = str(ROOT / 'tests/fixtures/tiny.dump')
assert not source.channels_loaded and output.target is None
live.tick()
assert not tree.has_error, tree.last_message
obj = output.target
assert tuple(obj.data.vertices[0].co) == (1,1,1)
assert (scene.frame_start,scene.frame_end) == (0,1)
assert source.channels_loaded and 'c_energy' in source.outputs
assert scene.render.use_lock_interface
state = live._states[tree.as_pointer()]
graph = state['graph']
mesh = obj.data
live.tick()
assert obj.data == mesh, 'Idle timer rebuilt geometry'
scene.frame_set(1)
assert tuple(obj.data.vertices[0].co) == (3,1,1), tree.last_message
assert obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.color_attributes.active_color_name == 'bleMD Color'
assert live._states[tree.as_pointer()]['graph'] is graph, 'Scrubbing rebuilt the OVITO pipeline'
scene.frame_set(0)
assert tuple(obj.data.vertices[0].co) == (1,1,1)
assert len(graph.samples) <= 2

# Changing settings, links, node properties, and Text contents needs no Update.
source.timesteps_per_frame = 2
scene.frame_set(1)
assert tuple(obj.data.vertices[0].co) == (2,1,1)
color.low_color = (.2,.8,.4)
live.tick()
np.testing.assert_allclose(obj.data.color_attributes['bleMD Color'].data[0].color[:3], (.2,.8,.4), atol=1e-6)
mesh = obj.data
color.location.x += 10
color.label = 'Presentation only'
live.tick()
assert obj.data == mesh
script = tree.nodes.new(SCRIPT_TYPE)
script.script = bpy.data.texts.new('Live script')
script.script.write('from ovito.modifiers import AffineTransformationModifier\npipeline.modifiers.append(AffineTransformationModifier(transformation=((1,0,0,2),(0,1,0,0),(0,0,1,0))))\n')
tree.links.new(source.outputs['Data'], script.inputs['Data'])
tree.links.new(script.outputs['Data'], output.inputs['Data'])
live.tick()
assert not tree.has_error, tree.last_message
assert tuple(obj.data.vertices[0].co) == (4,1,1)
script.script.clear()
script.script.write('from ovito.modifiers import AffineTransformationModifier\npipeline.modifiers.append(AffineTransformationModifier(transformation=((1,0,0,4),(0,1,0,0),(0,0,1,0))))\n')
live.tick()
assert tuple(obj.data.vertices[0].co) == (6,1,1)
script.enabled = False
live.tick()
assert tuple(obj.data.vertices[0].co) == (2,1,1)

# Generated OVITO parameter controls and override checkboxes are observed too.
from bleMD.bleMDModifiers import CATALOG
native = tree.nodes.new('BleMD_AssignColorModifier')
spec = next(p for p in CATALOG['AssignColorModifier']['parameters'] if p.key == 'color')
tree.links.new(source.outputs['Data'], native.inputs['Data'])
tree.links.new(native.outputs['Data'], output.inputs['Data'])
tree.links.remove(output.inputs['Color'].links[0])
setattr(native, 'value_' + spec.storage_key, (.8,.3,.2))
live.tick()
assert not tree.has_error, tree.last_message
np.testing.assert_allclose(obj.data.color_attributes['bleMD Color'].data[0].color[:3], (.8,.3,.2), atol=1e-6)
setattr(native, 'value_' + spec.storage_key, (.1,.7,.4))
live.tick()
np.testing.assert_allclose(obj.data.color_attributes['bleMD Color'].data[0].color[:3], (.1,.7,.4), atol=1e-6)
tree.nodes.remove(native)
tree.links.new(source.outputs['Data'], output.inputs['Data'])
tree.links.new(color.outputs['Color'], output.inputs['Color'])
live.tick()

# Pause stops BOTH frame and parameter updates, including source I/O.
tree.automatic_updates = False
mesh = obj.data
source.filepath = str(ROOT / 'tests/fixtures/does-not-exist.dump')
output.radius = .35
scene.frame_set(2)
live.tick()
assert obj.data == mesh and not source.channels_loaded and not source.channels_error
source.filepath = str(ROOT / 'tests/fixtures/tiny.dump')
live.evaluate(tree, scene, force=True)
assert tuple(obj.data.vertices[0].co) == (3,1,1)
assert np.isclose(obj.modifiers['build_geonode'].node_group.nodes['Mesh to Points'].inputs['Radius'].default_value,.35)
mesh = obj.data
scene.frame_set(0)
assert obj.data == mesh
tree.automatic_updates = True
live.tick()
assert tuple(obj.data.vertices[0].co) == (1,1,1)

# File Sources also discover fields before they have downstream connections.
extra = tree.nodes.new(SOURCE_TYPE)
extra.filepath = str(ROOT / 'tests/fixtures/fields.xyz')
live.tick()
assert extra.channels_loaded and 'vel' in extra.outputs
tree.nodes.remove(extra)
live.tick()

# Invalid in-progress wiring preserves the previous mesh and doesn't retry
# continuously. Correcting the graph recovers automatically.
mesh = obj.data
tree.links.remove(output.inputs['Data'].links[0])
live.tick()
assert tree.has_error and obj.data == mesh
state = live._states[tree.as_pointer()]
live.tick()
assert live._states[tree.as_pointer()] is state
tree.links.new(source.outputs['Data'], output.inputs['Data'])
live.tick()
assert not tree.has_error, tree.last_message

# An actual animation render calls the frame handler before each render graph.
import os
seen = []
class BLEMD_TEST_Animation(bpy.types.RenderEngine):
    bl_idname = 'BLEMD_TEST_ANIMATION'
    bl_label = 'bleMD animation test'
    def render(self, dg):
        seen.append((dg.scene_eval.frame_current, tuple(output.target.data.vertices[0].co)))
        result = self.begin_result(0,0,16,16)
        self.end_result(result)
bpy.utils.register_class(BLEMD_TEST_Animation)
camera_data = bpy.data.cameras.new('Live test camera')
camera = bpy.data.objects.new('Live test camera', camera_data)
scene.collection.objects.link(camera)
old_camera, old_engine, old_path = scene.camera, scene.render.engine, scene.render.filepath
scene.camera = camera
scene.render.engine = 'BLEMD_TEST_ANIMATION'
scene.render.resolution_x = scene.render.resolution_y = 16
scene.render.resolution_percentage = 100
scene.render.filepath = str(Path(os.environ['BLENDER_USER_CONFIG']) / 'live-render-')
scene.frame_start, scene.frame_end = 0,2
try:
    bpy.ops.render.render(animation=True)
    assert seen == [(0,(1,1,1)), (1,(2,1,1)), (2,(3,1,1))], seen
finally:
    scene.render.engine, scene.render.filepath = old_engine, old_path
    scene.camera = old_camera
    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    bpy.utils.unregister_class(BLEMD_TEST_Animation)

# Saved configuration survives reopening; runtime caches never do.
import os
path = str(Path(os.environ['BLENDER_USER_CONFIG']) / 'live-roundtrip.blend')
name = tree.name
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
assert not live._states
tree = bpy.data.node_groups[name]
assert tree.automatic_updates and tree.scene == bpy.context.scene
bpy.context.scene.frame_set(2)
output = next(n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE)
assert tuple(output.target.data.vertices[0].co) == (3,1,1)
live.reset(None)
assert not live._states
print('PASS: automatic source loading, timeline playback, cached scrubbing, interpolation, edits/links/scripts, idle stability, native parameters, pause/manual update/resume, error recovery, animation render, persistence')
