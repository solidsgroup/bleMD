try:
    import bpy
    bpy.ops.preferences.addon_install(filepath="bleMD.zip",overwrite=True)
    bpy.ops.preferences.addon_enable(module='bleMD')

except Exception as e:
    print("Aha I caught an exception")
    print(e)
    raise e
### You must print this line, otherwise the Github action will think 
### the script failed.
#print("SCRIPT COMPLETED SUCCESSFULLY")

