"""Blender-style utilities evaluated on identity-carrying particle fields."""
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty
from .bleMDFields import FieldNode, SCALAR, VECTOR, COLOR

# Keep Blender's operation names and ordering. Socket kinds remain bleMD fields.
MATH_ITEMS = [(e.identifier,e.name,e.description) for e in bpy.types.ShaderNodeMath.bl_rna.properties['operation'].enum_items]
VECTOR_ITEMS = [(e.identifier,e.name,e.description) for e in bpy.types.ShaderNodeVectorMath.bl_rna.properties['operation'].enum_items]
MATH_UNARY = {'SQRT','INVERSE_SQRT','ABSOLUTE','EXPONENT','SIGN','ROUND','FLOOR','CEIL','TRUNC','FRACT',
              'SINE','COSINE','TANGENT','ARCSINE','ARCCOSINE','ARCTANGENT','SINH','COSH','TANH','RADIANS','DEGREES'}
MATH_TERNARY = {'MULTIPLY_ADD','COMPARE','SMOOTH_MIN','SMOOTH_MAX','WRAP'}
VECTOR_UNARY = {'LENGTH','NORMALIZE','ABSOLUTE','FLOOR','CEIL','FRACTION','SINE','COSINE','TANGENT'}
VECTOR_TERNARY = {'MULTIPLY_ADD','FACEFORWARD','WRAP'}
VECTOR_SCALAR = {'DOT_PRODUCT','DISTANCE','LENGTH'}


def input_indices(node):
    kind = node.bl_idname
    if kind == 'BleMDMath':
        return tuple(range(1 if node.operation in MATH_UNARY else 3 if node.operation in MATH_TERNARY else 2))
    if kind == 'BleMDVectorMath':
        op = node.operation
        return ((0,3) if op=='SCALE' else (0,1,3) if op=='REFRACT' else
                tuple(range(1 if op in VECTOR_UNARY else 3 if op in VECTOR_TERNARY else 2)))
    if kind == 'BleMDMapRange':
        return tuple(range(6 if node.interpolation_type=='STEPPED' else 5))
    if kind == 'BleMDMix':
        offset = {'FLOAT':1,'VECTOR':3,'COLOR':5}[node.data_type]
        return (0,offset,offset+1)
    return tuple(range(len(node.inputs)))


def output_indices(node):
    if node.bl_idname == 'BleMDVectorMath':
        return (1,) if node.operation in VECTOR_SCALAR else (0,)
    if node.bl_idname == 'BleMDMix':
        return ({'FLOAT':0,'VECTOR':1,'COLOR':2}[node.data_type],)
    return tuple(range(len(node.outputs)))


def changed(node, context=None):
    active = input_indices(node)
    for i,socket in enumerate(node.inputs):
        socket.hide = i not in active
    active = output_indices(node)
    for i,socket in enumerate(node.outputs):
        socket.hide = i not in active


def sockets(node, inputs, outputs):
    node.width = 200
    for kind,name,default in inputs:
        socket = node.inputs.new(kind,name)
        socket.default_value = default
    for kind,name in outputs:
        node.outputs.new(kind,name)
    changed(node)


class UtilityNode(FieldNode):
    blemd_utility = True


