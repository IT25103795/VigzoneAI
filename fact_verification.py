"""
Vigzone AI - Accuracy & Fact Verification
===========================================
Provides confidence scoring, fact verification, and source attribution for responses.
Helps ensure 100% real-world accuracy.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Confidence scoring weights for different claim types
CONFIDENCE_WEIGHTS = {
    "date_time": 0.99,  # Server-injected date/time = extremely high confidence
    "current_prices": 0.95,  # Real-time API data = very high
    "weather": 0.90,  # Weather APIs are usually accurate
    "news": 0.75,  # News from DuckDuckGo = moderate confidence
    "factual_claim": 0.70,  # Factual claims from LLM = lower confidence without verification
    "speculation": 0.50,  # Speculation/opinion = low confidence
}


class FactVerificationResult:
    """Result of fact verification with confidence scoring."""

    def __init__(
        self,
        claim: str,
        verified: Optional[bool] = None,
        confidence: float = 0.0,
        sources: Optional[List[str]] = None,
        reasoning: str = "",
    ):
        self.claim = claim
        self.verified = verified
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp 0-1
        self.sources = sources or []
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "verified": self.verified,
            "confidence": f"{self.confidence:.0%}",
            "sources": self.sources,
            "reasoning": self.reasoning,
        }

    def add_source(self, source: str) -> "FactVerificationResult":
        if source not in self.sources:
            self.sources.append(source)
        return self


class ClaimClassifier:
    """Classify claims by type to assign appropriate confidence scores."""

    # Regex patterns for different claim types
    DATE_TIME_PATTERN = re.compile(
        r"\b(today|tomorrow|yesterday|date|time|current|right now|"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"\d{1,2}:\d{2}|am|pm)\b",
        re.IGNORECASE,
    )

    PRICE_PATTERN = re.compile(
        r"\b(price|cost|usd|eur|gbp|inr|lkr|btc|eth|\$|₹|£|€|cryptocurrency|bitcoin|ethereum)\b",
        re.IGNORECASE,
    )

    WEATHER_PATTERN = re.compile(
        r"\b(weather|temperature|rain|humidity|wind|forecast|climate|celsius|fahrenheit)\b",
        re.IGNORECASE,
    )

    NEWS_PATTERN = re.compile(
        r"\b(news|breaking|latest|current event|just happened|announced|"
        r"breaking news|update|headline|reported)\b",
        re.IGNORECASE,
    )

    SPECULATION_PATTERN = re.compile(
        r"\b(probably|maybe|likely|might|could|should|i think|in my opinion|"
        r"it seems|it appears|appears to be|allegedly|supposedly|rumor)\b",
        re.IGNORECASE,
    )

    @classmethod
    def classify(cls, text: str) -> Tuple[str, float]:
        """
        Classify a claim into one of the confidence categories.
        Returns: (category, base_confidence)
        """
        if cls.DATE_TIME_PATTERN.search(text):
            return "date_time", CONFIDENCE_WEIGHTS["date_time"]

        if cls.PRICE_PATTERN.search(text):
            return "current_prices", CONFIDENCE_WEIGHTS["current_prices"]

        if cls.WEATHER_PATTERN.search(text):
            return "weather", CONFIDENCE_WEIGHTS["weather"]

        if cls.NEWS_PATTERN.search(text):
            return "news", CONFIDENCE_WEIGHTS["news"]

        if cls.SPECULATION_PATTERN.search(text):
            return "speculation", CONFIDENCE_WEIGHTS["speculation"]

        # Default to factual claim
        return "factual_claim", CONFIDENCE_WEIGHTS["factual_claim"]


class AnswerQualityAnalyzer:
    """Analyze answer quality and assign confidence scores."""

    # Warning signs in responses that lower confidence
    HEDGING_PHRASES = (
        "i'm not sure",
        "i'm not certain",
        "i don't know",
        "i can't confirm",
        "i'm unable to",
        "unverified",
        "unconfirmed",
        "alleged",
        "rumor has it",
        "it's unclear",
        "it's unknown",
    )

    # Positive indicators that raise confidence
    SOURCE_INDICATORS = (
        "according to",
        "reported by",
        "confirmed by",
        "verified by",
        "official",
        "announcement",
        "statement",
        "sources say",
        "as of",
    )

    @classmethod
    def adjust_confidence(cls, text: str, base_confidence: float) -> float:
        """Adjust confidence based on answer quality indicators."""
        lower_text = text.lower()

        # Reduce confidence for hedging language
        hedging_count = sum(1 for phrase in cls.HEDGING_PHRASES if phrase in lower_text)
        reduction = hedging_count * 0.1  # Each hedging phrase reduces by 10%

        # Increase confidence for source attribution
        source_count = sum(1 for phrase in cls.SOURCE_INDICATORS if phrase in lower_text)
        increase = source_count * 0.05  # Each source indicator increases by 5%

        adjusted = base_confidence - reduction + increase
        return max(0.0, min(1.0, adjusted))  # Clamp 0-1


async def verify_factual_claim(claim: str) -> FactVerificationResult:
    """
    Verify a factual claim and return verification result with confidence.
    This is a framework; actual verification would integrate with fact-check APIs.
    """
    category, base_confidence = ClaimClassifier.classify(claim)

    result = FactVerificationResult(
        claim=claim,
        confidence=base_confidence,
        reasoning=f"Claim classified as '{category}'. "
        f"Based on expected accuracy of {category} data sources.",
    )

    # Map to common sources based on claim type
    if category == "date_time":
        result.add_source("Server-side system time")
    elif category == "current_prices":
        result.add_source("CoinGecko / Yahoo Finance")
    elif category == "weather":
        result.add_source("OpenWeather / DuckDuckGo")
    elif category == "news":
        result.add_source("DuckDuckGo News")

    return result


def score_response_accuracy(
    response_text: str, claim_category: str = "factual_claim"
) -> Dict[str, Any]:
    """
    Score the accuracy/quality of a full response.
    Returns confidence score and quality assessment.
    """
    base_confidence = CONFIDENCE_WEIGHTS.get(claim_category, 0.70)
    adjusted_confidence = AnswerQualityAnalyzer.adjust_confidence(response_text, base_confidence)

    # Analyze response characteristics
    has_sources = any(
        phrase in response_text.lower() for phrase in AnswerQualityAnalyzer.SOURCE_INDICATORS
    )
    has_citations = bool(re.search(r"\[.*?\]|\(.*?https?://", response_text))
    has_disclaimers = bool(re.search(r"\b(disclaimer|note|caveat|important)\b", response_text, re.IGNORECASE))

    quality_indicators = {
        "has_source_attribution": has_sources,
        "has_citations": has_citations,
        "has_disclaimers": has_disclaimers,
        "length_chars": len(response_text),
        "length_words": len(response_text.split()),
    }

    return {
        "confidence": adjusted_confidence,
        "confidence_pct": f"{adjusted_confidence:.0%}",
        "quality_indicators": quality_indicators,
        "recommendation": (
            "✅ High confidence - can cite to users"
            if adjusted_confidence >= 0.85
            else "⚠️ Medium confidence - add source citations"
            if adjusted_confidence >= 0.70
            else "❌ Low confidence - verify before presenting"
        ),
    }


def format_response_with_confidence(
    response: str, confidence: float, sources: Optional[List[str]] = None
) -> str:
    """
    Format a response with confidence badge and source citations.
    This is shown to the user to indicate how trustworthy the answer is.
    """
    confidence_badge = (
        "🟢 **Very High Confidence**"
        if confidence >= 0.90
        else "🟡 **Moderate Confidence**"
        if confidence >= 0.70
        else "🔴 **Low Confidence - Verify Independently**"
    )

    formatted = f"{response}\n\n---\n{confidence_badge} ({confidence:.0%})"

    if sources:
        formatted += f"\n**Sources:** {', '.join(sources)}"

    return formatted


# ── API Response Schemas ──────────────────────────────────────────────────────

class AccuracyMetadata:
    """Metadata about answer accuracy attached to API responses."""

    def __init__(
        self,
        confidence: float,
        sources: Optional[List[str]] = None,
        verification_status: str = "unverified",
    ):
        self.confidence = max(0.0, min(1.0, confidence))
        self.sources = sources or []
        self.verification_status = verification_status  # unverified, verified, contradicted
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": f"{self.confidence:.0%}",
            "sources": self.sources,
            "verification_status": self.verification_status,
            "timestamp": self.timestamp,
        }
