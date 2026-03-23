"""Pytest plugin: --no-reports toggle for QuarkSum physics output."""

import importlib
import sys
from pathlib import Path

_TESTS_DIR = str(Path(__file__).parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)


def pytest_addoption(parser):
    parser.addoption(
        "--no-reports",
        action="store_true",
        default=False,
        help="Suppress physics report boxes in test output",
    )


def pytest_configure(config):
    import report
    report.set_enabled(not config.getoption("--no-reports", default=False))
