"""Evaluate bleMD node recipes and transfer their particle output to Blender.

OVITO pipelines are cached during live playback. The .blend stores the recipe,
not native OVITO objects, so reopening a file always rebuilds a valid pipeline.
"""

import math

import bpy
import numpy as np

from .bleMDNodes import create_geonodes

TREE_TYPE = "BleMDNodeTree"
SOURCE_TYPE = "BleMDFileSource"
SCRIPT_TYPE = "BleMDOvitoScript"
OUTPUT_TYPE = "BleMDParticleOutput"
SOCKET_TYPE = "BleMDPipelineSocket"


def pipeline_chain(tree):
    from .bleMDModifiers import is_modifier_node
    outputs = [node for node in tree.nodes if node.bl_idname == OUTPUT_TYPE]
    if len(outputs) != 1:
        raise ValueError("Use exactly one Particle Output in each bleMD tree")
    chain, visited = [], set()
    node = outputs[0]
    while True:
        if node.as_pointer() in visited:
            raise ValueError("The pipeline contains a cycle; remove the circular connection")
        visited.add(node.as_pointer())
        chain.append(node)
        if node.bl_idname == SOURCE_TYPE:
            break
        if node.bl_idname not in {SCRIPT_TYPE, OUTPUT_TYPE} and not is_modifier_node(node):
            raise ValueError(f"Unsupported pipeline node: {node.name}")
        links = list(node.inputs[0].links)
        if len(links) != 1:
            raise ValueError(f"Connect the Pipeline input on '{node.name}'")
        link = links[0]
        if link.from_socket.bl_idname != SOCKET_TYPE:
            raise ValueError(f"'{node.name}' needs a bleMD Pipeline connection")
        node = link.from_node
    return list(reversed(chain))


def build_pipeline(tree):
    from .bleMDGraph import Graph
    graph = Graph(tree)
    pipeline, _ = graph.output_pipeline()
    return pipeline, graph.output


def particle_arrays(data, requested):
    if data.particles is None or data.particles.positions is None:
        raise ValueError("The pipeline has no particle positions")
    positions = np.asarray(data.particles.positions, dtype=np.float32)
    names = [name.strip() for name in requested.split(",") if name.strip()]
    available = data.particles
    attributes = {}
    for name in names or available.keys():
        if name == "Position":
            continue
        if name not in available:
            raise ValueError(f"Particle property '{name}' is missing from the pipeline output")
        values = np.asarray(available[name])
        if values.dtype.kind not in "biuf" or values.ndim not in {1, 2}:
            if names:
                raise ValueError(f"Particle property '{name}' is not numeric")
            continue
        # Blender supports scalar and 3-component vector attributes. Other
        # component counts are skipped unless explicitly requested.
        if values.ndim == 2 and values.shape[1] != 3:
            if names:
                raise ValueError(f"'{name}' must be a scalar or a 3-component vector")
            continue
        if values.dtype.kind in "iu" and values.ndim == 1:
            limits = np.iinfo(np.int32)
            if values.size and (values.min() < limits.min or values.max() > limits.max):
                raise ValueError(f"'{name}' exceeds Blender's 32-bit integer attribute range")
        attributes[name] = values.astype(np.int32 if values.dtype.kind in 'biu' and values.ndim == 1 else np.float32, copy=False)
    return positions, attributes


def sample_particles(pipeline, tree, frame, requested, compute=None, source=None):
    compute = compute or pipeline.compute
    count = pipeline.num_frames
    if count < 1:
        raise ValueError("The pipeline has no trajectory frames")
    start = source.start_frame if source else tree.start_frame
    stride = source.timesteps_per_frame if source else tree.frame_stride
    interpolate = stride > 1 if source else tree.interpolation == 'LINEAR'
    time = min(max((frame - start) / stride, 0), count - 1)
    lower = math.floor(time)
    fraction = time - lower
    data = compute(lower)
    positions, attributes = particle_arrays(data, requested)
    if interpolate and fraction > 0:
        following = compute(lower + 1)
        next_positions, next_attributes = particle_arrays(following, requested)
        if "Particle Identifier" not in data.particles or "Particle Identifier" not in following.particles:
            raise ValueError("Linear interpolation requires Particle Identifier; set Timesteps per Frame to 1")
        ids = np.asarray(data.particles["Particle Identifier"])
        next_ids = np.asarray(following.particles["Particle Identifier"])
        if len(np.unique(ids)) != len(ids) or len(np.unique(next_ids)) != len(next_ids):
            raise ValueError("Particle identifiers must be unique for linear interpolation")
        order = np.argsort(next_ids)
        indices = np.searchsorted(next_ids[order], ids)
        if (len(ids) != len(next_ids) or np.any(indices >= len(next_ids))
                or not np.array_equal(next_ids[order][indices], ids)):
            raise ValueError("Particle membership changes between frames; set Timesteps per Frame to 1")
        order = order[indices]
        positions = (1 - fraction) * positions + fraction * next_positions[order]
        for name, values in attributes.items():
            # IDs, types, selections and other integer properties are discrete.
            if values.dtype.kind == 'f':
                if name not in next_attributes or next_attributes[name].shape != values.shape:
                    raise ValueError(f"'{name}' changes between frames; set Timesteps per Frame to 1")
                attributes[name] = (1 - fraction) * values + fraction * next_attributes[name][order]
    return positions, attributes, count


