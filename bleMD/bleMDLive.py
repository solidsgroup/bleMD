"""Main-thread live evaluation and bounded, per-recipe OVITO caches."""
import bpy
from bpy.app.handlers import persistent

from .bleMDPipeline import TREE_TYPE, SOURCE_TYPE, OUTPUT_TYPE

INTERVAL = 0.15
suspended = False
_busy = False
_states = {}

# Presentation/status changes must not invalidate an OVITO pipeline. In
# particular, evaluation itself writes source schemas and automatic limits.
IGNORED = {'frame_count', 'last_message', 'has_error', 'automatic_updates',
           'scene', 'channels_loaded', 'channels_error', 'channels_message',
           'show_parameters', 'expose_dataset'}


def value_key(value):
    if isinstance(value, bpy.types.Text):
        return (value.as_pointer(), value.as_string())
    if isinstance(value, bpy.types.ID):
        return value.as_pointer()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return tuple(value)


def properties(item):
    names = set()
    for cls in type(item).__mro__:
        names.update(getattr(cls, '__annotations__', {}))
    if getattr(item, 'range_mode', None) == 'FIRST_FRAME':
        names -= {'minimum', 'maximum'}
    return tuple((name, value_key(getattr(item, name)))
                 for name in sorted(names - IGNORED) if hasattr(item, name))


def signature(tree):
    return (properties(tree),
            tuple((node.as_pointer(), node.bl_idname, node.mute, properties(node), tuple((s.identifier, s.get('bleMD_export_name'), value_key(getattr(s, 'default_value', None)), s.is_property_set('default_value') if hasattr(s, 'default_value') else False) for s in node.inputs)) for node in tree.nodes),
            tuple((link.from_node.as_pointer(), link.from_socket.identifier,
                   link.to_node.as_pointer(), link.to_socket.identifier) for link in tree.links))


def processing_signature(tree):
    """Visualization edits reuse native OVITO pipelines and their cached results."""
    from .bleMDModifiers import is_modifier_node
    processors = [n for n in tree.nodes if n.bl_idname in {SOURCE_TYPE, 'BleMDOvitoScript'} or is_modifier_node(n)]
    return (tuple((n.as_pointer(), n.mute,
                   tuple((k,v) for k,v in properties(n) if n.bl_idname != SOURCE_TYPE or k not in {'start_frame','timesteps_per_frame'}),
                   tuple((s.identifier, s.is_linked) for s in n.outputs)) for n in processors),
            tuple((link.from_node.as_pointer(), link.to_node.as_pointer()) for link in tree.links
                  if (link.to_node in processors and link.to_socket.bl_idname == 'BleMDPipelineSocket') or link.to_node.bl_idname == 'NodeReroute'),
            tuple(n.as_pointer() for n in tree.nodes if n.bl_idname == OUTPUT_TYPE))


def scene_for(tree):
    if tree.scene is not None:
        return tree.scene
    for node in tree.nodes:
        if node.bl_idname == OUTPUT_TYPE and node.target:
            scenes = node.target.users_scene
            if scenes:
                return scenes[0]
    # New/unbound graphs are evaluated only if open in an editor.
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            space = area.spaces.active
            if space.type == 'NODE_EDITOR' and space.node_tree == tree:
                return window.scene
    return None


def invalidate(tree=None):
    if tree is None:
        _states.clear()
    else:
        _states.pop(tree.as_pointer(), None)


def evaluate(tree, scene, force=False):
    """Run synchronously; frame handlers must finish before Blender draws/renders."""
    global _busy
    if _busy or (not force and (suspended or not tree.automatic_updates)):
        return None
    key = tree.as_pointer()
    before = signature(tree)
    state = _states.get(key)
    processing = processing_signature(tree)
    frame = scene.frame_current + scene.frame_subframe
    if not force and state and state['signature'] == before and state['frame'] == frame:
        return None
    _busy = True
    graph = None
    try:
        from .bleMDGraph import Graph
        from .bleMDPipeline import evaluate_tree
        if not force and state and state.get('processing') == processing:
            graph = state['graph']
            if graph is not None and state['signature'] != before:
                graph.fields.clear()
                graph.color_ranges.clear()
        if graph is None:
            # Release the obsolete native graph before allocating its replacement.
            if state:
                state['graph'] = None
            graph = Graph(tree)
        else:
            # Retain native pipeline caches and first-frame color ranges, but
            # never retain Python DataCollections for an entire trajectory.
            graph.release_samples()
        # Blender renders animations on a worker thread. Locking the interface
        # prevents the viewport from reading meshes while the frame handler swaps them.
        if tree.automatic_updates:
            scene.render.use_lock_interface = True
        first = tree.frame_count == 0
        obj = evaluate_tree(tree, scene, graph=graph)
        tree.scene = scene
        from .bleMDPlayback import settings, fit
        if tree.frame_count > 1 and (first or not state or state.get('timing') != settings(tree)):
            fit(scene, tree)
        return obj
    except Exception as error:
        graph = None
        tree.has_error = True
        tree.last_message = str(error)
        if force:
            raise
    finally:
        # Unconnected sources still expose their fields while a graph is being
        # assembled. Sources already computed by Graph do not perform a second read.
        from .bleMDSource import inspect_source
        for node in tree.nodes:
            if node.bl_idname == SOURCE_TYPE and node.filepath.strip() and not node.channels_loaded:
                inspect_source(node)
        if graph is not None:
            graph.release_samples()  # Native pipelines cache what they need; release Python snapshots now.
        # Snapshot after generated material/target pointers and sockets settle.
        from .bleMDPlayback import settings
        _states[key] = {'timing': settings(tree), 'signature': signature(tree), 'processing': processing_signature(tree), 'frame': frame, 'graph': graph}
        _busy = False
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'NODE_EDITOR', 'VIEW_3D', 'DOPESHEET_EDITOR'}:
                    area.tag_redraw()


def update_scene(scene):
    if suspended or _busy:
        return
    for tree in tuple(bpy.data.node_groups):
        if tree.bl_idname == TREE_TYPE and tree.automatic_updates and scene_for(tree) == scene:
            if any(n.bl_idname == SOURCE_TYPE and n.filepath.strip() for n in tree.nodes):
                evaluate(tree, scene)


@persistent
def frame_changed(scene, depsgraph=None):
    update_scene(scene)


def tick():
    from .bleMDScene import update_clipping
    if not bpy.app.is_job_running('RENDER'):
        for scene in {window.scene for window in bpy.context.window_manager.windows}:
            update_clipping(scene)
    if suspended or _busy or bpy.app.is_job_running('RENDER'):
        return INTERVAL
    existing = set()
    scenes = set()
    for tree in tuple(bpy.data.node_groups):
        if tree.bl_idname != TREE_TYPE:
            continue
        key = tree.as_pointer()
        existing.add(key)
        if not tree.automatic_updates:
            _states.pop(key, None)
            continue
        scene = scene_for(tree)
        if scene is not None:
            scenes.add(scene)
    for key in set(_states) - existing:
        _states.pop(key, None)
    for scene in scenes:
        update_scene(scene)
    return INTERVAL


@persistent
def reset(_):
    invalidate()


def register():
    bpy.app.handlers.frame_change_pre.append(frame_changed)
    for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        handlers.append(reset)
    bpy.app.timers.register(tick, first_interval=INTERVAL, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    bpy.app.handlers.frame_change_pre.remove(frame_changed)
    for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        handlers.remove(reset)
    invalidate()
