"""
Root conftest.py — lives at apps/api/conftest.py

This file ensures the api/ root is on sys.path so that
`from domain.models import ...` works from any test file.

This runs before pytest collects any tests, so the path
is set before any import in any test file or conftest is attempted.
"""

import sys
from pathlib import Path

# Add the api/ directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))
