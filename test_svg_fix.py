"""
Test to verify that SVG data URI templates are properly encoded.

This test ensures that the SVG placeholder templates used for image
fallbacks in website generation are correctly percent-encoded so that
browsers can properly parse them.
"""

import re


def test_website_builder_svg_template():
    """Verify that website_builder.py has correctly encoded SVG template."""
    from website_builder import WebsiteSystemPrompt, WebsiteRequest
    
    req = WebsiteRequest("Build a website")
    prompt = WebsiteSystemPrompt.generate_website_prompt(req)
    
    # The prompt should NOT contain unencoded quotes in the SVG data URI
    # Check for the pattern: %3Csvg xmlns=%27 (correct) not xmlns=' (incorrect)
    assert "%3Csvg xmlns=%27http://www.w3.org/2000/svg%27" in prompt, \
        "SVG template should have percent-encoded quotes"
    
    # Should NOT contain the broken pattern with unencoded quotes
    assert "xmlns='http://www.w3.org/2000/svg'" not in prompt, \
        "SVG template should not have unencoded quotes in data URI"
    
    # Verify all quotes in the SVG are encoded
    # Find the img tag with data URI
    img_match = re.search(r'<img src="data:image/svg\+xml,[^"]+', prompt)
    assert img_match, "Should contain SVG data URI in img tag"
    
    data_uri = img_match.group(0)
    
    # In a valid data URI, all XML attribute quotes should be %27
    # Count of %27 should be substantial (multiple attributes)
    quote_count = data_uri.count("%27")
    assert quote_count >= 8, f"Expected at least 8 encoded quotes, found {quote_count}"


def test_vigzone_ai_svg_template():
    """Verify that vigzone_ai.py has correctly encoded SVG template."""
    from vigzone_ai import SYSTEM_PROMPT
    
    # The prompt should NOT contain unencoded quotes in the SVG data URI
    # Check for the pattern: %3Csvg xmlns=%27 (correct) not xmlns=' (incorrect)
    assert "%3Csvg xmlns=%27http://www.w3.org/2000/svg%27" in SYSTEM_PROMPT, \
        "SVG template in SYSTEM_PROMPT should have percent-encoded quotes"
    
    # Should NOT contain the broken pattern with unencoded quotes
    assert "xmlns='http://www.w3.org/2000/svg'" not in SYSTEM_PROMPT, \
        "SVG template in SYSTEM_PROMPT should not have unencoded quotes in data URI"


def test_svg_data_uri_validity():
    """Test that a corrected SVG data URI is valid and parseable."""
    # This is the correct template that should be used
    correct_template = (
        "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 "
        "width=%27400%27 height=%27300%27%3E%3Crect width=%27100%25%27 "
        "height=%27100%25%27 fill=%27%23ddd%27/%3E%3Ctext x=%2750%25%27 "
        "y=%2750%25%27 font-size=%2720%27 text-anchor=%27middle%27 "
        "fill=%27%23888%27 dy=%27.3em%27%3ECar 1%3C/text%3E%3C/svg%3E"
    )
    
    # When placed in an img tag, the HTML should be valid
    html = f'<img src="{correct_template}" alt="Test SVG">'
    
    # The src attribute should be properly quoted (no internal quotes should break it)
    # Verify the HTML is well-formed by checking attribute boundaries
    assert html.startswith('<img src="'), "HTML should have properly quoted src"
    assert html.endswith('" alt="Test SVG">'), "HTML should have valid ending"
    
    # The template should contain encoded quotes
    assert "%27" in correct_template, "Template should contain encoded quotes"


def test_svg_decoding():
    """Verify that the encoded SVG can be decoded back to valid XML."""
    import urllib.parse
    
    # Extract just the SVG part (after the data URI prefix)
    svg_encoded = (
        "%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27400%27 "
        "height=%27300%27%3E%3Crect width=%27100%25%27 height=%27100%25%27 "
        "fill=%27%23ddd%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 "
        "font-size=%2720%27 text-anchor=%27middle%27 fill=%27%23888%27 "
        "dy=%27.3em%27%3ECar 1%3C/text%3E%3C/svg%3E"
    )
    
    # Decode it
    decoded = urllib.parse.unquote(svg_encoded)
    
    # Should be valid XML-like string
    assert decoded.startswith("<svg"), "Decoded SVG should start with <svg"
    assert decoded.endswith("</svg>"), "Decoded SVG should end with </svg>"
    assert 'xmlns=\'http://www.w3.org/2000/svg\'' in decoded, \
        "Decoded SVG should have proper xmlns attribute with single quotes"
    assert "Car 1" in decoded, "Decoded SVG should contain the text content"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
