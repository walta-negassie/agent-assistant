"""
agent.py — core agent loop.

This is step 1: prove that the model can call a tool, we can execute it,
and feed the result back for a final answer. No real integrations yet.
"""

import ollama
import permissions
from datetime import datetime

from tools import time_tool, calendar_tool, email_tool, tasks_tool

MODEL = "qwen2.5:3b"

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


def run_agent(user_message: str, max_steps: int = 5):
    today = datetime.now().strftime("%A, %B %d, %Y")

    system_prompt = (
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    print(f"\n[USER] {user_message}")

    for step in range(max_steps):
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        ai_message = response["message"]
        messages.append(ai_message)

        tool_calls = ai_message.get("tool_calls")

        if not tool_calls:
            # Model is done — no more tools needed, this is the final answer
            print(f"[AGENT] {ai_message['content']}")
            return ai_message["content"]

        # Only execute ONE tool call per step, even if the model requested
        # several — this forces true sequential reasoning: the model must
        # see each real result before deciding on its next action, instead
        # of speculatively queuing multiple calls before any data exists.
        call = tool_calls[0]
        tool_name = call["function"]["name"]
        tool_args = call["function"]["arguments"]

        print(f"[STEP {step + 1}] [TOOL CALL] {tool_name}({tool_args})")

        if permissions.requires_confirmation(tool_name):
            approved = permissions.ask_user_confirmation(tool_name, tool_args)
            if not approved:
                result = f"User denied permission to run '{tool_name}'."
                print(f"[BLOCKED] {result}")
                messages.append({"role": "tool", "content": result})
                continue

        function_to_call = AVAILABLE_FUNCTIONS.get(tool_name)
        if function_to_call is None:
            result = f"Error: unknown tool '{tool_name}'"
        else:
            result = function_to_call(**tool_args)

        print(f"[STEP {step + 1}] [TOOL RESULT] {result}")
        messages.append({"role": "tool", "content": str(result)})

        # Loop continues — model gets another turn to see these results
        # and decide whether it needs to call more tools or is done.

    # Safety valve: if we hit max_steps, stop instead of looping forever
    print("[AGENT] Reached max steps without a final answer.")
    return "I wasn't able to complete this in the allotted steps."
    
if __name__ == "__main__":
    run_agent("Draft an email to test@example.com saying hi, subject 'Retry Test'.")