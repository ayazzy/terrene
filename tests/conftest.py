"""Unit/worker regression tests never make implicit live environmental requests.

Real verification is an explicit executable script with retained source fixtures.
Acquisition tests call the provider adapters directly with captured or mock IO.
"""
import pytest


@pytest.fixture(autouse=True)
def offline_acquisition(monkeypatch):
    monkeypatch.setenv('CRC_ENVIRONMENT_ACQUISITION', 'disabled')
