"""Evidence retrieval for factual claims.

This module never invents a probability from the wording of a claim.  Search
snippets can help a person verify a statement, but they are not a substitute for
reading authoritative sources.  The API therefore returns attributable evidence
and an explicit ``verified: null`` unless a future deterministic verifier is
added for a specific data domain.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Optional

from web_search import search_evidence


class FactVerificationResult:
    def __init__(
        self,
        claim: str,
        *,
        evidence: Optional[list[dict]] = None,
        status: str = "unverified",
        reasoning: str = "",
    ):
        self.claim = claim
        self.evidence = evidence or []
        self.status = status
        self.reasoning = reasoning

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "verified": None,
            "confidence": None,
            "status": self.status,
            "sources": self.evidence,
            "reasoning": self.reasoning,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "warning": (
                "Search snippets are evidence leads, not a factual verdict. "
                "Open the cited sources and prefer primary/official material."
            ),
        }


class ClaimClassifier:
    """Lightweight routing only; it does not assign confidence."""

    @classmethod
    def classify(cls, text: str) -> tuple[str, None]:
        lowered = text.lower()
        if re.search(r"\b(weather|temperature|forecast|rain|humidity)\b", lowered):
            return "weather", None
        if re.search(r"\b(price|stock|crypto|exchange rate|currency)\b", lowered):
            return "price", None
        if re.search(r"\b(news|latest|announced|reported|election|score)\b", lowered):
            return "current_event", None
        if re.search(r"\b(time|date|today|tomorrow|timezone)\b", lowered):
            return "date_time", None
        return "general", None


async def verify_factual_claim(claim: str) -> FactVerificationResult:
    cleaned = re.sub(r"\s+", " ", (claim or "").strip())[:1000]
    if not cleaned:
        return FactVerificationResult(
            cleaned,
            status="invalid",
            reasoning="A non-empty claim is required.",
        )

    try:
        evidence = await asyncio.wait_for(search_evidence(cleaned, max_results=6), timeout=10.0)
    except asyncio.TimeoutError:
        evidence = []
    except Exception:
        evidence = []

    if not evidence:
        return FactVerificationResult(
            cleaned,
            status="evidence_unavailable",
            reasoning=(
                "No attributable search evidence was available. Vigzone did not "
                "guess a verdict or confidence score."
            ),
        )
    return FactVerificationResult(
        cleaned,
        evidence=evidence,
        status="evidence_found",
        reasoning=(
            f"Retrieved {len(evidence)} attributable result(s). Compare dates, "
            "open the sources, and use primary or official evidence for a final verdict."
        ),
    )


def score_response_accuracy(response_text: str, claim_category: str = "general") -> dict[str, Any]:
    """Return observable quality signals without a fabricated accuracy score."""

    urls = re.findall(r"https?://[^\s)>\]]+", response_text or "")
    return {
        "confidence": None,
        "verification_status": "unverified",
        "quality_indicators": {
            "source_url_count": len(urls),
            "has_uncertainty_language": bool(
                re.search(
                    r"\b(unverified|uncertain|could not confirm|may have changed)\b",
                    response_text or "",
                    re.IGNORECASE,
                )
            ),
            "length_words": len((response_text or "").split()),
        },
        "recommendation": "Verify material claims against the cited primary sources.",
    }


class AccuracyMetadata:
    """Compatibility container with no synthetic confidence percentage."""

    def __init__(
        self,
        confidence: Optional[float] = None,
        sources: Optional[list[str]] = None,
        verification_status: str = "unverified",
    ):
        self.confidence = None
        self.sources = sources or []
        self.verification_status = verification_status
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": None,
            "sources": self.sources,
            "verification_status": self.verification_status,
            "timestamp": self.timestamp,
        }
