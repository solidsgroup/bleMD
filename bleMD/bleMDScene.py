"""Scene defaults and distance-aware clipping for molecular coordinates."""
import bpy
from mathutils import Vector
from bpy.app.handlers import persistent

_initialized = set()
MIN_FAR = 10000.0


def ensure_defaults(scene):
    if scene.as_pointer() not in _initialized:
        scene.render.engine = 'CYCLES'
        _initialized.add(scene.as_pointer())
    update_clipping(scene)


def update_clipping(scene):
    bounds = []
    for obj in scene.objects:
        if obj.type != 'MESH' or not obj.data.get('bleMD_object'):
            continue
        extent = obj.data.get('bleMD_bounds')
        if extent is not None:
            lo, hi = extent[:3], extent[3:]
            corners = [obj.matrix_world @ Vector((x,y,z)) for x in (lo[0],hi[0])
                       for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
        else:
            corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        center = sum(corners, Vector()) / 8
        radius = max((c-center).length for c in corners)
        bounds.append((center,radius))
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                views = tuple(space.region_quadviews) or (space.region_3d,)
                far = MIN_FAR
                for view in views:
                    if view is None:
                        continue
                    # view_distance plus distance from the orbit center safely
                    # covers any orientation, including independent quad views.
                    reach = max(((center-view.view_location).length+radius for center,radius in bounds), default=0.)
                    far = max(far, 2*(view.view_distance+reach))
                if space.clip_end < far:
                    space.clip_end = far
    for obj in scene.objects:
        if obj.type == 'CAMERA':
            eye = obj.matrix_world.translation
            far = max(MIN_FAR, 2*max(((center-eye).length+radius for center,radius in bounds), default=0.))
            if obj.data.clip_end < far:
                obj.data.clip_end = far


@persistent
def initialize(_=None):
    _initialized.clear()
    for scene in getattr(bpy.data, 'scenes', ()):
        ensure_defaults(scene)


def deferred_initialize():
    for scene in getattr(bpy.data, 'scenes', ()):
        ensure_defaults(scene)
    return None


def register():
    bpy.app.handlers.load_post.append(initialize)
    initialize()
    # Add-on registration may run with restricted bpy.data until the next tick.
    bpy.app.timers.register(deferred_initialize, first_interval=0.0)


def unregister():
    if bpy.app.timers.is_registered(deferred_initialize):
        bpy.app.timers.unregister(deferred_initialize)
    bpy.app.handlers.load_post.remove(initialize)
    _initialized.clear()
