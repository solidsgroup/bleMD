"""OVITO's installed modifier catalog, parameter adapters, and native nodes.

Names and categories come from OVITO itself. Only user-overridden parameters
are assigned, preserving OVITO's defaults and pipeline initialization behavior.
"""

import json
import hashlib
import re
from dataclasses import dataclass

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, IntVectorProperty, PointerProperty, StringProperty

from .bleMDPipeline import TREE_TYPE, SOCKET_TYPE
from .bleMDFields import ANALYSIS_OUTPUTS, sync_analysis_sockets

CATEGORY_ORDER = ('Analysis', 'Coloring', 'Modification', 'Selection',
                  'Structure identification', 'Visualization', 'Python-based modifiers')
CATALOG = {}
NODE_CLASSES = []
IGNORED = {'enabled', 'title', 'delegate', 'some_modification_node', 'object_title',
           'code_template_path', 'working_dir', 'function', 'kwargs', 'reference', 'source'}
# Obsolete spellings otherwise expose duplicate controls for the same value.
ALIASES = {'SliceModifier': {'slice_width'}, 'AtomicStrainModifier': {'eliminate_cell_deformation'},
           'CalculateDisplacementsModifier': {'eliminate_cell_deformation'}}


@dataclass
class Parameter:
    path: tuple
    kind: str
    default: object
    label: str
    description: str = ''
    choices: tuple = ()
    shape: tuple = ()
    enum_type: object = None
    color: bool = False

    @property
    def key(self):
        return '.'.join(str(item) for item in self.path)

    @property
    def storage_key(self):
        # Stable across OVITO releases that insert or remove other parameters.
        return hashlib.sha1(self.key.encode()).hexdigest()[:12]


def member(obj, key):
    return obj[key] if isinstance(key, int) else getattr(obj, key)


def set_member(obj, path, value):
    for part in path[:-1]:
        obj = member(obj, part)
    if isinstance(path[-1], int):
        obj[path[-1]] = value
    else:
        setattr(obj, path[-1], value)


def label_for(name):
    return str(name).replace('_', ' ').capitalize()


def properties(obj):
    # Python-based ModifierInterface implementations use Traits rather than
    # pybind11 property descriptors.
    if hasattr(obj, 'trait_get'):
        return [(key, getattr(obj, key), '', obj.trait(key).label)
                for key in obj.trait_get() if not key.startswith('_')]
    result = []
    for key in dir(type(obj)):
        if key.startswith('_'):
            continue
        descriptor = getattr(type(obj), key)
        if isinstance(descriptor, property) and descriptor.fset:
            try:
                value = getattr(obj, key)
            except Exception:
                continue
            result.append((key, value, descriptor.__doc__ or '', None))
    return result


