import bpy
bpy.ops.preferences.addon_disable(module='bleMD')
bpy.ops.preferences.addon_remove(module='bleMD')
bpy.ops.preferences.addon_install(filepath="./bleMD.zip",overwrite=True)
bpy.ops.preferences.addon_enable(module='bleMD')
print("---successful completion---")
