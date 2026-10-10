"""Pytest guard: this project must be run from its isolated virtual environment."""
import os
import sys

import pytest


def pytest_sessionstart(session):
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv and os.environ.get("JALSETU_ALLOW_GLOBAL_PYTHON") != "1":
        pytest.exit(
            "Not running inside a virtual environment. Run setup.ps1 / setup.sh, activate .venv, "
            "then retry (or set JALSETU_ALLOW_GLOBAL_PYTHON=1 to bypass, e.g. in CI containers).",
            returncode=2,
        )
