# FinBridge Known Architectural Limitations & Operational Boundaries

**Document Version**: 1.0.0  
**Last Updated**: 2026-11-21  
**Scope**: Ingestion, Storage, Distributed State, AI Suggestion Pipeline, and Cryptographic Logging  

---

## 1. Document Ingestion Limitations

### Scanned PDFs and Handwritten Statements
- **Current Behavior**: FinBridge parses digital text layers and vector tables from PDF statements using `pdfplumber`. If an uploaded statement is a scanned bitmap or photocopied image with no extractable font layer, ingestion halts with an explicit error:
  ```
  HTTP 422 Unprocessable Entity: Scanned image PDF detected with no digital text layer.
  OCR processing required.
  ```
- **Rationale & Scope**: Optical Character Recognition (OCR) engines (e.g. Tesseract OCR, AWS Textract, Google Cloud Vision) require heavy external dependencies and introduce character error rates (CER) that can corrupt financial numbers (e.g. reading `$1,000.00` as `$1,000.80`). 
- **Production Recommendation**: Scanned PDFs must be routed through a dedicated OCR microservice with confidence scoring prior to FinBridge ingestion.

### Maximum Statement File Size
- Ingestion ceiling is capped at 15MB (`MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024`). Files exceeding this limit receive HTTP 413. For statements larger than 15MB, statements should be split by monthly or quarterly date periods.

---

## 2. Cryptographic Audit Chaining & Database Tampering Boundaries

### Hash Chaining Guarantees & Boundaries
- **What SHA-256 Hash Chaining Guarantees**:
  - Detects any modification, insertion, or deletion of historical audit events after creation.
  - The hash of event $N$ cryptographically binds all fields of event $N$ and the hash of event $N-1$.
  - ORM-level event listeners prevent application-layer `UPDATE` and `DELETE` commands.
- **What Hash Chaining Does Not Prevent**:
  - If an adversary acquires superuser access to the raw database server (e.g. `postgres` superuser or root disk access), they could rewrite all rows and recalculate the forward hash chain from the point of tampering to the tip.
- **Production Recommendation**:
  - Replicate audit event hashes to write-once-read-many (WORM) storage, Amazon S3 Object Lock in Compliance mode, or an immutable enterprise ledger (e.g. CloudTrail, Azure Immutable Blob Storage).

---

## 3. Rate Limiting in Distributed Topologies

### Node-Local In-Memory Sliding Window
- The built-in `SlidingWindowRateLimiter` maintains sliding window request timestamps in application memory (`defaultdict(list)`).
- **Limitation**: When FinBridge is scaled horizontally behind a round-robin load balancer across multiple Kubernetes pods or container replicas, each pod maintains its own rate limit counter.
- **Production Recommendation**:
  - Configure the centralized Redis connection (`REDIS_URL`) so sliding window counters use a distributed Redis ZSET (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`) shared across all worker instances.

---

## 4. AI-Assisted Reconciliation (LangGraph Pipeline)

### Non-Authoritative Advisory Role
- **Strict Constraint**: The OpenAI LangGraph workflow is an **advisory matching assistant only**.
- **Limitation**: The AI model **never approves or finalizes financial matches directly**. Every AI-proposed candidate match is passed to the deterministic Python mathematical validation engine (Tier 3) to verify:
  1. Amount compatibility (accounting for authorized fee tolerances).
  2. Currency identity (same ISO currency).
  3. Direction alignment (Bank Credit matches Ledger Debit, Bank Debit matches Ledger Credit).
  4. Date window constraints.
  5. Single-use uniqueness (transaction cannot be double-matched).
- If the deterministic gate fails, the AI proposal is rejected and queued in the Human Review Workspace.

---

## 5. End-to-End Browser Testing in Sandboxed Headless Environments

### Playwright Headless Browser Dependencies
- Playwright end-to-end browser tests require host-level Linux/Windows graphics libraries and Chromium binaries (`npx playwright install`).
- In minimal sandboxed environments or bare container runners lacking display libraries, browser automation must be executed via containerized browser sidecars or dedicated CI matrix runners.

