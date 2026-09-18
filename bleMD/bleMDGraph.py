"""Compile a bleMD DAG and join particle fields by stable identifiers."""
from dataclasses import dataclass

import bpy
import numpy as np

from .bleMDPipeline import SOURCE_TYPE, SCRIPT_TYPE, OUTPUT_TYPE, SOCKET_TYPE
from .bleMDFields import ANALYSIS_OUTPUTS, SCALAR, VECTOR, TENSOR, COLOR, COLOR_ATTRIBUTE
from . import bleMDUtilities


@dataclass
class Field:
    pipeline: object
    origin: int
    name: str
    kind: str
    operations: tuple = ()
    component: int = -1
    constant: object = None
    expression: object = None
    dependent: bool = True


@dataclass
class Expression:
    node: object
    output: int
    inputs: tuple


def linked_socket(socket):
    if len(socket.links) != 1:
        raise ValueError(f"Connect '{socket.name}' on '{socket.node.name}'")
    source = socket.links[0].from_socket
    seen = set()
    while source.node.bl_idname == 'NodeReroute':
        node = source.node
        if node.as_pointer() in seen:
            raise ValueError('The graph contains a cycle through reroutes')
        seen.add(node.as_pointer())
        if len(node.inputs[0].links) != 1:
            raise ValueError(f"Connect the input on reroute '{node.name}'")
        source = node.inputs[0].links[0].from_socket
    if source.bl_idname != socket.bl_idname:
        raise ValueError(f"'{socket.node.name}' / {socket.name} needs {socket.bl_label}; got {source.bl_label}")
    return source