class BleMDMath(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDMath'
    bl_label = 'Math'
    operation: EnumProperty(name='Operation', items=MATH_ITEMS, default='ADD', update=changed)
    use_clamp: BoolProperty(name='Clamp', description='Clamp the result to 0–1')
    def init(self, context):
        sockets(self,[(SCALAR,n,.5) for n in ('Value','Value 2','Value 3')],[(SCALAR,'Value')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'operation',text='')
        layout.prop(self,'use_clamp')


class BleMDVectorMath(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDVectorMath'
    bl_label = 'Vector Math'
    operation: EnumProperty(name='Operation', items=VECTOR_ITEMS, default='ADD', update=changed)
    def init(self, context):
        sockets(self,[(VECTOR,n,(0,0,0)) for n in ('Vector','Vector 2','Vector 3')]+[(SCALAR,'Scale',1)],[(VECTOR,'Vector'),(SCALAR,'Value')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'operation',text='')


class BleMDMapRange(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDMapRange'
    bl_label = 'Map Range'
    interpolation_type: EnumProperty(name='Interpolation', items=[('LINEAR','Linear',''),('STEPPED','Stepped Linear',''),('SMOOTHSTEP','Smooth Step',''),('SMOOTHERSTEP','Smoother Step','')], default='LINEAR', update=changed)
    clamp: BoolProperty(name='Clamp', default=True)
    def init(self, context):
        sockets(self,[(SCALAR,n,v) for n,v in [('Value',1),('From Min',0),('From Max',1),('To Min',0),('To Max',1),('Steps',4)]],[(SCALAR,'Result')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'interpolation_type',text='')
        layout.prop(self,'clamp')


class BleMDClamp(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDClamp'
    bl_label = 'Clamp'
    clamp_type: EnumProperty(name='Clamp Type', items=[('MINMAX','Min Max',''),('RANGE','Range','Sort the two bounds before clamping')],default='MINMAX')
    def init(self, context):
        sockets(self,[(SCALAR,n,v) for n,v in [('Value',1),('Min',0),('Max',1)]],[(SCALAR,'Result')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'clamp_type',text='')


class BleMDMix(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDMix'
    bl_label = 'Mix'
    data_type: EnumProperty(name='Type', items=[('FLOAT','Float',''),('VECTOR','Vector',''),('COLOR','Color','Linear RGB blend')],default='FLOAT',update=changed)
    clamp_factor: BoolProperty(name='Clamp Factor', default=True)
    def init(self, context):
        sockets(self,[(SCALAR,'Factor',.5),(SCALAR,'A',0),(SCALAR,'B',1),(VECTOR,'A Vector',(0,0,0)),(VECTOR,'B Vector',(1,1,1)),(COLOR,'A Color',(0,0,0)),(COLOR,'B Color',(1,1,1))],[(SCALAR,'Result'),(VECTOR,'Vector'),(COLOR,'Color')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'data_type',text='')
        layout.prop(self,'clamp_factor')


class BleMDValue(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDValue'
    bl_label = 'Value'
    value: FloatProperty(name='Value',default=0)
    def init(self, context):
        sockets(self,[],[(SCALAR,'Value')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'value',text='')


class BleMDVector(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDVector'
    bl_label = 'Vector'
    value: FloatVectorProperty(name='Vector',size=3)
    def init(self, context):
        sockets(self,[],[(VECTOR,'Vector')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'value',text='')


class BleMDRGB(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDRGB'
    bl_label = 'RGB'
    value: FloatVectorProperty(name='Color',size=3,subtype='COLOR',min=0,max=1,default=(.5,.5,.5))
    def init(self, context):
        sockets(self,[],[(COLOR,'Color')])
    def draw_buttons(self, context, layout):
        layout.prop(self,'value',text='')


class BleMDCombineXYZ(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDCombineXYZ'
    bl_label = 'Combine XYZ'
    def init(self, context):
        sockets(self,[(SCALAR,n,0) for n in ('X','Y','Z')],[(VECTOR,'Vector')])


class BleMDSeparateXYZ(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDSeparateXYZ'
    bl_label = 'Separate XYZ'
    def init(self, context):
        sockets(self,[(VECTOR,'Vector',(0,0,0))],[(SCALAR,n) for n in ('X','Y','Z')])


class BleMDCombineColor(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDCombineColor'
    bl_label = 'Combine Color (RGB)'
    def init(self, context):
        sockets(self,[(SCALAR,n,0) for n in ('Red','Green','Blue')],[(COLOR,'Color')])


class BleMDSeparateColor(UtilityNode, bpy.types.Node):
    bl_idname = 'BleMDSeparateColor'
    bl_label = 'Separate Color (RGB)'
    def init(self, context):
        sockets(self,[(COLOR,'Color',(0,0,0))],[(SCALAR,n) for n in ('Red','Green','Blue')])


NODE_CLASSES = (BleMDMath,BleMDVectorMath,BleMDMapRange,BleMDClamp,BleMDMix,
                BleMDValue,BleMDVector,BleMDRGB,BleMDCombineXYZ,BleMDSeparateXYZ,BleMDCombineColor,BleMDSeparateColor)
TYPES = {cls.bl_idname for cls in NODE_CLASSES}


def divide(a,b):
    return np.divide(a,b,out=np.zeros(np.broadcast_shapes(np.shape(a),np.shape(b)),dtype=float),where=b!=0)


def smooth_min(a,b,c):
    h = divide(np.maximum(c-np.abs(a-b),0),c)
    return np.minimum(a,b)-h*h*h*c/6


def math_values(op, v):
    a=v[0]; b=v[1] if len(v)>1 else None; c=v[2] if len(v)>2 else None
    if op=='ADD': return a+b
    if op=='SUBTRACT': return a-b
    if op=='MULTIPLY': return a*b
    if op=='DIVIDE': return divide(a,b)
    if op=='MULTIPLY_ADD': return a*b+c
    if op=='POWER': return np.where(((a>=0)|(b==np.floor(b)))&((a!=0)|(b>=0)),np.power(a,b),0)
    if op=='LOGARITHM': return np.where((a>0)&(b>0),divide(np.log(a),np.log(b)),0)
    if op=='SQRT': return np.sqrt(np.maximum(a,0))
    if op=='INVERSE_SQRT': return divide(1,np.sqrt(np.maximum(a,0)))
    if op=='ABSOLUTE': return np.abs(a)
    if op=='EXPONENT': return np.exp(a)
    if op=='MINIMUM': return np.minimum(a,b)
    if op=='MAXIMUM': return np.maximum(a,b)
    if op=='LESS_THAN': return (a<b).astype(float)
    if op=='GREATER_THAN': return (a>b).astype(float)
    if op=='SIGN': return np.sign(a)
    if op=='COMPARE': return (np.abs(a-b)<=np.maximum(c,1e-7)).astype(float)
    if op=='SMOOTH_MIN': return smooth_min(a,b,c)
    if op=='SMOOTH_MAX': return -smooth_min(-a,-b,c)
    if op=='ROUND': return np.floor(a+.5)
    if op=='FLOOR': return np.floor(a)
    if op=='CEIL': return np.ceil(a)
    if op=='TRUNC': return np.trunc(a)
    if op=='FRACT': return a-np.floor(a)
    if op=='MODULO': return np.where(b!=0,np.fmod(a,b),0)
    if op=='FLOORED_MODULO': return np.where(b!=0,a-b*np.floor(divide(a,b)),0)
    if op=='WRAP': return np.where(b!=c,a-(b-c)*np.floor(divide(a-c,b-c)),c)
    if op=='SNAP': return np.floor(divide(a,b))*b
    if op=='PINGPONG': return np.where(b!=0,np.abs((divide(a-b,2*b)-np.floor(divide(a-b,2*b)))*2*b-b),0)
    unary={'SINE':np.sin,'COSINE':np.cos,'TANGENT':np.tan,'ARCTANGENT':np.arctan,
           'SINH':np.sinh,'COSH':np.cosh,'TANH':np.tanh,'RADIANS':np.deg2rad,'DEGREES':np.rad2deg}
    if op in unary: return unary[op](a)
    if op=='ARCSINE': return np.arcsin(np.clip(a,-1,1))
    if op=='ARCCOSINE': return np.arccos(np.clip(a,-1,1))
    if op=='ARCTAN2': return np.arctan2(a,b)
    raise ValueError(f'Unsupported Math operation: {op}')


def vector_values(op,v):
    a=v[0]; b=v[1] if len(v)>1 else None; c=v[2] if len(v)>2 else None
    dot=lambda a,b: np.sum(a*b,axis=1)
    norm=lambda a: np.linalg.norm(a,axis=1)
    normalize=lambda a: divide(a,norm(a)[:,None])
    if op=='SCALE': return a*b[:,None]
    if op=='LENGTH': return norm(a)
    if op=='NORMALIZE': return normalize(a)
    if op=='DISTANCE': return norm(a-b)
    if op=='DOT_PRODUCT': return dot(a,b)
    if op=='CROSS_PRODUCT': return np.cross(a,b)
    if op=='PROJECT': return b*divide(dot(a,b),dot(b,b))[:,None]
    if op=='REFLECT':
        n=normalize(b); return a-2*dot(a,n)[:,None]*n
    if op=='REFRACT':
        b=normalize(b); d=dot(a,b); k=1-c*c*(1-d*d)
        return np.where((k>=0)[:,None],c[:,None]*a-(c*d+np.sqrt(np.maximum(k,0)))[:,None]*b,0)
    if op=='FACEFORWARD': return np.where((dot(c,b)<0)[:,None],a,-a)
    return math_values({'FRACTION':'FRACT'}.get(op,op),v)


def evaluate(node, output, values, count):
    """Evaluate one utility; inputs are aligned arrays with particle-leading axes."""
    values = [np.asarray(v,dtype=float) for v in values]
    kind=node.bl_idname
    with np.errstate(all='ignore'):
        if kind=='BleMDMath':
            result=math_values(node.operation,values)
            if node.use_clamp: result=np.clip(result,0,1)
        elif kind=='BleMDVectorMath': result=vector_values(node.operation,values)
        elif kind=='BleMDClamp':
            a,b,c=values
            if node.clamp_type=='RANGE': b,c=np.minimum(b,c),np.maximum(b,c)
            result=np.minimum(np.maximum(a,b),c)
        elif kind=='BleMDMapRange':
            a,lo,hi,out_lo,out_hi=values[:5]
            factor=divide(a-lo,hi-lo)
            mode=node.interpolation_type
            if mode=='STEPPED': factor=divide(np.floor(factor*(values[5]+1)),values[5])
            elif mode in {'SMOOTHSTEP','SMOOTHERSTEP'}:
                factor=np.clip(factor,0,1)
                factor=factor*factor*(3-2*factor) if mode=='SMOOTHSTEP' else factor**3*(factor*(factor*6-15)+10)
            result=out_lo+factor*(out_hi-out_lo)
            if node.clamp: result=np.clip(result,np.minimum(out_lo,out_hi),np.maximum(out_lo,out_hi))
        elif kind=='BleMDMix':
            f,a,b=values
            if node.clamp_factor: f=np.clip(f,0,1)
            if a.ndim==2: f=f[:,None]
            result=(1-f)*a+f*b
        elif kind in {'BleMDValue','BleMDVector','BleMDRGB'}:
            value=np.asarray(node.value,dtype=float)
            result=np.broadcast_to(value,(count,)+value.shape)
        elif kind in {'BleMDCombineXYZ','BleMDCombineColor'}: result=np.column_stack(values)
        elif kind in {'BleMDSeparateXYZ','BleMDSeparateColor'}: result=values[0][:,output]
        else: raise ValueError(f'Unsupported utility: {node.bl_label}')
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{node.bl_label} '{node.name}' produced non-finite values")
    return result
