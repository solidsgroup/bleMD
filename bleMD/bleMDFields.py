"""Particle-field signatures and Blender field nodes.

Fields retain their OVITO dataset and particle identity until they are joined
at Particle Output. A tensor is never silently truncated to a Blender vector.
"""
import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty

from .bleMDPipeline import TREE_TYPE, SOCKET_TYPE
from .bleMDPalette import FIELD_ITEMS

SCALAR = 'BleMDScalarSocket'
VECTOR = 'BleMDVectorSocket'
TENSOR = 'BleMDTensorSocket'
COLOR = 'BleMDColorSocket'
FIELD_TYPES = (SCALAR, VECTOR, TENSOR, COLOR)
COLOR_ATTRIBUTE = 'bleMD Color'

# (native property, socket type, native flag required to produce the property).
ANALYSIS_OUTPUTS = {
    'AtomicStrainModifier': (
        ('Shear Strain', SCALAR, None), ('Volumetric Strain', SCALAR, None),
        ('Strain Tensor', TENSOR, 'output_strain_tensors'),
        ('Deformation Gradient', TENSOR, 'output_deformation_gradients'),
        ('Stretch Tensor', TENSOR, 'output_stretch_tensors'),
        ('Rotation', TENSOR, 'output_rotations'),
        ('Nonaffine Squared Displacement', SCALAR, 'output_nonaffine_squared_displacements'),
        ('Selection', SCALAR, 'select_invalid_particles')),
    'CalculateDisplacementsModifier': (
        ('Displacement', VECTOR, None), ('Displacement Magnitude', SCALAR, None)),
    'CentroSymmetryModifier': (('Centrosymmetry', SCALAR, None),),
    'CoordinationAnalysisModifier': (('Coordination', SCALAR, None),),
    'CommonNeighborAnalysisModifier': (('Structure Type', SCALAR, None),),
    'AcklandJonesModifier': (('Structure Type', SCALAR, None),),
    'IdentifyDiamondModifier': (('Structure Type', SCALAR, None),),
    'ElasticStrainModifier': (
        ('Volumetric Strain', SCALAR, None), ('Structure Type', SCALAR, None),
        ('Elastic Strain', TENSOR, 'calculate_strain_tensors'),
        ('Elastic Deformation Gradient', TENSOR, 'calculate_deformation_gradients')),
}


def sync_analysis_sockets(node, context=None):
    specs = ANALYSIS_OUTPUTS.get(node.modifier_name)
    if specs is None:
        return
    dataset = next((s for s in node.outputs if s.bl_idname == SOCKET_TYPE), None)
    if node.expose_dataset and dataset is None:
        dataset = node.outputs.new(SOCKET_TYPE, 'Data')
        node.outputs.move(len(node.outputs) - 1, 0)
    elif not node.expose_dataset and dataset is not None:
        node.outputs.remove(dataset)
    for name, kind, flag in specs:
        if name not in node.outputs:
            node.outputs.new(kind, name)


def migrate_tree(tree):
    """Add new sockets without destroying the links in pre-field .blend files."""
    for node in tree.nodes:
        if node.bl_idname == 'BleMDFileSource' and not node.get('bleMD_timing_version'):
            if not node.is_property_set('start_frame'):
                node.start_frame = tree.start_frame
            if not node.is_property_set('timesteps_per_frame'):
                node.timesteps_per_frame = tree.frame_stride
            node['bleMD_timing_version'] = 1
        if node.bl_idname == 'BleMDFileSource' and not node.channels_loaded and not any(s.get('bleMD_source_property') for s in node.outputs):
            from .bleMDSource import ensure_atom_id
            ensure_atom_id(node)
        if getattr(node, 'modifier_name', None) in ANALYSIS_OUTPUTS:
            if any(s.bl_idname == SOCKET_TYPE for s in node.outputs):
                node.expose_dataset = True
            sync_analysis_sockets(node)
        if node.bl_idname == 'BleMDParticleOutput':
            for name, kind in (('Color', COLOR), ('Value', SCALAR), ('Vector', VECTOR), ('Radius', SCALAR)):
                if name not in node.inputs:
                    node.inputs.new(kind, name)
            radius_index = list(node.inputs).index(node.inputs['Radius'])
            if radius_index != 1:
                node.inputs.move(radius_index, 1)
            if not node.get('bleMD_socket_defaults'):
                node.inputs['Radius'].default_value = node.get('radius', 1.)
                mode = node.color_mode
                node.inputs['Color'].default_value = node.get('color', (.6,.6,.6))
                node.color_mode = mode
                node['bleMD_socket_defaults'] = 1