def parameters(obj, path=(), depth=0):
    result = []
    for key, value, doc, label in properties(obj):
        ignored = IGNORED if not path else IGNORED - {'enabled', 'title'}
        if key in ignored or (not path and key in ALIASES.get(type(obj).__name__, set())):
            continue
        route = path + (key,)
        description = re.sub(r'\s+', ' ', doc).strip()[:900]
        spec = Parameter(route, '', value, label or label_for(key), description)
        enum_members = getattr(type(value), '__members__', None)
        if enum_members:
            spec.kind = 'ENUM'
            spec.enum_type = type(value)
            spec.choices = tuple(enum_members)
            spec.default = next(name for name, item in enum_members.items() if item == value)
        elif isinstance(value, bool):
            spec.kind = 'BOOL'
        elif isinstance(value, int):
            if not -(2**31) <= value < 2**31:
                continue
            spec.kind = 'INT'
        elif isinstance(value, float):
            spec.kind = 'FLOAT'
        elif isinstance(value, str):
            spec.kind = 'STRING'
        elif isinstance(value, np.ndarray) and value.dtype.kind in 'fiu' and 1 <= value.size <= 32:
            spec.kind = 'VECTOR'
            spec.shape = value.shape
            spec.default = tuple(float(v) for v in value.ravel())
            spec.color = 'color' in key and value.shape == (3,)
        elif isinstance(value, tuple) and value and all(type(v) is int for v in value) and len(value) <= 32:
            spec.kind = 'INT_VECTOR'
            spec.shape = (len(value),)
        elif isinstance(value, tuple) and value and all(isinstance(v, (int, float)) for v in value) and len(value) <= 32:
            spec.kind = 'VECTOR'
            spec.shape = (len(value),)
            spec.color = 'color' in key and len(value) == 3
        elif value is None and key in {'interval', 'frame_interval'}:
            spec.kind = 'JSON'
            spec.default = 'null'
        elif isinstance(value, (tuple, list, set)) or type(value).__name__ in {'ModifierDelegatesList', 'TypeSelectionSet'}:
            try:
                spec.default = json.dumps(sorted(value) if isinstance(value, set) or type(value).__name__ in {'ModifierDelegatesList', 'TypeSelectionSet'} else list(value))
                spec.kind = 'JSON'
            except TypeError:
                pass
        if spec.kind:
            result.append(spec)
        elif depth < 2 and value is not None and key != 'gradient':
            nested = parameters(value, route, depth + 1)
            if not nested and key == 'structures':
                for index, item in enumerate(value):
                    nested.extend(parameters(item, route + (index,), depth + 1))
            result.extend(nested)
    return result


def discover():
    import ovito.modifiers as modifiers
    from ovito.pipeline import Modifier, ModifierInterface
    found = {}
    for name in dir(modifiers):
        cls = getattr(modifiers, name)
        if not isinstance(cls, type) or not issubclass(cls, (Modifier, ModifierInterface)):
            continue
        canonical = cls.__name__
        if canonical in found:
            continue
        try:
            instance = cls()
        except TypeError:
            # E.g. the abstract StructureIdentificationModifier base class.
            continue
        if isinstance(instance, Modifier):
            meta = instance._ovito_class
            label = meta.display_name
            category = meta.class_metadata('ModifierCategory') or 'Other modifiers'
            description = meta.description_string
        else:
            label = {'IdentifyFCCPlanarFaultsModifier': 'Identify fcc planar faults',
                     'RenderLAMMPSRegionsModifier': 'Render LAMMPS regions'}.get(canonical)
            label = label or re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', canonical.removesuffix('Modifier'))
            category = 'Python-based modifiers'
            description = cls.__doc__ or label
        found[canonical] = dict(cls=cls, label=label, category=category,
                                description=description, parameters=parameters(instance),
                                secondary='reference' if hasattr(instance, 'reference') else 'source' if hasattr(instance, 'source') else None)
    return found


def changed(index):
    def update(node, context):
        setattr(node, f'use_{index}', True)
    return update


def annotation(spec, index):
    kw = dict(name=spec.label, description=spec.description or spec.key, update=changed(index))
    if spec.kind == 'BOOL':
        return BoolProperty(default=spec.default, **kw)
    if spec.kind == 'INT':
        return IntProperty(default=spec.default, **kw)
    if spec.kind == 'FLOAT':
        return FloatProperty(default=spec.default, precision=5, **kw)
    if spec.kind in {'STRING', 'JSON'}:
        return StringProperty(default=spec.default, **kw)
    if spec.kind == 'ENUM':
        return EnumProperty(items=[(s, s, s) for s in spec.choices], default=spec.default, **kw)
    if spec.kind == 'INT_VECTOR':
        return IntVectorProperty(size=len(spec.default), default=spec.default, **kw)
    if spec.kind == 'VECTOR':
        return FloatVectorProperty(size=len(spec.default), default=spec.default,
                                   subtype='COLOR' if spec.color else 'NONE', **kw)
    raise ValueError(spec.kind)


