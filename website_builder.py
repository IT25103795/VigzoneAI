"""
Vigzone AI - Website Builder Module
====================================
Specialized tools for creating modern, production-quality websites and web apps.

This module is the Website Studio brain for Vigzone. It detects web-build
requests, infers the subject/industry, and injects a stricter design + code
prompt so generated websites look modern, intentional, responsive, and complete
instead of like a generic AI template.
"""

import re
from typing import Optional, List, Dict

# ── Website Detection Patterns ────────────────────────────────────────────────

# Broad but still web-specific. The old detector missed natural prompts like
# "Write a website for a hotel" or "create a modern website for a hospital".
# These patterns catch those everyday requests while avoiding ordinary non-web
# questions such as "explain machine learning".
WEBSITE_PATTERNS = {
    "generic_website": r"\b(?:web ?site|site|web ?page|homepage|home page)\b",
    "create_website": r"\b(?:build|create|make|design|develop|write|code|generate)\s+(?:me\s+)?(?:a|an|the\s+)?(?:modern|responsive|professional|full|complete|excellent\s+)?(?:web ?site|site|web ?page|homepage|home page|web ?app)\b",
    "website_for": r"\b(?:web ?site|site|web ?page|landing page|web ?app)\s+(?:for|about)\s+(?:my|a|an|the)?\s*[\w &'-]{2,80}\b",
    "landing_page": r"\b(landing page|landing site|sales page|squeeze page|coming soon page)\b",
    "portfolio": r"\b(portfolio|portfolio (?:site|page|website)|showcase|personal (?:site|website))\b",
    "business": r"\b(business site|business website|company (?:site|website)|corporate site|service website|(?:site|website|page) for (?:my|a|an|the)?\s*[\w &'-]{2,60})\b",
    "ecommerce": r"\b(e?commerce|online store|web ?store|web ?shop|shop(?:ping)? (?:site|page|cart)|product (?:site|page)|catalog|menu page|booking site|reservation site)\b",
    "blog": r"\b(blog|blog site|blogging platform|magazine site|news site)\b",
    "dashboard": r"\b(dashboard|admin (?:panel|dashboard)|control panel|analytics panel|crm ui|saas dashboard)\b",
    "spa": r"\b(single[- ]page app|spa|(?:react|vue|angular|svelte) (?:app|website|site))\b",
    "interactive": r"\b(interactive|game|animation|effects|micro interactions|scroll animation)\b",
    "api_docs": r"\b(api documentation|api docs|api reference|developer docs)\b",
    "framework": r"\b(tailwind|bootstrap|material[- ]?design|nextjs|next\.js|nuxt|gatsby|11ty|vite)\b",
    "html_css_js": r"\b(html|css|javascript|typescript|web design|ui design|ux|front[- ]?end|frontend)\b",
    "form_builder": r"\b(contact form|booking form|appointment form|form|survey|questionnaire)\b",
}

COMPILED_WEBSITE_PATTERNS = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in WEBSITE_PATTERNS.items()
}

SUBJECT_PATTERNS = [
    re.compile(r"\b(?:web ?site|site|web ?page|landing page|web ?app|homepage|home page)\s+(?:for|about)\s+(?:my|a|an|the)?\s*([\w &'-]{2,80})", re.I),
    re.compile(r"\b(?:build|create|make|design|develop|write|code|generate)\s+(?:me\s+)?(?:a|an|the)?\s*(?:modern|responsive|professional|full|complete|excellent)?\s*(?:web ?site|site|web ?page|landing page|web ?app)\s+(?:for|about)\s+(?:my|a|an|the)?\s*([\w &'-]{2,80})", re.I),
    re.compile(r"\b(?:for|about)\s+(?:my|a|an|the)?\s*([\w &'-]{2,80})\s+(?:web ?site|site|web ?page|landing page)\b", re.I),
]

INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "hotel": ["hotel", "resort", "villa", "guest house", "booking", "rooms", "travel", "tourism"],
    "hospital": ["hospital", "clinic", "medical", "doctor", "healthcare", "health care", "dental", "pharmacy"],
    "restaurant": ["restaurant", "cafe", "coffee", "bakery", "food", "menu", "pizza", "burger", "barbercue", "bbq"],
    "education": ["school", "college", "university", "academy", "course", "tuition", "learning", "education"],
    "real_estate": ["real estate", "property", "apartment", "house", "rent", "land", "homes"],
    "fitness": ["gym", "fitness", "yoga", "trainer", "sports", "wellness"],
    "portfolio": ["portfolio", "designer", "developer", "photographer", "artist", "creative"],
    "ecommerce": ["store", "shop", "ecommerce", "product", "catalog", "fashion", "clothing"],
    "saas": ["saas", "software", "app", "startup", "platform", "dashboard", "analytics"],
    "nonprofit": ["nonprofit", "charity", "ngo", "foundation", "donation"],
    "automotive": ["car", "auto", "vehicle", "garage", "mechanic", "bike", "motor"],
    "beauty": ["salon", "spa", "beauty", "makeup", "skincare", "cosmetic"],
    "security": ["security", "cctv", "surveillance", "automation", "iot", "smart home"],
}

INDUSTRY_GUIDANCE: Dict[str, Dict[str, str]] = {
    "hotel": {
        "sections": "hero with destination promise, room cards, amenities, local experiences, gallery, reviews, booking CTA/contact",
        "design": "luxury hospitality: cinematic hero, warm ambient illustrations or sourced imagery, calm spacing, premium room cards, trust badges and booking-first CTAs",
        "interactions": "working room filter chips, validated booking inquiry form, sticky reservation bar on desktop, mobile-friendly CTA",
    },
    "hospital": {
        "sections": "hero with emergency/contact CTA, departments, doctor cards, appointment form, patient trust stats, services, location/footer",
        "design": "healthcare trust: clean light palette, high contrast, reassuring blue/green accents, accessible cards, clear emergency and appointment actions",
        "interactions": "department tabs, appointment form validation, call-now button, accessible focus states",
    },
    "restaurant": {
        "sections": "hero, menu highlights, signature dishes, opening hours, reservation form, testimonials, location/footer",
        "design": "food-first editorial: appetizing palette, menu-card rhythm, textured but clean backgrounds, strong reservation/menu CTA",
        "interactions": "menu category filters, reservation form validation, sticky mobile order/reserve CTA",
    },
    "education": {
        "sections": "hero, programs/courses, outcomes, faculty, admissions steps, testimonials, contact/enroll CTA",
        "design": "optimistic academic: structured grids, friendly original illustrations, credibility stats and clear enrollment journey",
        "interactions": "course cards, FAQ accordion, enroll/contact form",
    },
    "real_estate": {
        "sections": "hero property search, featured listings, neighbourhoods, agent profile, process, testimonials, contact",
        "design": "premium property: large listing cards, map/search feeling, calm neutrals with confident accent, high-value trust signals",
        "interactions": "filter chips, listing cards, inquiry form",
    },
    "fitness": {
        "sections": "hero, classes/programs, trainers, schedule, pricing, transformations, join CTA",
        "design": "energetic performance: bold typography, strong contrast, motion used for energy, clear membership CTAs",
        "interactions": "working class tabs, pricing toggle, validated join inquiry form",
    },
    "portfolio": {
        "sections": "hero, selected work, about, skills/process, testimonials, contact",
        "design": "work-led portfolio: unique visual signature, generous project previews, restrained chrome around the work",
        "interactions": "project hover states, filter chips, contact form",
    },
    "ecommerce": {
        "sections": "hero offer, product grid, benefits/trust, reviews, functional local cart, clearly labelled checkout integration CTA, footer",
        "design": "conversion-first shop: scannable product cards, clear prices, ratings, trust badges, mobile shopping flow",
        "interactions": "working product filters, local add-to-cart state, quantity controls and cart summary",
    },
    "saas": {
        "sections": "hero, honest product interface preview, problem-solution, features, metrics, pricing, testimonials, CTA",
        "design": "modern product site: crisp hierarchy, bento feature blocks, clearly labelled product preview, polished gradients used sparingly",
        "interactions": "working tabs, pricing toggle, counters derived from declared page data",
    },
    "nonprofit": {
        "sections": "hero mission, impact stats, programs, stories, donation CTA, volunteers, footer",
        "design": "human impact: warm but not generic, story cards, strong donation/volunteer CTAs, trust and transparency",
        "interactions": "donation selector linked to a clearly labelled payment integration step, story cards, validated volunteer form",
    },
    "automotive": {
        "sections": "hero, services/vehicles, inspection checklist, packages, reviews, booking/contact",
        "design": "mechanical precision: bold grid, metallic/dark accents if fitting, clean service cards and trust signals",
        "interactions": "service selector, booking form, animated checklist",
    },
    "beauty": {
        "sections": "hero, services, packages, gallery, specialist/team, testimonials, booking CTA",
        "design": "premium beauty: elegant spacing, soft contrast, editorial cards, booking-first mobile layout",
        "interactions": "service tabs, booking form, gallery hover states",
    },
    "security": {
        "sections": "hero, system features, devices/services, monitoring benefits, packages, trust proofs, contact",
        "design": "secure tech: confident dark/light contrast, circuit/monitoring motifs, clear protection CTAs, technical credibility",
        "interactions": "feature tabs, package cards, contact form",
    },
}


