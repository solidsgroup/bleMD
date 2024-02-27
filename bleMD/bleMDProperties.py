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
#    Object Properties
# ------------------------------------------------------------------------

class bleMDProperties(bpy.types.PropertyGroup):

    valid_lammps_file: BoolProperty(default=False)
    number_of_lammps_frames: IntProperty(default=1)
    needs_refresh: BoolProperty(default=True)


    #
    # Re-enable the update button
    #
    def set_needs_refresh(self,context):
        context.object.bleMD_props.needs_refresh=True

    #
    # IO MANAGEMENT PROPERTIES
    #

    io_method_enum = [('openfile','Open File','open a file'),('script','Script','use a script')]
    io_method : bpy.props.EnumProperty(
        name="I/O Method",
        description="Select a file I/O method",
        items=io_method_enum,
        options = {"ENUM_FLAG"},
        default=set(['openfile']),
        update=set_needs_refresh
    )
    def io_script_update(self,context):
        context.object.bleMD_props.needs_refresh=True
    io_open_script : StringProperty(
        name="IO Script",
        default="None",
        update=set_needs_refresh
    )


    #
    # SCRIPTING PROPERTIES
    #
    process_script_enable: BoolProperty(
        name="Use a custom OVITO script",
        description="Use a custom OVITO script to process pipeline",
        default=False,
        update=set_needs_refresh
    )
    process_script : StringProperty(
        name="Process Script",
        default="None",
        update=set_needs_refresh
    )


    #
    # SHADING PROPERTIES
    #

    def mat_set(self,context):
        obj = context.object
        mytool = obj.bleMD_props
        #radius = mytool.my_radius
        #obj = context.object
        #if not "bleMD_object" in obj.data.keys():
        #    return
        #obj = bpy.data.objects["MD_Object"]
        #if not obj: return
        mat = mytool.mat_selection
        geonodes = obj.modifiers["build_geonode"]
        if not geonodes:
            print("object does not have build_geonode set")
            print(obj.modifiers.keys())
            return
        nodegroup = geonodes.node_group
        node = nodegroup.nodes["Set Material"]
        node.inputs['Material'].default_value = bpy.data.materials[mat]
        
    mat_selection : StringProperty(
        name="Material",
        default="None",
        update=mat_set,
    )
                                      

    def updateFrameStride(self, context):
        scene = context.scene
        obj = context.object
        mytool = obj.bleMD_props
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


    lammpsfile: StringProperty(
        name="LAMMPS Dump File",
        description="Choose a file:",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
        #update=openLAMMPSFile,
    )

    renderpath: StringProperty(
        name="Render output directory",
        description="Choose a file:",
        default="/tmp/",
        maxlen=1024,
        subtype='DIR_PATH'
    )



    def updateRadius(self, context):
        scene = context.scene
        obj = context.object
        mytool = obj.bleMD_props
        radius = mytool.my_radius
        obj = context.object
        if not "bleMD_object" in obj.data.keys():
            return
        #obj = bpy.data.objects["MD_Object"]
        #if not obj: return
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

    def updateSlice(self, context):
        """
        Update the slice using the given context and object properties.
        """
        scene = context.scene
        obj = context.object
        mytool = obj.bleMD_props
        thickness = mytool.my_plane_thickness
        planeVector = mytool.my_plane_vector
        planeVectorABC = planeVector[:3]
        planeVectorD = planeVector[3]
        obj = context.object
        if not "bleMD_object" in obj.data.keys(): return
        geonodes = obj.modifiers["build_geonode"]
        if not geonodes: return
        nodegroup = geonodes.node_group
        pvABC = nodegroup.nodes["Plane Vector"]
        pvABC.vector = planeVectorABC
        pvD = nodegroup.nodes["Plane Distance"]
        pvD.outputs["Value"].default_value = planeVectorD
        GT = nodegroup.nodes["Plane Thickness"]
        GT.inputs[1].default_value = thickness
    my_plane_vector: FloatVectorProperty(
        name="Plane Equation for Slice",
        description="Describe the plane in the form Ax + By + Cz + D = 0.  Set to [0 0 0 0] to disable slicing.",
        default=(0.0, 0.0, 0.0, 0.0),
        size=4,
        update=updateSlice,
    )
    my_plane_thickness: FloatProperty(
        name="Plane Thickness",
        description="Define the thickness of the slice.",
        default=0,
        update=updateSlice,
    )


#
# MATERIAL PROPERTIES
#

class bleMD_material(bpy.types.PropertyGroup):
    def colorby_property_items(self,context):
        ret = []
        for item in context.object.datafieldlist:
            if item.enable: ret.append((item.name,item.name,item.name))
        return ret
    def colorby_property_update(self,context):
        obj = context.object
        mat = bpy.data.materials[obj.bleMD_props.mat_selection]
        prop = mat.bleMD_props.colorby_property
        mat.node_tree.nodes['Attribute'].attribute_name = prop
    colorby_property: EnumProperty(
        items=colorby_property_items,
        update=colorby_property_update,
        name="Color by",
        default=None,
        description="Property to use for color shading",
    )
    
    def colormap_items(self,context):
        return [(n,n,n) for n in cm.keys()]
    def colormap_update(self,context):
        obj = context.object
        mat = bpy.data.materials[obj.bleMD_props.mat_selection]
        while True:
            elements = mat.node_tree.nodes['Color Ramp'].color_ramp.elements
            if len(elements) == 1: 
                mat.node_tree.nodes['Color Ramp'].color_ramp.elements[0].position=0
                break
            mat.node_tree.nodes['Color Ramp'].color_ramp.elements.remove(elements[-1])

        K,R,G,B = getkeys(mat.bleMD_props.colormap)
        mat.node_tree.nodes['Color Ramp'].color_ramp.elements[0].color = (R[0],G[0],B[0],1)

        for k,r,g,b in zip(K,R,G,B):
            elem = mat.node_tree.nodes['Color Ramp'].color_ramp.elements.new(position=k)
            elem.color=(r,g,b,1)
    colormap: bpy.props.EnumProperty(
        name="Colormap",
        description="Select a colormap",
        items=colormap_items,
        update=colormap_update
    )

    def my_normalhigh_normallow_update(self,context):
        obj = context.object
        mat = bpy.data.materials[obj.bleMD_props.mat_selection]
        
        my_normalhigh = mat.bleMD_props.my_normalhigh
        my_normallow = mat.bleMD_props.my_normallow
        my_range = my_normalhigh - my_normallow
        mat.node_tree.nodes["bleMD_MathNode1"].inputs[1].default_value = my_normallow
        mat.node_tree.nodes["bleMD_MathNode2"].inputs[1].default_value = my_range

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
    
