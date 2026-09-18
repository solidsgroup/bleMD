"""Jmol CPK element colors, converted from display sRGB to Blender linear RGB.

Color data: https://jmol.sourceforge.net/jscolors/jmol_constants.js
Table documented at https://jmol.sourceforge.net/jscolors/ (H through Mt).
Element colors are fixed here, independent of user OVITO display presets.
"""
import re
import numpy as np

# Atomic-number order; superheavy elements beyond the published table use the
# node's fallback. Keep their symbols valid for explicit type mappings.
ELEMENTS = """H:FFFFFF He:D9FFFF Li:CC80FF Be:C2FF00 B:FFB5B5 C:909090 N:3050F8 O:FF0D0D
F:90E050 Ne:B3E3F5 Na:AB5CF2 Mg:8AFF00 Al:BFA6A6 Si:F0C8A0 P:FF8000 S:FFFF30
Cl:1FF01F Ar:80D1E3 K:8F40D4 Ca:3DFF00 Sc:E6E6E6 Ti:BFC2C7 V:A6A6AB Cr:8A99C7
Mn:9C7AC7 Fe:E06633 Co:F090A0 Ni:50D050 Cu:C88033 Zn:7D80B0 Ga:C28F8F Ge:668F8F
As:BD80E3 Se:FFA100 Br:A62929 Kr:5CB8D1 Rb:702EB0 Sr:00FF00 Y:94FFFF Zr:94E0E0
Nb:73C2C9 Mo:54B5B5 Tc:3B9E9E Ru:248F8F Rh:0A7D8C Pd:006985 Ag:C0C0C0 Cd:FFD98F
In:A67573 Sn:668080 Sb:9E63B5 Te:D47A00 I:940094 Xe:429EB0 Cs:57178F Ba:00C900
La:70D4FF Ce:FFFFC7 Pr:D9FFC7 Nd:C7FFC7 Pm:A3FFC7 Sm:8FFFC7 Eu:61FFC7 Gd:45FFC7
Tb:30FFC7 Dy:1FFFC7 Ho:00FF9C Er:00E675 Tm:00D452 Yb:00BF38 Lu:00AB24 Hf:4DC2FF
Ta:4DA6FF W:2194D6 Re:267DAB Os:266696 Ir:175487 Pt:D0D0E0 Au:FFD123 Hg:B8B8D0
Tl:A6544D Pb:575961 Bi:9E4FB5 Po:AB5C00 At:754F45 Rn:428296 Fr:420066 Ra:007D00
Ac:70ABFA Th:00BAFF Pa:00A1FF U:008FFF Np:0080FF Pu:006BFF Am:545CF2 Cm:785CE3
Bk:8A4FE3 Cf:A136D4 Es:B31FD4 Fm:B31FBA Md:B30DA6 No:BD0D87 Lr:C70066 Rf:CC0059
Db:D1004F Sg:D90045 Bh:E00038 Hs:E6002E Mt:EB0026""".split()
SYMBOLS = [entry.split(':')[0] for entry in ELEMENTS] + 'Ds Rg Cn Nh Fl Mc Lv Ts Og'.split()
NUMBERS = {symbol: index + 1 for index, symbol in enumerate(SYMBOLS)}
NUMBERS.update(D=1, T=1)
_srgb = np.array([[int(entry.split(':')[1][i:i+2],16)/255 for i in (0,2,4)]
                  for entry in ELEMENTS], dtype=np.float32)
COLORS = np.where(_srgb <= .04045, _srgb / 12.92, ((_srgb + .055) / 1.055)**2.4)
del _srgb


def type_mapping(text):
    """Explicit IDs are labels, never assumed to be atomic numbers."""
    mapping = {}
    for entry in re.split(r'[,;\n]', text):
        if not entry.strip():
            continue
        match = re.fullmatch(r'\s*([+-]?\d+)\s*=\s*([A-Za-z]{1,2})\s*', entry)
        if not match or match[2] not in NUMBERS:
            raise ValueError('CPK Color: use element mappings such as 1=C, 2=O (case-sensitive symbols)')
        type_id = int(match[1])
        if type_id in mapping:
            raise ValueError(f'CPK Color: duplicate mapping for type {type_id}')
        mapping[type_id] = NUMBERS[match[2]]
    return mapping


def colors(node, values, prop=None):
    """Color a scalar field using its type metadata, overrides, or atomic numbers."""
    values = np.asarray(values)
    if values.ndim != 1 or not np.all(np.isfinite(values)) or np.any(values != np.floor(values)):
        raise ValueError('CPK Color requires finite integer type IDs or atomic numbers')
    # Compute once per distinct type; avoid allocating by maximum user type ID.
    unique, inverse = np.unique(values, return_inverse=True)
    lookup = np.tile(np.asarray(node.fallback_color,dtype=np.float32), (len(unique),1))
    if node.input_mode == 'TYPES':
        mapping = {t.id: NUMBERS.get(t.name.strip(),0) for t in getattr(prop,'types',())}
        mapping.update(type_mapping(node.type_mapping))
        numbers = [mapping.get(int(value),0) for value in unique]
    else:
        numbers = [int(value) for value in unique]
    for i, number in enumerate(numbers):
        if 1 <= number <= len(COLORS):
            lookup[i] = COLORS[number-1]
    return lookup[inverse]
