"""Discover and persist typed File Source outputs without discarding wired fields."""
import hashlib

import bpy
import numpy as np

from .bleMDFields import SCALAR, VECTOR, TENSOR, COLOR

PROPERTY = 'bleMD_source_property'
COMPONENT = 'bleMD_source_component'
AVAILABLE = 'bleMD_source_available'
ALIASES = {'Particle Identifier': 'Atom ID', 'Particle Type': 'Atom Type'}


def label(name):
    if name in ALIASES:
        return ALIASES[name]
    return name + ' (property)' if name in {'Data', *ALIASES.values()} else name


def channel(socket):
    name = socket.get(PROPERTY, '')
    return (name, socket.bl_idname, socket.get(COMPONENT, -1)) if name else None


def add_channel(node, name, kind, component=-1, display=None):
    key = f'{name}\0{kind}\0{component}'
    identifier = 'field_' + hashlib.sha1(key.encode()).hexdigest()[:20]
    socket = node.outputs.new(kind, display or label(name), identifier=identifier)
    socket[PROPERTY] = name
    socket[COMPONENT] = component
    socket[AVAILABLE] = True
    return socket


def ensure_atom_id(node):
    key = ('Particle Identifier', SCALAR, -1)
    existing = next((s for s in node.outputs if channel(s) == key), None)
    return existing if existing is not None else add_channel(node, *key)


def descriptors(data):
    if data.particles is None:
        return []  # Data may still contain meshes, bonds, or tables for scripts.
    specs = []
    for name in data.particles.keys():
        prop = data.particles[name]
        values = np.asarray(prop)
        if values.dtype.kind not in 'biuf':
            continue
        if values.ndim == 1:
            specs.append((name, SCALAR, -1, label(name)))
        elif values.ndim == 2:
            width = values.shape[1]
            if width == 3:
                specs.append((name, COLOR if name == 'Color' else VECTOR, -1, label(name)))
            elif width in {4, 6, 9}:
                specs.append((name, TENSOR, -1, label(name)))
            else:
                names = list(prop.component_names)
                for index in range(width):
                    suffix = names[index] if index < len(names) and names[index] else str(index)
                    specs.append((name, SCALAR, index, f'{label(name)}.{suffix}'))
    priority = {'Particle Identifier': 0, 'Particle Type': 1, 'Position': 2}
    return sorted(specs, key=lambda s: (priority.get(s[0], 3), s[0].casefold(), s[2]))


def sync_channels(node, data):
    specs = descriptors(data)
    wanted = {spec[:3] for spec in specs}
    existing = {channel(s): s for s in node.outputs if channel(s)}
    for key, socket in list(existing.items()):
        if key not in wanted:
            # A missing or differently typed field keeps its links. Evaluation
            # will report the missing data/type, rather than silently rewiring.
            if socket.is_linked:
                socket[AVAILABLE] = False
            else:
                node.outputs.remove(socket)
                del existing[key]
    for name, kind, component, display in specs:
        key = (name, kind, component)
        socket = existing.get(key)
        if socket is None:
            socket = add_channel(node, name, kind, component, display)
        socket[AVAILABLE] = True
    node.channels_loaded = True
    node.channels_error = False
    missing = sum(not s.get(AVAILABLE, True) for s in node.outputs if channel(s))
    node.channels_message = f'{len(specs)} particle fields' + (f'; {missing} connected fields unavailable' if missing else '')


def inspect_source(node, context=None):
    """Called on file choice or explicit refresh; never creates an output mesh."""
    if not node.filepath.strip():
        node.channels_loaded = False
        node.channels_error = False
        node.channels_message = 'Choose a file to discover particle fields'
        return False
    try:
        from ovito.io import import_file
        pipeline = import_file(bpy.path.abspath(node.filepath, library=node.id_data.library), sort_particles=True)
        sync_channels(node, pipeline.compute(0))
        return True
    except Exception as error:
        node.channels_loaded = True
        node.channels_error = True
        node.channels_message = str(error)
        for socket in node.outputs:
            if channel(socket):
                socket[AVAILABLE] = False
        return False


def source_changed(node, context):
    # File selection can involve expensive I/O. The live evaluator discovers
    # fields once, on the main-thread timer, unless updates are suppressed.
    from . import bleMDLive
    bleMDLive.invalidate(node.id_data)
    node.channels_loaded = False
    node.channels_error = False
    node.channels_message = ('Fields pending automatic update' if node.id_data.automatic_updates
                             else 'Updates paused; use Refresh Fields or Update')
