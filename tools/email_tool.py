"""
tools/email_tool.py — Gmail integration.

One tool for now:
  - create_draft (SENSITIVE — creates a draft, does NOT send)

Sending is intentionally left out for now. Sending is a DANGEROUS,
irreversible action and deserves its own explicit build step later,
with extra confirmation friction.
"""

import base64
from email.mime.text import MIMEText

from tools.calendar_tool import _get_credentials
from googleapiclient.discovery import build


def _get_gmail_service():
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds)


def create_draft(to: str, subject: str, body: str):
    """
    Creates a Gmail draft. Does not send it — the user must open Gmail
    and send it manually. This keeps the action reversible.
    """
    service = _get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw_message}})
        .execute()
    )

    return f"Draft created (id: {draft['id']}). Open Gmail to review and send it."


CREATE_DRAFT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_draft",
        "description": (
            "Create a draft email in Gmail. Does NOT send it — it only "
            "saves a draft for the user to review and send manually."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Email body text."},
            },
            "required": ["to", "subject", "body"],
        },
    },
}