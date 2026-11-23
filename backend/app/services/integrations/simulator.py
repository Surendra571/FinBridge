"""
Simulated External Financial Providers Engine (Phase 12).
Clearly labeled as SIMULATED integration infrastructure.
Accurately models Core Banking and NetSuite/SAP ERP behavior under distributed failure conditions:
- HTTP 429 rate limits
- HTTP 500 server crashes
- Connection & read timeouts
- Delayed server latency
- Network socket drops
- Critical scenario: ERP write commits on host but response drops before returning to client
"""
import uuid
import asyncio
import time
from typing import Dict, Any, Optional


class SimulatedExternalProvider:
    """
    Simulated external bank and ERP ledger host.
    Maintains an independent in-memory ledger to simulate true remote host behavior.
    """

    def __init__(self, provider_name: str, provider_type: str):
        self.provider_name = provider_name
        self.provider_type = provider_type
        # In-memory storage of transactions successfully committed by the remote host
        self.committed_operations: Dict[str, Dict[str, Any]] = {}
        # Count of operations executed
        self.total_writes_committed: int = 0

    def query_operation(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """
        Query API endpoint exposed by modern ERPs/Core Banking systems.
        Allows clients to verify if an operation succeeded before blindly retrying a write.
        """
        return self.committed_operations.get(idempotency_key)

    async def execute_request(
        self,
        endpoint: str,
        http_method: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        failure_mode: str = "NONE",
        simulated_delay_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Executes a simulated external HTTP request, inducing distributed failure modes where requested.
        """
        if simulated_delay_seconds > 0:
            await asyncio.sleep(simulated_delay_seconds)

        # Failure Case 1: Rate limit 429
        if failure_mode == "RATE_LIMIT_429":
            raise RateLimitError("HTTP 429: Rate limit exceeded. Retry-After: 1s")

        # Failure Case 2: Server error 500
        if failure_mode == "SERVER_ERROR_500":
            raise InternalServerError("HTTP 500: Remote ERP application database deadlock")

        # Failure Case 3: Connection timeout
        if failure_mode == "CONNECTION_TIMEOUT":
            raise ConnectionTimeoutError("Connection timed out: Failed to establish TCP handshake with remote host")

        # Failure Case 4: Network interruption
        if failure_mode == "NETWORK_INTERRUPTION":
            raise NetworkInterruptionError("Socket error: Remote peer abruptly reset connection during TLS negotiation")

        # Failure Case 5: Worker crash
        if failure_mode == "WORKER_CRASH":
            raise WorkerCrashError("FATAL: Distributed celery worker crashed with SIGSEGV")

        # Failure Case 6: CRITICAL SCENARIO - ERP Write succeeds, but HTTP response times out!
        if failure_mode == "ERP_WRITE_TIMEOUT":
            # The ERP server processes and COMMITS the financial journal entry to its ledger:
            operation_ref = f"ERP-JRN-{uuid.uuid4().hex[:6].upper()}"
            if idempotency_key:
                self.committed_operations[idempotency_key] = {
                    "operation_reference": operation_ref,
                    "status": "COMMITTED_IN_LEDGER",
                    "amount": payload.get("amount", "0.00"),
                    "currency": payload.get("currency", "USD"),
                    "committed_at": time.time(),
                }
            self.total_writes_committed += 1
            # BUT the return network connection times out before the client gets the HTTP response!
            raise ReadTimeoutAfterWriteError(
                "Read timeout: Write succeeded on remote ERP, but socket closed before HTTP response delivery"
            )

        # Standard Success Path (failure_mode == NONE or DELAYED_RESPONSE)
        if idempotency_key and idempotency_key in self.committed_operations:
            # Idempotent return of already committed transaction
            return {
                "status_code": 200,
                "data": self.committed_operations[idempotency_key],
                "message": "Operation already committed (idempotent return)",
            }

        operation_ref = f"TX-{uuid.uuid4().hex[:8].upper()}"
        res_data = {
            "operation_reference": operation_ref,
            "status": "COMMITTED",
            "amount": payload.get("amount", "0.00"),
            "currency": payload.get("currency", "USD"),
            "timestamp": time.time(),
        }

        if idempotency_key:
            self.committed_operations[idempotency_key] = res_data

        self.total_writes_committed += 1
        return {
            "status_code": 200,
            "data": res_data,
            "message": "Operation successfully executed on simulated host",
        }


# Custom simulated distributed error classes
class RateLimitError(Exception):
    pass

class InternalServerError(Exception):
    pass

class ConnectionTimeoutError(Exception):
    pass

class NetworkInterruptionError(Exception):
    pass

class ReadTimeoutAfterWriteError(Exception):
    pass

class WorkerCrashError(Exception):
    pass


# Shared singleton mock servers for testing
simulated_core_banking = SimulatedExternalProvider(
    provider_name="SIMULATED_CORE_BANKING_CHASE",
    provider_type="CORE_BANKING",
)

simulated_erp_netsuite = SimulatedExternalProvider(
    provider_name="SIMULATED_ERP_NETSUITE",
    provider_type="ERP_LEDGER",
)
