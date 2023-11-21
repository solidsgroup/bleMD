import bpy
bpy.ops.preferences.addon_install(filepath="./bleMD.zip",overwrite=True)
bpy.ops.preferences.addon_enable(module='bleMD')
print("---successful completion---")
