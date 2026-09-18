"""Integration checks run by make test inside an isolated Blender profile."""

from pathlib import Path
import math
import os
import runpy

import addon_utils
import bpy
import bleMD

ROOT = Path(__file__).resolve().parents[1]
installed_path = Path(bleMD.__file__).resolve()
assert installed_path.is_relative_to(Path(os.environ["BLENDER_USER_SCRIPTS"])), installed_path
assert addon_utils.check("bleMD") == (True, True), "Enablement did not survive restart"


def unrelated_handler(scene):
    pass


# Verify that repeated enable/disable cycles leave Blender clean and preserve
# handlers owned by other add-ons.
bpy.app.handlers.frame_change_post.append(unrelated_handler)
for _ in range(2):
    addon_utils.disable("bleMD", default_set=True)
    for owner, names in (
        (bpy.types.Object, ("bleMD_props", "datafieldlist", "list_index", "bleMD_node_tree")),
        (bpy.types.Material, ("bleMD", "bleMD_props")),
    ):
        for name in names:
            assert not hasattr(owner, name), f"Leaked property: {name}"
    assert addon_utils.enable("bleMD", default_set=True) is not None
    assert unrelated_handler in bpy.app.handlers.frame_change_post
bpy.app.handlers.frame_change_post.remove(unrelated_handler)

bpy.context.scene.frame_set(0)
assert bpy.ops.object.blemd_open_file_dialog(filepath=str(ROOT / "tests" / "fixtures" / "tiny.dump")) == {"FINISHED"}
obj = bpy.context.object
assert obj.bleMD_props.number_of_lammps_frames == 2
obj.datafieldlist["c_energy"].enable = True
assert bpy.ops.wm.read_lammps_file() == {"FINISHED"}
assert len(obj.data.vertices) == 3
assert tuple(obj.data.vertices[0].co) == (1.0, 1.0, 1.0), "Particle IDs were not sorted"
assert math.isclose(obj.data.attributes["c_energy"].data[0].value, 0.1, abs_tol=1e-6)
assert obj.modifiers["build_geonode"].node_group is not None
assert bpy.ops.wm.create_material() == {"FINISHED"}
assert bpy.data.materials[obj.bleMD_props.mat_selection].bleMD

# Test interpolation of both positions and an imported scalar property.
obj.bleMD_props.lammps_frame_stride = 2
bpy.context.scene.frame_set(1)
assert bpy.ops.wm.read_lammps_file() == {"FINISHED"}
assert tuple(obj.data.vertices[0].co) == (2.0, 1.0, 1.0)
assert math.isclose(obj.data.attributes["c_energy"].data[0].value, 0.2, abs_tol=1e-6)
bpy.context.scene.frame_set(2)
assert bpy.ops.wm.read_lammps_file() == {"FINISHED"}
assert tuple(obj.data.vertices[0].co) == (3.0, 1.0, 1.0)

from bleMD import bleMDLive
bleMDLive.suspended = True  # Existing suites explicitly control evaluation.

runpy.run_path(str(ROOT / "scripts" / "node_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "modifier_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "field_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "viewport_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "source_smoke_test.py"), run_name="__main__")
bleMDLive.suspended = False
runpy.run_path(str(ROOT / "scripts" / "live_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "appearance_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "inputs_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "utility_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "cpk_smoke_test.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "uninstall.py"), run_name="__main__")
assert not installed_path.exists(), "Uninstall left add-on files behind"
assert "bleMD" not in bpy.context.preferences.addons
assert not addon_utils.check("bleMD")[1]

print(f"PASS: bleMD on Blender {bpy.app.version_string}: install, restart, reinstall, registration, import, geometry, material, interpolation, uninstall")
