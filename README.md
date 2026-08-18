# Agent Assistant

A personal AI agent that takes natural language requests and performs real actions — creating calendar events, (soon) drafting emails, (soon) managing tasks — using a local, free LLM with a custom tool-calling loop and a permissions layer.

Built as a hands-on project to learn real agent engineering: tool-call orchestration, permission boundaries, OAuth integration, and error handling — not just prompting an LLM.

**Runs entirely free.** No API keys with billing, no cloud LLM costs. Uses a local model via [Ollama](https://ollama.com) and free-tier Google APIs.

## What it does right now

- Understands natural language requests via a local LLM (Qwen2.5 3B, run through Ollama)
- Decides which tool(s) to call and with what arguments
- Executes real actions against Google Calendar:
  - `list_events` — read upcoming events (read-only)
  - `create_event` — create a new event (writes to your real calendar)
- Every tool call passes through a permissions layer before executing

## Architecture
User message
│
▼
agent.py (core loop)
│
├─▶ sends message + tool schemas to local model (Ollama)
│
├─▶ model responds, optionally requesting a tool call
│
├─▶ permissions.py checks the tool's risk level
│ SAFE → runs automatically
│ SENSITIVE → prompts user for y/n confirmation
│ DANGEROUS → prompts user for y/n confirmation
│ (unregistered → treated as DANGEROUS by default — fail safe)
│
├─▶ if approved, tools/*.py executes the real action
│ (e.g. tools/calendar_tool.py hits the real Google Calendar API)
│
├─▶ result is sent back to the model
│
└─▶ model produces a final natural-language answer


### Why a permissions layer

The model never gets to decide how risky its own action is — that's hardcoded by the developer, per tool, in `permissions.py`. Read-only actions (like listing events) run automatically. Anything that changes real state (creating a calendar event, later: sending an email) requires the user to explicitly approve it before it executes. Unregistered tools default to the highest risk tier, so a bug or oversight can't accidentally let something risky run silently.

## A real bug I caught and fixed

Early on, I asked the agent to "schedule a test event tomorrow." It called `create_event` with a start date of `2023-11-28` — a fully hallucinated date, since the local model has no built-in awareness of the actual current date. The event was created for real, in the past, in my actual calendar.

**Fix:** every request now includes a system prompt that explicitly states the real current date (pulled from the system clock, not the model's guess) and instructs the model to compute relative dates like "tomorrow" from that ground truth. I also added an explicit instruction not to claim an action succeeded unless it was backed by an actual tool result — since I separately observed the model claiming it "used a multiply function" that didn't exist.

This is why every tool call is logged to the console (`[TOOL CALL]` / `[TOOL RESULT]`) — so incorrect model behavior is visible immediately instead of hidden inside a plausible-sounding sentence.

## Setup

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed
- A free Google Cloud project with the Calendar API enabled (see below)

### 1. Clone and install
```bash
git clone https://github.com/walta-negassie/agent-assistant.git
cd agent-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Pull the local model
```bash
ollama pull qwen2.5:3b
ollama serve   # keep running in a separate terminal tab
```

### 3. Google Calendar API access
1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Google Calendar API**
3. Configure the OAuth consent screen (External, add yourself as a test user)
4. Create OAuth credentials (Desktop app type), download the JSON
5. Save it as `credentials.json` in the project root (already gitignored — never commit this file)

### 4. Run it
```bash
python3 agent.py
```

First run opens a browser to authorize calendar access. After that, a `token.json` is cached locally (also gitignored) so you won't need to re-authorize.

## Project structure

agent-assistant/
├── agent.py # core agent loop
├── permissions.py # risk-tiered permission checks
├── tools/
│ ├── time_tool.py # get_current_time (SAFE)
│ └── calendar_tool.py # list_events (SAFE), create_event (SENSITIVE)
├── requirements.txt
└── README.md


## What's next
- Gmail integration — draft emails (SENSITIVE), send emails (DANGEROUS)
- Task tracker integration (Todoist)
- Multi-step planning (e.g. "find a free slot tomorrow and schedule X, then email Y")
- Retry/backoff for transient API failures, structured logging of every tool call
- Simple CLI or web front end

