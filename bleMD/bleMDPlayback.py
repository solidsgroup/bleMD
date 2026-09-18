"""Playback timing belongs to the File Source feeding Particle Output."""
from .bleMDPipeline import SOURCE_TYPE, OUTPUT_TYPE


def source_for(tree, origin=None):
    if origin is not None:
        return next((n for n in tree.nodes if n.bl_idname == SOURCE_TYPE and n.as_pointer() == origin), None)
    output = next((n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE), None)
    node, seen = output, set()
    while node is not None and node.as_pointer() not in seen:
        seen.add(node.as_pointer())
        if node.bl_idname == SOURCE_TYPE:
            return node
        socket = node.inputs.get('Data')
        if socket and len(socket.links) == 1:
            from .bleMDGraph import linked_socket
            try:
                node = linked_socket(socket).node
            except ValueError:
                return None
        else:
            node = None
    return None


def settings(tree, source=None):
    source = source or source_for(tree)
    return (source.start_frame, source.timesteps_per_frame) if source else (0, 1)


def fit(scene, tree):
    start, stride = settings(tree)
    scene.frame_start = start
    scene.frame_end = start + max(0, tree.frame_count - 1) * stride
