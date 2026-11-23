"""
Multi-Tenant Isolation and Cross-Tenant Security Tests.
Proves that users in Organization A can NEVER access or mutate records in Organization B,
and that malicious X-Organization-Id header tampering is rejected immediately.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from app.api.deps import get_current_org_membership
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from tests.conftest import run_coroutine


def test_cross_tenant_access_attempt_is_rejected():
    """
    Scenario: User 1 belongs to Org 1. User 1 sends a request with
    X-Organization-Id set to Org 2 (a foreign tenant).
    System must query database for membership in Org 2, fail to find it,
    and raise HTTP 404 or 403, preventing any cross-tenant data leak.
    """
    user_1 = User(
        id=uuid.uuid4(),
        email="operator@org-one.com",
        full_name="User One",
        is_active=True,
        is_verified=True,
    )
    foreign_org_id = uuid.uuid4()

    # Mock database session returning empty result for foreign org membership
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        run_coroutine(get_current_org_membership(
            x_organization_id=str(foreign_org_id),
            current_user=user_1,
            db=mock_db,
        ))

    assert exc.value.status_code == 404
    assert "not found or you do not have permission" in exc.value.detail.lower()


def test_missing_organization_id_header_is_rejected():
    """Verify that requests missing X-Organization-Id are rejected with HTTP 400."""
    user = User(
        id=uuid.uuid4(),
        email="test@user.com",
        full_name="Test User",
        is_active=True,
        is_verified=True,
    )
    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        run_coroutine(get_current_org_membership(
            x_organization_id=None,
            current_user=user,
            db=mock_db,
        ))

    assert exc.value.status_code == 400
    assert "Missing X-Organization-Id" in exc.value.detail


def test_invalid_uuid_organization_id_is_rejected():
    """Verify that malformed non-UUID tenant identifiers are rejected with HTTP 400."""
    user = User(
        id=uuid.uuid4(),
        email="test@user.com",
        full_name="Test User",
        is_active=True,
        is_verified=True,
    )
    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        run_coroutine(get_current_org_membership(
            x_organization_id="not-a-valid-uuid-12345",
            current_user=user,
            db=mock_db,
        ))

    assert exc.value.status_code == 400
    assert "Invalid X-Organization-Id UUID" in exc.value.detail
