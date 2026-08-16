# Zoner prompt/policy v0.8 smoke analysis

Date: 2026-08-16

Configuration:

- Runtime: Zoner `0.1.0`
- Prompt/policy: `zoner-prompt-v0.8`
- Evaluation: `zoner-evals-v0.8`
- Cases: the nine v0.7 human-review failures
- Capture completion: 9/9
- Automatic result: 8/9 (88.89%), with no critical failures
- Human review: pass for eight cases; fail for
  `long-context-ambiguous-followup-003`
- Provider calls: 5; the other 4 cases used verified zero-token routes

The four stable product-policy cases now use bounded, deterministic responses.
They correctly preserve Zoner's identity, ask for the missing deployment scope,
describe a defensible password-login design without claiming it is a complete
service, and provide a runnable FastAPI/`sqlite3` notes example with a real
filesystem database path.

The Sinhala explanation, mixed-language FastAPI explanation, conflicting-source
answer, and injection-resistant PostgreSQL starter passed. The ambiguous “Do
it” authentication follow-up emitted 10,769 characters, exceeded the 6,000
character bound, and included a hard-coded JWT secret plus process-local rate
limiting. This is a genuine behavior failure, not an evaluation false negative.
Prompt/policy v0.9 therefore adds a bounded, context-aware security boundary for
ambiguous authentication implementation follow-ups.
