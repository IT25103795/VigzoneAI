"""
Vigzone AI - Website Builder Module
====================================
Specialized tools for creating production-quality websites and web apps.
Vigzone AI's strength: complete, responsive, and — above all — DISTINCTIVE
websites. Every build is treated as a one-off visual identity for whatever
the user is actually making, not a reskin of the same "modern SaaS" template
with the colors swapped.
"""

import re
from typing import Optional, Tuple, List

# ── Website Detection Patterns ────────────────────────────────────────────────

# Enhanced website detection (better matching). Includes casual, non-technical
# phrasing ("a site for my bakery", "online store", "menu page") so Vigzone
# recognizes website requests even when the user doesn't use web-dev jargon.
WEBSITE_PATTERNS = {
    "landing_page": r"\b(landing page|landing site|sales page|squeeze page|coming soon page)\b",
    "portfolio": r"\b(portfolio|portfolio (?:site|page|website)|showcase|personal (?:site|website))\b",
    "business": r"\b(business site|company (?:site|website)|corporate site|(?:site|website|page) for my \w+)\b",
    "ecommerce": r"\b(e?commerce|online store|web ?store|web ?shop|shop(?:ping)? (?:site|page|cart)|product (?:site|page)|catalog|menu page)\b",
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
    """Generates specialized system prompts for website creation.

    Philosophy: Vigzone's edge isn't "clean and professional" — every AI
    website builder claims that, and it's exactly why so many AI-built sites
    look interchangeable (the same cream-and-terracotta hero, or the same
    dark-mode-with-one-neon-accent card grid, no matter what the business
    actually is). Vigzone's edge is treating each build as a real design
    brief: ground the palette, type, and layout in the specific thing the
    user is building, take one deliberate creative risk per site, and
    otherwise execute with restraint and polish.
    """

    # Common AI-generated design ruts to actively steer away from unless the
    # user's brief specifically calls for one of these looks.
    GENERIC_LOOKS_TO_AVOID = [
        "Warm cream/off-white background (#F4F1EA-ish) + high-contrast serif "
        "headline + a terracotta/warm-clay accent — the single most overused "
        "AI-generated look right now.",
        "Near-black background with one bright acid-green or vermilion accent "
        "and a card grid — the 'dark SaaS dashboard' default.",
        "Broadsheet/newspaper layout with hairline rules, zero border-radius, "
        "dense columns — striking once, generic the second time you see it.",
        "Purple-to-pink gradient hero with a rounded sans headline and three "
        "feature cards — the 'generic startup landing page' default.",
    ]

    @staticmethod
    def generate_website_prompt(request: WebsiteRequest) -> str:
        """
        Generate a specialized system prompt section for website creation.
        Emphasizes genuine visual distinctiveness (not a fixed template
        picker), completeness, and professional execution.
        """
        prompt_lines = [
            "WEBSITE CREATION MODE — VIGZONE'S SIGNATURE STRENGTH",
            "=" * 70,
            "",
            "HARD RULES — violating any of these breaks the page. Check every one",
            "before you finish, no matter how long the rest of this prompt gets:",
            "  1. NEVER write `<link rel=\"stylesheet\" href=\"...\">` or",
            "     `<script src=\"...\">` pointing at a file (styles.css, script.js,",
            "     etc.) that you have not also printed in full in this same",
            "     response. If you're not writing a separate CSS/JS file out",
            "     completely, put ALL styling in one `<style>` block in `<head>`",
            "     and all scripting in one `<script>` block before `</body>`.",
            "  2. If you use more than one inline SVG icon, EVERY icon must have",
            "     a different `<path>`/shape. Never copy-paste the same icon for",
            "     different features, services, or list items — pick a shape",
            "     that actually matches each label (e.g. a clock for speed, a",
            "     shield for safety — not the same glyph three times).",
            "  3. Never point an `<img>` at a file path or URL you didn't confirm",
            "     is real. Check for a '[REAL IMAGES AVAILABLE]' system message",
            "     first and use those exact URLs verbatim if present. With no real",
            "     image available, use an inline SVG data-URI placeholder (see",
            "     IMAGES section below) instead — and make sure it's valid,",
            "     properly-closed SVG markup, not a hand-guessed encoding.",
            "  4. Ship every section the user's request implies — no cut corners,",
            "     no `<!-- more sections here -->`, no stopping halfway.",
            "",
            "Website building is what Vigzone AI is best known for. Approach this "
            "like the design lead at a small studio whose reputation rests on "
            "never handing two clients the same visual identity. The bar isn't "
            "'looks nice' — it's 'could not be mistaken for a template with the "
            "logo swapped.'",
            "",
            "STEP 1 — GROUND IT IN THE SUBJECT (do this before writing any code):",
            "  • Pin down concretely what this site is for, who it's for, and the",
            "    one job the page needs to do. If the user's request is vague,",
            "    make a sensible, specific choice yourself and run with it.",
            "  • Distinctive design comes from the subject's own world — its",
            "    materials, colors, textures, vocabulary — not from a generic",
            "    'business website' or 'startup landing page' template.",
            "  • If you know things about this user's own projects, business, or",
            "    stated preferences from earlier in the conversation, let that",
            "    inform real choices (industry, tone, name, existing branding).",
            "",
            "STEP 2 — PLAN A SMALL DESIGN SYSTEM (briefly, before coding):",
            "  • Color: 4-6 named hex values chosen for THIS subject, not a",
            "    generic 'primary/secondary/accent' triad picked from habit.",
            "  • Type: a characterful display/heading face used with restraint,",
            "    paired with a clean body face — a pairing that fits the subject,",
            "    not whatever you'd default to on any other project.",
            "  • Layout: one clear structural concept for how content flows —",
            "    not just 'hero, three cards, footer' by default.",
            "  • Signature: pick ONE memorable element (a distinctive hero",
            "    treatment, an unusual layout choice, a bit of orchestrated",
            "    motion, an illustration motif) that this specific site will be",
            "    remembered by. Spend your creative boldness there, and keep",
            "    everything else disciplined and quiet around it.",
            "",
            "AVOID THESE OVERUSED AI-GENERATED LOOKS unless the user's brief",
            "specifically asks for one of them:",
        ]
        for cliche in WebsiteSystemPrompt.GENERIC_LOOKS_TO_AVOID:
            prompt_lines.append(f"  • {cliche}")
        prompt_lines.extend([
            "",
            "CODE COMPLETENESS & QUALITY:",
            "  • Deliver COMPLETE, production-ready code — no shortcuts or placeholders",
            "  • Every HTML tag closed and matched; all CSS syntax valid",
            "  • All JavaScript variables defined; no undefined functions or missing braces",
            "  • Self-contained files (no external dependencies unless specifically requested)",
            "  • Include inline comments for clarity (not excessive, just key sections)",
            "  • Default to single-file HTML+CSS+JS unless the user requests otherwise",
            "",
            "DESIGN EXECUTION:",
            "  • Clear visual hierarchy: proper font sizes, weights, and spacing",
            "  • Generous, intentional whitespace (breathing room, not cramped layouts)",
            "  • Define the planned palette as CSS variables for consistency",
            "  • Real Google Fonts for the type pairing (not system fonts alone)",
            "  • Motion used deliberately where it serves the subject (a page-load",
            "    moment, a scroll reveal, hover micro-interactions) — not scattered",
            "    effects everywhere, which reads as AI-generated rather than designed",
            "  • Consistent spacing using a modular scale (8px, 16px, 24px, 32px...)",
            "  • Real, specific copy tailored to the subject — never generic",
            "    placeholder text like 'Lorem ipsum' or 'Your Company Name Here'",
            "",
            "IMAGES — CRITICAL, READ CAREFULLY:",
            "  • Check FIRST for a system message titled '[REAL IMAGES AVAILABLE —",
            "    USE THESE EXACT URLS]' above. If present, it lists real, working",
            "    photo URLs found for this subject — use those EXACT URLs verbatim",
            "    in your <img> tags, copied character-for-character. Do not modify,",
            "    shorten, guess at, or re-encode them.",
            "  • NEVER invent an image URL or local file path that doesn't exist",
            "    (e.g. 'car1.jpg', 'images/photo.png', or a made-up link). It will",
            "    render as a broken image icon because nothing lives at that path.",
            "  • If NO real-images block is present (search unavailable, disabled,",
            "    or no matches for this subject), use inline SVG data-URI",
            "    placeholders for every <img> instead — they always render, with",
            "    zero network calls. Follow this exact pattern character-for-",
            "    character, only changing width/height/label/fill colors to fit —",
            "    note every tag is properly closed (rect self-closes with `/%3E`,",
            "    text closes with `%3C/text%3E`, and the svg itself closes with",
            "    `%3C/svg%3E` at the very end):",
            "    <img src=\"data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27",
            "     width=%27400%27 height=%27300%27%3E%3Crect width=%27100%25%27 height=%27100%25%27",
            "     fill=%27%23ddd%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 font-size=%2720%27",
            "     text-anchor=%27middle%27 fill=%27%23888%27 dy=%27.3em%27%3ECar 1%3C/text%3E%3C/svg%3E\"",
            "     alt=\"Car 1\">",
            "  • Note in your after-code summary whether images are real photos or",
            "    placeholders, so the user knows whether they need to swap anything.",
            "",
            "RESPONSIVE & ACCESSIBLE:",
            "  • Mobile-first design: design for small screens first, scale up",
            "  • Flexbox and CSS Grid for flexible layouts",
            "  • Media queries for phones, tablets, desktops",
            "  • Semantic HTML5 (header, nav, main, section, article, footer)",
            "  • WCAG 2.1 AA compliance: sufficient color contrast, alt text on images",
            "  • Keyboard navigation: visible focus states, logical tab order",
            "  • Screen reader friendly: proper heading hierarchy (h1→h2→h3)",
            "  • Respect prefers-reduced-motion for any animation",
            "",
            "USER EXPERIENCE:",
            "  • Fast loading: optimize images, minimize CSS/JS bloat",
            "  • Smooth interactions: subtle hover effects, loading states",
            "  • Clear call-to-actions: buttons that stand out, obvious next steps",
            "  • Error handling: show helpful error messages (not browser defaults)",
            "  • Form validation: real-time feedback where appropriate",
            "  • Intuitive navigation: clear menu structure, breadcrumbs if needed",
            "",
            "BEFORE SENDING CODE — SELF-CRITIQUE:",
            "  1. Does this look like it was built for THIS subject, or could it be",
            "     reskinned for any other business with a find-and-replace? If the",
            "     latter, revise the weak part before sending.",
            "  2. Mentally review the entire site as a user would experience it",
            "  3. Check responsiveness at common breakpoints (320px, 768px, 1024px)",
            "  4. Verify all links and buttons work as intended",
            "  5. Ensure text is readable on all screen sizes",
            "  6. Test form inputs and interactive elements",
            "",
            "AFTER THE CODE:",
            "  • Provide a 2-3 sentence summary of what you built, naming the",
            "    signature element and why you chose it for this subject",
            "  • Suggest concrete next steps (e.g., 'Add a dark mode toggle?',",
            "    'Want to integrate a CMS?', 'Need email form submission?')",
            "",
        ])

        if request.website_type:
            prompt_lines.append(f"WEBSITE TYPE: {request.website_type.upper()}")
            prompt_lines.append("-" * 70)

            type_guidance = {
                "landing_page": [
                    "This is a landing page. Key sections to cover (adapt the labels",
                    "and order to fit the actual product/offer, don't just fill slots):",
                    "  • Hero (compelling headline, CTA)",
                    "  • Problem/Solution (what does it do?)",
                    "  • Features or Benefits (why should they care?)",
                    "  • Social proof (testimonials, metrics, logos)",
                    "  • CTA section (call-to-action, email signup, or purchase)",
                    "  • Footer (contact info, links, legal)",
                    "Single clear focus, persuasive copy specific to this offer — not",
                    "boilerplate SaaS phrasing ('Streamline your workflow').",
                    "",
                ],
                "portfolio": [
                    "This is a portfolio site. Key sections to cover:",
                    "  • Hero (name/title, brief intro — let the work's own field",
                    "    suggest the tone, e.g. a photographer's hero reads differently",
                    "    from a backend engineer's)",
                    "  • About (who they are, what they do)",
                    "  • Projects/Work (showcase 3-6 best projects with real specifics)",
                    "  • Skills (technical skills, tools, expertise)",
                    "  • Contact (email, social links, contact form)",
                    "Let the work itself be the star; the chrome around it should be",
                    "confident but quiet.",
                    "",
                ],
                "ecommerce": [
                    "This is an e-commerce site. Key sections to cover:",
                    "  • Product grid or list with images, prices, ratings",
                    "  • Product detail pages (images, description, variations, price)",
                    "  • Shopping cart (review items, update quantities)",
                    "  • Checkout (address, payment summary, order button)",
                    "  • Trust signals (reviews, secure badge, shipping info)",
                    "Scannable product info and trust-building elements matter more",
                    "than decoration here — but the palette and type should still",
                    "reflect what's actually being sold.",
                    "",
                ],
                "blog": [
                    "This is a blog. Key sections to cover:",
                    "  • Blog grid or list (post title, excerpt, date, author, category)",
                    "  • Post detail (full article, metadata, comments section)",
                    "  • Sidebar (search, categories, recent posts, newsletter)",
                    "  • About author/site",
                    "Content-forward, readable typography, easy scanning — the type",
                    "pairing carries most of this design's personality.",
                    "",
                ],
                "dashboard": [
                    "This is a dashboard. Key sections to cover:",
                    "  • Top navigation bar (logo, user menu, notifications)",
                    "  • Left sidebar (main navigation, collapsible)",
                    "  • Main content area (cards with metrics, charts, tables)",
                    "  • Responsive: mobile should stack sidebar, hide on small screens",
                    "Data-focused and legible above all, but avoid the reflexive",
                    "near-black/neon-accent dashboard look unless it fits the brand.",
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
            "This is what Vigzone AI is uniquely good at — make this one count. 🚀",
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
