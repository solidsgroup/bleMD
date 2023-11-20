import bpy
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       UIList,
                       )
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       BoolVectorProperty,
                       CollectionProperty,
                       )


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class bleMDProperties(bpy.types.PropertyGroup):

    valid_lammps_file: BoolProperty(default=False)
    number_of_lammps_frames: IntProperty(default=1)

    def updateFrameStride(self, context):
        scene = context.scene
        mytool = scene.bleMD_props
        nframes = mytool.number_of_lammps_frames
        stride = mytool.lammps_frame_stride
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_end = nframes * stride

    lammps_frame_stride: IntProperty(
        name="Frame interpolation stride",
        description="How many frames to interpolate",
        default=1,
        min=1,
        max=100,
        update=updateFrameStride,
    )

    lammps_frame_min: IntProperty(
        name="Start",
        description="A integer property",
        default=0,
        min=0,
        max=100
    )
    lammps_frame_max: IntProperty(
        name="End",
        description="A integer property",
        default=0,
        min=0,
        max=100
    )

    def openLAMMPSFile(self, context):
        scene = context.scene
        mytool = scene.bleMD_props

        import ovito
        from ovito.io import import_file
        pipeline = import_file(mytool.lammpsfile, sort_particles=True)
        nframes = pipeline.source.num_frames
        mytool.number_of_lammps_frames = nframes
        bpy.context.scene.frame_end = nframes * mytool.lammps_frame_stride
        mytool.valid_lammps_file = True

        data = pipeline.compute()
        props = list(data.particles.keys())

        scene.datafieldlist.clear()
        for prop in props:
            item = scene.datafieldlist.add()
            item.name = prop
            if prop == "Position":
                item.enable = True
                item.editable = False

    lammpsfile: StringProperty(
        name="LAMMPS Dump File",
        description="Choose a file:",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
        update=openLAMMPSFile,
    )

    renderpath: StringProperty(
        name="Render output directory",
        description="Choose a file:",
        default="/tmp/",
        maxlen=1024,
        subtype='DIR_PATH'
    )

    my_shader: StringProperty(
        name="Select shader data",
        description="Type in desired data field to shade by:",
        default="c_csym",
        maxlen=1024,
        subtype='NONE'
    )
    
    my_normalhigh: FloatProperty(
        name="Data Max (for normalization)",
        description="Insert maximum value to shade by",
        default=1,
    )
    
    my_normallow: FloatProperty(
        name="Data Min (for normalization)",
        description="Insert minimum value to shade by",
        default=0,
    )

    #
    # Ovito Modifiers
    #
    ovito_wrap_periodic_images: BoolProperty(
        name="OVITO Wrap Periodic Images",
        default=False)
    ovito_unwrap_trajectories: BoolProperty(
        name="OVITO Unwrap Trajectories",
        default=False)

 
