# Operations reference for IndieGala Auto-Spin.
#
# Covers exit codes, prize logging, failure notifications, scheduling, and Docker.
# See README.md for setup and first-run.

## Exit codes

| Code | Constant | When |
| ---- | -------- | ---- |
| `0` | `EXIT_OK` | Prize won, result unread after spin, or already spun today |
| `1` | `EXIT_ERROR` | Missing credentials, Chrome failed to start, login/UI failure, crash |
| `2` | `EXIT_NEEDS_HUMAN` | CAPTCHA required while headless |

Task Scheduler / cron should treat `0` as success. Alert on `1` and `2` (the script also notifies on those).

## Prize log

Path: `$INDIEGALA_SESSION_DIR/prizes.jsonl` (default `~/.indiegala-session/prizes.jsonl`).

One JSON object per line:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `ts` | string | UTC ISO-8601 timestamp |
| `date` | string | Local calendar date (`YYYY-MM-DD`) |
| `status` | string | `won` \| `spun_unknown` \| `already_spun` |
| `result` | string\|null | Prize text when `status=won` |

Example:

```bash
tail -n 5 ~/.indiegala-session/prizes.jsonl
```

## Failure notifications

Triggered by `main()` when the exit code is not `0`.

1. **`NOTIFY_WEBHOOK`** — POST JSON with both `content` (Discord) and `text` (Slack-style) fields.
2. **Windows toast** — PowerShell balloon tip (no extra Python packages). Skipped on non-Windows.

Webhook failures are logged as warnings and do not change the exit code.

## Environment variables

| Variable | Required | Default | Purpose |
| -------- | -------- | ------- | ------- |
| `INDIEGALA_EMAIL` | yes | — | Login email |
| `INDIEGALA_PASSWORD` | yes | — | Login password |
| `INDIEGALA_SESSION_DIR` | no | `~/.indiegala-session` | Chrome profile + prize log |
| `NOTIFY_WEBHOOK` | no | — | Failure webhook URL |

## Scheduling tips

- Prefer checking `%ERRORLEVEL%` / `$?` after `run.bat` / `run.sh`.
- On exit `2`, delete/reset the session dir and re-run visibly once.
- Docker daily runs assume a seeded session volume (CAPTCHA cannot be solved headless in CI/containers easily).

## Docker

- Image installs Google Chrome + Python deps; `CMD` runs `--headless`.
- Mount/persist `/data/session` (`INDIEGALA_SESSION_DIR`).
- `shm_size: 2gb` in Compose — Chrome is unstable with the default 64MB shm.

Seed once from a host login, then:

```bash
docker compose run --rm spin
```

## Debugging

| Artifact | Meaning |
| -------- | ------- |
| `debug_*.png` | Screenshot at failure (gitignored) |
| `--debug` | Verbose console tracing |
| `--visible` | Watch the browser live |
