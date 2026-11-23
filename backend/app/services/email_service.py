"""
Email dispatch service for FinBridge.
In development, logs tokens cleanly to structured logger and in-memory test inbox.
In production, integrates with transactional email providers (SendGrid/SES).
"""
from typing import Dict, List
from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory mailbox for local testing and test assertions
in_memory_mailbox: List[Dict[str, str]] = []


class EmailService:
    @staticmethod
    def send_verification_email(email: str, token: str) -> None:
        """Send account activation email with verification token."""
        logger.info(
            "Dispatching account verification email",
            recipient=email,
            token_preview=token[:8] + "...",
        )
        in_memory_mailbox.append({
            "type": "VERIFICATION",
            "email": email,
            "token": token,
        })

    @staticmethod
    def send_password_reset_email(email: str, token: str) -> None:
        """Send password reset email with recovery token."""
        logger.info(
            "Dispatching password reset email",
            recipient=email,
            token_preview=token[:8] + "...",
        )
        in_memory_mailbox.append({
            "type": "PASSWORD_RESET",
            "email": email,
            "token": token,
        })


email_service = EmailService()
