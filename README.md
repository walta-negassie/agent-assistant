# Agent Assistant

A personal AI agent that takes natural language requests and performs real actions — creating calendar events, drafting emails, managing tasks — using a local, free LLM with a custom tool-calling loop and a permissions layer.

Built as a hands-on project to learn real agent engineering: tool-call orchestration, permission boundaries, OAuth and API-key integration, and error handling — not just prompting an LLM.

**Runs entirely free.** No API keys with billing, no cloud LLM costs. Uses a local model via [Ollama](https://ollama.com) and free-tier Google and Todoist APIs.

## What it does right now

Understands natural language requests via a local LLM (Qwen2.5 3B, run through Ollama), decides which tool(s) to call, and executes real actions:

| Tool | Service | Risk tier | What it does |
|---|---|---|---|
| `get_current_time` | — | SAFE | Returns the real system date/time |
| `list_events` | Google Calendar | SAFE | Reads upcoming events |
| `create_event` | Google Calendar | SENSITIVE | Creates a real calendar event |
| `create_draft` | Gmail | SENSITIVE | Creates a draft (never auto-sends) |
| `list_tasks` | Todoist | SAFE | Reads open tasks |
| `create_task` | Todoist | SENSITIVE | Creates a real task |

Every tool call passes through a permissions layer before executing.

## Architecture

```
User message
    │
    ▼
agent.py (core loop)
    │
    ├─▶ system prompt grounds the model with the real current date
    │
    ├─▶ sends message + tool schemas to local model (Ollama)
    │
    ├─▶ model responds, optionally requesting a tool call
    │
    ├─▶ permissions.py checks the tool's risk level
    │       SAFE        → runs automatically
    │       SENSITIVE    → prompts user for y/n confirmation
    │       DANGEROUS     → prompts user for y/n confirmation
    │       (unregistered → treated as DANGEROUS by default — fail safe)
    │
    ├─▶ if approved, tools/*.py executes the real action
    │       (Google Calendar API, Gmail API, or Todoist API)
    │
    ├─▶ result is sent back to the model
    │
    └─▶ model produces a final natural-language answer
```

### Why a permissions layer

The model never gets to decide how risky its own action is — that's hardcoded by the developer, per tool, in `permissions.py`. Read-only actions (listing events, listing tasks) run automatically. Anything that changes real state (creating an event, drafting an email, creating a task) requires explicit user approval before it executes. Unregistered tools default to the highest risk tier, so a bug or oversight can't accidentally let something risky run silently.

Email is deliberately draft-only for now — `create_draft` writes to the Gmail Drafts folder but never sends. Sending is a DANGEROUS, irreversible action and is planned as a separate, more heavily-gated tool.

## Real bugs I found and fixed

Building this surfaced three genuine engineering problems, not just typos:

**1. Hallucinated dates.** Early on, "schedule a test event tomorrow" produced a start date of `2023-11-28` — the local model has no built-in awareness of the actual current date and simply guessed. The event was created for real, in the past. **Fix:** every request now includes a system prompt stating the real current date pulled from the system clock, with explicit instructions to compute relative dates from that ground truth — and to never claim an action succeeded without a real tool result backing it up.

**2. A leaked OAuth token in git history.** A stray typo in `.gitignore` (`token.json.DS_Store` instead of two separate lines) caused `token.json` to be silently tracked and committed. GitHub's push protection caught it before the push succeeded. **Fix:** corrected `.gitignore`, ran `git rm --cached` to untrack the file, and amended the commit before it was ever visible publicly.

**3. A breaking third-party API migration.** Todoist retired their REST v2 API mid-project, returning `410 Gone` on every request. Once switched to the new `api/v1` endpoint, task creation worked but `list_tasks` still broke — the new API wraps results in `{"results": [...], "next_cursor": ...}` instead of returning a bare list, while single-resource endpoints (like creating one task) still return the resource directly. **Fix:** updated the base URL and unwrapped the paginated response correctly, after inspecting the raw response instead of guessing at the fix.

**4. Speculative tool-call batching with fabricated data.** When I built multi-step tool chaining (e.g. "check my calendar, then create a task using the exact event title"), the model would sometimes return *two* tool calls in a single response — `list_events` and `create_task` together — before it had actually seen the calendar result. With no real data yet, it filled the task content with literal unresolved template syntax (`{{next_event_title}}`), sent that to the real Todoist API, and then told me it had created a task with the correct event title — a hallucinated success claim that directly contradicted its own tool result. **Fix:** changed the agent loop to execute only one tool call per step, forcing the model to see each real result before it's allowed to decide on its next action, and tightened the system prompt to require exact values from tool results rather than paraphrased or placeholder text.

Every tool call is logged to the console (`[STEP N] [TOOL CALL]` / `[TOOL RESULT]`) specifically so issues like these are visible immediately instead of hidden inside a plausible-sounding final answer.

**5. Retry logic silently failing to catch its own custom exceptions.** While building `retry.py`, I wrote a `with_retry()` wrapper that classifies errors as retryable (`TransientError`) or not (`PermanentError`). Testing it with a function that raises `TransientError` directly (not wrapped in an HTTP exception) crashed immediately instead of retrying — the `except` clauses only covered `requests`-derived exceptions, not the module's own exception types. **Fix:** added an explicit `except TransientError` clause, then verified with a standalone test script that intentionally fails twice before succeeding, confirming the correct exponential backoff (1s, 2s) and eventual success.

## Error handling

Every real API call (Google Calendar, Gmail, Todoist) is wrapped in `retry.py`'s `with_retry()`, which classifies failures into two categories:

- **Transient** (rate limits, 5xx server errors, network/timeout issues) — retried automatically up to 3 times with exponential backoff (1s, 2s, 4s)
- **Permanent** (bad auth, malformed requests, not found) — fails immediately, since retrying can't fix these

Every tool function catches these and returns a clean error string instead of crashing, so a failure becomes a normal `tool` message the model can see and explain to the user in plain language — rather than an unhandled exception taking down the whole agent.

## Tests

```bash
pytest tests/ -v
```

22 tests covering the two subsystems where a silent regression would actually matter:

- **`tests/test_permissions.py`** — every registered tool has the correct risk tier, SAFE tools skip confirmation, SENSITIVE/DANGEROUS tools require it, and unregistered tools correctly default to DANGEROUS (the fail-safe guarantee).
- **`tests/test_retry.py`** — HTTP status codes are classified correctly (429/5xx → retry, 4xx → fail fast), retries actually happen with the right count, and permanent errors fail immediately without wasting attempts. Uses fake functions instead of real API calls, so the suite runs instantly and has no network dependency.

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed
- A free Google Cloud project with Calendar + Gmail APIs enabled
- A free Todoist account

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

### 3. Google Calendar + Gmail API access
1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Google Calendar API** and **Gmail API**
3. Configure the OAuth consent screen (External, add yourself as a test user)
4. Create OAuth credentials (Desktop app type), download the JSON
5. Save it as `credentials.json` in the project root (gitignored — never commit this file)
6. First run opens a browser to authorize both calendar and Gmail (`gmail.compose`) scopes. A `token.json` is cached locally afterward (also gitignored).

### 4. Todoist API access
1. Sign up at [todoist.com](https://todoist.com) (free plan, no card required)
2. Settings → Integrations → Developer → copy your API token
3. Create a `.env` file in the project root:
   ```
   TODOIST_API_TOKEN=your_actual_token_here
   ```

### 5. Run it
```bash
python3 agent.py
```

## Project structure

```
agent-assistant/
├── agent.py              # core agent loop
├── permissions.py         # risk-tiered permission checks
├── retry.py               # retry/backoff logic and error classification
├── tools/
│   ├── time_tool.py       # get_current_time (SAFE)
│   ├── calendar_tool.py   # list_events (SAFE), create_event (SENSITIVE)
│   ├── email_tool.py      # create_draft (SENSITIVE)
│   └── tasks_tool.py      # list_tasks (SAFE), create_task (SENSITIVE)
├── requirements.txt
└── README.md
```

## What's next
- Sending emails (DANGEROUS tier, extra confirmation friction)
- Multi-step planning (e.g. "find a free slot tomorrow, schedule X, then email Y")
- Retry/backoff for transient API failures (rate limits, timeouts)
- Structured logging of every tool call to a file, for auditability
- Simple CLI or web front end