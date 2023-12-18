import bpy
bpy.ops.preferences.addon_disable(module='bleMD')
bpy.ops.preferences.addon_remove(module='bleMD')
bpy.ops.wm.quit_blender()
print("---successful completion---")