def write_output(tree, node, scene, positions, attributes):
    obj = node.target
    if obj is not None and obj.bleMD_node_tree != tree:
        # Duplicating a tree must not overwrite the original tree's output.
        obj = None
    if obj is not None and (obj.type != 'MESH' or obj.mode != 'OBJECT'):
        raise ValueError("The output must be a mesh in Object Mode")
    if obj is not None and obj.data.shape_keys:
        raise ValueError("Remove shape keys from the output before updating the pipeline")
    if obj is not None and obj.name not in scene.objects:
        raise ValueError("The output belongs to another scene; create a separate pipeline for this scene")

    if not np.isfinite(node.radius) or node.radius < 0:
        if not node.inputs['Radius'].is_linked:
            raise ValueError('Particle radius must be finite and nonnegative')
    # Prepare a complete mesh first. Failed conversion leaves the old output intact.
    mesh = bpy.data.meshes.new("bleMD Particles")
    try:
        mesh.vertices.add(len(positions))
        mesh.vertices.foreach_set('co', np.asarray(positions, dtype=np.float32).ravel())
        mesh["bleMD_object"] = True
        if len(positions):
            radii = attributes.get('bleMD Radius')
            padding = float(np.max(radii)) if radii is not None and len(radii) else node.radius
            mesh['bleMD_bounds'] = [float(v) for v in np.concatenate((np.min(positions, axis=0)-padding, np.max(positions, axis=0)+padding))]
        from .bleMDFields import output_bindings, COLOR
        color_names = {'bleMD Color'} | {name for socket,name in output_bindings(node) if socket.bl_idname == COLOR}
        for name, values in attributes.items():
            if name in color_names and values.ndim == 2:
                kind, field = 'FLOAT_COLOR', 'color'
                values = np.column_stack((values, np.ones(len(values), dtype=np.float32)))
            elif values.ndim == 2:
                kind, field = 'FLOAT_VECTOR', 'vector'
            elif values.dtype.kind in 'biu':
                kind, field = 'INT', 'value'
            else:
                kind, field = 'FLOAT', 'value'
            attribute = mesh.attributes.new(name, kind, 'POINT')
            attribute.data.foreach_set(field, values.ravel())
        if node.material:
            mesh.materials.append(node.material)
        mesh.update()
    except Exception:
        bpy.data.meshes.remove(mesh)
        raise

    if obj is None:
        obj = bpy.data.objects.new("bleMD Particles", mesh)
        scene.collection.objects.link(obj)
        obj.bleMD_node_tree = tree
        node.target = obj
    else:
        previous = obj.data
        obj.data = mesh
        if previous.users == 0:
            bpy.data.meshes.remove(previous)
    create_geonodes(obj)
    group = obj.modifiers["build_geonode"].node_group
    from .bleMDViewport import configure_radius
    configure_radius(obj, node)
    group.nodes["Set Material"].inputs["Material"].default_value = node.material
    from .bleMDViewport import ensure_preview
    ensure_preview(obj, node.viewport_detail)
    from .bleMDScene import update_clipping
    update_clipping(scene)
    return obj


def evaluate_tree(tree, scene, graph=None):
    from .bleMDGraph import Graph
    from .bleMDScene import ensure_defaults
    ensure_defaults(scene)
    graph = graph or Graph(tree)
    pipeline, origin = graph.output_pipeline()
    output = graph.output
    # Explicit field connections are always transferred, even when the user
    # has restricted the legacy dataset attribute list.
    requested = output.attributes
    if requested.strip():
        from .bleMDFields import output_bindings
        for socket, attribute in output_bindings(output):
            requested += ',' + attribute
        if output.inputs['Color'].is_linked:
            # A Color Map's raw scalar is also available for shader operations.
            from .bleMDGraph import linked_socket
            field = graph.field(linked_socket(output.inputs['Color']))
            if any(n.bl_idname == 'BleMDColorMap' for n in field.operations):
                requested += ',bleMD Color Value'
    from .bleMDPlayback import source_for
    positions, attributes, count = sample_particles(
        pipeline, tree, scene.frame_current + scene.frame_subframe, requested,
        compute=lambda frame: graph.sample_output(pipeline, origin, frame), source=source_for(tree, origin))
    # Native OVITO coloring modifiers expose RGB as Color. Use the same
    # display attribute as typed Color fields, which take precedence.
    if 'bleMD Color' not in attributes and 'Color' in attributes and output.color_mode == 'AUTO':
        values = attributes['Color']
        if values.ndim == 2 and values.shape[1] == 3:
            attributes['bleMD Color'] = values
    if 'bleMD Color' not in attributes or (not output.inputs['Color'].is_linked and output.color_mode == 'UNIFORM'):
        attributes['bleMD Color'] = np.broadcast_to(np.asarray(output.color, dtype=np.float32), (len(positions),3))
    if output.material is None:
        from .bleMDNodes import create_field_material
        output.material = create_field_material()
    obj = write_output(tree, output, scene, positions, attributes)
    tree.frame_count = count
    tree.last_message = f"Updated {len(positions):,} particles at Blender frame {scene.frame_current}"
    tree.has_error = False
    return obj
