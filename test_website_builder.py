"""
Vigzone AI - Website Builder Tests
===================================
Tests for website detection, categorization, and specialized prompts.
"""

import pytest
from website_builder import (
    WebsiteRequest,
    WebsiteSystemPrompt,
    get_website_specific_params,
    COMPILED_WEBSITE_PATTERNS,
)


class TestWebsiteDetection:
    """Test website request detection."""

    def test_detect_landing_page(self):
        """Test landing page detection."""
        text = "Build me a landing page for my SaaS product"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "landing_page" in req.matched_patterns

    def test_detect_portfolio(self):
        """Test portfolio detection."""
        text = "Create a portfolio website to showcase my design work"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "portfolio" in req.matched_patterns

    def test_detect_ecommerce(self):
        """Test e-commerce detection."""
        text = "Build an online store with product pages and shopping cart"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "ecommerce" in req.matched_patterns

    def test_detect_blog(self):
        """Test blog detection."""
        text = "Create a blog site with article listings"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "blog" in req.matched_patterns

    def test_detect_dashboard(self):
        """Test dashboard detection."""
        text = "Build an admin dashboard for analytics"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "dashboard" in req.matched_patterns

    def test_detect_react_app(self):
        """Test React app detection."""
        text = "Create a React single-page app with state management"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "spa" in req.matched_patterns

    def test_detect_html_css_request(self):
        """Test HTML/CSS/JS request detection."""
        text = "Build an HTML5 website with responsive CSS"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert "html_css_js" in req.matched_patterns

    def test_non_website_request(self):
        """Test that non-website requests are not detected."""
        text = "Explain how machine learning works"
        req = WebsiteRequest(text)
        assert not req.is_website_request

    def test_framework_detection_react(self):
        """Test React framework detection."""
        text = "Build a React website"
        req = WebsiteRequest(text)
        assert "React" in req.frameworks

    def test_framework_detection_vue(self):
        """Test Vue framework detection."""
        text = "Create a Vue.js app"
        req = WebsiteRequest(text)
        assert "Vue" in req.frameworks

    def test_framework_detection_tailwind(self):
        """Test Tailwind framework detection."""
        text = "Build with Tailwind CSS"
        req = WebsiteRequest(text)
        assert "Tailwind" in req.frameworks

    def test_multiple_frameworks(self):
        """Test detection of multiple frameworks."""
        text = "Build a Next.js website using Tailwind CSS"
        req = WebsiteRequest(text)
        assert "Next.js" in req.frameworks
        assert "Tailwind" in req.frameworks

    def test_website_type_priority(self):
        """Test that primary website type is correctly prioritized."""
        text = "Build a landing page portfolio website"
        req = WebsiteRequest(text)
        # Landing page should have priority over portfolio
        assert req.website_type == "landing_page"

    def test_confidence_scoring(self):
        """Test confidence scoring based on match count."""
        # Single match
        text1 = "Build a website"
        req1 = WebsiteRequest(text1)
        confidence1 = req1.confidence

        # Multiple matches
        text2 = "Build a responsive HTML5 website with CSS and JavaScript"
        req2 = WebsiteRequest(text2)
        confidence2 = req2.confidence

        # More matches should have higher confidence
        assert confidence2 > confidence1

    def test_description_generation(self):
        """Test human-readable description generation."""
        text = "Build a React landing page"
        req = WebsiteRequest(text)
        desc = req.get_description()
        assert "landing_page" in desc
        assert "React" in desc


