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
                       BoolVectorProperty,
                       CollectionProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       UIList,
                       )


#import ovito


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class MyProperties(PropertyGroup):

    valid_lammps_file: BoolProperty(default = False)
    number_of_lammps_frames: IntProperty(default = 1)

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
        bpy.context.scene.frame_start = 0
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

        data=pipeline.compute()
        props = list(data.particles.keys())
        
        scene.my_list.clear()
        for prop in props:
            item  = scene.my_list.add()
            item.name = prop
            if prop == "Position":
                item.enable=True
                item.editable=False
                


    my_lammpsfile: StringProperty(
        name = "LAMMPS Dump File",
        description="Choose a file:",
        default="/home/jackson/Desktop/",
        maxlen=1024,
        subtype='FILE_PATH',
        update=openLAMMPSFile,
        )

    my_ovitodir: StringProperty(
        name = "OVITO Directory",
        description="Choose a file:",
        default="/home/jackson/.local/lib/python3.10/site-packages/",
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


    #
    # Ovito Modifiers
    #
    ovito_wrap_periodic_images: BoolProperty(
        name="OVITO Wrap Periodic Images",
        default = False)
    ovito_unwrap_trajectories: BoolProperty(
        name="OVITO Unwrap Trajectories",
        default = False)

#
# KEY SUBROUTINE 1/2
# Opens Ovito and does basic communication with dump fil
#
def startOvito():
    filename = bpy.context.scene.my_tool.my_lammpsfile
    interp = bpy.context.scene.my_tool.my_lammps_frame_stride

    from ovito.io import import_file
    from ovito.modifiers import UnwrapTrajectoriesModifier
    from ovito.modifiers import WrapPeriodicImagesModifier

    # Load pipeline from ovito
    pipeline = import_file(filename, sort_particles=True)
    
    # Check if checkboxes are ticked in the panel
    # If so, apply the appropriate modifier to the ovito
    # pipeline
    if bpy.context.scene.my_tool.ovito_wrap_periodic_images:
        pipeline.modifiers.append(WrapPeriodicImagesModifier())
    if bpy.context.scene.my_tool.ovito_unwrap_trajectories:
        pipeline.modifiers.append(UnwrapTrajectoriesModifier())

    # Note the number of timestep dumps 
    nframes = pipeline.source.num_frames
    bpy.context.scene.my_tool.number_of_lammps_frames = nframes

    return pipeline
    
#
# KEY SUBROUTINE 2/2
# Updates the current data based on the Blender timestep
#
def loadUpdatedData(pipeline):
    # Determine what the frame (or frames if interpolating)
    # are that need to be pulled from
    frame = bpy.data.scenes[0].frame_current
    interp = bpy.context.scene.my_tool.my_lammps_frame_stride

    # Determine interpolation (if any)
    fac = (frame % interp)/interp
    frame_lo = int(frame / interp)

    print("FAC = ",fac)
    print("frame_lo ",frame_lo)

    # Set up the object or grab the existing object
    # TODO: how do we handle multiple objects?
    if not "MD_Object" in bpy.data.objects.keys():
        # Object does not yet exist: create it
        me = bpy.data.meshes.new("MD_Mesh")
        ob = bpy.data.objects.new("MD_Object", me)
        ob.show_name = True
        bpy.context.collection.objects.link(ob)
    else:
        # Object exists: use it
        ob = bpy.data.objects['MD_Object']
        me = ob.data

    # Update the data - storing the appropriate Ovito data
    # in python data structure, but no updates yet.
    attrs = {}
    if fac == 0:
        data = pipeline.compute(frame_lo)
        coords = [list(xyz) for xyz in data.particles.positions]
        for prop in bpy.context.scene.my_list:
            if prop.enable and prop.editable:
                attrs[prop.name] = [x for x in data.particles[prop.name]]
        #c_csym = [x for x in data.particles['c_csym']]
    else:
        frame_hi = frame_lo + 1
        data_lo = pipeline.compute(frame_lo)
        data_hi = pipeline.compute(frame_hi)
        coords = [list((1-fac)*xyz_lo + fac*xyz_hi) for xyz_lo, xyz_hi in
                  zip(data_lo.particles.positions,data_hi.particles.positions)]
        for prop in bpy.context.scene.my_list:
            if prop.enable and prop.editable:
                attrs[prop.name] = [(1-fac)*x_lo + fac*x_hi for x_lo,x_hi in
                                    zip(data_lo.particles[prop.name], data_hi.particles[prop.name])]

        #c_csym = [(1-fac)*x_lo + fac*x_hi for x_lo,x_hi in zip(data_lo.particles['c_csym'], data_hi.particles['c_csym'])]

    if not len(me.vertices):
        # Do this if the object has not been created yet
        # This line actually creates all the points
        me.from_pydata(coords,[],[])
        # Now, we go through the properties that were selected in the panel
        # and set each of those properties as attributes
        for prop in bpy.context.scene.my_list:
            if prop.enable and prop.editable:
                attr = me.attributes.new(prop.name,'FLOAT','POINT')
                attr.data.foreach_set("value",attrs[prop.name])
    else:
        # We do this if we are just updating the positions and properties,
        # not creating
        
        # For some reason we have to do this in order to update the mesh
        # vertex locations. There doesn't appear to be a handy blender 
        # routine to do this automatically
        for i,v in enumerate(me.vertices):
            new_location = v.co            
            new_location[0] = coords[i][0]
            new_location[1] = coords[i][1]
            new_location[2] = coords[i][2]
            v.co = new_location
        
        # Here we update the properties (e.g. c_csym)
        for prop in bpy.context.scene.my_list:
            if prop.enable and prop.editable:
                if not prop.name in me.attributes.keys():
                    attr = me.attributes.new(prop.name,'FLOAT','POINT')
                else:
                    attr = me.attributes.get(prop.name)
                attr.data.foreach_set("value",attrs[prop.name])

    me.update()
    
    # Call setup function - Jackson
    setup()


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class WM_OT_HelloWorld(Operator):
    bl_idname = "wm.read_lammps_file"
    bl_label = "Load File"

    my_tmp_cntr = 0

    def execute(self, context):
        #scene = context.scene
        #mytool = scene.my_tool
        pipeline = startOvito()
        loadUpdatedData(pipeline)
        

        return {'FINISHED'}


class WM_OT_RigKeyframes(Operator):
    bl_idname = "wm.rig_keyframes"
    bl_label = "Rig Keyframes"
    def execute(self, context):
        scene = bpy.context.scene
        nlammpsframes = scene.my_tool.number_of_lammps_frames
        stride = scene.my_tool.my_lammps_frame_stride


        keyInterp = context.preferences.edit.keyframe_new_interpolation_type
        context.preferences.edit.keyframe_new_interpolation_type ='LINEAR'


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


            ob.shape_key_add(name="Key"+str(i).zfill(4),from_mix=False)
            
            if i>0:
                for j in range(nlammpsframes):
                    if j==i:
                        bpy.data.shape_keys["Key"].key_blocks["Key"+str(i).zfill(4)].value=1
                    else:
                        bpy.data.shape_keys["Key"].key_blocks["Key"+str(i).zfill(4)].value=0
                    keyframe = bpy.data.shape_keys["Key"].key_blocks["Key"+str(i).zfill(4)].keyframe_insert("value",frame=j*stride)
            

        context.preferences.edit.keyframe_new_interpolation_type = keyInterp


        return {'FINISHED'}


class WM_OT_RenderAnimation(Operator):
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
            print("Rendering ",frame)
            scene.render.filepath = scene.my_tool.my_renderpath + str(frame).zfill(4)
            scene.frame_set(frame)
            loadUpdatedData(pipeline)
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

        layout.prop(mytool, "my_ovitodir")

        layout.label(text="Input file")
        layout.prop(mytool, "my_lammpsfile")

        layout.label(text="OVITO Operations")

        layout.prop(mytool,"ovito_wrap_periodic_images")
        layout.prop(mytool,"ovito_unwrap_trajectories")

        if len(scene.my_list):
            layout.label(text="Data fields from file")
            row = layout.row()
            row.template_list("MY_UL_List", "The_List", scene,
                              "my_list", scene, "list_index")

        layout.operator("wm.read_lammps_file")

        layout.label(text="Animation")

        layout.prop(mytool, "my_lammps_frame_stride")
        layout.operator("wm.rig_keyframes")

        layout.label(text="Render")

        layout.prop(mytool, "my_renderpath")
        layout.operator("wm.render_animation")

        











class ParticleProperty(PropertyGroup):
    """Group of properties representing an item in the list."""

    name: StringProperty(
           name="Name",
           description="Property",
           default="Untitled")

    enable: BoolProperty(
           name="Enable",
           description="Include as a coloring property")

    editable: BoolProperty(
           name="Editable",
           description="Whether or not the user can modify",
        default=True,
        )


class MY_UL_List(UIList):
    """Demo UIList."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        # We could write some code to decide which icon to use here...
        custom_icon = 'OBJECT_DATAMODE'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.label(text=item.name, icon = custom_icon)
            row = layout.row()
            row.enabled = item.editable
            row.prop(item,"enable")

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon = custom_icon)


#class LIST_OT_NewItem(Operator):
#    """Add a new item to the list."""
#
#    bl_idname = "my_list.new_item"
#    bl_label = "Add a new item"
#
#    def execute(self, context):
#        item  = context.scene.my_list.add()
#        item.name = "Hello"
#        print(item)
#        #context.scene.my_list.clear()
#
#        return{'FINISHED'}


#def frame_handler(scene, depsgraph):
#    if bpy.context.scene.my_tool.update_on_frame_change:
#        loadUpdatedData()
#
#    print(bpy.data.scenes[0].frame_current)



# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    MyProperties,
    WM_OT_HelloWorld,
    WM_OT_RenderAnimation,
    WM_OT_RigKeyframes,
    OBJECT_PT_bleMDPanel,
#    OBJECT_MT_CustomMenu,
#    MessageBox,
#    BasicMenu,
#    MATERIAL_UL_matslots_example,
#    uilist.MATERIAL_UL_matslots_example,
#    uilist.UIListPanelExample1,
    ParticleProperty,
    MY_UL_List,
#    LIST_OT_NewItem,
#    PT_ListExample,
)




def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.app.handlers.frame_change_post.clear()
    #bpy.app.handlers.frame_change_post.append(frame_handler)


    bpy.types.Scene.my_tool = PointerProperty(type=MyProperties)

    print("He")
    bpy.types.Scene.my_list = CollectionProperty(type = ParticleProperty)
    bpy.types.Scene.list_index = IntProperty(name = "Index for my_list",default = 0)


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.my_tool

#
# Jackson messing around with automatically setting up geonode environment
#

def create_geonodes():
	obj = bpy.data.objects["MD_Object"]
	geo_nodes = obj.modifiers.new("build_geonode", "NODES")

	node_group = create_group()
	geo_nodes.node_group = node_group
	

def create_group(name = "geonode_object"):
    group = bpy.data.node_groups.get(name)
    # if the group already exists, return it and don't create a new one
    if group:
        pass
    
    # create a new group for this particular name and do some initial setup
    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    group.inputs.new('NodeSocketGeometry', "Geometry")
    group.outputs.new('NodeSocketGeometry', "Geometry")
    input_node = group.nodes.new('NodeGroupInput')
    output_node = group.nodes.new('NodeGroupOutput')
    output_node.is_active_output = True
    input_node.location.x = -300
    output_node.location.x = 350
    
    
    mesh_to_points = group.nodes.new('GeometryNodeMeshToPoints')
    set_material = group.nodes.new('GeometryNodeSetMaterial')
    mesh_to_points.location.x = -75
    set_material.location.x = 125
    
    bpy.data.node_groups[name].nodes["Mesh to Points"].inputs[3].default_value = 1
    
    group.links.new(input_node.outputs[0], mesh_to_points.inputs[0])
    group.links.new(mesh_to_points.outputs[0], set_material.inputs[0])
    group.links.new(set_material.outputs[0], output_node.inputs[0])
    
    return group
    
def setup():
	create_geonodes()
	for scene in bpy.data.scenes:
		scene.render.engine = 'CYCLES'



if __name__ == "__main__":
    import bpy
    register()

    #bpy.ops.wm.call_menu(name="OBJECT_MT_select_test")

    #bpy.ops.message.messagebox('INVOKE_DEFAULT')
