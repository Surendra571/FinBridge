"""
FinBridge Demo Data Seeder.
Creates an initial verified administrator user, default organization,
and primary bank account for local interactive development.
"""
import asyncio
import os
import sys
from decimal import Decimal

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import select
from app.db.session import get_session_factory, get_engine
from app.db.base import Base
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.models.financial import BankAccount
from app.core.security import hash_password


async def seed():
    print("Checking and seeding database schema...")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = get_session_factory()
    async with session_factory() as db:
        # 1. Check if demo user already exists
        user_res = await db.execute(select(User).where(User.email == "admin@finbridge.com"))
        user = user_res.scalar_one_or_none()

        if not user:
            print("Creating demo admin user: admin@finbridge.com ...")
            user = User(
                email="admin@finbridge.com",
                hashed_password=hash_password("AdminPass123!"),
                full_name="Alex Administrator",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
        else:
            print("Demo user admin@finbridge.com already exists.")

        # 1b. Check if Elena Rostova exists
        elena_res = await db.execute(select(User).where(User.email == "elena.rostova@northstarlogistics.com"))
        elena = elena_res.scalar_one_or_none()
        if not elena:
            print("Creating demo controller user: elena.rostova@northstarlogistics.com ...")
            elena = User(
                email="elena.rostova@northstarlogistics.com",
                hashed_password=hash_password("ElenaPass123!"),
                full_name="Elena Rostova",
                is_active=True,
                is_verified=True,
            )
            db.add(elena)
            await db.flush()
        else:
            print("Demo user elena.rostova@northstarlogistics.com already exists.")

        # 2. Check if demo organizations exist
        org_res = await db.execute(select(Organization).where(Organization.slug == "finbridge-tech"))
        org = org_res.scalar_one_or_none()

        if not org:
            print("Creating demo organization: FinBridge Technologies Inc. ...")
            org = Organization(
                name="FinBridge Technologies Inc.",
                slug="finbridge-tech",
                base_currency="USD",
                settings={"fiscal_year_start": "01-01"},
                is_active=True,
            )
            db.add(org)
            await db.flush()
        else:
            print("Demo organization already exists.")

        # 2b. Check Northstar Logistics organization
        nl_org_res = await db.execute(select(Organization).where(Organization.slug == "northstar-logistics"))
        nl_org = nl_org_res.scalar_one_or_none()
        if not nl_org:
            print("Creating demo organization: Northstar Logistics ...")
            nl_org = Organization(
                name="Northstar Logistics",
                slug="northstar-logistics",
                base_currency="USD",
                settings={"fiscal_year_start": "01-01"},
                is_active=True,
            )
            db.add(nl_org)
            await db.flush()

        # 3. Check memberships
        memb_res = await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == org.id,
            )
        )
        membership = memb_res.scalar_one_or_none()
        if not membership:
            print("Assigning ADMIN membership...")
            membership = OrganizationMembership(
                user_id=user.id,
                organization_id=org.id,
                role="ADMIN",
                is_active=True,
            )
            db.add(membership)
            await db.flush()

        # Elena memberships
        elena_memb_res = await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == elena.id,
                OrganizationMembership.organization_id == nl_org.id,
            )
        )
        if not elena_memb_res.scalar_one_or_none():
            print("Assigning CONTROLLER membership for Elena in Northstar Logistics...")
            db.add(OrganizationMembership(
                user_id=elena.id,
                organization_id=nl_org.id,
                role="CONTROLLER",
                is_active=True,
            ))
            await db.flush()

        elena_tech_res = await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == elena.id,
                OrganizationMembership.organization_id == org.id,
            )
        )
        if not elena_tech_res.scalar_one_or_none():
            print("Assigning CONTROLLER membership for Elena in FinBridge Tech...")
            db.add(OrganizationMembership(
                user_id=elena.id,
                organization_id=org.id,
                role="CONTROLLER",
                is_active=True,
            ))
            await db.flush()

        # 4. Check demo bank account
        acc_res = await db.execute(
            select(BankAccount).where(
                BankAccount.organization_id == org.id,
                BankAccount.account_number_masked == "•••• 4242",
            )
        )
        account = acc_res.scalar_one_or_none()

        if not account:
            print("Creating primary operating bank account...")
            account = BankAccount(
                organization_id=org.id,
                account_name="Primary Operating Account",
                institution_name="JPMorgan Chase",
                account_number_masked="•••• 4242",
                account_type="CHECKING",
                currency="USD",
                current_balance=Decimal("250000.00"),
                is_active=True,
            )
            db.add(account)

        await db.commit()
        print("\nSeed completed successfully!")
        print("========================================")
        print("Demo User Credentials:")
        print("  Email:    admin@finbridge.com")
        print("  Password: Password123!")
        print("  Role:     ADMIN")
        print("  Org:      FinBridge Technologies Inc.")
        print("========================================")


if __name__ == "__main__":
    asyncio.run(seed())
