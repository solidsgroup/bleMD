"""An opt-in, saved bleMD workspace using Blender's native Quad View."""
import bpy

from .bleMDPipeline import TREE_TYPE, OUTPUT_TYPE

NAME = 'bleMD'
_pending = set()


def choose_tree(context):
    space = context.space_data
    if space and space.type == 'NODE_EDITOR' and space.tree_type == TREE_TYPE and space.node_tree:
        return space.node_tree
    obj = context.object
    if obj and obj.bleMD_node_tree:
        return obj.bleMD_node_tree
    return next((t for t in bpy.data.node_groups if t.bl_idname == TREE_TYPE
                 and any(n.bl_idname == OUTPUT_TYPE and n.target
                         and context.scene in n.target.users_scene for n in t.nodes)), None)


def configure(window, workspace, tree):
    from .bleMDTree import starter_tree
    window.workspace = workspace
    screen = window.screen
    viewport = max(screen.areas, key=lambda a: a.width * a.height)
    viewport.type = 'VIEW_3D'
    before = {a.as_pointer() for a in screen.areas}
    with bpy.context.temp_override(window=window, area=viewport):
        bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.36)
    pair = [a for a in screen.areas if a == viewport or a.as_pointer() not in before]
    bottom, viewport = sorted(pair, key=lambda a: a.y)
    bottom.type = 'NODE_EDITOR'
    bottom.ui_type = TREE_TYPE
    bottom.spaces.active.tree_type = TREE_TYPE
    tree = tree or starter_tree()
    tree.scene = window.scene
    bottom.spaces.active.node_tree = tree
    bottom.spaces.active.pin = True
    bottom.spaces.active.show_region_ui = False
    viewport.type = 'VIEW_3D'
    space = viewport.spaces.active
    space.shading.color_type = 'VERTEX'
    space.region_3d.view_perspective = 'PERSP'
    region = next(r for r in viewport.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=window, area=viewport, region=region):
        if not space.region_quadviews:
            bpy.ops.screen.region_quadview()
    # Blender initializes front/right/top plus the original perspective view.
    for view in space.region_quadviews[:3]:
        view.lock_rotation = True
        view.show_sync_view = False
        view.use_box_clip = False
    space.region_quadviews[3].view_perspective = 'PERSP'
    # Frame the MD output without changing selection or object transforms.
    window.view_layer.update()
    targets = [n.target for n in tree.nodes if n.bl_idname == OUTPUT_TYPE and n.target]
    if targets:
        from mathutils import Vector
        corners = [obj.matrix_world @ Vector(c) for obj in targets for c in obj.bound_box]
        center = sum(corners, Vector()) / len(corners)
        radius = max((c - center).length for c in corners)
        for view in space.region_quadviews:
            view.view_location = center
            view.view_distance = max(4.0, radius * 3)
    # Nonstandard starting workspaces may not have a Timeline.
    if not any(a.type == 'DOPESHEET_EDITOR' and a.ui_type == 'TIMELINE' for a in screen.areas):
        before = {a.as_pointer() for a in screen.areas}
        with bpy.context.temp_override(window=window, area=bottom):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.12)
        pair = [a for a in screen.areas if a == bottom or a.as_pointer() not in before]
        timeline, bottom = sorted(pair, key=lambda a: a.y)
        timeline.type = 'DOPESHEET_EDITOR'
        timeline.ui_type = 'TIMELINE'
    def frame_nodes():
        _pending.discard(frame_nodes)
        try:
            if window.workspace == workspace and bottom.type == 'NODE_EDITOR':
                region = next(r for r in bottom.regions if r.type == 'WINDOW')
                with bpy.context.temp_override(window=window, area=bottom, region=region):
                    bpy.ops.node.view_all()
        except (ReferenceError, RuntimeError):
            pass
        return None

    # Node dimensions and region bounds are only valid after the first draw.
    _pending.add(frame_nodes)
    bpy.app.timers.register(frame_nodes, first_interval=0.3)
    workspace['bleMD_layout'] = True
    workspace['bleMD_independent_views'] = True


class BLEMD_OT_layout(bpy.types.Operator):
    bl_idname = 'blemd.layout'
    bl_label = 'bleMD Layout'
    bl_description = 'Open a bleMD workspace with three axis views, a perspective view, nodes, and a timeline'

    @classmethod
    def poll(cls, context):
        return context.window is not None and not bpy.app.background

    def execute(self, context):
        from .bleMDScene import ensure_defaults
        ensure_defaults(context.scene)
        existing = next((w for w in bpy.data.workspaces if w.get('bleMD_layout')), None)
        if existing:
            context.window.workspace = existing
            return {'FINISHED'}
        tree = choose_tree(context)
        window = context.window
        # Use Layout's familiar Outliner/Properties/Timeline when available.
        template = bpy.data.workspaces.get('Layout')
        if template:
            window.workspace = template
        before = {w.as_pointer() for w in bpy.data.workspaces}
        bpy.ops.workspace.duplicate()
        workspace = next(w for w in bpy.data.workspaces if w.as_pointer() not in before)
        workspace.name = NAME

        def finish():
            _pending.discard(finish)
            try:
                if workspace.name in bpy.data.workspaces:
                    configure(window, workspace, tree)
            except (ReferenceError, RuntimeError) as error:
                print(f'bleMD layout: {error}')
            return None

        # Workspace activation is deferred by Blender until the next UI cycle.
        _pending.add(finish)
        bpy.app.timers.register(finish, first_interval=0.1)
        return {'FINISHED'}


def draw_menu(self, context):
    self.layout.operator('blemd.layout', icon='WORKSPACE')


def register():
    bpy.utils.register_class(BLEMD_OT_layout)
    bpy.types.TOPBAR_MT_window.append(draw_menu)


def unregister():
    for callback in tuple(_pending):
        if bpy.app.timers.is_registered(callback):
            bpy.app.timers.unregister(callback)
    _pending.clear()
    bpy.types.TOPBAR_MT_window.remove(draw_menu)
    bpy.utils.unregister_class(BLEMD_OT_layout)


def migrate_views():
    for workspace in bpy.data.workspaces:
        if not workspace.get('bleMD_layout') or workspace.get('bleMD_independent_views'):
            continue
        for screen in workspace.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    for view in area.spaces.active.region_quadviews:
                        view.show_sync_view = False
                        view.use_box_clip = False
        workspace['bleMD_independent_views'] = True
