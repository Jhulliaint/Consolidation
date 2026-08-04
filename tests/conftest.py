from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "samples"))

from mageconso.config import load_config  # noqa: E402
from mageconso.engine import ConsolidationEngine  # noqa: E402
from mageconso.importers.excel import ManagementAccountsReader  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return load_config(ROOT / "config")


@pytest.fixture(scope="session")
def sample_files(tmp_path_factory):
    import make_samples

    return make_samples.build(tmp_path_factory.mktemp("samples"))


@pytest.fixture(scope="session")
def workbooks(cfg, sample_files):
    reader = ManagementAccountsReader(cfg)
    return [reader.read(p) for p in sample_files]


@pytest.fixture(scope="session")
def result(cfg, workbooks):
    return ConsolidationEngine(cfg).consolidate(workbooks)
