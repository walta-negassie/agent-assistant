"""
agent.py — core agent loop.

This is step 1: prove that the model can call a tool, we can execute it,
and feed the result back for a final answer. No real integrations yet.
"""

import ollama
import permissions
from datetime import datetime

from tools import time_tool, calendar_tool

MODEL = "qwen2.5:3b"

TOOLS = [
    time_tool.SCHEMA,
    calendar_tool.LIST_EVENTS_SCHEMA,
    calendar_tool.CREATE_EVENT_SCHEMA,
]

AVAILABLE_FUNCTIONS = {
    "get_current_time": time_tool.get_current_time,
    "list_events": calendar_tool.list_events,
    "create_event": calendar_tool.create_event,
}


def run_agent(user_message: str):
    today = datetime.now().strftime("%A, %B %d, %Y")

    system_prompt = (
        f"You are a helpful personal assistant with access to tools. "
        f"Today's date is {today}. Use this as ground truth for anything "
        f"involving relative dates like 'tomorrow' or 'next week'. "
        f"Only claim to have done something if you actually called a tool "
        f"and received a real result — never say an action succeeded without "
        f"tool evidence."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    print(f"\n[USER] {user_message}")

    # Step 1: send the message + available tools to the model
    response = ollama.chat(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
    )

    ai_message = response["message"]
    messages.append(ai_message)

    # Step 2: did the model decide to call a tool?
    tool_calls = ai_message.get("tool_calls")

    if not tool_calls:
        print(f"[AGENT] {ai_message['content']}")
        return ai_message["content"]

    # Step 3: execute each requested tool call, through the permissions layer
    for call in tool_calls:
        tool_name = call["function"]["name"]
        tool_args = call["function"]["arguments"]  # dict of arguments

        print(f"[TOOL CALL] {tool_name}({tool_args})")

        # Check permissions BEFORE running anything
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

        print(f"[TOOL RESULT] {result}")

        # Step 4: feed the tool result back to the model as a new message
        messages.append(
            {
                "role": "tool",
                "content": str(result),
            }
        )

    # Step 5: ask the model for its final answer now that it has the tool result
    final_response = ollama.chat(model=MODEL, messages=messages)
    final_answer = final_response["message"]["content"]

    print(f"[AGENT] {final_answer}")
    return final_answer


if __name__ == "__main__":
    run_agent("Schedule a test event called 'Agent Project Test' tomorrow from 2pm to 2:30pm.")