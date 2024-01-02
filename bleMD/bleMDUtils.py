import bpy
import bmesh

from . bleMDNodes import *

#
# Many of the blender defaults do not look very good for MD.
# This is a general routine to set several of the default
# values so that things look good the first time.
#
def resetDefaultsForMD():
    # Set the camera so that objects too far away do not get clipped off
    bpy.data.objects['Camera'].data.clip_end=10000000000

    # Go through all current 3D views and set clips for that as well
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.clip_end = 100000000000

    # Set up the World to 
    bpy.data.worlds["World"].node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)


#
# KEY SUBROUTINE 1/2
# Opens Ovito and does basic communication with dump file
#
def startOvito(hardrefresh=False, filename=None):
    if not filename:
        filename = bpy.context.object.bleMD_props.lammpsfile


    #
    # Determine whether we need to create a new object
    #

    ob = bpy.context.object
    createNewObject = False
    if not len(bpy.context.selected_objects): createNewObject = True
    if not ob: createNewObject = True
    if ob:
        if not "bleMD_object" in ob.data.keys():
            createNewObject = True
    if createNewObject:
        print("Creating new MD object")
        # Object does not yet exist: create it
        me = bpy.data.meshes.new("MD_Mesh")
        ob = bpy.data.objects.new("MD_Object", me)
        ob.data['bleMD_object'] = True
        ob.show_name = True

        # Select the object
        bpy.context.collection.objects.link(ob)
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
    ob.bleMD_props.lammpsfile = filename
        
        
    interp = ob.bleMD_props.lammps_frame_stride
    mytool = ob.bleMD_props

    #
    # Load the file
    #
    pipline = None

    if mytool.io_method == {"openfile"}:
        from ovito.io import import_file
        pipeline = import_file(filename, sort_particles=True)
    elif mytool.io_method == {"script"}:
        scriptname = mytool.io_open_script
        local = {}
        exec(bpy.data.texts[scriptname].as_string(),globals(),local)
        pipeline = local['pipeline']
    else:
        print("Error in IO method selection",mytool.io_method)

    #
    # Execute User's Ovito Python script if applicable
    #
    if mytool.process_script_enable:
        scriptname = mytool.process_script
        local = locals()
        exec(bpy.data.texts[scriptname].as_string(),globals(),local)
        pipeline = local['pipeline']
    
    #
    # Adjust number of frames 
    #
    nframes = pipeline.source.num_frames
    mytool.number_of_lammps_frames = nframes
    mytool.frame_end = nframes * mytool.lammps_frame_stride
    mytool.valid_lammps_file = True

    #
    # Populate the properties list
    #
    data = pipeline.compute()
    props = list(data.particles.keys())
    if hardrefresh:
        ob.datafieldlist.clear()
    
    for prop in props:
        if prop not in [i.name for i in ob.datafieldlist]:
            item = ob.datafieldlist.add()
            item.name = prop
            if prop == "Position":
                item.enable = True
                item.editable = False



    return ob, pipeline


#
# KEY SUBROUTINE 2/2
# Updates the current data based on the Blender timestep
#
def loadUpdatedData(ob, pipeline):
    # Determine what the frame (or frames if interpolating)
    # are that need to be pulled from
    frame = bpy.data.scenes[0].frame_current
    interp = bpy.context.object.bleMD_props.lammps_frame_stride

    # Determine interpolation (if any)
    fac = (frame % interp)/interp
    frame_lo = int(frame / interp)

    print("FAC = ", fac)
    print("frame_lo ", frame_lo)

    me = ob.data

    # Set up the object or grab the existing object
    # TODO: how do we handle multiple objects?
    #if not "MD_Object" in bpy.data.objects.keys():
    #    print("Creating new MD object")
    #    # Object does not yet exist: create it
    #    me = bpy.data.meshes.new("MD_Mesh")
    #    ob = bpy.data.objects.new("MD_Object", me)
    #    ob.show_name = True
    #    bpy.context.collection.objects.link(ob)
    #else:
    #    # Object exists: use it
    #    print("Using existing")
    #    ob = bpy.data.objects['MD_Object']
    #    me = ob.data

    # Update the data - storing the appropriate Ovito data
    # in python data structure, but no updates yet.
    attrs = {}
    if fac == 0:
        data = pipeline.compute(frame_lo)
        coords = [list(xyz) for xyz in data.particles.positions]
        for prop in ob.datafieldlist:
            if prop.enable and prop.editable:
                attrs[prop.name] = [x for x in data.particles[prop.name]]
        #c_csym = [x for x in data.particles['c_csym']]
    else:
        frame_hi = frame_lo + 1
        data_lo = pipeline.compute(frame_lo)
        data_hi = pipeline.compute(frame_hi)
        coords = [list((1-fac)*xyz_lo + fac*xyz_hi) for xyz_lo, xyz_hi in
                  zip(data_lo.particles.positions, data_hi.particles.positions)]
        for prop in ob.datafieldlist:
            if prop.enable and prop.editable:
                attrs[prop.name] = [(1-fac)*x_lo + fac*x_hi for x_lo, x_hi in
                                    zip(data_lo.particles[prop.name], data_hi.particles[prop.name])]

        #c_csym = [(1-fac)*x_lo + fac*x_hi for x_lo,x_hi in zip(data_lo.particles['c_csym'], data_hi.particles['c_csym'])]

    if len(me.vertices) != len(coords):
        print("Regenerating mesh. Need {} vertices".format(len(coords)))

        # Do this if the object has not been created yet
        # This line actually creates all the points
        me.from_pydata(coords, [], [])
        # Now, we go through the properties that were selected in the panel
        # and set each of those properties as attributes
        for prop in ob.datafieldlist:
            if prop.enable and prop.editable:
                attr = me.attributes.new(prop.name, 'FLOAT', 'POINT')
                attr.data.foreach_set("value", attrs[prop.name])
    else:
        print("Updating existing vertex properties")
        # We do this if we are just updating the positions and properties,
        # not creating

        # For some reason we have to do this in order to update the mesh
        # vertex locations. There doesn't appear to be a handy blender
        # routine to do this automatically
        for i, v in enumerate(me.vertices):
            new_location = v.co
            new_location[0] = coords[i][0]
            new_location[1] = coords[i][1]
            new_location[2] = coords[i][2]
            v.co = new_location

        # Here we update the properties (e.g. c_csym)
        for prop in ob.datafieldlist:
            if prop.enable and prop.editable:
                if not prop.name in me.attributes.keys():
                    attr = me.attributes.new(prop.name, 'FLOAT', 'POINT')
                else:
                    attr = me.attributes.get(prop.name)
                attr.data.foreach_set("value", attrs[prop.name])

    me.update()


    #props_for_selector = ()
    #for a in attrs.keys():
    #    props_for_selector.add((attr,attr,attr))
    #bpy.context.scene.bleMD_props.colorby_property.items=props_for_selector


    # Call setup function - Jackson
    setup()

    
