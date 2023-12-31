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
    bl_label = "Open an Ovito script"

    def execute(self, context):
        if "Ovito" not in bpy.data.texts.keys():
            bpy.data.texts.new("Ovito")
            bpy.data.texts['Ovito'].write(
"""
#
# You can set up OVITO commands to run here.
#
# You are given a "pipeline" object that has already been loaded.
# All you need to do is set up the modifiers that you want to use.
# For instance, you can use the following lines to unwrap trajectories:
#
#         from ovito.modifiers import UnwrapTrajectoriesModifier
#         from ovito.modifiers import WrapPeriodicImagesModifier
#         pipeline.modifiers.append(WrapPeriodicImagesModifier())
#         pipeline.modifiers.append(UnwrapTrajectoriesModifier())
#
""")


        bpy.context.window.workspace = bpy.data.workspaces['Scripting']
        for area in context.screen.areas:
            if area.type == "TEXT_EDITOR":
                for space in area.spaces:
                    if type(space) == bpy.types.SpaceTextEditor:
                        space.text = bpy.data.texts['Ovito']

        return {'FINISHED'}


class WM_OT_bleMDReadLAMMPSFile(Operator):
    """This is the docstring"""
    bl_idname = "wm.read_lammps_file"
    bl_label = "Load File"

    my_tmp_cntr = 0

    def execute(self, context):
        ob, pipeline = startOvito()
        loadUpdatedData(ob, pipeline)

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
        obj = bpy.context.obj

        # Remove shape keyframes if there are any
        ob = bpy.data.objects['MD_Object']
        if ob.data.shape_keys:
            for key in ob.data.shape_keys.key_blocks:
                ob.shape_key_remove(key)

        ob, pipeline = startOvito()
        for frame in range(scene.frame_start, scene.frame_end + 1):
            print("Rendering ", frame)
            scene.render.filepath = obj.bleMD_props.renderpath + \
                str(frame).zfill(4)
            scene.frame_set(frame)
            loadUpdatedData(ob, pipeline)
            bpy.ops.render.render(write_still=True)

        return {'FINISHED'}


class WM_OT_bleMDBasicShade(Operator):
    bl_idname = "wm.basic_shade"
    bl_label = "Shade"

    def execute(self, context):
        updateDefaultShader()

        return {'FINISHED'}
    
class WM_OT_Enumerator(Operator):
    bl_idname = "wm.enumerator"
    bl_label = "Select Colormap"
    
    def execute(self, context):
        scene = context.scene
        obj = context.object
        mytool = obj.bleMD_props

        mat = bpy.data.materials.get("my_mat")
        mat_nodes = mat.node_tree.nodes
        color_ramp = mat_nodes.get('ShaderNodeValToRGB')
        
        #Not currently functional
        #TODO: set up color map to color ramp
        if mytool.my_enum == 'OP1':
            for x in range(128):
                try:
                    print('TRY')
                    color_ramp.color_ramp.elements.remove(color_ramp.color_ramp.elements[1])
                except:
                    print('EXCEPT')
                    break
            print('DONE')
        #if mytool.my_enum == 'OP2':
        #if mytool.my_enum == 'OP3':
        #if mytool.my_enum == 'OP4':
        #if mytool.my_enum == 'OP5':

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

        layout.prop(mytool, "override_defaults")

        #
        # FILE IO
        #
        layout.label(text="Load Data File",icon='FILE_FOLDER')
        layout.prop(mytool, "lammpsfile")

        #
        # OVITO OPERATIONS
        #
        layout.label(text="OVITO Operations",icon='GROUP_VERTEX')
        layout.operator("wm.open_ovito_script")
        #layout.prop(mytool, "ovito_wrap_periodic_images")
        #layout.prop(mytool, "ovito_unwrap_trajectories")

        layout.prop(mytool,"my_radius")

        #
        # DATA FIELDS
        #
        if len(obj.datafieldlist):
            layout.label(text="Data fields from file")
            row = layout.row()
            row.template_list("bleMDDataFieldsList", "The_List", obj,
                              "datafieldlist", obj, "list_index")
        layout.operator("wm.read_lammps_file")

        layout.label(text="Basic Shader",)
        layout.prop(mytool, "colorby_property")
        layout.prop(mytool, "my_normallow")
        layout.prop(mytool, "my_normalhigh")
        
        layout.operator("wm.basic_shade")

        layout.prop(mytool, "colormap")
        row = layout.row()
        row.operator("wm.enumerator")

        layout.label(text="Animation")

        layout.prop(mytool, "lammps_frame_stride")
        layout.operator("wm.rig_keyframes")

        layout.label(text="Render")

        layout.prop(mytool, "renderpath")
        layout.operator("wm.render_animation")


class bleMDOpenFileDialogOperator(bpy.types.Operator):
    bl_idname = "object.blemd_open_file_dialog"
    bl_label = "Open MD file"

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        #resetDefaultsForMD()
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
    self.layout.operator(bleMDOpenFileDialogOperator.bl_idname, text="Dialog Operator")


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------
classes = (
    bleMDProperties,
    WM_OT_bleMDOpenOvitoScript,
    WM_OT_bleMDReadLAMMPSFile,
    WM_OT_bleMDRenderAnimation,
    WM_OT_bleMDRigKeyframes,
    WM_OT_bleMDBasicShade,
    WM_OT_Enumerator,
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

    bpy.types.VIEW3D_MT_add.append(bleMDOpenFileDialogOperator_menu)


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
