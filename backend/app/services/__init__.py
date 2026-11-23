"""
Services Package Registry.
"""
from app.services.auth_service import AuthService
from app.services.org_service import OrgService
from app.services.email_service import email_service

__all__ = ["AuthService", "OrgService", "email_service"]
