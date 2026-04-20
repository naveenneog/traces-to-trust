"""Mock email tool — simulates sending an email with audit logging."""
import time
import random
import uuid

def send_email(to: str, subject: str, body: str) -> dict:
    time.sleep(random.uniform(0.2, 0.5))  # simulate SMTP latency
    return {
        "status": "sent",
        "message_id": str(uuid.uuid4()),
        "to": to,
        "subject": subject,
        "timestamp": "2026-04-21T11:45:00Z",
    }

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "Send an email to a specified recipient",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"},
            },
            "required": ["to", "subject", "body"],
        },
    },
}
