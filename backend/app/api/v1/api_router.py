"""
FinBridge API v1 Router Aggregator.
Mounts all versioned domain routers.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    auth,
    organizations,
    dashboard,
    bank_accounts,
    statements,
    ledger,
    reconciliation,
    ai_reconciliation,
    reviews,
    audit,
    integrations,
    reports,
)

api_v1_router = APIRouter()

# Mount health endpoints
api_v1_router.include_router(health.router)

# Mount authentication & session endpoints
api_v1_router.include_router(auth.router)

# Mount organization & membership endpoints
api_v1_router.include_router(organizations.router)

# Mount dashboard overview endpoints
api_v1_router.include_router(dashboard.router)

# Mount bank account endpoints
api_v1_router.include_router(bank_accounts.router)

# Mount statement ingestion endpoints
api_v1_router.include_router(statements.router)

# Mount general ledger ingestion endpoints
api_v1_router.include_router(ledger.router)

# Mount deterministic reconciliation endpoints
api_v1_router.include_router(reconciliation.router)

# Mount AI-assisted reconciliation endpoints (LangGraph)
api_v1_router.include_router(ai_reconciliation.router)

# Mount human review and maker-checker endpoints
api_v1_router.include_router(reviews.router)

# Mount audit trail and cryptographic integrity endpoints
api_v1_router.include_router(audit.router)

# Mount simulated integrations and reliability endpoints
api_v1_router.include_router(integrations.router)

# Mount financial reports and analytics endpoints
api_v1_router.include_router(reports.router)