def _clean_subject(raw: str) -> str:
    raw = re.sub(r"\b(with|using|that|and|please|bro|for me)\b.*$", "", raw, flags=re.I)
    raw = re.sub(r"[^\w &'-]", " ", raw).strip(" -_\t\n")
    raw = re.sub(r"\s+", " ", raw)
    if len(raw) > 60:
        raw = raw[:60].rsplit(" ", 1)[0]
    return raw.strip()


class WebsiteRequest:
    """Detects and categorizes website requests."""

    def __init__(self, user_text: str):
        self.user_text = user_text or ""
        self.lower_text = self.user_text.lower()
        self.matched_patterns: List[str] = []
        self.website_type: Optional[str] = None
        self.confidence: float = 0.0
        self.frameworks: List[str] = []
        self.subject: Optional[str] = None
        self.industry: Optional[str] = None

        self._detect()

    def _detect(self):
        """Detect website type, subject, industry, and frameworks."""
        for pattern_name, pattern in COMPILED_WEBSITE_PATTERNS.items():
            if pattern.search(self.user_text):
                self.matched_patterns.append(pattern_name)

        framework_keywords = {
            "React": r"\breact\b",
            "Vue": r"\bvue\b",
            "Angular": r"\bangular\b",
            "Svelte": r"\bsvelte\b",
            "Tailwind": r"\btailwind\b",
            "Bootstrap": r"\bbootstrap\b",
            "Next.js": r"\bnext\.?js\b",
            "Nuxt": r"\bnuxt\b",
            "Gatsby": r"\bgatsby\b",
            "Vite": r"\bvite\b",
        }

        for framework, pattern in framework_keywords.items():
            if re.search(pattern, self.user_text, re.IGNORECASE):
                self.frameworks.append(framework)

        for subject_pattern in SUBJECT_PATTERNS:
            match = subject_pattern.search(self.user_text)
            if match:
                cleaned = _clean_subject(match.group(1))
                if cleaned:
                    self.subject = cleaned
                    break

        # Infer industry from the whole request plus extracted subject.
        probe = f"{self.lower_text} {self.subject or ''}".lower()
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            if any(re.search(r"\b" + re.escape(keyword) + r"\b", probe) for keyword in keywords):
                self.industry = industry
                break

        if not self.matched_patterns:
            return

        priority_order = [
            "landing_page",
            "ecommerce",
            "dashboard",
            "blog",
            "portfolio",
            "business",
            "spa",
            "api_docs",
            "generic_website",
            "create_website",
            "website_for",
        ]

        for prio in priority_order:
            if prio in self.matched_patterns:
                self.website_type = prio
                break

        if not self.website_type:
            self.website_type = self.matched_patterns[0]

        # Generic website/site should usually be treated as business site.
        if self.website_type in {"generic_website", "create_website", "website_for"}:
            self.website_type = "business"

        self.confidence = min(1.0, len(self.matched_patterns) * 0.18 + 0.55)

    @property
    def is_website_request(self) -> bool:
        return len(self.matched_patterns) > 0

    @property
    def is_framework_specific(self) -> bool:
        return len(self.frameworks) > 0

    def get_description(self) -> str:
        if not self.is_website_request:
            return "Not a website request"
        base = f"Website ({self.website_type})"
        if self.subject:
            base += f" for {self.subject}"
        if self.industry:
            base += f" [{self.industry}]"
        if self.frameworks:
            base += f" using {', '.join(self.frameworks)}"
        return base


