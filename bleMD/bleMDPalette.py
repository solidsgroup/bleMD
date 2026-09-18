"""One palette library for particle fields, legacy materials, and shader nodes."""
import numpy as np
from .bleMDColormaps import cm, getkeys

ITEMS = [(name, name, '') for name in cm]
FIELD_ITEMS = [('CUSTOM', 'Two colors', 'Interpolate between Low and High')] + ITEMS


def stops(name):
    """At most 32 stops, Blender's Color Ramp limit, including both endpoints."""
    if 'colors' in cm[name]:
        colors = np.asarray(cm[name]['colors'], dtype=float)[:, :3]
        indices = np.linspace(0, len(colors)-1, min(32,len(colors))).round().astype(int)
        return np.linspace(0, 1, len(indices)), colors[indices]
    positions, r, g, b = getkeys(name)
    positions, colors = np.asarray(positions), np.array([r,g,b]).T
    if len(positions) > 32:
        sample = np.linspace(0,1,32)
        colors = np.column_stack([np.interp(sample, positions, colors[:,i]) for i in range(3)])
        positions = sample
    return positions, colors


def sample(name, fraction, low=None, high=None):
    if name == 'CUSTOM':
        return (1-fraction[:,None])*np.asarray(low) + fraction[:,None]*np.asarray(high)
    positions, colors = stops(name)
    return np.column_stack([np.interp(fraction, positions, colors[:,i]) for i in range(3)])


def apply_ramp(ramp, name):
    positions, colors = stops(name)
    while len(ramp.elements) > 1:
        ramp.elements.remove(ramp.elements[-1])
    ramp.interpolation = 'LINEAR'
    ramp.color_mode = 'RGB'
    ramp.elements[0].position = float(positions[0])
    ramp.elements[0].color = (*colors[0], 1)
    for position, color in zip(positions[1:], colors[1:]):
        ramp.elements.new(float(position)).color = (*color, 1)
