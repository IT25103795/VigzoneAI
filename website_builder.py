"""
Vigzone AI - Website Builder Module
====================================
Specialized tools for creating production-quality websites and web apps.
Vigzone AI's strength: Complete, responsive, professional websites.
"""

import re
from typing import Optional, Tuple, List

# ── Website Detection Patterns ────────────────────────────────────────────────

# Enhanced website detection (better matching)
WEBSITE_PATTERNS = {
    "landing_page": r"\b(landing page|landing site|sales page|squeeze page)\b",
    "portfolio": r"\b(portfolio|portfolio (?:site|page|website)|showcase)\b",
    "business": r"\b(business site|company (?:site|website)|corporate site)\b",
    "ecommerce": r"\b(e?commerce|store|shop|product (?:site|page)|catalog)\b",
    "blog": r"\b(blog|blog site|blogging platform)\b",
    "dashboard": r"\b(dashboard|admin (?:panel|dashboard)|control panel)\b",
    "spa": r"\b(single[- ]page app|spa|(?:react|vue|angular) (?:app|website))\b",
    "interactive": r"\b(interactive|game|animation|effects)\b",
    "api_docs": r"\b(api documentation|api docs|api reference)\b",
    "framework": r"\b(tailwind|bootstrap|material[- ]?design|nextjs|nuxt|gatsby|11ty)\b",
    "html_css_js": r"\b(html|css|javascript|typescript|web design|ui design|ux)\b",
    "form_builder": r"\b(contact form|form|survey|questionnaire)\b",
}

# Compile all patterns
COMPILED_WEBSITE_PATTERNS = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in WEBSITE_PATTERNS.items()
}


class WebsiteRequest:
    """Detects and categorizes website requests."""

    def __init__(self, user_text: str):
        self.user_text = user_text
        self.lower_text = user_text.lower()
        self.matched_patterns: List[str] = []
        self.website_type: Optional[str] = None
        self.confidence: float = 0.0
        self.frameworks: List[str] = []

        self._detect()

    def _detect(self):
        """Detect website type and frameworks."""
        for pattern_name, pattern in COMPILED_WEBSITE_PATTERNS.items():
            if pattern.search(self.user_text):
                self.matched_patterns.append(pattern_name)

        # Detect specific frameworks
        framework_keywords = {
            "React": r"\breact\b",
            "Vue": r"\bvue\b",
            "Angular": r"\bangular\b",
            "Tailwind": r"\btailwind\b",
            "Bootstrap": r"\bbootstrap\b",
            "Next.js": r"\bnext\.?js\b",
            "Nuxt": r"\bnuxt\b",
            "Gatsby": r"\bgatsby\b",
        }

        for framework, pattern in framework_keywords.items():
            if re.search(pattern, self.user_text, re.IGNORECASE):
                self.frameworks.append(framework)

        # Determine primary website type
        if not self.matched_patterns:
            return

        priority_order = [
            "landing_page",
            "ecommerce",
            "blog",
            "portfolio",
            "business",
            "dashboard",
            "spa",
        ]

        for prio in priority_order:
            if prio in self.matched_patterns:
                self.website_type = prio
                break

        if not self.website_type:
            self.website_type = self.matched_patterns[0]

        # Confidence based on number of matches
        self.confidence = min(1.0, len(self.matched_patterns) * 0.25 + 0.5)

    @property
    def is_website_request(self) -> bool:
        """Returns True if this appears to be a website creation request."""
        return len(self.matched_patterns) > 0

    @property
    def is_framework_specific(self) -> bool:
        """Returns True if a specific framework was requested."""
        return len(self.frameworks) > 0

    def get_description(self) -> str:
        """Get human-readable description of the website request."""
        if not self.is_website_request:
            return "Not a website request"

        base = f"Website ({self.website_type})"
        if self.frameworks:
            base += f" using {', '.join(self.frameworks)}"

        return base


