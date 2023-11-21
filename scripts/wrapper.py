import subprocess
import sys

try:
    output = subprocess.check_output(sys.argv[1:])
    print(output.decode('ascii'))
    if not "---successful completion---" in output.decode('utf-8'):
        raise Exception("Script errored out")
    print("Successful completion")
except FileNotFoundError as e:
    print("could not find file", e)#, e.output)
    raise e
except subprocess.CalledProcessError as e:
    print("error code", e.returncode)#, e.output)
    raise e
except Exception as e:
    print(e)
    raise e

print("Ah yes, definitely successful")
