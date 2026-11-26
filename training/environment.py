"""Print the actual Python, package, and acceleration availability."""

import importlib
import platform
import sys

print("Python:", sys.version.replace("\n", " "))
print("Executable:", sys.executable)
print("Platform:", platform.platform())
print("Architecture:", platform.machine())
for name in ("numpy", "pandas", "torch"):
    try:
        module = importlib.import_module(name)
        print(f"{name}: {module.__version__}")
        if name == "torch":
            print("CUDA available:", module.cuda.is_available())
            print("MPS built:", module.backends.mps.is_built())
            print("MPS available:", module.backends.mps.is_available())
    except ImportError:
        print(f"{name}: not installed")
