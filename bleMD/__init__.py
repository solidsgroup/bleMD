bl_info = {
    "name": "bleMD",
    "description": "Visualize MD data with Ovito plugins",
    "author": "brunnels",
    "version": (0, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Tools",
    "warning": "",  # used for warning icon and text in addons panel
    "category": "Generic"
}

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


from . bleMDProperties    import *
from . bleMDDataFieldList import *
from . bleMDUtils         import *


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class WM_OT_bleMDOpenOvitoScript(Operator):
    """This is the docstring"""
    bl_idname = "wm.open_ovito_script"
    bl_label = "Create a new Ovito process script"

    def execute(self, context):
        newtext = bpy.data.texts.new("Ovito_ProcessScript")
        newtext.write(
"""
#
# You can set up OVITO commands to run here.
#
# You are given a "pipeline" object that has already been loaded.
# All you need to do is set up the modifiers that you want to use.
# The following are some examples...
#
# from ovito.modifiers import UnwrapTrajectoriesModifier
# pipeline.modifiers.append(WrapPeriodicImagesModifier())
#
# from ovito.modifiers import WrapPeriodicImagesModifier
# pipeline.modifiers.append(UnwrapTrajectoriesModifier())
#
# from ovito.modifiers import CentroSymmetryModifier
# pipeline.modifiers.append(CentroSymmetryModifier())
#
""")
        context.object.bleMD_props.process_script = newtext.name

        return {'FINISHED'}

class WM_OT_bleMDNewOvitoOpenScript(Operator):
    """This is the docstring"""
    bl_idname = "wm.new_ovito_open_script"
    bl_label = "Create an Ovito script for I/O"

    def execute(self, context):
        obj = context.object
        newtext = bpy.data.texts.new("Ovito_OpenScript")
        newtext.write(
"""
#
# This is a basic IO routine using your original filename.
# You can use this to add options or special features to the
# import_file routine.
#
# This script MUST create a valid pipeline called "pipeline".
#

from ovito.io import import_file
pipeline = import_file("{}",sort_particles=True)
""".format(context.object.bleMD_props.lammpsfile))
        
        context.object.bleMD_props.io_open_script = newtext.name

        return {'FINISHED'}
    

class WM_OT_bleMDCreateMaterial(Operator):
    """Create bleMD Shader"""
    bl_idname = "wm.create_material"
    bl_label = "Create a new material"

    def execute(self, context):
        mat = create_material()
        context.object.bleMD_props.mat_selection = mat.name
        return {'FINISHED'}

class WM_OT_bleMDDefaultSettings(Operator):
    """Set some world properties"""
    bl_idname = "wm.default_settings"
    bl_label = "Configure blender for MD"

    def execute(self, context):
        resetDefaultsForMD()
        return {'FINISHED'}

class WM_OT_bleMDReadLAMMPSFile(Operator):
    """This is the docstring"""
    bl_idname = "wm.read_lammps_file"
    bl_label = "Load File"

    my_tmp_cntr = 0

    def execute(self, context):
        ob, pipeline = startOvito()
        loadUpdatedData(ob, pipeline)
        ob.bleMD_props.needs_refresh = False
        return {'FINISHED'}


class WM_OT_bleMDRigKeyframes(Operator):
    bl_idname = "wm.rig_keyframes"
    bl_label = "Rig Keyframes"

    def execute(self, context):
        scene = bpy.context.scene
        obj = bpy.context.object
        nlammpsframes = obj.bleMD_props.number_of_lammps_frames
        stride = obj.bleMD_props.lammps_frame_stride

        keyInterp = context.preferences.edit.keyframe_new_interpolation_type
        context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'

        ob = bpy.data.objects['MD_Object']

        if ob.data.shape_keys:
            for key in ob.data.shape_keys.key_blocks:
                ob.shape_key_remove(key)

        ob, pipeline = startOvito()
        for i in range(nlammpsframes):
            loadUpdatedData(ob, pipeline)
            print(i)
            scene.frame_set(i*stride)

            ob.data.shape_keys

            ob.shape_key_add(name="Key"+str(i).zfill(4), from_mix=False)

            if i > 0:
                for j in range(nlammpsframes):
                    if j == i:
                        bpy.data.shape_keys["Key"].key_blocks["Key" +
                                                              str(i).zfill(4)].value = 1
                    else:
                        bpy.data.shape_keys["Key"].key_blocks["Key" +
                                                              str(i).zfill(4)].value = 0
                    keyframe = bpy.data.shape_keys["Key"].key_blocks["Key"+str(
                        i).zfill(4)].keyframe_insert("value", frame=j*stride)

        context.preferences.edit.keyframe_new_interpolation_type = keyInterp

        return {'FINISHED'}


class WM_OT_bleMDRenderAnimation(Operator):
    bl_idname = "wm.render_animation"
    bl_label = "Render animation"

    def execute(self, context):
        scene = bpy.context.scene
        obj = bpy.context.object

        # Remove shape keyframes if there are any
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                obj.shape_key_remove(key)

        ob, pipeline = startOvito()
        for frame in range(scene.frame_start, scene.frame_end + 1):
            print("Rendering ", frame)
            scene.render.filepath = obj.bleMD_props.renderpath + \
                str(frame).zfill(4)
            scene.frame_set(frame)
            loadUpdatedData(ob, pipeline)
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
    def poll(self, context):
        if not len(bpy.context.selected_objects): return False
        if not context.object: return False
        ob = bpy.context.object
        if 'bleMD_object' not in ob.data.keys(): return False
        return True
        #return context.object is not None

    def execute(self, context):
        return {'FINISHED'}

    def draw_header(self, context):
        self.layout.label(text="", icon_value=custom_icons["ovito"].icon_id)
        
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        mytool = obj.bleMD_props

        layout.operator("wm.default_settings")

        #
        # FILE IO
        #
        layout.label(text="Load Data File",icon='FILE_FOLDER')
        layout.prop(mytool,"io_method",expand=True)
        if mytool.io_method == {"openfile"}:
            layout.prop(mytool, "lammpsfile")
        elif mytool.io_method == {"script"}:
            layout.operator("wm.new_ovito_open_script")
            layout.prop_search(mytool,"io_open_script",bpy.data,"texts")

        #
        # OVITO OPERATIONS
        #
        layout.label(text="OVITO Operations",icon='GROUP_VERTEX')
        layout.prop(mytool,"process_script_enable")
        if mytool.process_script_enable:
            layout.operator("wm.open_ovito_script")
            layout.prop_search(mytool,"process_script",bpy.data,"texts")



        #
        # DATA FIELDS
        #


        if len(obj.datafieldlist):
            layout.label(text="Data fields from file")
            row = layout.row()
            row.template_list("bleMDDataFieldsList", "The_List", obj,
                              "datafieldlist", obj, "list_index")

        
        row = layout.row()
        row.alert = mytool.needs_refresh
        row.operator("wm.read_lammps_file")

        
        if not len(obj.data.vertices):
            return

        layout.label(text="Load",icon='GROUP_VERTEX')
        layout.prop(mytool,"my_radius")

        layout.label(text="Shading",icon='SHADING_RENDERED')

        layout.operator("wm.create_material")
        layout.prop_search(mytool,
                           "mat_selection",
                           bpy.data,
                           "materials")
        
        if mytool.mat_selection in bpy.data.materials.keys():
            if bpy.data.materials[mytool.mat_selection].bleMD:
                mattool = bpy.data.materials[mytool.mat_selection].bleMD_props
                layout.prop(mattool, "colorby_property")
                layout.prop(mattool, "colormap")
                row = layout.row()
                split = row.split()
                split.prop(mattool, "my_normallow")
                split.prop(mattool, "my_normalhigh")

        layout.label(text="Animation",icon='FORCE_VORTEX')

        layout.prop(mytool, "lammps_frame_stride")
        layout.operator("wm.rig_keyframes")

        layout.label(text="Render",icon='CAMERA_DATA')

        layout.prop(mytool, "renderpath")
        layout.operator("wm.render_animation")


class bleMDOpenFileDialogOperator(bpy.types.Operator):
    bl_idname = "object.blemd_open_file_dialog"
    bl_label = "Open MD file"

    filepath: StringProperty(subtype='FILE_PATH')

    @classmethod
    def poll(self, context):
        if not len(bpy.context.selected_objects):
            return True
        ob = bpy.context.object
        if ob:
            if 'bleMD_object' in ob.data.keys():
                return False
        return True


    def execute(self, context):
        #print("MY DATAFILE=",self.filepath)
        ob, pipeline = startOvito(hardrefresh=True,filename=self.filepath)
        #loadUpdatedData(ob, pipeline)
        #bpy.context.object.bleMD_props.lammpsfile = self.filepath
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# Only needed if you want to add into a dynamic menu.
def bleMDOpenFileDialogOperator_menu(self, context):
    self.layout.operator_context = 'INVOKE_DEFAULT'
    self.layout.operator(bleMDOpenFileDialogOperator.bl_idname, text="Open MD file")


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------
classes = (
    bleMDProperties,
    bleMD_material,
    WM_OT_bleMDDefaultSettings,
    WM_OT_bleMDOpenOvitoScript,
    WM_OT_bleMDNewOvitoOpenScript,
    WM_OT_bleMDCreateMaterial,
    WM_OT_bleMDReadLAMMPSFile,
    WM_OT_bleMDRenderAnimation,
    WM_OT_bleMDRigKeyframes,
    bleMDDataFieldsLIProperty,
    bleMDDataFieldsList,
    OBJECT_PT_bleMDPanel,
    bleMDOpenFileDialogOperator,
)



def installOvito():
    import sys
    import subprocess
    exe = sys.executable
    subprocess.check_call([exe,'-m','pip','install','ovito'])

    #import pip
    #pip.main(['install', 'ovito'])
    import ovito
 
print('FINISHED')

def register():
    import bpy
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.app.handlers.frame_change_post.clear()

    bpy.types.Object.bleMD_props = PointerProperty(type=bleMDProperties)

    bpy.types.Object.datafieldlist = CollectionProperty(type=bleMDDataFieldsLIProperty)
    bpy.types.Object.list_index = IntProperty(
        name="Index for datafieldlist", default=0)


    installOvito()

    import bpy.utils.previews
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    import os
    ## this will work for addons 
    icons_dir = os.path.join(os.path.dirname(__file__), "resources")
    custom_icons.load("ovito", os.path.join(icons_dir, "ovito.png"), 'IMAGE')

    # Add "Open MD File" to the "add" menu
    bpy.types.VIEW3D_MT_add.append(bleMDOpenFileDialogOperator_menu)

    #
    # Add custom material types
    #
    bpy.types.Material.bleMD = bpy.props.BoolProperty(name="bleMD enabled")
    bpy.types.Material.bleMD_props = PointerProperty(type=bleMD_material)
    
def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Object.bleMD_props
    bpy.utils.previews.remove(custom_icons)
    bpy.types.VIEW3D_MT_view.remove(bleMDOpenFileDialogOperator_menu)


if __name__ == "__main__":
    import bpy
    register()

    # bpy.ops.wm.call_menu(name="OBJECT_MT_select_test")

    # bpy.ops.message.messagebox('INVOKE_DEFAULT')
