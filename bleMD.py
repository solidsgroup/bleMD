bl_info = {
    "name": "Add-on Template",
    "description": "",
    "author": "p2or",
    "version": (0, 0, 3),
    "blender": (2, 80, 0),
    "location": "3D View > Tools",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Development"
}

#### #  --- this works, do not change it !! ---
#### import bpy
#### import pip
#### import sys
#### print(sys.executable)
#### sys.path.append('/home/brunnels/.local/lib/python3.10/site-packages/') ## Portability issue - need to overcome this
#### import ovito
#### from ovito.io import import_file
#### pipeline = import_file("/home/brunnels/Desktop/MDVisualization/dump.Cu_s21_inc33.004490_dE_0_v0.01_T900_freeends")
#### for frame in range(pipeline.source.num_frames):
####     data = pipeline.compute(frame)
####     coords = [list(xyz) for xyz in data.particles.positions]
####     print("frame = {} of {}".format(frame,pipeline.source.num_frames))
####     me = bpy.data.meshes.new("MD_Mesh")
####     ob = bpy.data.objects.new("MD_Object", me)
####     ob.show_name = True
####     bpy.context.collection.objects.link(ob)
####     me.from_pydata(coords,[],[])
####     me.update()

import bpy

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )


import ovito

# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class MyProperties(PropertyGroup):

    valid_lammps_file: BoolProperty(default = False)
    number_of_lammps_frames: IntProperty(default = 1)

    my_bool: BoolProperty(
        name="Create a new object",
        description="A bool property",
        default = True
        )

    update_on_frame_change: BoolProperty(
        name="Update when frame changes",
        description="Do a refresh of positions when frame changes (warning - can cause slowdown)",
        default = False
        )

    my_int: IntProperty(
        name = "Int Value",
        description="A integer property",
        default = 23,
        min = 10,
        max = 100
        )


    def updateFrameStride(self,context):
        scene=context.scene
        mytool=scene.my_tool
        nframes = mytool.number_of_lammps_frames
        stride = mytool.my_lammps_frame_stride
        bpy.context.scene.frame_end = nframes * stride
        
    my_lammps_frame_stride: IntProperty(
        name = "Frame interpolation stride",
        description="How many frames to interpolate",
        default = 1,
        min = 1,
        max = 100,
        update = updateFrameStride,
        )

    my_lammps_frame_min: IntProperty(
        name = "Start",
        description="A integer property",
        default = 0,
        min = 0,
        max = 100
        )
    my_lammps_frame_max: IntProperty(
        name = "End",
        description="A integer property",
        default = 0,
        min = 0,
        max = 100
        )

    def openLAMMPSFile(self,context):
        scene=context.scene
        mytool=scene.my_tool

        import sys
        sys.path.append(mytool.my_ovitodir)
        import ovito
        from ovito.io import import_file
        pipeline = import_file(mytool.my_lammpsfile, sort_particles=True)
        nframes = pipeline.source.num_frames
        mytool.number_of_lammps_frames = nframes

        bpy.context.scene.frame_end = nframes * mytool.my_lammps_frame_stride

        mytool.valid_lammps_file = True

    my_lammpsfile: StringProperty(
        name = "LAMMPS Dump File",
        description="Choose a file:",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
        update=openLAMMPSFile,
        )

    my_ovitodir: StringProperty(
        name = "OVITO Directory",
        description="Choose a file:",
        default="/home/brunnels/.local/lib/python3.10/site-packages/",
        maxlen=1024,
        subtype='DIR_PATH'
        )

    my_renderpath: StringProperty(
        name = "Render output directory",
        description="Choose a file:",
        default="/tmp/",
        maxlen=1024,
        subtype='DIR_PATH'
        )
        

