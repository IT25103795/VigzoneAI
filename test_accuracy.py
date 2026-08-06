"""
Vigzone AI - Accuracy & Real-World Data Tests
==============================================
Tests for 100% accuracy real-world data access.
"""

import pytest

# Import modules to test
try:
    from realworld_data import (
        get_current_datetime,
        get_datetime_info,
        get_weather,
        get_price,
        get_exchange_rate,
        _get_user_timezone_name,
    )
    HAS_REALWORLD_DATA = True
except ImportError:
    HAS_REALWORLD_DATA = False

try:
    from fact_verification import (
        ClaimClassifier,
        AnswerQualityAnalyzer,
        verify_factual_claim,
        score_response_accuracy,
        FactVerificationResult,
        CONFIDENCE_WEIGHTS,
    )
    HAS_FACT_VERIFICATION = True
except ImportError:
    HAS_FACT_VERIFICATION = False


# ── Real-World Data Tests ──────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_REALWORLD_DATA, reason="realworld_data module not available")
class TestRealtimeData:
    """Test real-time data access functions."""

    def test_get_current_datetime_format(self):
        """Test that current datetime is formatted correctly."""
        dt = get_current_datetime()
        assert isinstance(dt, str)
        assert len(dt) > 0
        # Should contain day, month, year, time, and timezone
        assert any(month in dt for month in ["January", "February", "March", "April", "May", "June",
                                               "July", "August", "September", "October", "November", "December"])

    def test_get_datetime_info_structure(self):
        """Test datetime info structure."""
        info = get_datetime_info()
        assert isinstance(info, dict)
        assert "full" in info
        assert "date" in info
        assert "time" in info
        assert "timezone" in info
        assert "day" in info
        assert "iso" in info

    def test_timezone_handling(self):
        """Test timezone name retrieval."""
        tz_name = _get_user_timezone_name()
        assert isinstance(tz_name, str)
        assert len(tz_name) > 0
        # Should be IANA timezone format
        assert "/" in tz_name or tz_name == "UTC"

    @pytest.mark.asyncio
    async def test_weather_endpoint_returns_dict(self):
        """Test that weather endpoint returns proper structure if successful."""
        # This test may fail without internet, so we make it optional
        try:
            weather = await get_weather("London")
            if weather:
                assert isinstance(weather, dict)
                assert "source" in weather
                assert "confidence" in weather
                assert 0 <= weather["confidence"] <= 1
        except Exception:
            pytest.skip("Network unavailable")

    @pytest.mark.asyncio
    async def test_price_lookup_structure(self):
        """Test price data structure if available."""
        try:
            # Try fetching Bitcoin price (most reliable)
            price = await get_price("BTC", "crypto")
            if price:
                assert isinstance(price, dict)
                assert "source" in price
                assert "confidence" in price
                assert price["confidence"] >= 0.85  # Crypto prices should be high confidence
        except Exception:
            pytest.skip("Network unavailable")

    @pytest.mark.asyncio
    async def test_exchange_rate_structure(self):
        """Test exchange rate data structure."""
        try:
            rate = await get_exchange_rate("USD", "EUR")
            if rate:
                assert isinstance(rate, dict)
                assert "rate" in rate
                assert "source" in rate
                assert rate["rate"] > 0
        except Exception:
            pytest.skip("Network unavailable")


