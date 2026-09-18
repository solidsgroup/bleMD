"""Source timing, editable socket defaults, migration, Cycles, and far clipping."""
from pathlib import Path
import os
import bpy
import numpy as np
from bleMD import bleMDLive as live, bleMDScene
from bleMD.bleMDTree import starter_tree
from bleMD.bleMDFields import SCALAR, VECTOR, COLOR, migrate_tree
from bleMD.bleMDPipeline import evaluate_tree

ROOT = Path(__file__).resolve().parents[1]
for old in bpy.data.node_groups:
    if old.bl_idname == 'BleMDNodeTree': old.automatic_updates = False
scene = bpy.context.scene
live.suspended = False
scene.frame_set(0)
tree = starter_tree(); tree.scene = scene
source = next(n for n in tree.nodes if n.bl_idname == 'BleMDFileSource')
output = next(n for n in tree.nodes if n.bl_idname == 'BleMDParticleOutput')
color = next(n for n in tree.nodes if n.bl_idname == 'BleMDColorMap')
assert (source.start_frame, source.timesteps_per_frame) == (0,1)
assert output.inputs['Radius'].default_value == 1
assert scene.render.engine == 'CYCLES'
source.filepath = str(ROOT / 'tests/fixtures/tiny.dump')
source.start_frame = 10; source.timesteps_per_frame = 5
live.tick()
assert not tree.has_error, tree.last_message
obj = output.target
graph = live._states[tree.as_pointer()]['graph']
assert (scene.frame_start, scene.frame_end) == (10,15)
for frame, x in ((0,1), (10,1), (11,1.4), (12,1.8), (14,2.6), (15,3), (99,3)):
    scene.frame_set(frame)
    assert np.isclose(obj.data.vertices[0].co.x, x), (frame, obj.data.vertices[0].co[:])
    assert live._states[tree.as_pointer()]['graph'] is graph
source.start_frame = 20; source.timesteps_per_frame = 2
scene.frame_set(21)
assert np.isclose(obj.data.vertices[0].co.x,2)
assert (scene.frame_start,scene.frame_end) == (20,22)
assert live._states[tree.as_pointer()]['graph'] is graph
# The source actually feeding Data determines the timing, not an unused source.
unused = tree.nodes.new('BleMDFileSource'); unused.start_frame = 100; unused.timesteps_per_frame = 20
scene.frame_set(20)
assert np.isclose(obj.data.vertices[0].co.x,1)

# Unconnected sockets own their values, linking overrides them, disconnecting
# restores them; named constants export even without a connection.
output.inputs['Radius'].default_value = .37
for kind, name, value in ((SCALAR,'Constant scalar',.25), (VECTOR,'Constant vector',(2,-3,4)), (COLOR,'Constant color',(.1,.2,.3))):
    socket = output.inputs.new(kind,'Shader field'); socket['bleMD_export_name'] = name
    socket.default_value = value
output.inputs['Value'].default_value = .9
output.inputs['Vector'].default_value = (1,2,3)
live.tick()
assert not tree.has_error, tree.last_message
np.testing.assert_allclose([v.value for v in obj.data.attributes['Constant scalar'].data], [.25]*3)
np.testing.assert_allclose([v.vector[:] for v in obj.data.attributes['Constant vector'].data], [[2,-3,4]]*3)
np.testing.assert_allclose([v.color[:3] for v in obj.data.color_attributes['Constant color'].data], [[.1,.2,.3]]*3,atol=1e-6)
np.testing.assert_allclose([v.value for v in obj.data.attributes['bleMD Value'].data], [.9]*3)
np.testing.assert_allclose([v.vector[:] for v in obj.data.attributes['bleMD Vector'].data], [[1,2,3]]*3)
radius_socket = obj.modifiers['build_geonode'].node_group.nodes['Mesh to Points'].inputs['Radius']
assert np.isclose(radius_socket.default_value,.37)
tree.links.new(source.outputs['c_energy'],output.inputs['Radius']);live.tick()
assert radius_socket.is_linked
assert np.isclose(output.inputs['Radius'].default_value,.37)
tree.links.remove(output.inputs['Radius'].links[0]);live.tick()
assert not radius_socket.is_linked and np.isclose(radius_socket.default_value,.37)
# Unconnected Color switches to the socket's uniform value when edited.
tree.links.remove(output.inputs['Color'].links[0])
output.inputs['Color'].default_value = (.2,.8,.4)
live.tick()
np.testing.assert_allclose([v.color[:3] for v in obj.data.color_attributes['bleMD Color'].data], [[.2,.8,.4]]*3,atol=1e-6)
# Color Map also accepts an unconnected scalar socket.
tree.links.remove(color.inputs['Value'].links[0])
color.inputs['Value'].default_value = .25
color.range_mode='FIXED';color.minimum=0;color.maximum=1
color.palette='CUSTOM'
tree.links.new(color.outputs['Color'],output.inputs['Color']);live.tick()
assert not tree.has_error,tree.last_message
expected = .75*np.asarray(color.low_color)+.25*np.asarray(color.high_color)
np.testing.assert_allclose([v.color[:3] for v in obj.data.color_attributes['bleMD Color'].data],[expected]*3,atol=1e-6)
color.range_mode='FIRST_FRAME';live.tick()
expected = .5*(np.asarray(color.low_color)+np.asarray(color.high_color))
np.testing.assert_allclose([v.color[:3] for v in obj.data.color_attributes['bleMD Color'].data],[expected]*3,atol=1e-6)

