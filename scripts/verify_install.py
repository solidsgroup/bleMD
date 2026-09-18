"""Verify an installation by starting Blender with the saved preferences."""

from pathlib import Path
import zipfile

import addon_utils
import bpy
import bleMD

if addon_utils.check('bleMD') != (True, True):
    raise RuntimeError('bleMD failed to enable; see the Blender traceback above')
installed = Path(bleMD.__file__).resolve().parent
expected = Path(bpy.utils.user_resource('SCRIPTS')) / 'addons' / 'bleMD'
assert installed == expected.resolve(), f'Loaded a different installation: {installed}'
archive = Path(__file__).resolve().parents[1] / 'bleMD.zip'
with zipfile.ZipFile(archive) as package:
    for name in package.namelist():
        if not name.endswith('/'):
            assert (installed.parent / name).read_bytes() == package.read(name), name
print(f'Verified installed and enabled bleMD: {installed}')