class Graph:
    def __init__(self, tree):
        from .bleMDFields import migrate_tree
        migrate_tree(tree)
        self.tree = tree
        self.pipelines = {}
        self.origins = {}
        self.fields = {}
        self.active = set()
        self.samples = {}
        self.color_ranges = {}
        self.expression_values = {}
        outputs = [n for n in tree.nodes if n.bl_idname == OUTPUT_TYPE]
        if len(outputs) != 1:
            raise ValueError('Use exactly one Particle Output in each bleMD tree')
        self.output = outputs[0]

    def enter(self, key):
        if key in self.active:
            raise ValueError('The graph contains a cycle; remove the circular connection')
        self.active.add(key)

    def pipeline(self, node):
        from ovito.io import import_file
        from ovito.pipeline import Pipeline
        from .bleMDModifiers import is_modifier_node, append_modifier
        key = node.as_pointer()
        if key in self.pipelines:
            return self.pipelines[key]
        self.enter(key)
        try:
            if node.bl_idname == SOURCE_TYPE:
                if not node.filepath.strip():
                    raise ValueError('Choose a simulation file on the File Source node')
                from .bleMDSource import sync_channels, channel, AVAILABLE
                try:
                    result = import_file(bpy.path.abspath(node.filepath, library=self.tree.library), sort_particles=True)
                    first = result.compute(0)
                    self.samples[(id(result), 0)] = first
                    sync_channels(node, first)
                except Exception as error:
                    node.channels_loaded = True
                    node.channels_error = True
                    node.channels_message = str(error)
                    for socket in node.outputs:
                        if channel(socket):
                            socket[AVAILABLE] = False
                    raise
                origin = key
            elif node.bl_idname == SCRIPT_TYPE or is_modifier_node(node):
                source = linked_socket(node.inputs[0]).node
                upstream = self.pipeline(source)
                origin = self.origins[source.as_pointer()]
                # Independent tails share the upstream graph. Appending an
                # analysis must never change the sibling geometry branch.
                result = Pipeline(head=upstream.head)
                if node.enabled and not node.mute:
                    if is_modifier_node(node):
                        modifier = append_modifier(node, result, self.tree)
                        for name, kind, flag in ANALYSIS_OUTPUTS.get(node.modifier_name, ()):
                            if flag and node.outputs.get(name) and node.outputs[name].is_linked:
                                setattr(modifier, flag, True)
                    else:
                        if node.script is None:
                            raise ValueError(f"Choose a text or disable the OVITO Script node '{node.name}'")
                        namespace = {'pipeline': result, '__name__': '__blemd_script__'}
                        try:
                            exec(compile(node.script.as_string(), node.script.name, 'exec'), namespace)
                            result = namespace['pipeline']
                            if not isinstance(result, Pipeline):
                                raise ValueError("the script must leave 'pipeline' as an OVITO Pipeline")
                        except Exception as error:
                            raise ValueError(f"OVITO Script '{node.name}': {error}") from error
            else:
                raise ValueError(f'Unsupported data node: {node.name}')
            self.pipelines[key] = result
            self.origins[key] = origin
            return result
        finally:
            self.active.remove(key)

    def field(self, socket):
        key = socket.as_pointer()
        if key in self.fields:
            return self.fields[key]
        self.enter(key)
        node = socket.node
        try:
            if node.bl_idname == SOURCE_TYPE:
                from .bleMDSource import PROPERTY, COMPONENT
                name = socket.get(PROPERTY)
                if not name:
                    raise ValueError(f"'{socket.name}' is not a particle field")
                pipeline = self.pipeline(node)
                result = Field(pipeline, self.origins[node.as_pointer()], name, socket.bl_idname,
                               component=socket.get(COMPONENT, -1))
            elif getattr(node, 'modifier_name', None) in ANALYSIS_OUTPUTS:
                if not node.enabled or node.mute:
                    raise ValueError(f"Enable analysis '{node.name}' to use its field outputs")
                pipeline = self.pipeline(node)
                result = Field(pipeline, self.origins[node.as_pointer()], socket.name, socket.bl_idname)
            elif node.bl_idname == 'BleMDReadProperty':
                source = linked_socket(node.inputs[0]).node
                pipeline = self.pipeline(source)
                if not node.property_name.strip():
                    raise ValueError(f"Choose a property on '{node.name}'")
                result = Field(pipeline, self.origins[source.as_pointer()], node.property_name, socket.bl_idname)
            elif node.bl_idname in bleMDUtilities.TYPES:
                if node.mute:
                    raise ValueError(f"Unmute '{node.name}' to use its result")
                output_index = list(node.outputs).index(socket)
                if output_index not in bleMDUtilities.output_indices(node):
                    raise ValueError(f"'{node.name}' has an inactive output; reconnect its active output")
                inputs = tuple(self.field(linked_socket(node.inputs[i])) if node.inputs[i].is_linked
                               else np.asarray(node.inputs[i].default_value, dtype=float)
                               for i in bleMDUtilities.input_indices(node))
                fields = [value for value in inputs if isinstance(value, Field) and value.dependent]
                if fields:
                    pipeline, origin = fields[0].pipeline, fields[0].origin
                    for value in fields[1:]:
                        if value.origin != origin:
                            raise ValueError('Utility inputs must share the same File Source node')
                        if value.pipeline.num_frames != pipeline.num_frames:
                            raise ValueError('Utility inputs have different trajectory lengths')
                else:
                    pipeline, origin = self.output_pipeline()
                result = Field(pipeline, origin, '', socket.bl_idname,
                               expression=Expression(node, output_index, inputs), dependent=bool(fields))
            elif node.bl_idname in {'BleMDColorMap', 'BleMDFieldComponent', 'BleMDCPKColor'}:
                if node.mute:
                    raise ValueError(f"Unmute '{node.name}' to use its field output")
                inputs = [s for s in node.inputs if s.is_linked]
                if not inputs and node.bl_idname == 'BleMDColorMap':
                    pipeline, origin = self.output_pipeline()
                    upstream = Field(pipeline, origin, '', SCALAR, constant=node.inputs['Value'].default_value, dependent=False)
                elif len(inputs) != 1:
                    raise ValueError(f"Connect exactly one field input on '{node.name}'")
                else:
                    upstream = self.field(linked_socket(inputs[0]))
                result = Field(upstream.pipeline, upstream.origin, upstream.name, upstream.kind,
                               upstream.operations + (node,), component=upstream.component, constant=upstream.constant, expression=upstream.expression, dependent=upstream.dependent)
            else:
                raise ValueError(f'Unsupported field node: {node.name}')
            self.fields[key] = result
            return result
        finally:
            self.active.remove(key)

    def compute(self, pipeline, frame):
        key = (id(pipeline), frame)
        if key not in self.samples:
            self.samples[key] = pipeline.compute(frame)
        return self.samples[key]

    def release_samples(self):
        self.samples.clear()
        self.expression_values.clear()

    def expression_result(self, field, frame, data):
        expression = field.expression
        key = (id(expression), frame, id(data))
        if key not in self.expression_values:
            values = []
            for value in expression.inputs:
                if isinstance(value, Field):
                    source, array, _ = self.field_values(value, frame, context_data=data)
                    if value.dependent:
                        array = array[self.align(data, source, value.pipeline.head == field.pipeline.head)]
                    values.append(array)
                else:
                    values.append(np.broadcast_to(value, (data.particles.count,) + value.shape))
            self.expression_values[key] = bleMDUtilities.evaluate(expression.node, expression.output, values, data.particles.count)
        return self.expression_values[key]

    def field_values(self, field, frame, context_data=None):
        data = context_data if not field.dependent and context_data is not None else self.compute(field.pipeline, frame)
        if data.particles is None or (field.expression is None and field.constant is None and field.name not in data.particles):
            raise ValueError(f"Particle field '{field.name}' is missing from the connected dataset")
        values = (self.expression_result(field, frame, data) if field.expression is not None else
                  np.full(data.particles.count, field.constant) if field.constant is not None else
                  np.asarray(data.particles[field.name]))
        if field.component >= 0:
            if values.ndim != 2 or field.component >= values.shape[1]:
                raise ValueError(f"Component {field.component} is missing from particle field '{field.name}'")
            values = values[:, field.component]
        valid = values.dtype.kind in 'biuf'
        if field.kind == SCALAR:
            valid &= values.ndim == 1
        elif field.kind in {VECTOR, COLOR}:
            valid &= values.ndim == 2 and values.shape[1] == 3
        else:
            valid &= values.ndim == 2 and values.shape[1] in {4, 6, 9}
        if not valid:
            raise ValueError(f"'{field.name}' does not match the connected particle field type")
        color_value = None
        for index, node in enumerate(field.operations):
            if node.bl_idname == 'BleMDFieldComponent':
                if node.operation == 'NORM':
                    values = np.linalg.norm(values, axis=1)
                else:
                    if node.component >= values.shape[1]:
                        raise ValueError(f"Component {node.component} is outside '{field.name}' ({values.shape[1]} components)")
                    values = values[:, node.component]
            elif node.bl_idname == 'BleMDCPKColor':
                from .bleMDCPK import colors
                # Only a direct property retains its type-name metadata. Math
                # expressions/component extraction require an explicit mapping.
                prop = data.particles[field.name] if index == 0 and field.expression is None and field.component < 0 and field.name else None
                values = colors(node, values, prop)
            else:
                if not np.all(np.isfinite(values)):
                    raise ValueError(f"Color Map '{node.name}': input contains non-finite values")
                color_value = values
                if node.range_mode == 'FIRST_FRAME':
                    key = node.as_pointer()
                    if key not in self.color_ranges:
                        preceding = Field(field.pipeline, field.origin, field.name, field.kind,
                                          field.operations[:index], component=field.component, constant=field.constant, expression=field.expression, dependent=field.dependent)
                        reference = self.field_values(preceding, 0, context_data=context_data)[1]
                        if not np.all(np.isfinite(reference)):
                            raise ValueError(f"Color Map '{node.name}': first frame contains non-finite values")
                        bounds = (float(np.min(reference)), float(np.max(reference))) if reference.size else (0., 1.)
                        self.color_ranges[key] = bounds
                        node.minimum, node.maximum = bounds
                    minimum, maximum = self.color_ranges[key]
                    # A uniform field has no range; display the midpoint color.
                    fraction = np.full(len(values), .5) if maximum == minimum else np.clip((values - minimum) / (maximum - minimum), 0, 1)
                else:
                    if node.maximum <= node.minimum:
                        raise ValueError(f"Color Map '{node.name}': Maximum must exceed Minimum")
                    fraction = np.clip((values - node.minimum) / (node.maximum - node.minimum), 0, 1)
                from .bleMDPalette import sample
                values = sample(node.palette, fraction, node.low_color, node.high_color)
        return data, values, color_value

    @staticmethod
    def align(target, source, same_head):
        target_ids = target.particles.identifiers
        source_ids = source.particles.identifiers
        if target_ids is None or source_ids is None:
            if same_head and target.particles.count == source.particles.count:
                return np.arange(target.particles.count)
            raise ValueError('Joining analysis branches requires Particle Identifier on both datasets')
        ids, other = np.asarray(target_ids), np.asarray(source_ids)
        if len(np.unique(ids)) != len(ids) or len(np.unique(other)) != len(other):
            raise ValueError('Particle identifiers must be unique when joining analysis fields')
        if np.array_equal(ids, other):
            return slice(None)
        order = np.argsort(other)
        indices = np.searchsorted(other[order], ids)
        if np.any(indices >= len(other)) or not np.array_equal(other[order][indices], ids):
            raise ValueError('Analysis field is missing particle identifiers required by Particle Output')
        return order[indices]

    def output_pipeline(self):
        source = linked_socket(self.output.inputs[0]).node
        return self.pipeline(source), self.origins[source.as_pointer()]

    def sample_output(self, pipeline, origin, frame):
        data = self.compute(pipeline, frame)
        if data.particles is None:
            raise ValueError('The pipeline has no particles')
        result = data.clone()
        from .bleMDFields import output_bindings
        for socket, attribute in output_bindings(self.output):
            if not socket.is_linked:
                value = np.asarray(socket.default_value, dtype=np.float32)
                result.particles_.create_property(attribute, data=np.broadcast_to(value, (data.particles.count,) + value.shape))
                continue
            field = self.field(linked_socket(socket))
            if field.origin != origin:
                raise ValueError('Particle data and analysis fields must share the same File Source node')
            if field.pipeline.num_frames != pipeline.num_frames:
                raise ValueError('Particle data and analysis fields have different trajectory lengths')
            source, values, color_value = self.field_values(field, frame)
            order = self.align(data, source, field.pipeline.head == pipeline.head)
            values = values[order]
            if attribute == 'bleMD Radius':
                values = np.asarray(values, dtype=np.float32) * self.output.radius_scale
                if not np.all(np.isfinite(values)) or np.any(values < 0):
                    raise ValueError('Particle radii must be finite and nonnegative')
            result.particles_.create_property(attribute, data=values)
            if color_value is not None and attribute == COLOR_ATTRIBUTE:
                result.particles_.create_property('bleMD Color Value', data=color_value[order])
        return result
