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


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class MyProperties(PropertyGroup):

    pipeline = None

    valid_lammps_file: BoolProperty(default = False)

    my_bool: BoolProperty(
        name="Create a new object",
        description="A bool property",
        default = True
        )

    my_int: IntProperty(
        name = "Int Value",
        description="A integer property",
        default = 23,
        min = 10,
        max = 100
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


#    my_float: FloatProperty(
#        name = "Float Value",
#        description = "A float property",
#        default = 23.7,
#        min = 0.01,
#        max = 30.0
#        )

#    my_float_vector: FloatVectorProperty(
#        name = "Float Vector Value",
#        description="Something",
#        default=(0.0, 0.0, 0.0), 
#        min= 0.0, # float
#        max = 0.1
#    ) 

#    my_string: StringProperty(
#        name="User Input",
#        description=":",
#        default="",
#        maxlen=1024,
#        )

#    my_path: StringProperty(
#        name = "Directory",
#        description="Choose a directory:",
#        default="",
#        maxlen=1024,
#        subtype='DIR_PATH'
#        )

    def openLAMMPSFile(self,context):
        scene=context.scene
        mytool=scene.my_tool

        import sys
        sys.path.append(mytool.my_ovitodir)
        import ovito
        from ovito.io import import_file
        pipeline = import_file(mytool.my_lammpsfile)
        self.my_lammps_frame_max = pipeline.source.num_frames

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
        
#    my_enum: EnumProperty(
#        name="Dropdown:",
#        description="Apply Data to attribute.",
#        items=[ ('OP1', "Option 1", ""),
#                ('OP2', "Option 2", ""),
#                ('OP3', "Option 3", ""),
#               ]
#        )

# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class WM_OT_HelloWorld(Operator):
    bl_idname = "wm.hello_world"
    bl_label = "Read LAMMPS File"

    def execute(self, context):
        scene = context.scene
        mytool = scene.my_tool

        from ovito.io import import_file
        pipeline = import_file(mytool.my_lammpsfile)

        #for frame in [0]:# range(pipeline.source.num_frames):

        data = pipeline.compute(0)
        coords = [list(xyz) for xyz in data.particles.positions]
        #print("frame = {} of {}".format(frame,pipeline.source.num_frames))
        me = bpy.data.meshes.new("MD_Mesh")
        ob = bpy.data.objects.new("MD_Object", me)
        ob.show_name = True
        bpy.context.collection.objects.link(ob)
        me.from_pydata(coords,[],[])
        me.update()

        
        #if not len(ob.modifiers):
        #modifier = ob.modifiers.new("Atoms",type="NODES")
        #modifier.node.new_geometry

        return {'FINISHED'}


#class MessageBox(bpy.types.Operator):
#    bl_idname = "message.messagebox"
#    bl_label = "Open LAMMPS dump file"
# 
#    message = bpy.props.StringProperty(
#        name = "message",
#        description = "message",
#        default = ''
#    )
# 
#    def execute(self, context):
#        #self.report({'INFO'}, self.message)
#        print("OK GETTING REA")
#        print(self.message)
#        return {'FINISHED'}
# 
#    def invoke(self, context, event):
#        #return context.window_manager.invoke_props_dialog(self, width = 400)
#        return context.window_manager.invoke_props_popup(self, width = 400)
# 
#    def draw(self, context):
#        scene = context.scene
#        mytool = scene.my_tool
#        self.layout.prop(mytool, "my_bool")
#        self.layout.prop(mytool, "my_lammpsfile")
#        self.layout.prop(mytool, "my_ovitodir")


        
# Creates a menu for global 3D View
#class customMenu(bpy.types.Menu):
#    bl_label = "Custom Menu"
#    bl_idname = "view3D.custom_menu"
#
#    # Set the menu operators and draw functions
#    def draw(self, context):
#        layout = self.layout
#
#        layout.operator("mesh.primitive_cube_add")
#        layout.operator("object.duplicate_move")           

# ------------------------------------------------------------------------
#    Menus
# ------------------------------------------------------------------------
#class BasicMenu(bpy.types.Menu):
#    bl_idname = "OBJECT_MT_select_test"
#    bl_label = "My Select"
#
#    def draw(self, context):
#        layout = self.layout
#
#        layout.operator("object.select_all", text="Select/Deselect All").action = 'TOGGLE'
#        layout.operator("object.select_all", text="Inverse").action = 'INVERT'
#        layout.operator("object.select_random", text="Random")




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

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.my_tool

        layout.prop(mytool, "my_bool")
        layout.prop(mytool, "my_lammpsfile")
        layout.prop(mytool, "my_ovitodir")

        #layout.prop(mytool, "my_enum", text="") 
        
        if mytool.valid_lammps_file:
            layout.label(text="Frame selection")
            row = layout.row()
            row.prop(mytool, "my_lammps_frame_min")
            row.prop(mytool, "my_lammps_frame_max")
        #layout.prop(mytool, "my_float")
        #layout.prop(mytool, "my_float_vector", text="")
        #layout.prop(mytool, "my_string")
        #layout.prop(mytool, "my_path")
        layout.operator("wm.hello_world")
        #layout.menu(OBJECT_MT_CustomMenu.bl_idname, text="Presets", icon="SCENE")
        #layout.separator()

# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    MyProperties,
    WM_OT_HelloWorld,
    OBJECT_PT_bleMDPanel,
#    OBJECT_MT_CustomMenu,
#    MessageBox,
#    BasicMenu,
)

def frame_handler(scene, depsgraph):
    print(bpy.data.scenes[0].frame_current)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

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