class TestWebsiteSystemPrompt:
    """Test specialized system prompt generation."""

    def test_prompt_generation_basic(self):
        """Test that system prompt is generated."""
        req = WebsiteRequest("Build a website")
        prompt = WebsiteSystemPrompt.generate_website_prompt(req)
        assert "WEBSITE CREATION MODE" in prompt
        assert len(prompt) > 500  # Should be substantial

    def test_prompt_includes_design_principles(self):
        """Test that prompt emphasizes design principles."""
        req = WebsiteRequest("Build a portfolio")
        prompt = WebsiteSystemPrompt.generate_website_prompt(req)
        assert "DESIGN EXCELLENCE" in prompt
        assert "responsive" in prompt.lower()
        assert "accessible" in prompt.lower()

    def test_prompt_includes_landing_page_guidance(self):
        """Test landing page-specific guidance."""
        req = WebsiteRequest("Build a landing page")
        prompt = WebsiteSystemPrompt.generate_website_prompt(req)
        assert "hero section" in prompt.lower()
        assert "CTA" in prompt

    def test_prompt_includes_portfolio_guidance(self):
        """Test portfolio-specific guidance."""
        req = WebsiteRequest("Create a portfolio website")
        prompt = WebsiteSystemPrompt.generate_website_prompt(req)
        assert "project" in prompt.lower()
        assert "showcase" in prompt.lower()

    def test_prompt_includes_dashboard_guidance(self):
        """Test dashboard-specific guidance."""
        req = WebsiteRequest("Build a dashboard")
        prompt = WebsiteSystemPrompt.generate_website_prompt(req)
        assert "dashboard" in prompt.lower()
        assert "metric" in prompt.lower()

    def test_prompt_framework_warning(self):
        """Test that framework-specific requests warn to use exact framework."""
        req = WebsiteRequest("Build a React website")
        prompt = WebsiteSystemPrompt.generate_website_prompt(req)
        assert "React" in prompt
        assert "exactly" in prompt.lower()

    def test_color_schemes_available(self):
        """Test that color schemes are defined."""
        schemes = WebsiteSystemPrompt.COLOR_SCHEMES
        assert "modern" in schemes
        assert "professional" in schemes
        assert "minimal" in schemes
        assert "creative" in schemes

    def test_font_pairings_available(self):
        """Test that font pairings are defined."""
        fonts = WebsiteSystemPrompt.FONT_PAIRINGS
        assert "elegant" in fonts
        assert "modern" in fonts
        assert "professional" in fonts
        assert all("heading" in fonts[k] for k in fonts)
        assert all("body" in fonts[k] for k in fonts)


class TestWebsiteParams:
    """Test model parameters for website generation."""

    def test_website_params_token_budget(self):
        """Test that website requests get higher token budget."""
        req = WebsiteRequest("Build a website")
        params = get_website_specific_params(req)
        assert params["max_tokens"] == 8192

    def test_website_params_temperature(self):
        """Test that temperature is lowered for consistency."""
        req = WebsiteRequest("Build a website")
        params = get_website_specific_params(req)
        assert params["temperature"] == 0.4

    def test_website_params_penalties(self):
        """Test that penalties are disabled for code generation."""
        req = WebsiteRequest("Build a website")
        params = get_website_specific_params(req)
        assert params["frequency_penalty"] == 0.0
        assert params["presence_penalty"] == 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_text(self):
        """Test handling of empty text."""
        req = WebsiteRequest("")
        assert not req.is_website_request

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        text_lower = "build a landing page"
        text_upper = "BUILD A LANDING PAGE"
        req_lower = WebsiteRequest(text_lower)
        req_upper = WebsiteRequest(text_upper)
        assert req_lower.is_website_request == req_upper.is_website_request

    def test_website_type_fallback(self):
        """Test fallback for unknown website type."""
        text = "Build something with HTML and CSS"
        req = WebsiteRequest(text)
        assert req.is_website_request
        assert req.website_type is not None

    def test_partial_matches(self):
        """Test that keyword matches work."""
        text = "create an ecommerce store"
        req = WebsiteRequest(text)
        assert req.is_website_request

    def test_multiple_website_types(self):
        """Test detection with multiple website type keywords."""
        text = "Build a portfolio landing page with a blog section"
        req = WebsiteRequest(text)
        assert len(req.matched_patterns) > 1


class TestPatternCompilation:
    """Test that all patterns compile correctly."""

    def test_all_patterns_compile(self):
        """Test that all website patterns are compiled."""
        assert len(COMPILED_WEBSITE_PATTERNS) > 0
        assert all(
            hasattr(pattern, "search")
            for pattern in COMPILED_WEBSITE_PATTERNS.values()
        )

    def test_pattern_names_match(self):
        """Test that pattern names are descriptive."""
        expected_names = [
            "landing_page",
            "portfolio",
            "business",
            "ecommerce",
            "blog",
            "dashboard",
            "spa",
            "interactive",
            "api_docs",
            "framework",
            "html_css_js",
            "form_builder",
        ]
        for name in expected_names:
            assert name in COMPILED_WEBSITE_PATTERNS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
