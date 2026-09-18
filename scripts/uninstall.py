"""Run inside Blender to remove bleMD and persist the preference change."""

import bpy

# Blender 4.2's remove operator redraws an area even in background mode.
with bpy.context.temp_override(area=bpy.context.screen.areas[0]):
    result = bpy.ops.preferences.addon_remove(module="bleMD")
if result != {"FINISHED"}:
    raise RuntimeError(f"Uninstall failed: {result}")
bpy.ops.wm.save_userpref()
print("Removed bleMD")
