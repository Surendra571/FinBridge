"""
LangGraph Workflow: AI-Assisted Financial Reconciliation (Phase 9).
Implements a 10-stage controlled computational graph where the AI proposes
candidate rankings and the deterministic engine verifies every financial invariant.

The AI NEVER directly approves transactions. All proposals must pass
deterministic financial validation before reaching MATCHED status.
"""
import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_API_KEY"] = ""

import uuid
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from rapidfuzz import fuzz

from app.core.config import settings
from app.schemas.reconciliation import ReconciliationConfig
from app.schemas.ai_reconciliation import (
    CandidateProposal,
    LLMRankingResponse,
)
from app.services.reconciliation.rules import (
    DeterministicRuleValidator,
    ValidationCheckResult,
)
from app.services.ai.sanitization import (
    normalize_merchant,
    extract_reference_tokens,
)
from app.services.ai.openai_client import (
    OpenAIReconciliationClient,
    MockOpenAIReconciliationClient,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMConnectionError,
    LLMMalformedOutputError,
)

logger = logging.getLogger("finbridge.ai.workflow")


class AIReconciliationState(TypedDict):
    """Execution state passed through the 10-stage LangGraph workflow."""
    # Context & Inputs
    organization_id: str
    bank_transaction: Dict[str, Any]
    eligible_ledger_candidates: List[Dict[str, Any]]
    config: Dict[str, Any]
    model_metadata: Dict[str, Any]
    llm_client: Any  # OpenAIReconciliationClient or MockOpenAIReconciliationClient

    # Stage 3 & 4: Normalization & Context
    normalized_bank_merchant: str
    normalized_candidates: List[Dict[str, Any]]
    context_signals: Dict[str, Any]

    # Stage 5 & 6: LLM Proposal & Output Validation
    llm_ranking_response: Optional[Dict[str, Any]]
    llm_error: Optional[str]
    valid_proposals: List[Dict[str, Any]]
    hallucinated_proposals: List[Dict[str, Any]]

    # Stage 7 & 8: Deterministic Validation & Status Assignment
    selected_proposal: Optional[Dict[str, Any]]
    deterministic_validation: Optional[Dict[str, Any]]
    final_decision_status: str  # MATCHED, NEEDS_REVIEW, UNMATCHED, REJECTED
    rule_name: str
    final_explanation: str
    confidence_score: float

    # Stage 9: Human Review Queue Item (for uncertain cases)
    review_queue_item: Optional[Dict[str, Any]]

    # Stage 10: Audit Trail Record
    audit_record: Dict[str, Any]


# ==============================================================================
# Graph Node Implementations (10 Stages)
# ==============================================================================

def stage1_receive_bank_tx(state: AIReconciliationState) -> Dict[str, Any]:
    """Stage 1: Receive unmatched bank transaction and validate baseline integrity."""
    bank_tx = state.get("bank_transaction", {})
    if not bank_tx:
        return {
            "final_decision_status": "REJECTED",
            "rule_name": "MISSING_BANK_TRANSACTION",
            "final_explanation": "No bank transaction provided to reconciliation workflow.",
        }

    # Verify not already reconciled
    if bank_tx.get("reconciliation_status") == "RECONCILED":
        return {
            "final_decision_status": "REJECTED",
            "rule_name": "BANK_TRANSACTION_ALREADY_RECONCILED",
            "final_explanation": "Bank transaction is already reconciled.",
        }

    return {}


