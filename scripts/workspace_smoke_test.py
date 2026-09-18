"""UI integration test. Run in a disposable profile; exits its Blender window."""
import os
import bpy, addon_utils, traceback
from pathlib import Path
addon_utils.enable('bleMD', default_set=False)
from bleMD.bleMDTree import starter_tree
from bleMD.bleMDPipeline import SOURCE_TYPE, OUTPUT_TYPE
from bleMD import bleMDLive
root = Path(__file__).resolve().parents[1]
artifacts = Path(os.environ['BLENDER_USER_CONFIG'])
artifacts.mkdir(parents=True, exist_ok=True)
tree = starter_tree()
tree.scene = bpy.context.scene
bpy.context.scene.frame_set(0)
source = next(n for n in tree.nodes if n.bl_idname == SOURCE_TYPE)
output = next(n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE)
output.radius = .4
source.filepath = str(root / 'tests/fixtures/tiny.dump')
bleMDLive.tick()
original = bpy.context.workspace
original_areas = [(a.type,a.x,a.y,a.width,a.height) for a in bpy.context.screen.areas]

def fail():
    (artifacts / 'workspace-result.txt').write_text(traceback.format_exc())
    traceback.print_exc()
    bpy.ops.wm.quit_blender()

def start():
    try:
        assert bpy.ops.blemd.layout() == {'FINISHED'}
        bpy.app.timers.register(check, first_interval=2)
    except Exception:
        fail()

def check():
    try:
        assert bpy.context.workspace.get('bleMD_layout'), bpy.context.workspace.name
        screen = bpy.context.screen
        views = [a for a in screen.areas if a.type == 'VIEW_3D']
        nodes = [a for a in screen.areas if a.type == 'NODE_EDITOR' and a.ui_type == 'BleMDNodeTree']
        assert len(views) == len(nodes) == 1, [(a.type,a.ui_type) for a in screen.areas]
        assert len(views[0].spaces.active.region_quadviews) == 4
        assert [v.view_perspective for v in views[0].spaces.active.region_quadviews] == ['ORTHO']*3+['PERSP']
        assert not any(v.show_sync_view or v.use_box_clip for v in views[0].spaces.active.region_quadviews[:3])
        assert nodes[0].y < views[0].y
        assert nodes[0].spaces.active.node_tree == tree
        assert any(a.ui_type == 'TIMELINE' for a in screen.areas)
        assert [(a.type,a.x,a.y,a.width,a.height) for a in original.screens[0].areas] == original_areas
        count = len(bpy.data.workspaces)
        bpy.ops.blemd.layout()
        assert len(bpy.data.workspaces) == count
        bpy.context.scene.frame_set(1)
        assert tuple(output.target.data.vertices[0].co) == (3,1,1)
        assert output.target.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.color_attributes.active_color_name == 'bleMD Color'
        # Let the real timer, not an explicit call, observe an edit.
        output.radius = .25
        bpy.ops.wm.save_as_mainfile(filepath=str(artifacts / 'live-layout.blend'))
        bpy.app.timers.register(capture, first_interval=1)
    except Exception:
        fail()

def capture():
    try:
        assert abs(output.target.modifiers['build_geonode'].node_group.nodes['Mesh to Points'].inputs['Radius'].default_value - .25) < 1e-6
        bpy.ops.screen.screenshot(filepath=str(artifacts / 'blemd-layout.png'))
        (artifacts / 'workspace-result.txt').write_text('PASS: workspace, quad views, nodes, timeline, original layout preserved, reuse, live frame')
    except Exception:
        fail()
    bpy.ops.wm.quit_blender()
bpy.app.timers.register(start, first_interval=1)
