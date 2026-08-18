"""
tools/time_tool.py — a simple read-only tool.

Every tool file follows this same pattern:
  1. The actual function that does the work
  2. A SCHEMA describing it to the model
"""

from datetime import datetime


def get_current_time():
    """Returns the current date and time as a string."""
    return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current date and time.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}