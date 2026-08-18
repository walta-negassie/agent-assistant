"""
tools/calendar_tool.py — Google Calendar integration.

Two tools:
  - list_events   (SAFE — read-only)
  - create_event  (SENSITIVE — modifies your calendar, needs confirmation)

Auth flow: first run opens a browser to log in and approve access.
After that, a token is saved to token.json and reused automatically.
"""

import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If you ever change SCOPES, delete token.json and re-authenticate.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            print("\nOpening your browser to authorize Google Calendar access...")
            creds = flow.run_local_server(port=0, open_browser=True)
            print("Authorization successful.\n")

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def _get_service():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def list_events(max_results: int = 10):
    """Lists the next upcoming events on the user's primary calendar."""
    service = _get_service()
    now = datetime.datetime.utcnow().isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        return "No upcoming events found."

    lines = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        lines.append(f"- {event.get('summary', '(no title)')} at {start}")

    return "\n".join(lines)


def create_event(summary: str, start_time: str, end_time: str, description: str = ""):
    """
    Creates a calendar event.
    start_time and end_time must be ISO 8601, e.g. '2026-08-20T15:00:00'
    """
    service = _get_service()

    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_time, "timeZone": "America/Chicago"},
        "end": {"dateTime": end_time, "timeZone": "America/Chicago"},
    }

    created_event = service.events().insert(calendarId="primary", body=event_body).execute()
    return f"Event created: {created_event.get('htmlLink')}"


# ---- Schemas the model sees ----

LIST_EVENTS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_events",
        "description": "List the user's upcoming calendar events.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max number of events to return.",
                }
            },
            "required": [],
        },
    },
}

CREATE_EVENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_event",
        "description": "Create a new event on the user's calendar.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format, e.g. 2026-08-20T15:00:00",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format, e.g. 2026-08-20T16:00:00",
                },
                "description": {
                    "type": "string",
                    "description": "Optional event description.",
                },
            },
            "required": ["summary", "start_time", "end_time"],
        },
    },
}