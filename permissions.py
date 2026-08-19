"""
permissions.py — the safety layer between "the model wants to call a tool"
and "the tool actually runs."

Every tool declares a risk level. This module decides whether a given
tool call can run automatically, needs user confirmation, or should be
blocked outright.
"""

from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"            # read-only, no side effects
    SENSITIVE = "sensitive"  # creates/modifies, but reversible
    DANGEROUS = "dangerous"  # hard to reverse or high impact


# Maps tool name -> risk level. Every tool MUST be registered here.
# If a tool isn't listed, we treat it as dangerous by default (fail safe).
TOOL_RISK_LEVELS = {
    "get_current_time": RiskLevel.SAFE,
    "list_events": RiskLevel.SAFE,
    "create_event": RiskLevel.SENSITIVE,
    "create_draft": RiskLevel.SENSITIVE,
    "list_tasks": RiskLevel.SAFE,
    "create_task": RiskLevel.SENSITIVE,
}


def get_risk_level(tool_name: str) -> RiskLevel:
    return TOOL_RISK_LEVELS.get(tool_name, RiskLevel.DANGEROUS)


def requires_confirmation(tool_name: str) -> bool:
    """SAFE tools run automatically. Everything else needs confirmation."""
    return get_risk_level(tool_name) != RiskLevel.SAFE


def ask_user_confirmation(tool_name: str, tool_args: dict) -> bool:
    """
    Shows the user exactly what the agent wants to do, and asks for
    explicit approval before it happens. This is a CLI version for now —
    later this becomes a UI prompt.
    """
    risk = get_risk_level(tool_name)
    print(f"\n⚠️  The agent wants to run a [{risk.value.upper()}] action:")
    print(f"    Tool: {tool_name}")
    print(f"    Arguments: {tool_args}")

    answer = input("Allow this? (y/n): ").strip().lower()
    return answer == "y"