"""Run inside Blender to install the repository's freshly built ZIP."""

from pathlib import Path
import os
import shutil

import addon_utils
import bpy

# Fail before changing anything if Blender ignored a requested profile path.
for resource in ("CONFIG", "SCRIPTS"):
    expected = os.environ.get(f"BLENDER_USER_{resource}")
    if expected and (not Path(expected).is_dir()
                     or Path(bpy.utils.user_resource(resource)).resolve() != Path(expected).resolve()):
        raise RuntimeError(f"Unsafe BLENDER_USER_{resource}; create that directory before launch")

archive = Path(__file__).resolve().parents[1] / "bleMD.zip"
if addon_utils.check("bleMD")[1]:
    addon_utils.disable("bleMD", default_set=True)
    if addon_utils.check("bleMD")[1]:
        raise RuntimeError("Could not disable the existing bleMD installation")

result = bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=True, enable_on_install=False)
if result != {"FINISHED"}:
    raise RuntimeError(f"Installation failed: {result}")
# Persist enablement for the next Blender process. Hot-reloading generated
# node RNA classes in Blender 4.2 is unstable after subsequent .blend reads.
# workflow.py verifies registration in a fresh process before reporting success.
if "bleMD" not in bpy.context.preferences.addons:
    bpy.context.preferences.addons.new().module = "bleMD"
preferences = Path(bpy.utils.user_resource("CONFIG", create=True)) / "userpref.blend"
if preferences.exists():
    shutil.copy2(preferences, preferences.with_name("userpref.blemd-backup.blend"))
bpy.ops.wm.save_userpref()
print("Installed bleMD; enablement saved for the next Blender process")
