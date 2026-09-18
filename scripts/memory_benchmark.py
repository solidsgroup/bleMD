"""Run with Blender --background --factory-startup --python scripts/memory_benchmark.py.

Optional arguments after --: --atoms 100000 --detail AUTO. Compares whole-process
peak RSS and evaluated preview size over three frames; it never saves preferences.
"""
import argparse
import json
from pathlib import Path
import resource
import sys
import tempfile

import addon_utils
import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--atoms', type=int, default=100000)
parser.add_argument('--detail', choices=['AUTO','LOW','MEDIUM','HIGH','POINTS'], default='AUTO')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.atoms < 1:
    parser.error('--atoms must be positive')
addon_utils.enable('bleMD', default_set=False)
from bleMD.bleMDTree import starter_tree
from bleMD import bleMDLive

with tempfile.TemporaryDirectory(prefix='blemd-memory-') as directory:
    path = Path(directory) / 'trajectory.xyz'
    with path.open('w') as stream:
        for frame in range(3):
            stream.write(f'{args.atoms}\nProperties=id:I:1:pos:R:3:energy:R:1\n')
            for i in range(args.atoms):
                stream.write(f'{i+1} {i%30 + frame*.1} {(i//30)%20} {i//600} {i/args.atoms}\n')
    tree = starter_tree(); tree.scene = bpy.context.scene
    source = next(n for n in tree.nodes if n.bl_idname == 'BleMDFileSource')
    output = next(n for n in tree.nodes if n.bl_idname == 'BleMDParticleOutput')
    source.filepath = str(path)
    output.radius = .3
    output.viewport_detail = args.detail
    for frame in range(3):
        bpy.context.scene.frame_set(frame)
        bleMDLive.tick()
        if tree.has_error:
            raise RuntimeError(tree.last_message)
        bpy.context.view_layer.update()
    mesh = output.target.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    print('BENCHMARK', json.dumps(dict(atoms=args.atoms, detail=output.viewport_detail,
          peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          vertices=len(mesh.vertices), polygons=len(mesh.polygons), meshes=len(bpy.data.meshes))))
