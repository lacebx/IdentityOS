"""Global pytest configuration and opt-in integration-test controls."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests that call real external services",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-network"):
        return
    skip_network = pytest.mark.skip(reason="requires --run-network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_network)
