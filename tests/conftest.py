"""Unit/worker regression tests never make implicit live environmental requests.

Retained-data verification is an explicit opt-in with local prerequisite checks.
Acquisition tests call the provider adapters directly with captured or mock IO.
"""
from pathlib import Path

import pytest


RETAINED_ROOTS = (
    Path(__file__).parents[1] / 'data/verification/england-real-v1-final',
    Path(__file__).parents[1] / 'data/verification/england-real-openmap-local-2026-04',
    Path(__file__).parents[1] / 'data/verification/england-real-phi-v1',
)
RETAINED_MODULES = {
    'test_land_evidence.py',
    'test_land_evidence_persistence.py',
    'test_screening_context.py',
}


def pytest_addoption(parser):
    parser.addoption(
        '--retained-data', action='store_true', default=False,
        help='run ignored local retained-data suites after checking prerequisites',
    )


def _requires_retained_data(item):
    name = item.path.name
    if name in RETAINED_MODULES:
        return True
    if name == 'test_wetland_module_runs.py':
        return item.name != 'test_binding_contract_refuses_semantic_substitutions'
    return (
        name == 'test_priority_habitats.py'
        and item.name.startswith('test_phi_change_creates_')
    ) or (
        name == 'test_openmap_local.py'
        and item.name.startswith('test_snapshot_history_')
    )


def pytest_collection_modifyitems(config, items):
    selected = config.getoption('--retained-data')
    retained_items = [item for item in items if _requires_retained_data(item)]
    if not selected:
        reason = (
            'retained local assets are opt-in; rerun with --retained-data '
            'after provisioning data/verification'
        )
        for item in retained_items:
            item.add_marker(pytest.mark.skip(reason=reason))
        return
    missing = [str(root) for root in RETAINED_ROOTS if not root.is_dir()]
    if retained_items and missing:
        raise pytest.UsageError(
            '--retained-data requires ignored local verification assets: '
            + ', '.join(missing)
        )


@pytest.fixture(autouse=True)
def offline_acquisition(monkeypatch):
    monkeypatch.setenv('CRC_ENVIRONMENT_ACQUISITION', 'disabled')
