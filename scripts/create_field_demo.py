"""Run in a fresh Blender process to save examples/atomic-strain.blend.

/opt/blender-4.2.2-linux-x64/blender --background --factory-startup --python scripts/create_field_demo.py
Install the current add-on first with make install. No preferences are saved.
"""
from pathlib import Path
import addon_utils
import bpy

addon_utils.enable('bleMD', default_set=False)
from bleMD.bleMDPipeline import TREE_TYPE, evaluate_tree

ROOT = Path(__file__).resolve().parents[1]
tree = bpy.data.node_groups.new('Atomic Strain — particle fields', TREE_TYPE)
tree.use_fake_user = True
source = tree.nodes.new('BleMDFileSource')
source.filepath = str(ROOT / 'tests/fixtures/strain.dump')
source.location = (-900, 300)
strain = tree.nodes.new('BleMD_AtomicStrainModifier')
strain.location = (-550, 80)
strain.show_parameters = False
color = tree.nodes.new('BleMDColorMap')
color.location = (-160, 80)
color.maximum = .2
component = tree.nodes.new('BleMDFieldComponent')
component.location = (-160, -270)
component.label = 'Strain tensor XX'
output = tree.nodes.new('BleMDParticleOutput')
output.location = (190, 300)
output.radius = .2
for a, b in ((source.outputs[0], strain.inputs[0]),
             (source.outputs[0], output.inputs[0]),
             (strain.outputs['Shear Strain'], color.inputs[0]),
             (color.outputs[0], output.inputs['Color']),
             (strain.outputs['Strain Tensor'], component.inputs['Tensor / Quaternion']),
             (component.outputs[0], output.inputs['Value'])):
    tree.links.new(a, b)
scene = bpy.context.scene
scene.frame_start = 0; scene.frame_end = 1
scene.frame_set(1)
obj = evaluate_tree(tree, scene)
for other in scene.objects:
    other.select_set(False)
    if other != obj:
        other.hide_set(True)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
area = max(bpy.context.screen.areas, key=lambda area: area.width * area.height)
area.ui_type = TREE_TYPE
area.spaces.active.node_tree = tree
area.spaces.active.show_region_ui = False
for node in tree.nodes:
    node.select = False
region = next(r for r in area.regions if r.type == 'WINDOW')
with bpy.context.temp_override(area=area, region=region):
    bpy.ops.node.view_all()
path = ROOT / 'examples/atomic-strain.blend'
path.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
print('Saved field demo:', path)
