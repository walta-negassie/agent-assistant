"""
tools/tasks_tool.py — Todoist integration.

Two tools:
  - list_tasks    (SAFE — read-only)
  - create_task   (SENSITIVE — adds a new task)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables

TODOIST_API_TOKEN = os.getenv("TODOIST_API_TOKEN")
BASE_URL = "https://api.todoist.com/api/v1"


def _headers():
    return {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}


def list_tasks():
    """Lists the user's current open tasks."""
    response = requests.get(f"{BASE_URL}/tasks", headers=_headers())
    response.raise_for_status()
    data = response.json()
    tasks = data.get("results", [])

    if not tasks:
        return "No open tasks found."

    lines = [f"- {task['content']}" for task in tasks]
    return "\n".join(lines)


def create_task(content: str, due_string: str = None):
    """
    Creates a new task.
    due_string is natural language, e.g. 'tomorrow', 'next Monday' — Todoist parses it.
    """
    payload = {"content": content}
    if due_string:
        payload["due_string"] = due_string

    response = requests.post(f"{BASE_URL}/tasks", headers=_headers(), json=payload)
    response.raise_for_status()
    task = response.json()

    return f"Task created: '{task['content']}' (id: {task['id']})"


LIST_TASKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_tasks",
        "description": "List the user's current open tasks from their task tracker.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

CREATE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_task",
        "description": "Create a new task in the user's task tracker.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The task text."},
                "due_string": {
                    "type": "string",
                    "description": "Optional natural language due date, e.g. 'tomorrow', 'next Monday'.",
                },
            },
            "required": ["content"],
        },
    },
}