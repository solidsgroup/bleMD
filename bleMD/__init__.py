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
                       ShaderNodeValToRGB,
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
        pipeline = startOvito()
        loadUpdatedData(pipeline)

        return {'FINISHED'}


class WM_OT_bleMDRigKeyframes(Operator):
    bl_idname = "wm.rig_keyframes"
    bl_label = "Rig Keyframes"

    def execute(self, context):
        scene = bpy.context.scene
        nlammpsframes = scene.bleMD_props.number_of_lammps_frames
        stride = scene.bleMD_props.lammps_frame_stride

        keyInterp = context.preferences.edit.keyframe_new_interpolation_type
        context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'

        ob = bpy.data.objects['MD_Object']

        if ob.data.shape_keys:
            for key in ob.data.shape_keys.key_blocks:
                ob.shape_key_remove(key)

        pipeline = startOvito()
        for i in range(nlammpsframes):
            loadUpdatedData(pipeline)
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

        # Remove shape keyframes if there are any
        ob = bpy.data.objects['MD_Object']
        if ob.data.shape_keys:
            for key in ob.data.shape_keys.key_blocks:
                ob.shape_key_remove(key)

        pipeline = startOvito()
        for frame in range(scene.frame_start, scene.frame_end + 1):
            print("Rendering ", frame)
            scene.render.filepath = scene.bleMD_props.renderpath + \
                str(frame).zfill(4)
            scene.frame_set(frame)
            loadUpdatedData(pipeline)
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

    colormap32 = {
        'viridis':  [(0.267004, 0.004874, 0.329415), (0.277018, 0.050344, 0.375715), (0.282327, 0.094955, 0.417331), (0.282884, 0.13592, 0.453427), (0.278012, 0.180367, 0.486697), (0.269308, 0.218818, 0.509577), (0.257322, 0.25613, 0.526563), (0.243113, 0.292092, 0.538516), (0.225863, 0.330805, 0.547314), (0.210503, 0.363727, 0.552206), (0.19586, 0.395433, 0.555276), (0.182256, 0.426184, 0.55712), (0.168126, 0.459988, 0.558082), (0.15627, 0.489624, 0.557936), (0.144759, 0.519093, 0.556572), (0.133743, 0.548535, 0.553541), (0.123463, 0.581687, 0.547445), (0.119423, 0.611141, 0.538982), (0.12478, 0.640461, 0.527068), (0.143303, 0.669459, 0.511215), (0.180653, 0.701402, 0.488189), (0.226397, 0.728888, 0.462789), (0.281477, 0.755203, 0.432552), (0.344074, 0.780029, 0.397381), (0.421908, 0.805774, 0.35191), (0.496615, 0.826376, 0.306377), (0.575563, 0.844566, 0.256415), (0.657642, 0.860219, 0.203082), (0.751884, 0.874951, 0.143228), (0.83527, 0.886029, 0.102646), (0.916242, 0.896091, 0.100717), (0.993248, 0.906157, 0.143936)],
        'plasma':   [(0.050383, 0.029803, 0.527975), (0.132381, 0.022258, 0.56325), (0.193374, 0.018354, 0.59033), (0.248032, 0.014439, 0.612868), (0.30621, 0.008902, 0.633694), (0.356359, 0.003798, 0.64781), (0.405503, 0.000678, 0.656977), (0.453677, 0.002755, 0.66031), (0.506454, 0.016333, 0.656202), (0.551715, 0.043136, 0.645277), (0.595011, 0.07719, 0.627917), (0.636008, 0.112092, 0.605205), (0.67916, 0.151848, 0.575189), (0.714883, 0.187299, 0.546338), (0.748289, 0.222711, 0.516834), (0.779604, 0.258078, 0.487539), (0.812612, 0.297928, 0.455338), (0.840155, 0.33358, 0.427455), (0.866078, 0.36966, 0.400126), (0.89034, 0.406398, 0.37313), (0.915471, 0.448807, 0.34289), (0.93563, 0.487712, 0.315952), (0.953428, 0.52796, 0.288883), (0.968526, 0.5697, 0.261721), (0.981826, 0.618572, 0.231287), (0.989935, 0.663787, 0.204859), (0.994103, 0.710698, 0.180097), (0.993851, 0.759304, 0.159092), (0.987621, 0.815978, 0.144363), (0.976265, 0.868016, 0.143351), (0.959276, 0.921407, 0.151566), (0.940015, 0.975158, 0.131326)],
        'inferno':  [(0.001462, 0.000466, 0.013866), (0.013995, 0.011225, 0.071862), (0.042253, 0.028139, 0.141141), (0.081962, 0.043328, 0.215289), (0.135778, 0.046856, 0.299776), (0.190367, 0.039309, 0.361447), (0.244967, 0.037055, 0.400007), (0.297178, 0.04747, 0.420491), (0.354032, 0.066925, 0.430906), (0.403894, 0.08558, 0.433179), (0.453651, 0.103848, 0.430498), (0.503493, 0.121575, 0.423356), (0.559624, 0.141346, 0.410078), (0.60933, 0.159474, 0.393589), (0.658463, 0.178962, 0.372748), (0.7065, 0.200728, 0.347777), (0.758422, 0.229097, 0.315266), (0.801871, 0.258674, 0.283099), (0.841969, 0.292933, 0.248564), (0.878001, 0.33206, 0.212268), (0.912966, 0.381636, 0.169755), (0.938675, 0.430091, 0.130438), (0.959114, 0.482014, 0.089499), (0.974176, 0.53678, 0.048392), (0.984591, 0.601122, 0.023606), (0.987926, 0.66025, 0.05175), (0.985566, 0.720782, 0.112229), (0.977497, 0.782258, 0.185923), (0.962517, 0.851476, 0.285546), (0.948683, 0.910473, 0.395289), (0.95174, 0.960587, 0.524203), (0.988362, 0.998364, 0.644924)],
        'jet':      [(0.0, 0.0, 0.5), (0.0, 0.0, 0.642602495543672), (0.0, 0.0, 0.785204991087344), (0.0, 0.0, 0.927807486631016), (0.0, 0.0176470588235293, 1.0), (0.0, 0.14313725490196066, 1.0), (0.0, 0.26862745098039204, 1.0), (0.0, 0.3941176470588234, 1.0), (0.0, 0.5352941176470586, 1.0), (0.0, 0.66078431372549, 1.0), (0.0, 0.7862745098039213, 1.0), (0.009487666034155417, 0.9117647058823527, 0.9582542694497156), (0.12333965844402275, 1.0, 0.8444022770398483), (0.2245414294750158, 1.0, 0.7432005060088551), (0.3257432005060088, 1.0, 0.6419987349778622), (0.42694497153700184, 1.0, 0.540796963946869), (0.5407969639468686, 1.0, 0.4269449715370023), (0.641998734977862, 1.0, 0.3257432005060089), (0.7432005060088547, 1.0, 0.2245414294750162), (0.844402277039848, 1.0, 0.12333965844402273), (0.9582542694497153, 0.973856209150327, 0.009487666034155628), (1.0, 0.8576615831517794, 0.0), (1.0, 0.741466957153232, 0.0), (1.0, 0.6252723311546844, 0.0), (1.0, 0.4945533769063183, 0.0), (1.0, 0.3783587509077707, 0.0), (1.0, 0.26216412490922314, 0.0), (1.0, 0.14596949891067557, 0.0), (0.9278074866310163, 0.015250544662309573, 0.0), (0.7852049910873442, 0.0, 0.0), (0.6426024955436721, 0.0, 0.0), (0.5, 0.0, 0.0)],
        'gnuplot2': [(0.0, 0.0, 0.0), (0.0, 0.0, 0.12549019607843137), (0.0, 0.0, 0.25098039215686274), (0.0, 0.0, 0.3764705882352941), (0.0, 0.0, 0.5176470588235293), (0.0, 0.0, 0.6431372549019607), (0.0, 0.0, 0.7686274509803921), (0.0, 0.0, 0.8941176470588235), (0.027573529411764608, 0.0, 1.0), (0.1256127450980391, 0.0, 1.0), (0.2236519607843137, 0.0, 1.0), (0.3216911764705881, 0.0, 1.0), (0.43198529411764697, 0.0, 1.0), (0.5300245098039216, 0.0, 1.0), (0.6280637254901962, 0.061960784313725537, 0.9380392156862746), (0.7261029411764706, 0.12470588235294122, 0.8752941176470589), (0.8363970588235292, 0.19529411764705873, 0.8047058823529414), (0.934436274509804, 0.25803921568627464, 0.7419607843137255), (1.0, 0.3207843137254901, 0.67921568627451), (1.0, 0.383529411764706, 0.6164705882352941), (1.0, 0.4541176470588236, 0.5458823529411765), (1.0, 0.5168627450980393, 0.4831372549019608), (1.0, 0.579607843137255, 0.4203921568627451), (1.0, 0.6423529411764707, 0.35764705882352943), (1.0, 0.7129411764705883, 0.2870588235294118), (1.0, 0.775686274509804, 0.22431372549019613), (1.0, 0.8384313725490197, 0.16156862745098044), (1.0, 0.9011764705882354, 0.09882352941176475), (1.0, 0.971764705882353, 0.028235294117647136), (1.0, 1.0, 0.21568627450980316), (1.0, 1.0, 0.6078431372549016), (1.0, 1.0, 1.0)]
    }

    shader_node = None

    def linspace(self, n):
        if n < 2:
            raise ValueError("Number of points (n) must be at least 2.")

        step = 1 / (n - 1)
        result = [i * step for i in range(n)]

        return result

    def clearNode(self):
        while len(self.shader_node.color_ramp.elements) > 1:
            self.shader_node.color_ramp.elements.remove(self.shader_node.color_ramp.elements[1]) 
        return

    def assignNode(self,rgb_list):
        n = len(rgb_list)
        values = self.linspace(n)
        for x in range (n-1):
            element = rgb_list[x]
            val1 = element[0]; val2 = element[1]; val3 = element[2]
            self.shader_node.color_ramp.elements.new(values[x])
            self.shader_node.color_ramp.elements[x+1].color = (val1,val2,val3,1)
        return


    
    def execute(self, context):
        scene = context.scene
        mytool = scene.bleMD_props

        mat = bpy.data.materials.get("my_mat")

        for node in mat.node_tree.nodes:
            if isinstance(node, ShaderNodeValToRGB) and node.name == 'basicshader':
                self.shader_node = node
                break
        

        #Not currently functional
        #TODO: set up color map to color ramp
        if mytool.my_enum == 'OP1':
            self.clearNode()
            self.assignNode(self.colormap32['viridis'])
        if mytool.my_enum == 'OP2':
            self.clearNode()
            self.assignNode(self.colormap32['plasma'])
        if mytool.my_enum == 'OP3':
            self.clearNode()
            self.assignNode(self.colormap32['inferno'])
        if mytool.my_enum == 'OP4':
            self.clearNode()
            self.assignNode(self.colormap32['jet'])
        if mytool.my_enum == 'OP5':
            self.clearNode()
            self.assignNode(self.colormap32['gnuplot2'])

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
        return context.object is not None

    def execute(self, context):
        return {'FINISHED'}

    def draw_header(self, context):
        self.layout.label(text="", icon_value=custom_icons["ovito"].icon_id)
        
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.bleMD_props

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

        #
        # DATA FIELDS
        #
        if len(scene.datafieldlist):
            layout.label(text="Data fields from file")
            row = layout.row()
            row.template_list("bleMDDataFieldsList", "The_List", scene,
                              "datafieldlist", scene, "list_index")
        layout.operator("wm.read_lammps_file")

        layout.label(text="Basic Shader",)
        layout.prop(mytool, "my_shader")
        layout.prop(mytool, "my_normallow")
        layout.prop(mytool, "my_normalhigh")
        
        layout.operator("wm.basic_shade")

        layout.prop(mytool, "my_enum")
        row = layout.row()
        row.operator("wm.enumerator")

        layout.label(text="Animation")

        layout.prop(mytool, "lammps_frame_stride")
        layout.operator("wm.rig_keyframes")

        layout.label(text="Render")

        layout.prop(mytool, "renderpath")
        layout.operator("wm.render_animation")



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

    bpy.types.Scene.bleMD_props = PointerProperty(type=bleMDProperties)

    bpy.types.Scene.datafieldlist = CollectionProperty(type=bleMDDataFieldsLIProperty)
    bpy.types.Scene.list_index = IntProperty(
        name="Index for datafieldlist", default=0)


    installOvito()

    import bpy.utils.previews
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    import os
    ## this will work for addons 
    icons_dir = os.path.join(os.path.dirname(__file__), "resources")
    custom_icons.load("ovito", os.path.join(icons_dir, "ovito.png"), 'IMAGE')


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.bleMD_props
    bpy.utils.previews.remove(custom_icons)



if __name__ == "__main__":
    import bpy
    register()

    # bpy.ops.wm.call_menu(name="OBJECT_MT_select_test")

    # bpy.ops.message.messagebox('INVOKE_DEFAULT')
