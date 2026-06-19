---
name: cn-market-writeback
description: Use this skill after a China-market analysis has produced a complete kimi-market-v1 JSON envelope and the user or autoPersist policy wants to persist it into ai-trading-business ingest APIs. It posts the full envelope to the ingest.url supplied by Java payload, never hardcoding production hosts.
---

# cn-market-writeback

Persist a complete `kimi-market-v1` JSON envelope to the ai-trading-business ingest API.

## Inputs

The caller must provide one complete JSON object with:

- `schemaVersion="kimi-market-v1"`
- `mode`
- `persistContract.bizType`
- `persistContract.bizId`
- `persistContract.taskNo`
- `persistContract.ingest.url`
- an ingest token from payload, either as `persistContract.ingest.token`, top-level `ingest.token`, or CLI `--token`

The Skill must post the complete envelope, not a partial `stocks` or `sections` object.

## Workflow

1. Validate that the envelope has `schemaVersion="kimi-market-v1"` and a supported China-market `mode`.
2. Read `persistContract`.
3. Resolve the ingest URL only from input:
   - first `persistContract.ingest.url`
   - then top-level `ingest.url`
   - then CLI `--url`
   - never hardcode `101.37.208.179` or any production host in the Skill.
4. Resolve the token only from input:
   - first `persistContract.ingest.token`
   - then top-level `ingest.token`
   - then CLI `--token`
5. Run `scripts/persist.py` with the envelope.
6. Return the script JSON result to the user, including `success`, `persisted`, `idempotent`, HTTP status, retry count, and response ids when available.

## Idempotency

The backend is authoritative for idempotency. The Skill must preserve:

- `taskNo`
- `bizType`
- `bizId`
- `persistContract.idempotencyKey`

Repeated calls with the same task identity should be safe. If the backend returns an idempotent result, report it as success.

## Failure Handling

- Retry network/5xx/429 failures with exponential backoff.
- Do not retry schema or auth errors (`400`, `401`, `403`, `422`) unless the user changes the input.
- If persistence fails after retries, return the full error summary and keep the complete analysis JSON available for Java gateway fallback/replay.

## Security

- Send token only in `X-Ingest-Token`.
- Do not print token values in logs or final output.
- Do not write the envelope to a persistent path unless the caller explicitly provides one.