def color_default_changed(socket, context):
    node = socket.node
    if not socket.is_output and node.bl_idname == 'BleMDParticleOutput' and socket.name == 'Color':
        node.color_mode = 'UNIFORM'


def radius_get(node):
    socket = node.inputs.get('Radius')
    return socket.default_value if socket else node.get('radius', 1.)


def radius_set(node, value):
    socket = node.inputs.get('Radius')
    if socket:
        socket.default_value = value
    else:
        node['radius'] = value


def color_get(node):
    socket = node.inputs.get('Color')
    return tuple(socket.default_value) if socket else node.get('color', (.6,.6,.6))


def color_set(node, value):
    socket = node.inputs.get('Color')
    if socket:
        socket.default_value = value
    else:
        node['color'] = value


class FieldSocket:
    def draw(self, context, layout, node, text):
        missing = node.bl_idname == 'BleMDFileSource' and getattr(node, 'channels_loaded', False) and not self.get('bleMD_source_available', True)
        label = self.get('bleMD_export_name', text)
        editable = (not self.is_output and not self.is_linked and hasattr(self, 'default_value')
                    and (node.bl_idname in {'BleMDParticleOutput', 'BleMDColorMap'} or getattr(node, 'blemd_utility', False)))
        if editable:
            layout.prop(self, 'default_value', text=label)
        else:
            layout.label(text=label + (' (unavailable)' if missing else ''))


class BleMDScalarSocket(FieldSocket, bpy.types.NodeSocket):
    bl_idname = SCALAR
    bl_label = 'Particle Scalar'
    default_value: FloatProperty(name='Value', default=0)

    @classmethod
    def draw_color_simple(cls):
        return (0.65, 0.65, 0.65, 1)


class BleMDVectorSocket(FieldSocket, bpy.types.NodeSocket):
    bl_idname = VECTOR
    bl_label = 'Particle Vector'
    default_value: FloatVectorProperty(name='Vector', size=3, default=(0,0,0))

    @classmethod
    def draw_color_simple(cls):
        return (0.35, 0.4, 0.85, 1)


class BleMDTensorSocket(FieldSocket, bpy.types.NodeSocket):
    bl_idname = TENSOR
    bl_label = 'Particle Tensor / Quaternion'

    @classmethod
    def draw_color_simple(cls):
        return (0.65, 0.3, 0.8, 1)


class BleMDColorSocket(FieldSocket, bpy.types.NodeSocket):
    bl_idname = COLOR
    bl_label = 'Particle Color'
    default_value: FloatVectorProperty(name='Color', subtype='COLOR', size=3, min=0, max=1, default=(.6,.6,.6), update=color_default_changed)

    @classmethod
    def draw_color_simple(cls):
        return (0.85, 0.7, 0.15, 1)


class FieldNode:
    @classmethod
    def poll(cls, tree):
        return tree.bl_idname == TREE_TYPE


READ_TYPES = [('SCALAR', 'Scalar', ''), ('VECTOR', 'Vector', ''),
              ('TENSOR', 'Tensor / Quaternion', ''), ('COLOR', 'Color', '')]
TYPE_IDS = dict(zip(('SCALAR', 'VECTOR', 'TENSOR', 'COLOR'), FIELD_TYPES))


def read_type_changed(node, context):
    kind = TYPE_IDS[node.field_type]
    if node.outputs and node.outputs[0].bl_idname == kind:
        return
    node.outputs.clear()
    node.outputs.new(kind, 'Field')


class BleMDReadProperty(FieldNode, bpy.types.Node):
    bl_idname = 'BleMDReadProperty'
    bl_label = 'Read Particle Property'
    property_name: StringProperty(name='Property', default='c_energy')
    field_type: EnumProperty(name='Type', items=READ_TYPES, default='SCALAR', update=read_type_changed)

    def init(self, context):
        self.width = 240
        self.inputs.new(SOCKET_TYPE, 'Data')
        self.outputs.new(SCALAR, 'Field')

    def draw_buttons(self, context, layout):
        layout.prop(self, 'property_name')
        layout.prop(self, 'field_type')