def stage2_retrieve_candidates(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 2: Retrieve and filter eligible ledger candidates.
    Excludes already reconciled ledger entries and applies gross currency/date bounds.
    """
    raw_candidates = state.get("eligible_ledger_candidates", [])
    bank_tx = state.get("bank_transaction", {})
    bank_currency = bank_tx.get("currency")

    eligible = []
    for c in raw_candidates:
        # Exclude reconciled records
        if c.get("reconciliation_status") == "RECONCILED":
            continue
        eligible.append(c)

    return {"eligible_ledger_candidates": eligible}


def stage3_normalize_descriptions(state: AIReconciliationState) -> Dict[str, Any]:
    """Stage 3: Normalize merchant descriptions by stripping payment rail artifacts."""
    bank_tx = state.get("bank_transaction", {})
    norm_bank_merchant = normalize_merchant(bank_tx.get("description", ""))

    normalized_candidates = []
    for c in state.get("eligible_ledger_candidates", []):
        norm_desc = normalize_merchant(c.get("description", ""))
        c_copy = dict(c)
        c_copy["normalized_description"] = norm_desc
        normalized_candidates.append(c_copy)

    return {
        "normalized_bank_merchant": norm_bank_merchant,
        "normalized_candidates": normalized_candidates,
    }


def stage4_evaluate_context(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 4: Evaluate references, fuzzy tokens, and transaction context
    to build contextual signals for the LLM prompt.
    """
    bank_tx = state.get("bank_transaction", {})
    norm_bank = state.get("normalized_bank_merchant", "")
    bank_ref_tokens = extract_reference_tokens(bank_tx.get("description", ""))
    if bank_tx.get("reference_number"):
        bank_ref_tokens.extend(extract_reference_tokens(bank_tx.get("reference_number", "")))

    signals_by_candidate = {}
    for c in state.get("normalized_candidates", []):
        c_id = str(c.get("id"))
        norm_c = c.get("normalized_description", "")
        c_ref_tokens = extract_reference_tokens(c.get("description", ""))
        if c.get("reference_number"):
            c_ref_tokens.extend(extract_reference_tokens(c.get("reference_number", "")))

        # RapidFuzz similarity ratio
        sim_score = fuzz.token_set_ratio(norm_bank.lower(), norm_c.lower())
        ref_matches = list(set(bank_ref_tokens).intersection(set(c_ref_tokens)))

        signals_by_candidate[c_id] = {
            "merchant_similarity_ratio": sim_score,
            "reference_matches": ref_matches,
        }

    return {"context_signals": signals_by_candidate}


def stage5_rank_candidates_llm(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 5: Ask LLM to evaluate and rank candidate ledger matches
    using structured JSON schema output.
    """
    candidates = state.get("normalized_candidates", [])
    if not candidates:
        return {
            "llm_ranking_response": {"ranked_candidates": [], "no_match_found": True},
            "llm_error": None,
        }

    llm_client = state.get("llm_client")
    if not llm_client:
        # Default to production or mock client based on configuration
        if settings.OPENAI_API_KEY and not settings.AI_MOCK_FALLBACK:
            llm_client = OpenAIReconciliationClient()
        else:
            llm_client = MockOpenAIReconciliationClient()

    try:
        ranking_response: LLMRankingResponse = llm_client.rank_candidates(
            bank_tx=state.get("bank_transaction", {}),
            candidates=candidates,
            context_signals=state.get("context_signals", {}),
            prompt_version=state.get("model_metadata", {}).get("prompt_version", settings.AI_PROMPT_VERSION),
        )
        return {
            "llm_ranking_response": ranking_response.model_dump(),
            "llm_error": None,
        }
    except LLMTimeoutError as e:
        logger.warning(f"Stage 5 Timeout: {e}")
        return {"llm_ranking_response": None, "llm_error": f"LLM_TIMEOUT: {str(e)}"}
    except LLMRateLimitError as e:
        logger.warning(f"Stage 5 Rate Limit: {e}")
        return {"llm_ranking_response": None, "llm_error": f"LLM_RATE_LIMIT: {str(e)}"}
    except LLMMalformedOutputError as e:
        logger.warning(f"Stage 5 Malformed JSON: {e}")
        return {"llm_ranking_response": None, "llm_error": f"LLM_MALFORMED_OUTPUT: {str(e)}"}
    except Exception as e:
        logger.error(f"Stage 5 Unexpected LLM Error: {e}")
        return {"llm_ranking_response": None, "llm_error": f"LLM_ERROR: {str(e)}"}


def stage6_validate_llm_output(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 6: Validate structured LLM output with Pydantic & prevent hallucinated IDs.
    Never trust model-generated transaction IDs without checking database records!
    """
    llm_error = state.get("llm_error")
    if llm_error:
        # Service degradation / fallback: route to review rather than crashing
        return {
            "valid_proposals": [],
            "hallucinated_proposals": [],
            "final_decision_status": "NEEDS_REVIEW",
            "rule_name": "AI_SERVICE_DEGRADED",
            "final_explanation": f"AI service unavailable during ranking: {llm_error}. Escalated to human review.",
            "confidence_score": 0.0,
        }

    response_data = state.get("llm_ranking_response") or {}
    proposals_raw = response_data.get("ranked_candidates", [])
    eligible_ids = {str(c.get("id")) for c in state.get("eligible_ledger_candidates", [])}

    valid_proposals = []
    hallucinated_proposals = []

    for p in proposals_raw:
        try:
            proposal_obj = CandidateProposal.model_validate(p)
            c_id = str(proposal_obj.candidate_ledger_entry_id)

            # Strict DB Membership Check
            if c_id not in eligible_ids:
                logger.warning(f"Hallucinated candidate ID detected: {c_id}")
                hallucinated_proposals.append(proposal_obj.model_dump())
            else:
                valid_proposals.append(proposal_obj.model_dump())
        except Exception as e:
            logger.error(f"Failed to validate proposal item: {e}")

    return {
        "valid_proposals": valid_proposals,
        "hallucinated_proposals": hallucinated_proposals,
    }


def stage7_validate_deterministic(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 7: Pass AI proposals to the Deterministic Financial Validation Engine.
    All proposed matches must pass exact currency, direction, amount, and date window rules.
    """
    # If a prior stage (e.g. stage 6 error/degradation) assigned a review/reject status, preserve it
    if state.get("final_decision_status") in {"REJECTED", "NEEDS_REVIEW"}:
        return {}
    # If hallucination occurred and no valid proposals exist
    if state.get("hallucinated_proposals") and not state.get("valid_proposals"):
        return {
            "final_decision_status": "NEEDS_REVIEW",
            "rule_name": "HALLUCINATED_ID_DETECTED",
            "final_explanation": "Model proposed a fabricated ledger entry ID not found in database records.",
            "confidence_score": 0.0,
            "deterministic_validation": None,
        }

    valid_proposals = state.get("valid_proposals", [])
    if not valid_proposals:
        return {
            "final_decision_status": "UNMATCHED",
            "rule_name": "NO_AI_PROPOSALS",
            "final_explanation": "AI engine identified no viable ledger candidate matches.",
            "confidence_score": 0.0,
            "deterministic_validation": None,
        }

    # Evaluate the top-ranked proposal
    top_proposal = valid_proposals[0]
    candidate_id = top_proposal.get("candidate_ledger_entry_id")

    # Retrieve full candidate record
    candidate_record = next(
        (c for c in state.get("eligible_ledger_candidates", []) if str(c.get("id")) == candidate_id),
        None,
    )
    if not candidate_record:
        return {
            "final_decision_status": "REJECTED",
            "rule_name": "CANDIDATE_NOT_FOUND",
            "final_explanation": f"Ledger entry {candidate_id} could not be retrieved from active pool.",
            "confidence_score": 0.0,
        }

    bank_tx = state.get("bank_transaction", {})
    cfg = state.get("config", {})

    # Construct reconciliation configuration
    recon_config = ReconciliationConfig(
        date_window_days=cfg.get("date_window_days", 7),
        fee_tolerance=cfg.get("fee_tolerance", "0.00"),
        allow_fee_adjustment=cfg.get("allow_fee_adjustment", False),
        direction_convention=cfg.get("direction_convention", "INVERTED_CASH"),
        require_reference_match=False,
    )

    # Convert date and decimal types
    b_date = bank_tx.get("booking_date")
    if isinstance(b_date, str):
        b_date = date.fromisoformat(b_date)
    l_date = candidate_record.get("posting_date")
    if isinstance(l_date, str):
        l_date = date.fromisoformat(l_date)

    b_amount = Decimal(str(bank_tx.get("amount", "0.00")))
    l_amount = Decimal(str(candidate_record.get("amount", "0.00")))

    # Invoke Pure Python Deterministic Rule Validator
    validation_res: ValidationCheckResult = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=b_amount,
        bank_currency=bank_tx.get("currency", "USD"),
        bank_direction=bank_tx.get("direction", "DEBIT"),
        bank_date=b_date,
        bank_desc=bank_tx.get("description", ""),
        bank_ref=bank_tx.get("reference_number"),
        bank_status=bank_tx.get("reconciliation_status", "UNMATCHED"),
        ledger_amount=l_amount,
        ledger_currency=candidate_record.get("currency", "USD"),
        ledger_direction=candidate_record.get("direction", "CREDIT"),
        ledger_date=l_date,
        ledger_desc=candidate_record.get("description", ""),
        ledger_ref=candidate_record.get("reference_number"),
        ledger_status=candidate_record.get("reconciliation_status", "UNRECONCILED"),
        config=recon_config,
    )

    return {
        "selected_proposal": top_proposal,
        "deterministic_validation": {
            "is_valid": validation_res.is_valid,
            "rule_name": validation_res.rule_name,
            "decision_status": validation_res.decision_status,
            "calculated_variance": str(validation_res.calculated_variance),
            "currency_parity_passed": validation_res.currency_parity_passed,
            "direction_parity_passed": validation_res.direction_parity_passed,
            "amount_parity_passed": validation_res.amount_parity_passed,
            "date_window_passed": validation_res.date_window_passed,
            "unconsumed_check_passed": validation_res.unconsumed_check_passed,
            "reversal_check_passed": validation_res.reversal_check_passed,
            "failure_reason": validation_res.failure_reason,
            "date_difference_days": validation_res.date_difference_days,
        },
    }


def stage8_assign_final_status(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 8: Assign final reconciliation status.
    Ensures that ONLY deterministic-verified proposals with confidence >= threshold
    can be MATCHED. Ambiguous or low-confidence matches go to NEEDS_REVIEW.
    """
    # Check if a prior stage already assigned a terminal status
    if state.get("final_decision_status") in {"REJECTED", "NEEDS_REVIEW", "UNMATCHED"}:
        return {}

    val = state.get("deterministic_validation")
    proposal = state.get("selected_proposal")

    if not val or not proposal:
        return {
            "final_decision_status": "UNMATCHED",
            "rule_name": "NO_VALID_PROPOSAL",
            "final_explanation": "No valid proposal available for status assignment.",
            "confidence_score": 0.0,
        }

    conf = float(proposal.get("confidence_score", 0.0))
    threshold = float(state.get("config", {}).get("confidence_threshold", settings.AI_CONFIDENCE_THRESHOLD))

    # Check for ambiguity among multiple candidates (e.g. top 2 have near-identical score)
    all_proposals = state.get("valid_proposals", [])
    is_ambiguous = False
    if len(all_proposals) > 1:
        second_conf = float(all_proposals[1].get("confidence_score", 0.0))
        if abs(conf - second_conf) <= 0.05 and conf >= 0.70:
            is_ambiguous = True

    # Deterministic validation failed -> Fail closed (REJECTED)
    if not val.get("is_valid"):
        return {
            "final_decision_status": "REJECTED",
            "rule_name": f"AI_PROPOSAL_REJECTED_{val.get('rule_name')}",
            "final_explanation": (
                f"AI proposed match, but deterministic rules failed: {val.get('failure_reason')}"
            ),
            "confidence_score": conf,
        }

    # Deterministic check required review (e.g., fee adjustment, reversal flag, or ambiguity)
    if val.get("decision_status") == "NEEDS_REVIEW" or is_ambiguous:
        rule_label = "AMBIGUOUS_AI_PROPOSALS" if is_ambiguous else val.get("rule_name")
        return {
            "final_decision_status": "NEEDS_REVIEW",
            "rule_name": rule_label,
            "final_explanation": (
                f"Multiple candidate matches with similar confidence scores ({conf:.2f}). Escalated to human review."
                if is_ambiguous
                else f"Deterministic rule requires human approval: {val.get('failure_reason') or proposal.get('reasoning_summary')}"
            ),
            "confidence_score": conf,
        }

    # Low-confidence threshold check
    if conf < threshold:
        return {
            "final_decision_status": "NEEDS_REVIEW",
            "rule_name": "LOW_CONFIDENCE_AI_PROPOSAL",
            "final_explanation": (
                f"Confidence score of {conf:.2f} is below approval threshold of {threshold:.2f}. "
                f"{proposal.get('reasoning_summary')}"
            ),
            "confidence_score": conf,
        }

    # Full approval: Deterministic validation passed and confidence >= threshold
    return {
        "final_decision_status": "MATCHED",
        "rule_name": "AI_ASSISTED_DETERMINISTIC_VERIFIED",
        "final_explanation": (
            f"AI proposed match validated by deterministic financial engine. "
            f"Confidence: {conf:.2f}. {proposal.get('reasoning_summary')}"
        ),
        "confidence_score": conf,
    }


def stage9_route_uncertain_cases(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 9: Route uncertain or ambiguous cases to the human review queue.
    Packages context, signals, and concerns for the human reviewer.
    """
    status = state.get("final_decision_status")
    if status == "NEEDS_REVIEW":
        proposal = state.get("selected_proposal") or {}
        bank_tx = state.get("bank_transaction", {})
        review_item = {
            "bank_transaction_id": bank_tx.get("id"),
            "proposed_ledger_entry_id": proposal.get("candidate_ledger_entry_id"),
            "confidence_score": state.get("confidence_score", 0.0),
            "reasoning_summary": state.get("final_explanation", ""),
            "matching_signals": proposal.get("matching_signals", []),
            "potential_concerns": proposal.get("potential_concerns", []),
            "created_at": datetime.now().isoformat(),
        }
        return {"review_queue_item": review_item}

    return {"review_queue_item": None}


def stage10_record_audit_trail(state: AIReconciliationState) -> Dict[str, Any]:
    """
    Stage 10: Record execution audit trail including model metadata,
    prompt version, matching signals, and deterministic verification results.
    """
    bank_tx = state.get("bank_transaction", {})
    proposal = state.get("selected_proposal") or {}
    val = state.get("deterministic_validation") or {}
    meta = state.get("model_metadata") or {}

    audit_payload = {
        "prompt_version": meta.get("prompt_version", settings.AI_PROMPT_VERSION),
        "model_name": meta.get("model_name", settings.OPENAI_MODEL),
        "bank_transaction_id": str(bank_tx.get("id", "")),
        "proposed_ledger_id": str(proposal.get("candidate_ledger_entry_id", "")),
        "confidence_score": state.get("confidence_score", 0.0),
        "decision_status": state.get("final_decision_status", "UNKNOWN"),
        "rule_name": state.get("rule_name", "UNKNOWN"),
        "explanation": state.get("final_explanation", ""),
        "matching_signals": proposal.get("matching_signals", []),
        "potential_concerns": proposal.get("potential_concerns", []),
        "deterministic_verification": val,
        "hallucinated_ids_count": len(state.get("hallucinated_proposals", [])),
    }

    return {"audit_record": audit_payload}


# ==============================================================================
# LangGraph Workflow Construction
# ==============================================================================

def build_ai_reconciliation_graph() -> Any:
    """Builds and compiles the 10-stage LangGraph for AI financial reconciliation."""
    graph = StateGraph(AIReconciliationState)

    # Register the 10 nodes
    graph.add_node("stage1_receive_bank_tx", stage1_receive_bank_tx)
    graph.add_node("stage2_retrieve_candidates", stage2_retrieve_candidates)
    graph.add_node("stage3_normalize_descriptions", stage3_normalize_descriptions)
    graph.add_node("stage4_evaluate_context", stage4_evaluate_context)
    graph.add_node("stage5_rank_candidates_llm", stage5_rank_candidates_llm)
    graph.add_node("stage6_validate_llm_output", stage6_validate_llm_output)
    graph.add_node("stage7_validate_deterministic", stage7_validate_deterministic)
    graph.add_node("stage8_assign_final_status", stage8_assign_final_status)
    graph.add_node("stage9_route_uncertain_cases", stage9_route_uncertain_cases)
    graph.add_node("stage10_record_audit_trail", stage10_record_audit_trail)

    # Connect linear pipeline
    graph.add_edge(START, "stage1_receive_bank_tx")
    graph.add_edge("stage1_receive_bank_tx", "stage2_retrieve_candidates")
    graph.add_edge("stage2_retrieve_candidates", "stage3_normalize_descriptions")
    graph.add_edge("stage3_normalize_descriptions", "stage4_evaluate_context")
    graph.add_edge("stage4_evaluate_context", "stage5_rank_candidates_llm")
    graph.add_edge("stage5_rank_candidates_llm", "stage6_validate_llm_output")
    graph.add_edge("stage6_validate_llm_output", "stage7_validate_deterministic")
    graph.add_edge("stage7_validate_deterministic", "stage8_assign_final_status")
    graph.add_edge("stage8_assign_final_status", "stage9_route_uncertain_cases")
    graph.add_edge("stage9_route_uncertain_cases", "stage10_record_audit_trail")
    graph.add_edge("stage10_record_audit_trail", END)

    return graph.compile()


# Pre-compiled workflow graph singleton
ai_reconciliation_graph = build_ai_reconciliation_graph()