class WebsiteSystemPrompt:
    """Generates specialized system prompts for modern website creation."""

    GENERIC_LOOKS_TO_AVOID = [
        "Warm cream/off-white background (#F4F1EA-ish) + high-contrast serif headline + a terracotta/warm-clay accent — the single most overused AI-generated look right now.",
        "Near-black background with one bright acid-green or vermilion accent and a card grid — the 'dark SaaS dashboard' default.",
        "Broadsheet/newspaper layout with hairline rules, zero border-radius, dense columns — striking once, generic the second time you see it.",
        "Purple-to-pink gradient hero with a rounded sans headline and three feature cards — the generic startup landing page default.",
        "Plain Bootstrap-looking blue navbar + white cards + stock icons — this reads old and unfinished.",
    ]

    @staticmethod
    def _industry_block(request: WebsiteRequest) -> List[str]:
        if not request.industry or request.industry not in INDUSTRY_GUIDANCE:
            return []
        g = INDUSTRY_GUIDANCE[request.industry]
        return [
            "INDUSTRY-SPECIFIC DIRECTION:",
            f"  • Detected industry: {request.industry}",
            f"  • Sections expected: {g['sections']}",
            f"  • Visual direction: {g['design']}",
            f"  • Useful interactions: {g['interactions']}",
            "  • Do not make it look like a generic SaaS/product template. Make the",
            "    visuals, copy, CTAs, icon metaphors, and content architecture match this industry.",
            "",
        ]

    @staticmethod
    def generate_website_prompt(request: WebsiteRequest) -> str:
        """
        Generate a specialized system prompt section for website creation.
        """
        subject = request.subject or "the user's requested website"
        prompt_lines = [
            "WEBSITE CREATION MODE — VIGZONE WEBSITE STUDIO V5",
            "=" * 76,
            "",
            "MISSION:",
            "  Create a modern, excellent, production-ready website that feels like it",
            "  was designed by a real web designer, not generated from a generic AI template.",
            f"  Current site subject: {subject}",
            f"  Website type: {request.website_type or 'business'}",
            "",
            "OUTPUT CONTRACT — follow this exact structure:",
            "  1. Start with a tiny design brief of 3-5 bullets: target user, visual",
            "     direction, palette, sections, and signature element.",
            "  2. Then provide COMPLETE code in fenced blocks. For normal requests,",
            "     deliver one single self-contained `index.html` block containing HTML,",
            "     CSS inside <style>, and JS inside <script>. If the user explicitly asks",
            "     for React/Next/Tailwind/etc., provide the exact framework files needed.",
            "  3. After code, give a short usage note and 2-3 concrete next upgrades.",
            "  4. Never ask follow-up questions unless the request is impossible. Make",
            "     smart assumptions and build the site now.",
            "",
            "HARD RULES — check every one before finalizing:",
            "  1. No placeholders like Lorem ipsum, 'Your Company', or 'image here'.",
            "     Write real, subject-specific copy and labels.",
            "  2. No broken external file references. If using single-file HTML, all CSS",
            "     must be in <style> and all JavaScript in <script> before </body>.",
            "  3. Never invent image paths or fake URLs. If a [REAL IMAGES AVAILABLE]",
            "     block exists, use those exact URLs. Otherwise use polished inline SVG",
            "     original inline SVG or CSS illustrations that match the subject and always render.",
            "  4. Every page must be responsive at 320px, 768px, and desktop widths.",
            "  5. Every interactive element must work: mobile menu, filters, tabs, FAQ,",
            "     booking/contact form validation, toast messages, smooth scroll, etc.",
            "  6. Ship complete, fully concluded code. Structure CSS and JavaScript",
            "     efficiently so the entire HTML concludes cleanly and closes all tags",
            "     (e.g. </script></body></html>). Never leave code hanging or cut off mid-tag.",
            "     If continuing a prior turn, resume from the exact character where it stopped.",
            "  7. Keep accessibility strong: semantic tags, visible focus states, alt text,",
            "     high contrast, correct h1→h2→h3 order, reduced-motion support.",
            "",
            "MODERN DESIGN STANDARD:",
            "  • Aim for a polished Framer/Webflow-level landing page feel, but with clean",
            "    hand-written HTML/CSS/JS that can run immediately.",
            "  • Use CSS variables for a real design system: colors, radii, shadows, spacing.",
            "  • Use clamp() for fluid typography and spacing where useful.",
            "  • Use a modern layout concept: bento grid, editorial split hero, sticky CTA,",
            "    layered cards, timeline, comparison strip, clearly labelled dashboard preview, gallery",
            "    rail — pick the pattern that fits the subject.",
            "  • Build strong hierarchy: a clear hero, scannable sections, balanced whitespace,",
            "    consistent card rhythm, and a footer that looks designed.",
            "  • Use restrained motion: scroll reveal, hover lift, active nav, form toast. Avoid",
            "    childish animations or too many effects.",
            "  • Use real Google Fonts only if allowed by the brief; otherwise use strong",
            "    system font stacks. Do not rely on icon libraries or external CSS frameworks",
            "    unless explicitly requested.",
            "",
            "DESIGN EXECUTION:",
            "  • Make a small design system first: 4-6 named hex colors, 2 font roles,",
            "    radius scale, shadow scale, spacing scale.",
            "  • Create one memorable signature element for this subject — not for generic",
            "    decoration. Example: a hotel gets a booking ribbon/gallery moodboard; a",
            "    hospital gets a care-path appointment panel; a restaurant gets an editorial",
            "    menu strip; a dashboard gets a clearly labelled product UI preview.",
            "  • Real, specific copy tailored to the business/idea. The site should feel",
            "    useful even before real assets are swapped in.",
            "  • Sections should be complete enough for a real client demo, not just hero +",
            "    three feature cards.",
            "",
            "AVOID THESE OVERUSED AI-GENERATED LOOKS unless the brief explicitly asks:",
        ]
        for cliche in WebsiteSystemPrompt.GENERIC_LOOKS_TO_AVOID:
            prompt_lines.append(f"  • {cliche}")
        prompt_lines.extend([
            "",
            *WebsiteSystemPrompt._industry_block(request),
            "CODE QUALITY CHECKLIST:",
            "  • Valid HTML5: no missing closing tags, no duplicate IDs, no invalid nesting.",
            "  • CSS is organized: reset/base, layout, components, responsive media queries.",
            "  • JavaScript is small but useful: mobile nav, form validation, UI interactions,",
            "    no undefined variables, no syntax errors.",
            "  • Never claim a form submitted when there is no backend. Either connect it",
            "    to a real endpoint supplied by the user, or validate it and clearly say",
            "    that a deployment endpoint still needs to be configured.",
            "  • Buttons/links should have meaningful targets. Use section anchors for nav.",
            "  • Use inline SVG icons/illustrations with distinct shapes — do not paste the",
            "    same icon for every feature.",
            "",
            "IMAGES — CRITICAL:",
            "  • Check FIRST for a system message titled '[REAL IMAGES AVAILABLE — USE THESE EXACT URLS]'.",
            "    If present, use those exact working URLs verbatim in <img> tags.",
            "  • If no real image block exists, build attractive inline SVG/data-URI visuals",
            "    or CSS illustrations instead of fake paths. They must render without network calls.",
            "  • Safe SVG data-URI pattern to copy when you need an original illustration:",
            "    <img src=\"data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27400%27 height=%27300%27%3E%3Crect width=%27100%25%27 height=%27100%25%27 fill=%27%23e5e7eb%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 font-size=%2720%27 text-anchor=%27middle%27 fill=%27%236b7280%27 dy=%27.3em%27%3EImage%3C/text%3E%3C/svg%3E\" alt=\"Preview image\">",
            "  • State after the code whether the page uses sourced photos or original illustrations.",
            "",
            "RESPONSIVE & ACCESSIBLE:",
            "  • Mobile-first layout. Use media queries for tablet/desktop.",
            "  • Nav should collapse gracefully on small screens.",
            "  • Touch targets at least 44px where possible.",
            "  • Respect prefers-reduced-motion.",
            "",
            "BEFORE SENDING CODE — SELF-CRITIQUE:",
            "  1. Would this look modern next to a good Webflow/Framer template? If not, upgrade it.",
            "  2. Does it clearly match the subject/industry? If it could be reskinned for",
            "     anything else, revise the hero, palette, sections, and microcopy.",
            "  3. Is the website complete enough to open as index.html and demo immediately?",
            "  4. Are mobile layout, contrast, focus states, and interactions handled?",
            "",
        ])

        type_guidance = {
            "landing_page": [
                "WEBSITE TYPE: LANDING PAGE",
                "  • Hero with strong promise and CTA",
                "  • Problem/solution or outcome story",
                "  • Benefits/features with real examples",
                "  • Social proof / metrics / testimonials",
                "  • Pricing, signup, lead form, or contact CTA",
                "  • Footer with useful links",
                "  • Keep one conversion goal obvious throughout.",
                "",
            ],
            "portfolio": [
                "WEBSITE TYPE: PORTFOLIO",
                "  • Hero with identity and specialty",
                "  • Selected work/project showcase with context, not generic cards",
                "  • About/process/skills",
                "  • Testimonials or proof",
                "  • Contact section",
                "",
            ],
            "ecommerce": [
                "WEBSITE TYPE: E-COMMERCE",
                "  • Product grid with prices, ratings, badges",
                "  • Category filters or featured collections",
                "  • Trust signals: delivery, returns, secure checkout",
                "  • Working local mini cart; label checkout as requiring a real payment integration",
                "  • Mobile shopping flow matters most.",
                "",
            ],
            "blog": [
                "WEBSITE TYPE: BLOG / MAGAZINE",
                "  • Editorial hero/featured article",
                "  • Post grid/list with categories and metadata",
                "  • Search/newsletter/sidebar if useful",
                "  • Readability-first typography.",
                "",
            ],
            "dashboard": [
                "WEBSITE TYPE: DASHBOARD",
                "  • App shell with sidebar/topbar",
                "  • Metrics and charts driven by declared sample data, with tables and alerts",
                "  • Responsive collapsed navigation",
                "  • Data clarity over decoration.",
                "",
            ],
            "business": [
                "WEBSITE TYPE: BUSINESS / SERVICE SITE",
                "  • Hero with clear service promise",
                "  • Services/products",
                "  • Why choose us / trust proof",
                "  • Process/how it works",
                "  • Testimonials or stats",
                "  • Contact/booking/CTA and footer",
                "",
            ],
        }
        if request.website_type in type_guidance:
            prompt_lines.extend(type_guidance[request.website_type])

        if request.frameworks:
            prompt_lines.extend([
                f"FRAMEWORKS REQUESTED: {', '.join(request.frameworks)}",
                "-" * 76,
                f"Use EXACTLY {', '.join(request.frameworks)}. Do not substitute another stack.",
                "If multiple files are required, label every code block with a clear filename.",
                "",
            ])

        prompt_lines.extend([
            "Make this website excellent enough that the user feels an immediate quality jump. 🚀",
            "",
        ])

        return "\n".join(prompt_lines)


def get_website_specific_params(request: WebsiteRequest) -> dict:
    """Get model parameters optimized for website creation."""
    return {
        "max_tokens": 8192,
        "temperature": 0.4,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }
