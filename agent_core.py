"""
agent_core.py — the shared agent loop, usable by both the CLI and the
web server.

Key difference from the original agent.py: this version can PAUSE when
a tool needs permission, instead of blocking on input(). The caller
(CLI or web server) decides how to actually ask the user and then calls
resolve_confirmation() to continue.

Session shape (a plain dict, caller owns storage):
{
    "messages": [...],      # full conversation history sent to the model
    "step": 0,               # how many tool-call steps we've taken
    "pending": None or {"tool_name": ..., "tool_args": ...}
}
"""

from datetime import datetime
import ollama
import permissions
from tools import time_tool, calendar_tool, email_tool, tasks_tool

MODEL = "qwen2.5:3b"
MAX_STEPS = 5

TOOLS = [
    time_tool.SCHEMA,
    calendar_tool.LIST_EVENTS_SCHEMA,
    calendar_tool.CREATE_EVENT_SCHEMA,
    email_tool.CREATE_DRAFT_SCHEMA,
    tasks_tool.LIST_TASKS_SCHEMA,
    tasks_tool.CREATE_TASK_SCHEMA,
]

AVAILABLE_FUNCTIONS = {
    "get_current_time": time_tool.get_current_time,
    "list_events": calendar_tool.list_events,
    "create_event": calendar_tool.create_event,
    "create_draft": email_tool.create_draft,
    "list_tasks": tasks_tool.list_tasks,
    "create_task": tasks_tool.create_task,
}


def new_session(user_message: str) -> dict:
    """Creates a fresh session for a new conversation."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    system_prompt = (
        f"You are a helpful personal assistant with access to tools. "
        f"Today's date is {today}. Use this as ground truth for anything "
        f"involving relative dates like 'tomorrow' or 'next week'. "
        f"Only claim to have done something if you actually called a tool "
        f"and received a real result — never say an action succeeded without "
        f"tool evidence. When describing what a tool did, use the EXACT "
        f"values from the tool result — never paraphrase, guess, or use "
        f"placeholder text. You may call multiple tools, one after another, "
        f"if completing the user's request requires it — for example, "
        f"checking a calendar before creating an event. Call only ONE tool "
        f"at a time, and wait to see its real result before deciding on "
        f"your next action."
    )
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "step": 0,
        "pending": None,
    }


def add_user_message(session: dict, user_message: str) -> None:
    """Adds a new user turn to an existing session (for follow-up messages)."""
    session["messages"].append({"role": "user", "content": user_message})
    session["step"] = 0


def advance(session: dict) -> dict:
    """
    Runs the agent forward until it either:
      - produces a final answer -> {"status": "final", "text": ...}
      - needs permission for a tool -> {"status": "confirm", "tool_name": ..., "tool_args": ...}
      - hits max steps -> {"status": "final", "text": "..."}

    Assumes session["pending"] is None when called (no unresolved confirmation).
    """
    if session["step"] >= MAX_STEPS:
        return {"status": "final", "text": "I wasn't able to complete this in the allotted steps."}

    response = ollama.chat(model=MODEL, messages=session["messages"], tools=TOOLS)
    ai_message = response["message"]
    session["messages"].append(ai_message)

    tool_calls = ai_message.get("tool_calls")

    if not tool_calls:
        return {"status": "final", "text": ai_message["content"]}

    # Only look at the first requested tool call (forces sequential reasoning)
    call = tool_calls[0]
    tool_name = call["function"]["name"]
    tool_args = call["function"]["arguments"]

    if permissions.requires_confirmation(tool_name):
        session["pending"] = {"tool_name": tool_name, "tool_args": tool_args}
        return {"status": "confirm", "tool_name": tool_name, "tool_args": tool_args}

    # Safe tool — run it immediately, no pause needed
    result = _execute_tool(tool_name, tool_args)
    session["messages"].append({"role": "tool", "content": str(result)})
    session["step"] += 1

    return advance(session)  # keep going until confirm needed or final


def resolve_confirmation(session: dict, approved: bool) -> dict:
    """
    Called after the user answers a pending confirmation.
    Executes (or blocks) the tool, then continues the loop.
    """
    pending = session["pending"]
    session["pending"] = None

    if pending is None:
        return {"status": "final", "text": "No pending action to resolve."}

    tool_name = pending["tool_name"]
    tool_args = pending["tool_args"]

    if not approved:
        result = f"User denied permission to run '{tool_name}'."
    else:
        result = _execute_tool(tool_name, tool_args)

    session["messages"].append({"role": "tool", "content": str(result)})
    session["step"] += 1

    return advance(session)


def _execute_tool(tool_name: str, tool_args: dict):
    function_to_call = AVAILABLE_FUNCTIONS.get(tool_name)
    if function_to_call is None:
        return f"Error: unknown tool '{tool_name}'"
    return function_to_call(**tool_args)