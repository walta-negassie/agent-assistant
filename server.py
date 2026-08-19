"""
server.py — FastAPI backend for the browser chat UI.

Wraps agent_core in HTTP endpoints. Sessions are kept in memory, keyed
by a session_id the browser generates and sends with every request.
This is fine for a single local user; it is NOT designed to scale to
many concurrent users or survive a server restart (a real product
would use a database or Redis for session storage instead).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent_core

app = FastAPI()

# Allow the browser page (served from the same host, but keep this
# permissive for local dev simplicity) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> session dict (as defined in agent_core)
SESSIONS = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ConfirmRequest(BaseModel):
    session_id: str
    approved: bool


@app.post("/chat")
def chat(req: ChatRequest):
    session = SESSIONS.get(req.session_id)

    if session is None:
        session = agent_core.new_session(req.message)
        SESSIONS[req.session_id] = session
    else:
        agent_core.add_user_message(session, req.message)

    result = agent_core.advance(session)
    return result


@app.post("/confirm")
def confirm(req: ConfirmRequest):
    session = SESSIONS.get(req.session_id)

    if session is None:
        return {"status": "error", "text": "Session not found."}

    result = agent_core.resolve_confirmation(session, req.approved)
    return result


# Serve the static frontend (index.html, etc.) from /static
app.mount("/", StaticFiles(directory="static", html=True), name="static")