"""
tests/test_permissions.py — tests for the permissions/risk-tiering layer.

These are the most important tests in the project: they protect the
safety boundary between "the model wants to do something" and "something
actually happens." A silent regression here (e.g. a SENSITIVE tool
accidentally running without confirmation) would be a real, dangerous bug.
"""

import pytest
from permissions import (
    RiskLevel,
    get_risk_level,
    requires_confirmation,
    TOOL_RISK_LEVELS,
)


def test_known_safe_tool_does_not_require_confirmation():
    assert get_risk_level("get_current_time") == RiskLevel.SAFE
    assert requires_confirmation("get_current_time") is False


def test_known_sensitive_tool_requires_confirmation():
    assert get_risk_level("create_event") == RiskLevel.SENSITIVE
    assert requires_confirmation("create_event") is True


@pytest.mark.parametrize("tool_name", [
    "list_events",
    "list_tasks",
])
def test_all_registered_safe_tools_run_automatically(tool_name):
    assert get_risk_level(tool_name) == RiskLevel.SAFE
    assert requires_confirmation(tool_name) is False


@pytest.mark.parametrize("tool_name", [
    "create_event",
    "create_draft",
    "create_task",
])
def test_all_registered_write_tools_require_confirmation(tool_name):
    assert requires_confirmation(tool_name) is True


def test_unregistered_tool_defaults_to_dangerous():
    """
    Fail-safe default: a tool that was never explicitly registered
    should never be trusted to run automatically. This protects against
    a developer forgetting to register a new tool's risk level.
    """
    fake_tool_name = "some_totally_unregistered_tool_xyz"
    assert fake_tool_name not in TOOL_RISK_LEVELS

    assert get_risk_level(fake_tool_name) == RiskLevel.DANGEROUS
    assert requires_confirmation(fake_tool_name) is True


def test_every_registered_tool_has_a_valid_risk_level():
    """Sanity check: nothing in the registry has a garbage/invalid value."""
    for tool_name, risk in TOOL_RISK_LEVELS.items():
        assert isinstance(risk, RiskLevel), f"{tool_name} has invalid risk level: {risk}"