class BleMDColorMap(FieldNode, bpy.types.Node):
    bl_idname = 'BleMDColorMap'
    bl_label = 'Color Map'
    palette: EnumProperty(name='Colorbar', items=FIELD_ITEMS, default='CUSTOM')
    range_mode: EnumProperty(name='Range', items=[
        ('FIXED', 'Manual range', 'Use the specified minimum and maximum'),
        ('FIRST_FRAME', 'First-frame range', 'Use the input field range at simulation frame 0; keep the scale stable during playback'),
    ], default='FIXED')
    minimum: FloatProperty(name='Minimum', default=0)
    maximum: FloatProperty(name='Maximum', default=1)
    low_color: FloatVectorProperty(name='Low', subtype='COLOR', size=3, min=0, max=1, default=(0.02, 0.08, 0.8))
    high_color: FloatVectorProperty(name='High', subtype='COLOR', size=3, min=0, max=1, default=(0.9, 0.03, 0.01))

    def init(self, context):
        self.width = 220
        self.inputs.new(SCALAR, 'Value')
        self.outputs.new(COLOR, 'Color')

    def draw_buttons(self, context, layout):
        layout.prop(self, 'range_mode', text='')
        limits = layout.column()
        limits.enabled = self.range_mode == 'FIXED'
        limits.prop(self, 'minimum')
        limits.prop(self, 'maximum')
        layout.prop(self, 'palette', text='')
        if self.palette == 'CUSTOM':
            layout.prop(self, 'low_color')
            layout.prop(self, 'high_color')
        layout.label(text='Clamp at endpoints')


class BleMDCPKColor(FieldNode, bpy.types.Node):
    bl_idname = 'BleMDCPKColor'
    bl_label = 'CPK Color'
    input_mode: EnumProperty(name='Input', items=[
        ('TYPES', 'Atom types', 'Read chemical symbols from the connected property’s type names; explicit mappings override them'),
        ('ATOMIC_NUMBER', 'Atomic numbers', 'Interpret input as atomic number: H=1, C=6, N=7, O=8'),
    ], default='TYPES')
    type_mapping: StringProperty(name='Type mapping', default='',
        description='Optional type-ID overrides, e.g. 1=C, 2=O, 3=Fe; element symbols are case-sensitive')
    fallback_color: FloatVectorProperty(name='Unmapped', subtype='COLOR', size=3,
        min=0, max=1, default=(1,0,1), description='Color for unnamed, unknown, or unsupported elements')

    def init(self, context):
        self.width = 260
        self.inputs.new(SCALAR, 'Element')
        self.outputs.new(COLOR, 'Color')

    def draw_buttons(self, context, layout):
        layout.label(text='Jmol CPK colors')
        layout.prop(self, 'input_mode', text='')
        if self.input_mode == 'TYPES':
            layout.prop(self, 'type_mapping', text='Map')
            layout.label(text='Type names or 1=C, 2=O')
        else:
            layout.label(text='Atomic number: C=6, O=8')
        layout.prop(self, 'fallback_color')


class BleMDFieldComponent(FieldNode, bpy.types.Node):
    bl_idname = 'BleMDFieldComponent'
    bl_label = 'Field Component'
    component: IntProperty(name='Component', default=0, min=0, max=8, description='Zero-based OVITO component index; symmetric tensors: XX, YY, ZZ, XY, XZ, YZ; quaternions: X, Y, Z, W')
    operation: EnumProperty(name='Operation', items=[('COMPONENT', 'Component', ''), ('NORM', 'Component norm', 'Euclidean norm of the stored components')])

    def init(self, context):
        self.width = 220
        self.inputs.new(VECTOR, 'Vector')
        self.inputs.new(TENSOR, 'Tensor / Quaternion')
        self.outputs.new(SCALAR, 'Value')

    def draw_buttons(self, context, layout):
        layout.prop(self, 'operation')
        if self.operation == 'COMPONENT':
            layout.prop(self, 'component')
        layout.label(text='Connect one input')


SOCKET_CLASSES = (BleMDScalarSocket, BleMDVectorSocket, BleMDTensorSocket, BleMDColorSocket)
NODE_CLASSES = (BleMDReadProperty, BleMDColorMap, BleMDCPKColor, BleMDFieldComponent)


def output_bindings(node):
    """Socket/attribute pairs, including user-named shader fields."""
    bindings = [(node.inputs.get(name), attr) for name, attr in
                (('Color', 'bleMD Color'), ('Radius', 'bleMD Radius'),
                 ('Value', 'bleMD Value'), ('Vector', 'bleMD Vector'))]
    used = {attr for _,attr in bindings} | {'Position', 'position', 'Particle Identifier', 'bleMD Color Value'}
    for socket in node.inputs:
        if 'bleMD_export_name' not in socket:
            continue
        name = socket['bleMD_export_name'].strip()
        if not name or name in used or name.startswith('.') or ',' in name:
            raise ValueError(f"Shader field '{name}' needs a unique, non-reserved attribute name")
        used.add(name)
        bindings.append((socket, name))
    return [(socket,name) for socket,name in bindings if socket is not None and
            (socket.is_linked or 'bleMD_export_name' in socket or
             (socket.name in {'Value','Vector'} and socket.is_property_set('default_value')))]
