import bpy
#bpy.ops.preferences.addon_disable(module="bleMD")
#bpy.ops.preferences.addon_remove(module="bleMD")
bpy.ops.preferences.addon_install(filepath="/home/brunnels/Research/bleMD/bleMD.zip",overwrite=True)
bpy.ops.preferences.addon_enable(module='bleMD')

#bpy.context.scene.bleMD_props.lammpsfile="/home/brunnels/Downloads/qstruct_S3_fcc_N13_n17_25_Al_M99_201228.389.out"
#bpy.ops.wm.read_lammps_file()