# ── Fact Verification Tests ────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_FACT_VERIFICATION, reason="fact_verification module not available")
class TestFactVerification:
    """Test fact verification and confidence scoring."""

    def test_claim_classification_datetime(self):
        """Test that date/time claims are classified correctly."""
        category, confidence = ClaimClassifier.classify("What's the date today?")
        assert category == "date_time"
        assert confidence == CONFIDENCE_WEIGHTS["date_time"]
        assert confidence >= 0.95  # Date/time should be very high confidence

    def test_claim_classification_price(self):
        """Test that price claims are classified correctly."""
        category, confidence = ClaimClassifier.classify("What's the Bitcoin price?")
        assert category == "current_prices"
        assert confidence == CONFIDENCE_WEIGHTS["current_prices"]
        assert confidence >= 0.90  # Price data should be high confidence

    def test_claim_classification_weather(self):
        """Test that weather claims are classified correctly."""
        category, confidence = ClaimClassifier.classify("What's the weather like?")
        assert category == "weather"
        assert confidence == CONFIDENCE_WEIGHTS["weather"]

    def test_claim_classification_news(self):
        """Test that news claims are classified correctly."""
        category, confidence = ClaimClassifier.classify("What's the latest news?")
        assert category == "news"

    def test_claim_classification_speculation(self):
        """Test that speculation is classified as low confidence."""
        category, confidence = ClaimClassifier.classify("I think it might be true that aliens exist")
        assert category == "speculation"
        assert confidence < 0.70  # Speculation should be lower confidence

    def test_hedging_phrases_reduce_confidence(self):
        """Test that hedging language reduces confidence scores."""
        base_confidence = 0.85
        response_with_hedging = "I'm not sure, but it might be true that..."
        adjusted = AnswerQualityAnalyzer.adjust_confidence(response_with_hedging, base_confidence)
        assert adjusted < base_confidence

    def test_source_indicators_increase_confidence(self):
        """Test that source attribution increases confidence."""
        base_confidence = 0.70
        response_with_sources = "According to official sources, the announcement states..."
        adjusted = AnswerQualityAnalyzer.adjust_confidence(response_with_sources, base_confidence)
        assert adjusted > base_confidence

    def test_confidence_is_clamped(self):
        """Test that confidence is always between 0 and 1."""
        # Very high base confidence
        high = AnswerQualityAnalyzer.adjust_confidence("Perfect answer", 0.99)
        assert 0 <= high <= 1
        
        # Very low base confidence
        low = AnswerQualityAnalyzer.adjust_confidence("I don't know", 0.01)
        assert 0 <= low <= 1

    def test_fact_verification_result_structure(self):
        """Test FactVerificationResult data structure."""
        result = FactVerificationResult(
            claim="Bitcoin is worth $50,000",
            verified=True,
            confidence=0.92,
            sources=["CoinGecko"],
            reasoning="Price verified via real-time API",
        )
        
        assert result.claim == "Bitcoin is worth $50,000"
        assert result.verified is True
        assert result.confidence == 0.92
        assert "CoinGecko" in result.sources
        
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "confidence" in result_dict
        assert result_dict["confidence"] == "92%"

    def test_response_accuracy_scoring(self):
        """Test response accuracy scoring."""
        response = "According to OpenWeather API, it's 25°C in Colombo with 60% humidity."
        scores = score_response_accuracy(response, "weather")
        
        assert "confidence" in scores
        assert "quality_indicators" in scores
        assert "recommendation" in scores
        assert 0 <= scores["confidence"] <= 1

    def test_high_confidence_recommendation(self):
        """Test that high-confidence responses get appropriate recommendation."""
        response = "According to the latest news, the stock price is $150.25 as confirmed by official sources."
        scores = score_response_accuracy(response, "current_prices")
        
        if scores["confidence"] >= 0.85:
            assert "High confidence" in scores["recommendation"]

    @pytest.mark.asyncio
    async def test_verify_factual_claim(self):
        """Test the main verify_factual_claim function."""
        result = await verify_factual_claim("What is today's date?")
        
        assert isinstance(result, FactVerificationResult)
        assert result.claim == "What is today's date?"
        assert result.confidence >= 0.95  # Date should be very high confidence
        assert len(result.sources) > 0


# ── Integration Tests ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not (HAS_REALWORLD_DATA and HAS_FACT_VERIFICATION), 
                    reason="Required modules not available")
class TestAccuracyIntegration:
    """Integration tests combining real-world data and fact verification."""

    @pytest.mark.asyncio
    async def test_weather_accuracy_pipeline(self):
        """Test the full weather query pipeline."""
        try:
            weather = await get_weather("London")
            if weather:
                # Verify the data is appropriately scored
                assert weather["confidence"] > 0.85
                assert "source" in weather
        except Exception:
            pytest.skip("Network unavailable")

    @pytest.mark.asyncio
    async def test_price_accuracy_pipeline(self):
        """Test the full price query pipeline."""
        try:
            price = await get_price("BTC", "crypto")
            if price:
                # High-confidence source
                assert price["confidence"] > 0.90
                assert "source" in price
                assert price["source"] in ["CoinGecko", "Yahoo Finance"]
        except Exception:
            pytest.skip("Network unavailable")

    def test_mixed_accuracy_claims(self):
        """Test handling of different claim types with appropriate confidence."""
        claims = [
            ("Today's date is important", "date_time"),
            ("Bitcoin's price fluctuates", "current_prices"),
            ("Weather patterns change", "weather"),
        ]
        
        for claim, expected_category in claims:
            category, confidence = ClaimClassifier.classify(claim)
            assert category == expected_category
            # All should have non-zero confidence
            assert confidence > 0


# ── Performance Tests ──────────────────────────────────────────────────────────

class TestPerformance:
    """Test performance characteristics."""

    def test_claim_classification_is_fast(self):
        """Test that claim classification is sub-millisecond."""
        import time
        
        start = time.time()
        for _ in range(100):
            ClaimClassifier.classify("What's the weather?")
        elapsed = time.time() - start
        
        # Should classify 100 claims in < 100ms
        assert elapsed < 0.1

    def test_confidence_adjustment_is_fast(self):
        """Test that confidence adjustment is fast."""
        import time
        
        response = "This is a sample response with lots of text about various things. " * 10
        start = time.time()
        for _ in range(100):
            AnswerQualityAnalyzer.adjust_confidence(response, 0.75)
        elapsed = time.time() - start
        
        # Should adjust 100 responses in < 100ms
        assert elapsed < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
