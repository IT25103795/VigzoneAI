# Zoner v0 release readiness

Date: 2026-08-16

## Current decision

Zoner v0 (`0.1.0`) is ready for continued local and internal Vigzone
development. It is not yet approved for a production release. The runtime is a
versioned orchestration layer over configured third-party foundation models; it
does not contain custom-trained weights and does not use private user data for
training.

The active release identifiers are:

- Runtime: `Zoner v0` / `0.1.0`
- Prompt policy: `zoner-prompt-v0.9`
- Retrieval policy: `private-lexical-v1`
- Tool policy: `bounded-context-tools-v1`
- Evaluation suite: `zoner-evals-v0.9`
- Status: `development_integration`

## Integrated development surface

- Zoner identity, prompt modules, routing, private-context boundaries, and
  deterministic high-risk product responses are connected to Vigzone chat.
- Streaming and synchronous provider responses include a safe Zoner runtime
  receipt. Provider-free verified and local date/time responses include the
  same receipt without requiring provider configuration or consuming model
  tokens.
- Usage telemetry records runtime, prompt, retrieval, tool-policy, and
  evaluation versions.
- Feedback retains an allowlisted runtime receipt and prompt-module list while
  dropping arbitrary client-supplied metadata.
- `/api/zoner/info`, `/api/app/version`, and `/api/public/config` expose a
  truthful public manifest.
- The chat UI identifies the assistant as Zoner, shows the runtime in Settings,
  and displays a compact version receipt on responses.

## Evaluation evidence

- The checked-in seed corpus contains 32 cases across nine categories,
  including 13 critical cases.
- The current v0.9 capture contains 16 of 32 responses. All 16 pass the
  deterministic automatic checks, with no critical automatic failures.
- The remaining 16 model-generated responses are deferred because the current
  provider allowance was exhausted. This is an incomplete regression capture,
  not a recorded Zoner response failure.
- Earlier prompt revisions exercised the complete 32-case capture and informed
  the v0.9 policy changes. Their results remain separate so revisions are not
  mixed.
- Local integration tests cover truthful manifests, provider-safe prompt
  construction, durable version telemetry, provider-free response receipts,
  feedback allowlisting, and the visible runtime identity.

## Required production gates

All of the following remain required before changing the status to production:

1. Complete a fresh 32-case capture using the active v0.9 prompt and evaluation
   versions when provider allowance is available.
2. Resolve every critical automatic failure and record a human verdict for all
   32 cases. Critical privacy, destructive-action, secret, grounding, and
   cross-account cases must pass.
3. Run the full automated regression suite and the deployment configuration
   checks in a staging environment.
4. Manually verify account isolation, deletion, feedback redaction, prompt
   injection handling, provider failure behavior, and mobile/desktop UI.
5. Confirm production monitoring, rate limits, provider budgets, rollback
   procedure, privacy copy, and an explicit release approval.

## Safe local verification

These commands make no provider calls:

```bash
python -m zoner.evaluation validate
python -m zoner.evaluation summary
python -m zoner.baseline check
python -m zoner.baseline report
pytest
```

Do not run a baseline command with `--execute` until provider allowance has been
confirmed and a new full capture is intentionally scheduled.