# Migrate saved tree timing and separate Radius/Color properties exactly once.
legacy = starter_tree();legacy.automatic_updates=False
old_source = next(n for n in legacy.nodes if n.bl_idname=='BleMDFileSource')
old_output = next(n for n in legacy.nodes if n.bl_idname=='BleMDParticleOutput')
del old_source['bleMD_timing_version']; del old_output['bleMD_socket_defaults']
legacy.start_frame=7; legacy.frame_stride=4
old_output['radius']=.75;old_output['color']=(.2,.4,.6);old_output.color_mode='AUTO'
migrate_tree(legacy)
assert (old_source.start_frame,old_source.timesteps_per_frame)==(7,4)
assert old_output.inputs['Radius'].default_value==.75
np.testing.assert_allclose(old_output.inputs['Color'].default_value,(.2,.4,.6),atol=1e-6)
assert old_output.color_mode=='AUTO'
old_source.start_frame=9;old_output.inputs['Radius'].default_value=.5
migrate_tree(legacy)
assert old_source.start_frame==9 and old_output.inputs['Radius'].default_value==.5

# Far clipping follows large simulation coordinates and viewport zoom without
# moving the camera or resetting independently chosen view centers.
camera_data = bpy.data.cameras.new('Clipping test')
camera = bpy.data.objects.new('Clipping test',camera_data);scene.collection.objects.link(camera)
camera.location=(5,10,15);camera_data.clip_end=100
script = tree.nodes.new('BleMDOvitoScript');script.script=bpy.data.texts.new('Far coordinates')
script.script.write('from ovito.modifiers import AffineTransformationModifier\npipeline.modifiers.append(AffineTransformationModifier(transformation=((1,0,0,100000),(0,1,0,0),(0,0,1,0))))')
tree.links.new(source.outputs['Data'],script.inputs['Data']);tree.links.new(script.outputs['Data'],output.inputs['Data'])
live.tick();assert not tree.has_error,tree.last_message
assert camera.data.clip_end>100000
assert tuple(camera.location)==(5,10,15)
spaces=[s for screen in bpy.data.screens for area in screen.areas for s in area.spaces if s.type=='VIEW_3D']
assert all(s.clip_end>100000 for s in spaces)
if spaces:
    space=spaces[0];space.region_3d.view_distance=200000
    live.tick()
    assert space.clip_end>400000
# Users can still select another renderer after bleMD initialization.
scene.render.engine='BLENDER_EEVEE_NEXT'
bleMDScene.ensure_defaults(scene)
assert scene.render.engine=='BLENDER_EEVEE_NEXT'
scene.render.engine='CYCLES'

name=tree.name
path=str(Path(os.environ['BLENDER_USER_CONFIG'])/'inputs-roundtrip.blend')
bpy.ops.wm.save_as_mainfile(filepath=path);bpy.ops.wm.open_mainfile(filepath=path)
tree=bpy.data.node_groups[name]
source=next(n for n in tree.nodes if n.bl_idname=='BleMDFileSource' and n.filepath)
output=next(n for n in tree.nodes if n.bl_idname=='BleMDParticleOutput')
assert (source.start_frame,source.timesteps_per_frame)==(20,2)
assert np.isclose(output.inputs['Radius'].default_value,.37)
assert next(s for s in output.inputs if s.get('bleMD_export_name')=='Constant scalar').default_value==.25
assert bpy.context.scene.render.engine=='CYCLES'
live.tick();assert not tree.has_error,tree.last_message
print('PASS: File Source timing/interpolation, editable radius/color/scalar/vector sockets, link override/restoration, constants, legacy migration, Cycles defaults, adaptive viewport/camera clipping and persistence')
