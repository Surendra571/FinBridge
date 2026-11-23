"""
Pydantic Schemas for Simulated Integrations, Reliability & DLQ Management (Phase 12).
Defines contracts for failure simulation, query-before-retry idempotency,
and dead-letter queue recovery.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class FailureMode(str, Enum):
    NONE = "NONE"
    RATE_LIMIT_429 = "RATE_LIMIT_429"
    SERVER_ERROR_500 = "SERVER_ERROR_500"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
    DELAYED_RESPONSE = "DELAYED_RESPONSE"
    DUPLICATE_WEBHOOK = "DUPLICATE_WEBHOOK"
    NETWORK_INTERRUPTION = "NETWORK_INTERRUPTION"
    ERP_WRITE_TIMEOUT = "ERP_WRITE_TIMEOUT"
    WORKER_CRASH = "WORKER_CRASH"


class ProviderType(str, Enum):
    CORE_BANKING = "CORE_BANKING"
    ERP_LEDGER = "ERP_LEDGER"
    WEBHOOK_RECEIVER = "WEBHOOK_RECEIVER"


class SimulateIntegrationRequest(BaseModel):
    provider_type: str = Field(default="ERP_LEDGER", description="CORE_BANKING or ERP_LEDGER")
    failure_mode: str = Field(default="NONE", description="Simulated failure scenario")
    endpoint: str = Field(default="/api/v1/erp/journals", description="Target provider endpoint")
    http_method: str = Field(default="POST", description="HTTP Method")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Request body payload")
    idempotency_key: Optional[str] = Field(default=None, description="Client-provided idempotency key")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum automated retry attempts")
    base_backoff_seconds: float = Field(default=0.1, ge=0.01, le=5.0, description="Base backoff multiplier")
    simulated_delay_seconds: float = Field(default=0.0, ge=0.0, le=5.0, description="Additional server latency")


class RetryScheduleItem(BaseModel):
    attempt: int
    backoff_delay_seconds: float
    jitter_seconds: float
    total_wait_seconds: float
    status: str
    error: Optional[str] = None


class SimulateIntegrationResponse(BaseModel):
    status: str = Field(..., description="COMPLETED, FAILED, DEAD_LETTER, or RECOVERED_BY_QUERY")
    response_status: Optional[int] = Field(default=None, description="HTTP response code")
    latency_ms: int
    attempts_made: int
    error_category: str
    error_message: Optional[str] = None
    idempotency_key: str
    correlation_id: str
    response_payload: Optional[Dict[str, Any]] = None
    retry_schedule: List[RetryScheduleItem] = Field(default_factory=list)
    query_before_retry_performed: bool = Field(default=False, description="Whether inquiry was made before blind retry")
    double_write_prevented: bool = Field(default=False, description="Whether double financial posting was prevented")


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    provider_name: str
    provider_type: str
    base_url: str
    is_simulated: bool
    is_active: bool
    health_status: str
    consecutive_failures: int
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class IntegrationRequestItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    integration_id: uuid.UUID
    idempotency_key: Optional[str] = None
    correlation_id: str
    endpoint: str
    http_method: str
    response_status: Optional[int] = None
    latency_ms: int
    error_category: str
    error_message: Optional[str] = None
    status: str
    retry_count: int
    recovery_notes: Optional[str] = None
    created_at: datetime


class SimulatedWebhookRequest(BaseModel):
    event_id: str = Field(..., description="Unique provider webhook event identifier")
    event_type: str = Field(default="TRANSACTION_SETTLED", description="Webhook event category")
    account_number: str = Field(..., description="Target bank account number")
    amount: str = Field(..., description="Monetary transaction amount")
    currency: str = Field(default="USD", description="Currency ISO code")
    transaction_reference: Optional[str] = Field(default=None)


class SimulatedWebhookResponse(BaseModel):
    status: str = Field(..., description="PROCESSED or DEDUPLICATED")
    is_duplicate: bool
    message: str
    event_id: str
    execution_time_ms: int


class DeadLetterRecoveryRequest(BaseModel):
    resolution_notes: Optional[str] = Field(default=None, description="Notes documenting resolution or manual fix")
