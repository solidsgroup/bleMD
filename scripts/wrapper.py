"""Legacy command wrapper. Pass Blender --python-exit-code 1 for script errors.

The Make targets use workflow.py directly; no success-message parsing is needed.
"""

import subprocess
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: wrapper.py COMMAND [ARG ...]")
    sys.exit(subprocess.run(sys.argv[1:]).returncode)