class WebsiteSystemPrompt:
    """Generates specialized system prompts for website creation."""

    # Color scheme templates for professional websites
    COLOR_SCHEMES = {
        "modern": {
            "primary": "#0066CC",
            "secondary": "#00D9FF",
            "accent": "#FF6B35",
            "background": "#F5F7FA",
            "text": "#1A202C",
            "border": "#E2E8F0",
        },
        "professional": {
            "primary": "#003366",
            "secondary": "#0099CC",
            "accent": "#FF9933",
            "background": "#F9FAFB",
            "text": "#2D3748",
            "border": "#E8ECEF",
        },
        "minimal": {
            "primary": "#000000",
            "secondary": "#666666",
            "accent": "#FF0000",
            "background": "#FFFFFF",
            "text": "#333333",
            "border": "#CCCCCC",
        },
        "creative": {
            "primary": "#7C3AED",
            "secondary": "#EC4899",
            "accent": "#F59E0B",
            "background": "#F8FAFC",
            "text": "#1E293B",
            "border": "#E2E8F0",
        },
    }

    # Font pairings for professional websites
    FONT_PAIRINGS = {
        "elegant": {
            "heading": "'Playfair Display', serif",
            "body": "'Lato', sans-serif",
        },
        "modern": {
            "heading": "'Poppins', sans-serif",
            "body": "'Inter', sans-serif",
        },
        "professional": {
            "heading": "'Open Sans', sans-serif",
            "body": "'Open Sans', sans-serif",
        },
        "creative": {
            "heading": "'Space Grotesk', sans-serif",
            "body": "'Outfit', sans-serif",
        },
        "minimal": {
            "heading": "'IBM Plex Sans', sans-serif",
            "body": "'IBM Plex Sans', sans-serif",
        },
    }

    @staticmethod
    def generate_website_prompt(request: WebsiteRequest) -> str:
        """
        Generate a specialized system prompt section for website creation.
        Emphasizes best practices, completeness, and professional design.
        """
        prompt_lines = [
            "WEBSITE CREATION MODE — EXPERT WEB DESIGN",
            "=" * 70,
            "",
            "You are an expert web designer and front-end developer. When building "
            "websites, follow these principles religiously:",
            "",
            "CODE COMPLETENESS & QUALITY:",
            "  • Deliver COMPLETE, production-ready code — no shortcuts or placeholders",
            "  • Every HTML tag closed and matched; all CSS syntax valid",
            "  • All JavaScript variables defined; no undefined functions or missing braces",
            "  • Self-contained files (no external dependencies unless specifically requested)",
            "  • Include inline comments for clarity (not excessive, just key sections)",
            "  • Default to single-file HTML+CSS+JS unless the user requests otherwise",
            "",
            "DESIGN EXCELLENCE:",
            "  • Modern, professional aesthetic by default (not generic templates)",
            "  • Clear visual hierarchy: proper font sizes, weights, and spacing",
            "  • Generous whitespace (breathing room, not cramped layouts)",
            "  • Cohesive color palette: define colors as CSS variables for consistency",
            "  • Professional font pairings from Google Fonts (not system fonts alone)",
            "  • Subtle shadows, rounded corners, smooth transitions",
            "  • Consistent spacing using a modular scale (8px, 16px, 24px, 32px...)",
            "",
            "RESPONSIVE & ACCESSIBLE:",
            "  • Mobile-first design: design for small screens first, scale up",
            "  • Flexbox and CSS Grid for flexible layouts",
            "  • Media queries for phones, tablets, desktops",
            "  • Semantic HTML5 (header, nav, main, section, article, footer)",
            "  • WCAG 2.1 AA compliance: sufficient color contrast, alt text on images",
            "  • Keyboard navigation: visible focus states, logical tab order",
            "  • Screen reader friendly: proper heading hierarchy (h1→h2→h3)",
            "",
            "USER EXPERIENCE:",
            "  • Fast loading: optimize images, minimize CSS/JS bloat",
            "  • Smooth interactions: subtle hover effects, loading states",
            "  • Clear call-to-actions: buttons that stand out, obvious next steps",
            "  • Error handling: show helpful error messages (not browser defaults)",
            "  • Form validation: real-time feedback where appropriate",
            "  • Intuitive navigation: clear menu structure, breadcrumbs if needed",
            "",
            "BEFORE SENDING CODE:",
            "  1. Mentally review the entire site as a user would experience it",
            "  2. Check responsiveness at common breakpoints (320px, 768px, 1024px)",
            "  3. Verify all links and buttons work as intended",
            "  4. Ensure text is readable on all screen sizes",
            "  5. Test form inputs and interactive elements",
            "",
            "AFTER THE CODE:",
            "  • Provide a 2-3 sentence summary of what you built",
            "  • Suggest concrete next steps (e.g., 'Add a dark mode toggle?',",
            "    'Want to integrate a CMS?', 'Need email form submission?')",
            "  • If it's a special type (landing page, portfolio, etc.), note key",
            "    sections and why they're designed that way",
            "",
        ]

        if request.website_type:
            prompt_lines.append(f"WEBSITE TYPE: {request.website_type.upper()}")
            prompt_lines.append("-" * 70)

            type_guidance = {
                "landing_page": [
                    "This is a landing page. Key sections:",
                    "  • Hero section (compelling headline, CTA)",
                    "  • Problem/Solution (what does it do?)",
                    "  • Features or Benefits (why should they care?)",
                    "  • Social proof (testimonials, metrics, logos)",
                    "  • CTA section (call-to-action, email signup, or purchase)",
                    "  • Footer (contact info, links, legal)",
                    "Design: Strong visual hierarchy, single focus, persuasive copy.",
                    "",
                ],
                "portfolio": [
                    "This is a portfolio site. Key sections:",
                    "  • Hero (your name/title, brief intro)",
                    "  • About (who you are, what you do)",
                    "  • Projects/Work (showcase 3-6 best projects)",
                    "  • Skills (technical skills, tools, expertise)",
                    "  • Contact (email, social links, contact form)",
                    "Design: Clean, minimal, let your work shine. Dark or light theme.",
                    "",
                ],
                "ecommerce": [
                    "This is an e-commerce site. Key sections:",
                    "  • Product grid or list with images, prices, ratings",
                    "  • Product detail pages (images, description, variations, price)",
                    "  • Shopping cart (review items, update quantities)",
                    "  • Checkout (address, payment summary, order button)",
                    "  • Trust signals (reviews, secure badge, shipping info)",
                    "Design: Professional, scannable product info, trust-building elements.",
                    "",
                ],
                "blog": [
                    "This is a blog. Key sections:",
                    "  • Blog grid or list (post title, excerpt, date, author, category)",
                    "  • Post detail (full article, metadata, comments section)",
                    "  • Sidebar (search, categories, recent posts, newsletter)",
                    "  • About author/site",
                    "Design: Content-forward, readable typography, easy scanning.",
                    "",
                ],
                "dashboard": [
                    "This is a dashboard. Key sections:",
                    "  • Top navigation bar (logo, user menu, notifications)",
                    "  • Left sidebar (main navigation, collapsible)",
                    "  • Main content area (cards with metrics, charts, tables)",
                    "  • Responsive: mobile should stack sidebar, hide on small screens",
                    "Design: Professional, data-focused, good use of white space.",
                    "",
                ],
            }

            if request.website_type in type_guidance:
                prompt_lines.extend(type_guidance[request.website_type])

        if request.frameworks:
            prompt_lines.append(f"FRAMEWORKS REQUESTED: {', '.join(request.frameworks)}")
            prompt_lines.append("-" * 70)
            prompt_lines.append(
                f"Use EXACTLY {', '.join(request.frameworks)}. Do not substitute."
            )
            prompt_lines.append("")

        prompt_lines.extend([
            "GO BUILD SOMETHING AMAZING! 🚀",
            "",
        ])

        return "\n".join(prompt_lines)


def get_website_specific_params(request: WebsiteRequest) -> dict:
    """
    Get model parameters optimized for website creation.
    """
    return {
        "max_tokens": 8192,  # Larger budget for complete websites
        "temperature": 0.4,  # Lower temperature for consistent, clean code
        "frequency_penalty": 0.0,  # Allow repetition (HTML tags, CSS resets, etc.)
        "presence_penalty": 0.0,  # Don't penalize reuse (closing tags, etc.)
    }
