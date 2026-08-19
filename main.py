"""
main.py — interactive CLI chat loop.

Run this instead of editing agent.py and re-running it. Talk to the
agent live, across multiple turns, in one session.
"""

import agent_core


def ask_confirmation(tool_name: str, tool_args: dict) -> bool:
    print(f"\n⚠️  The agent wants to run [{tool_name}]")
    print(f"    Arguments: {tool_args}")
    answer = input("Allow this? (y/n): ").strip().lower()
    return answer == "y"


def main():
    print("Agent Assistant — type your request, or 'quit' to exit.\n")

    session = None

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        if not user_input:
            continue

        if session is None:
            session = agent_core.new_session(user_input)
        else:
            agent_core.add_user_message(session, user_input)

        result = agent_core.advance(session)

        # Keep resolving confirmations until we get a final answer
        while result["status"] == "confirm":
            approved = ask_confirmation(result["tool_name"], result["tool_args"])
            result = agent_core.resolve_confirmation(session, approved)

        print(f"\nAgent: {result['text']}\n")


if __name__ == "__main__":
    main()