def loadUpdatedData():

    filename = bpy.context.scene.my_tool.my_lammpsfile
    interp = bpy.context.scene.my_tool.my_lammps_frame_stride
    frame = bpy.data.scenes[0].frame_current

    from ovito.io import import_file
    from ovito.modifiers import UnwrapTrajectoriesModifier
    from ovito.modifiers import WrapPeriodicImagesModifier

    pipeline = import_file(filename, sort_particles=True)
    pipeline.modifiers.append(WrapPeriodicImagesModifier())
    pipeline.modifiers.append(UnwrapTrajectoriesModifier())

    nframes = pipeline.source.num_frames
    bpy.context.scene.my_tool.number_of_lammps_frames = nframes
    
    fac = frame % interp
    frame_lo = int(frame / interp)
    if not "MD_Object" in bpy.data.objects.keys():
        me = bpy.data.meshes.new("MD_Mesh")
        ob = bpy.data.objects.new("MD_Object", me)
        ob.show_name = True
        bpy.context.collection.objects.link(ob)
    else:
        ob = bpy.data.objects['MD_Object']
        me = ob.data

    

    if fac == 0:
        data = pipeline.compute(frame_lo)
        coords = [list(xyz) for xyz in data.particles.positions]
        #print("frame = {} of {}".format(frame,pipeline.source.num_frames))
    else:
        frame_hi = frame_lo + 1
        data_lo = pipeline.compute(frame_lo)
        data_hi = pipeline.compute(frame_hi)
        coords = [list((1-fac)*xyz_lo + fac*xyz_hi) for xyz_lo, xyz_hi in
                  zip(data_lo.particles.positions,data_hi.particles.positions)]
    if not len(me.vertices):
        me.from_pydata(coords,[],[])
    else:
        for i,v in enumerate(me.vertices):
            new_location = v.co            
            new_location[0] = coords[i][0]
            new_location[1] = coords[i][1]
            new_location[2] = coords[i][2]
            v.co = new_location
    me.update()
    


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class WM_OT_HelloWorld(Operator):
    bl_idname = "wm.hello_world"
    bl_label = "Read LAMMPS File"

    my_tmp_cntr = 0

    def execute(self, context):
        #scene = context.scene
        #mytool = scene.my_tool
        loadUpdatedData()
        

        return {'FINISHED'}


class WM_OT_RenderAnimation(Operator):
    bl_idname = "wm.render_animation"
    bl_label = "Render animation"
    def execute(self, context):
        scene = bpy.context.scene
        for frame in range(scene.frame_start, scene.frame_end + 1):
            print("Rendering ",frame)
            scene.render.filepath = scene.my_tool.my_renderpath + str(frame).zfill(4)
            scene.frame_set(frame)
            loadUpdatedData()
            bpy.ops.render.render(write_still=True)

        return {'FINISHED'}

# ------------------------------------------------------------------------
#    Panel in Object Mode
# ------------------------------------------------------------------------

class OBJECT_PT_bleMDPanel(Panel):
    bl_label = "OVITO Molecular Dynamics"
    bl_idname = "OBJECT_PT_bleMDPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"


    @classmethod
    def poll(self,context):
        return context.object is not None
    
    def execute(self, context):
        print("I'm here")
        #scene = context.scene
        #mytool = scene.my_tool
        #from ovito.io import import_file
        #pipeline = import_file(mytool.my_lammpsfile)
        #data = pipeline.compute(0)
        #coords = [list(xyz) for xyz in data.particles.positions]
        #me = bpy.data.meshes.new("MD_Mesh")
        #ob = bpy.data.objects.new("MD_Object", me)
        #ob.show_name = True
        #bpy.context.collection.objects.link(ob)
        #me.from_pydata(coords,[],[])
        #me.update()
        return {'FINISHED'}


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.my_tool

        layout.prop(mytool, "my_bool")
        layout.prop(mytool, "update_on_frame_change")

        layout.prop(mytool, "my_lammpsfile")
        layout.prop(mytool, "my_ovitodir")

        layout.prop(mytool, "my_lammps_frame_stride")
        #layout.prop(mytool, "my_enum", text="") 
        
        #if mytool.valid_lammps_file:
        #    layout.label(text="Frame selection")
        #    row = layout.row()
        #    row.prop(mytool, "my_lammps_frame_min")
        #    row.prop(mytool, "my_lammps_frame_max")

        layout.operator("wm.hello_world")

        layout.row().separator()
        layout.prop(mytool, "my_renderpath")
        layout.operator("wm.render_animation")


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    MyProperties,
    WM_OT_HelloWorld,
    WM_OT_RenderAnimation,
    OBJECT_PT_bleMDPanel,
#    OBJECT_MT_CustomMenu,
#    MessageBox,
#    BasicMenu,
)

def frame_handler(scene, depsgraph):
    if bpy.context.scene.my_tool.update_on_frame_change:
        loadUpdatedData()

    print(bpy.data.scenes[0].frame_current)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.app.handlers.frame_change_post.clear()
    bpy.app.handlers.frame_change_post.append(frame_handler)

    bpy.types.Scene.my_tool = PointerProperty(type=MyProperties)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.my_tool




if __name__ == "__main__":
    import bpy
    register()

    #bpy.ops.wm.call_menu(name="OBJECT_MT_select_test")

    #bpy.ops.message.messagebox('INVOKE_DEFAULT')
