"""
Organization Management and RBAC Role Permission Tests.
Tests slug validation, role checks, and hierarchy policies.
"""
import uuid
import pytest
from app.schemas.organization import OrganizationCreateRequest, MemberInviteRequest
from app.api.deps import require_role
from app.models.organization import Organization, OrganizationMembership
from tests.conftest import run_coroutine
from fastapi import HTTPException


def test_organization_slug_validation():
    """Verify slug formatting and normalization."""
    req = OrganizationCreateRequest(
        name="Acme Treasury LLC",
        slug="Acme-Treasury_2026",
        base_currency="usd",
    )
    assert req.slug == "acme-treasury_2026"
    assert req.base_currency == "USD"

    with pytest.raises(Exception):
        OrganizationCreateRequest(
            name="Bad Slug Org",
            slug="Invalid Slug with Spaces!",
            base_currency="USD",
        )


def test_role_enforcement_dependency():
    """Verify require_role dependency allows permitted roles and blocks unauthorized roles."""
    org = Organization(
        id=uuid.uuid4(),
        name="Acme Corp",
        slug="acme-corp",
        base_currency="USD",
    )

    # 1. Admin allowed for Admin role check
    admin_membership = OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=uuid.uuid4(),
        role="ADMIN",
    )
    admin_checker = require_role(["ADMIN"])
    result = run_coroutine(admin_checker((org, admin_membership)))
    assert result == (org, admin_membership)

    # 2. Accountant blocked from Admin-only action
    accountant_membership = OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=uuid.uuid4(),
        role="ACCOUNTANT",
    )
    with pytest.raises(HTTPException) as exc:
        run_coroutine(admin_checker((org, accountant_membership)))
    assert exc.value.status_code == 403
    assert "Access denied" in exc.value.detail

    # 3. Finance Manager allowed for Reconciliation check
    finance_checker = require_role(["ADMIN", "FINANCE_MANAGER"])
    manager_membership = OrganizationMembership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=uuid.uuid4(),
        role="FINANCE_MANAGER",
    )
    result_manager = run_coroutine(finance_checker((org, manager_membership)))
    assert result_manager == (org, manager_membership)