def draw_parameters(node, layout, detailed):
    record = CATALOG[node.modifier_name]
    previous = None
    for index, spec in enumerate(record['parameters']):
        index = spec.storage_key
        if len(spec.path) > 1 and not detailed:
            continue
        prefix = '.'.join(map(str, spec.path[:-1]))
        if prefix and prefix != previous:
            layout.label(text=prefix)
        previous = prefix
        row = layout.row(align=True)
        row.prop(node, f'use_{index}', text='')
        row.prop(node, f'value_{index}', text=spec.label)
    if not detailed and any(len(p.path) > 1 for p in record['parameters']):
        layout.label(text='Nested settings in node sidebar')


class ModifierNode:
    @classmethod
    def poll(cls, tree):
        return tree.bl_idname == TREE_TYPE

    def init(self, context):
        self.width = 300
        self.inputs.new(SOCKET_TYPE, 'Data')
        if self.modifier_name in ANALYSIS_OUTPUTS:
            sync_analysis_sockets(self)
        else:
            self.outputs.new(SOCKET_TYPE, 'Data')

    def draw_buttons(self, context, layout):
        layout.prop(self, 'enabled')
        if self.modifier_name in ANALYSIS_OUTPUTS:
            layout.prop(self, 'expose_dataset')
            layout.label(text='Connected results computed on Update')
        record = CATALOG[self.modifier_name]
        if record['secondary']:
            layout.prop(self, 'secondary_file', text='Reference file' if record['secondary'] == 'reference' else 'Source file')
        if self.modifier_name == 'ManualSelectionModifier':
            layout.prop(self, 'selection_ids')
            layout.prop(self, 'selection_frame')
        if self.modifier_name == 'PythonModifier':
            layout.prop(self, 'function_text', text='Python text')
            layout.label(text='Define modify(frame, data)')
        if self.modifier_name == 'ColorCodingModifier':
            layout.prop(self, 'gradient_name')
        layout.prop(self, 'show_parameters', icon='TRIA_DOWN' if self.show_parameters else 'TRIA_RIGHT', emboss=False)
        if self.show_parameters:
            layout.label(text='Checked = override OVITO default')
            draw_parameters(self, layout, False)
        layout.prop(self, 'configuration', text='Configure')
        layout.operator('blemd.modifier_configuration', text='New Configuration', icon='TEXT').node_name = self.name

    def draw_buttons_ext(self, context, layout):
        self.draw_buttons(context, layout)
        layout.label(text='All parameters (checked = override)')
        draw_parameters(self, layout, True)


def gradient_names():
    from ovito.modifiers import ColorCodingModifier
    names = []
    for name, cls in vars(ColorCodingModifier).items():
        if isinstance(cls, type) and issubclass(cls, ColorCodingModifier.ColorCodingGradient):
            try:
                cls()
                names.append(name)
            except TypeError:
                pass
    return names


def register():
    if NODE_CLASSES:
        for cls in NODE_CLASSES:
            bpy.utils.register_class(cls)
        return
    CATALOG.update(discover())
    for name, record in CATALOG.items():
        props = {
            'expose_dataset': BoolProperty(name='Expose full dataset', default=False,
                description='Optional data output for chaining OVITO modifiers; analysis results also have individual field outputs',
                update=sync_analysis_sockets),
            'enabled': BoolProperty(name='Enabled', default=True),
            'show_parameters': BoolProperty(name='Parameters', default=True),
            'configuration': PointerProperty(type=bpy.types.Text, name='Configuration'),
            'secondary_file': StringProperty(subtype='FILE_PATH'),
            'function_text': PointerProperty(type=bpy.types.Text),
            'selection_ids': StringProperty(name='Particle IDs', description='Comma-separated particle identifiers to select'),
            'selection_frame': IntProperty(name='Selection Frame', default=0, min=0),
        }
        if name == 'ColorCodingModifier':
            props['gradient_name'] = EnumProperty(name='Gradient', items=[('DEFAULT', 'OVITO default', '')] + [(n,n,n) for n in gradient_names()], default='DEFAULT')
        for index, spec in enumerate(record['parameters']):
            index = spec.storage_key
            props[f'value_{index}'] = annotation(spec, index)
            props[f'use_{index}'] = BoolProperty(name='Override', description='Use the value shown instead of OVITO\'s initialized default', default=False)
        cls = type(f'BleMD_{name}', (ModifierNode, bpy.types.Node), {
            '__module__': __name__, '__annotations__': props,
            'bl_idname': f'BleMD_{name}', 'bl_label': record['label'],
            'bl_description': record['description'][:1000], 'modifier_name': name,
        })
        globals()[cls.__name__] = cls
        bpy.utils.register_class(cls)
        NODE_CLASSES.append(cls)


