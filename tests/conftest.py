"""Global pytest configuration and opt-in integration-test controls."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests that call real external services",
    )
    parser.addoption(
        "--run-browser",
        action="store_true",
        default=False,
        help="run deterministic tests that launch a local Chromium process",
    )


def pytest_collection_modifyitems(config, items):
    run_network = config.getoption("--run-network")
    run_browser = config.getoption("--run-browser")
    skip_network = pytest.mark.skip(reason="requires --run-network")
    skip_browser = pytest.mark.skip(reason="requires --run-browser")
    for item in items:
        if "network" in item.keywords and not run_network:
            item.add_marker(skip_network)
        if "browser" in item.keywords and not run_browser:
            item.add_marker(skip_browser)
