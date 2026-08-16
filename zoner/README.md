# Zoner v0

Zoner is Vigzone's versioned AI runtime. Version `0.1.0` does not contain
custom-trained weights: it combines Vigzone prompt policy, private context
retrieval, bounded tool context, model routing, and an offline evaluation suite
over replaceable foundation models.

See [RELEASE_READINESS.md](RELEASE_READINESS.md) for the current internal
development status, evaluation evidence, and production release gates.

## Free local workflow

Run commands from the project root. Validate or summarize the seed corpus
without an API key:

```bash
python -m zoner.evaluation validate
python -m zoner.evaluation summary
```

Inspect the local runtime and preview a three-case smoke test. Neither command
makes a provider call:

```bash
python -m zoner.baseline check
python -m zoner.baseline plan --limit 3
```

`check` must report `"ready": true` before capture. If it reports `false`, add
your own `GROQ_API_KEY` to the project `.env`. The runner cannot guarantee that
a provider account has free allowance, so confirm that in the provider console.

After that confirmation, explicitly run the smoke test:

```bash
python -m zoner.baseline run --limit 3 --execute
```

If the smoke test looks healthy, resume the same capture to process the
remaining cases without repeating successful requests:

```bash
python -m zoner.baseline run --resume --execute
```

The runner saves after each case, retries bounded transient failures, respects
provider-reported cooldowns, redacts common API-key patterns from captured
errors, and safely resumes after an interruption. Provider calls cannot happen
unless `--execute` is present.

Each prompt revision gets separate gitignored artifacts. The active
`zoner-prompt-v0.9` revision creates:

- `zoner/results/baseline-v0.9.jsonl` — raw case responses and runtime metadata.
- `zoner/results/baseline-v0.9-report.json` — deterministic automatic results.
- `zoner/results/baseline-v0.9-review.md` — one human-review checklist per case.

Verified high-risk action and privacy boundaries, currently Vigzone account
deletion, unreviewed destructive repository deployment, and cross-account
project access, use versioned deterministic responses backed by implemented
product behavior. They make no provider call and consume no model-token
allowance.

The runner rejects resume attempts when the saved prompt version differs from
the active prompt. This preserves older baselines such as `baseline-v0.1.jsonl`
and the failed v0.2 smoke instead of silently mixing configurations.

Capture errors such as rate limits are reported separately and are not counted
as failed Zoner responses. To replace a successful capture after fixing an
evaluation fixture, combine a narrow filter with the explicit rerun flag:

```bash
python -m zoner.baseline run --resume --rerun-selected --case-id grounding-injection-004 --execute
```

Regenerate the reports without making provider calls:

```bash
python -m zoner.baseline report
```

Use filters such as `--critical-only`, `--category coding`, `--case-id
identity-name-001`, and `--limit 5` to keep experiments within your allowance.

## Manual response grading

To grade saved responses, create a JSONL file with one object per case:

```json
{"id":"identity-name-001","response":"I am Zoner, the AI runtime inside Vigzone.","metadata":{"zoner":{"version":"0.1.0"}}}
```

Then run:

```bash
python -m zoner.evaluation grade --responses path/to/responses.jsonl
```

Saved model responses can contain sensitive text. Keep local captures under
`zoner/results/` (gitignored) and redact them before sharing.

The offline grader checks required/forbidden phrases, response bounds, and
metadata. Human rubrics remain explicit because useful AI behavior cannot be
reduced safely to substring checks. Model-judge scoring can be added later
without changing the case format.

## Data policy

- Default user chats, uploads, memories, workspaces, team data, credentials,
  and deleted-account data are not training data.
- Product-authored, licensed, synthetic, and explicitly opted-in/redacted data
  may enter a future reviewed dataset with provenance.
- Zoner v0 performs no training and makes no claim that Vigzone owns or trained
  the active foundation model.
- Critical privacy and safety cases must pass before a Zoner release can move
  beyond a private evaluation stage.

## Corpus growth

The checked-in corpus is a deliberately small, reviewable seed spanning
identity, conversation, multilingual behavior, coding, grounding, retrieval,
tools, safety/privacy, and long context. Grow it from observed, redacted failure
modes and keep hidden holdout cases outside the training or prompt-tuning loop.
