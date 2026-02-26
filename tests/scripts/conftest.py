"""Configure sys.path for scripts tests."""

import sys
from pathlib import Path

# Add project root so scripts package can be imported
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
