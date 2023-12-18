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

from . bleMDUtils import *

from . bleMDColormaps import cm, getkeys


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class bleMDProperties(bpy.types.PropertyGroup):

    valid_lammps_file: BoolProperty(default=False)
    number_of_lammps_frames: IntProperty(default=1)

    override_defaults: BoolProperty(
        name="Override blender environment defaults",
        description="Set general defaults to look better for MD on file load",
        default=True,
    )


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
        resetDefaultsForMD()
        startOvito(hardrefresh=True)


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

    def my_normalhigh_normallow_update(self,context):
        my_normalhigh = bpy.context.scene.bleMD_props.my_normalhigh
        my_normallow = bpy.context.scene.bleMD_props.my_normallow
        my_range = my_normalhigh - my_normallow
        bpy.data.materials["my_mat"].node_tree.nodes["bleMD_MathNode1"].inputs[1].default_value = my_normallow
        bpy.data.materials["my_mat"].node_tree.nodes["bleMD_MathNode2"].inputs[1].default_value = my_range

    my_normalhigh: FloatProperty(
        name="Data Max (for normalization)",
        description="Insert maximum value to shade by",
        default=1,
        update=my_normalhigh_normallow_update,
    )
    
    my_normallow: FloatProperty(
        name="Data Min (for normalization)",
        description="Insert minimum value to shade by",
        default=0,
        update=my_normalhigh_normallow_update,
    )

    def colormap_items(self,context):
        return [(n,n,n) for n in cm.keys()]
    def colormap_update(self,context):
        while True:
            elements = bpy.data.materials['my_mat'].node_tree.nodes['Color Ramp'].color_ramp.elements
            if len(elements) == 1: 
                bpy.data.materials['my_mat'].node_tree.nodes['Color Ramp'].color_ramp.elements[0].position=0
                break
            bpy.data.materials['my_mat'].node_tree.nodes['Color Ramp'].color_ramp.elements.remove(elements[-1])

        K,R,G,B = getkeys(context.scene.bleMD_props.colormap)
        bpy.data.materials['my_mat'].node_tree.nodes['Color Ramp'].color_ramp.elements[0].color = (R[0],G[0],B[0],1)

        for k,r,g,b in zip(K,R,G,B):
            elem = bpy.data.materials['my_mat'].node_tree.nodes['Color Ramp'].color_ramp.elements.new(position=k)
            elem.color=(r,g,b,1)
        
    colormap: bpy.props.EnumProperty(
        name="Colormap",
        description="Select a colormap",
        items=colormap_items,
        update=colormap_update
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

 
    def updateRadius(self, context):
        scene = context.scene
        mytool = scene.bleMD_props
        radius = mytool.my_radius
        obj = bpy.data.objects["MD_Object"]
        if not obj: return
        geonodes = obj.modifiers["build_geonode"]
        if not geonodes: return
        nodegroup = geonodes.node_group
        m2p = nodegroup.nodes["Mesh to Points"]
        m2p.inputs['Radius'].default_value = radius
    my_radius: FloatProperty(
        name="Atom Radius",
        description="Radius",
        default=1,
        min=0,
        update=updateRadius,
    )


    def colorby_property_items(self,context):
        ret = []
        for item in context.scene.datafieldlist:
            if item.enable: ret.append((item.name,item.name,item.name))
        return ret
    def colorby_property_update(self,context):
        prop = context.scene.bleMD_props.colorby_property
        print(prop)
        bpy.data.materials["my_mat"].node_tree.nodes['Attribute'].attribute_name = prop
    colorby_property: EnumProperty(
        items=colorby_property_items,
        update=colorby_property_update,
        name="Color by:",
        default=None,
        description="Property to use for color shading",
    )
