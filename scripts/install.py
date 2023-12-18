import bpy, addon_utils
bpy.ops.preferences.addon_install(filepath="./bleMD.zip",overwrite=True)
bpy.ops.preferences.addon_enable(module="bleMD")
addon_utils.enable('bleMD')
bpy.ops.wm.quit_blender()
print("---successful completion---")