def unregister():
    for cls in reversed(NODE_CLASSES):
        bpy.utils.unregister_class(cls)
    # Keep generated RNA definitions (including enum strings) alive just as
    # module-level, statically declared classes are kept alive after unregister.


def is_modifier_node(node):
    return getattr(node, 'modifier_name', None) in CATALOG


def parameter_value(node, index, spec):
    value = getattr(node, f'value_{index}')
    if spec.kind == 'ENUM':
        return spec.enum_type.__members__[value]
    if spec.kind == 'JSON':
        value = json.loads(value)
        return set(value) if spec.path[-1] in {'operate_on', 'types'} else value
    if spec.kind == 'VECTOR':
        return np.asarray(value).reshape(spec.shape)
    if spec.kind == 'INT_VECTOR':
        return tuple(value)
    return value


def append_modifier(node, pipeline, tree):
    record = CATALOG[node.modifier_name]
    try:
        modifier = record['cls']()
        for index, spec in enumerate(record['parameters']):
            index = spec.storage_key
            if getattr(node, f'use_{index}'):
                try:
                    set_member(modifier, spec.path, parameter_value(node, index, spec))
                except Exception as error:
                    raise ValueError(f'{spec.key}: {error}') from error
        if node.secondary_file:
            from ovito.pipeline import FileSource
            source = getattr(modifier, record['secondary'])
            if source is None:
                source = FileSource()
                setattr(modifier, record['secondary'], source)
            source.load(bpy.path.abspath(node.secondary_file, library=tree.library))
        if node.modifier_name == 'ColorCodingModifier' and node.gradient_name != 'DEFAULT':
            modifier.gradient = getattr(record['cls'], node.gradient_name)()
        if node.modifier_name == 'PythonModifier' and node.function_text:
            namespace = {'__name__': '__blemd_modifier__'}
            exec(compile(node.function_text.as_string(), node.function_text.name, 'exec'), namespace)
            function = namespace.get('modify')
            if not callable(function):
                raise ValueError('Python text must define modify(frame, data)')
            modifier.function = function
        pipeline.modifiers.append(modifier)
        if node.modifier_name == 'ManualSelectionModifier' and node.selection_ids.strip():
            ids = {int(value.strip()) for value in node.selection_ids.split(',') if value.strip()}
            application = modifier.some_modification_node
            upstream = application.input
            data = upstream.compute(node.selection_frame)
            if data.particles is None or data.particles.identifiers is None:
                raise ValueError('Manual selection by ID requires Particle Identifier')
            available = np.asarray(data.particles.identifiers)
            missing = ids - set(available.tolist())
            if missing:
                raise ValueError(f'Particle IDs are absent at the selection frame: {sorted(missing)}')
            state = upstream._evaluate(upstream.source_frame_to_anim_time(node.selection_frame))
            modifier.clear_selection(application, state)
            for index, identifier in enumerate(available):
                if int(identifier) in ids:
                    modifier.toggle_selection(application, state, index)
        if node.configuration:
            namespace = {'modifier': modifier, 'pipeline': pipeline,
                         '__name__': '__blemd_configuration__'}
            exec(compile(node.configuration.as_string(), node.configuration.name, 'exec'), namespace)
        return modifier
    except Exception as error:
        raise ValueError(f"{record['label']} '{node.name}': {error}") from error
