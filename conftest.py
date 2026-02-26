"""Root conftest.py: ensure the local workstream source takes priority over installed packages."""
import sys
import os

# Insert the workstream root at the beginning of sys.path so that our local
# wikigr/ and bootstrap/ directories take precedence over the installed package
# (which may point to a different source tree via a .pth file).
_workstream_root = os.path.dirname(os.path.abspath(__file__))
if _workstream_root not in sys.path:
    sys.path.insert(0, _workstream_root)
