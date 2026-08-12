# IndieGala Auto-Spin Bot

Automatically logs in to IndieGala and spins the daily Wheel of Fortune.

**Features:**
- Stealth browser mode to minimize CAPTCHA detection
- Human-like typing and delays
- Persistent session (login once, automated forever)
- Auto-detects first run — opens visibly for setup, headless for all future runs
- Automatic wheel spinning with prize result printed to console
- Prize history logged to `prizes.jsonl` in the session dir
- Failure notifications (Windows toast + optional webhook)
- Stable exit codes for Task Scheduler / cron / Docker
- Optional Docker image for headless daily runs
- Works with Windows Task Scheduler or cron

## Setup

1. **Create a virtual environment and install dependencies:**
   ```bash
   cd indiegala-auto-spin
   python -m venv venv
   pip install -r requirements.txt
   ```
   > The run scripts (`run.bat` / `run.sh`) do this automatically on first launch.

2. **Set up credentials:**

   Create a `.env` file with your IndieGala credentials:
   ```bash
   cp .env.example .env
   # Then edit .env with your email and password
   ```

## First Run

On first run the script detects that no session exists and **automatically opens the browser visibly** — no flags needed:

```bash
# Windows CMD / PowerShell
.\run.bat

# Git Bash / Linux
./run.sh
```

**What will happen:**
1. Browser opens in stealth mode
2. Script fills in your email and password automatically
3. **IF CAPTCHA APPEARS** — script pauses and asks you to solve it
4. Solve the "I'm not a robot" CAPTCHA in the browser window
5. Press ENTER in the terminal to continue
6. Script logs in and spins the wheel, printing the prize won
7. Session is saved — all future runs are fully headless and automated

> The stealth mode (`undetected-chromedriver`) significantly reduces CAPTCHA appearances. Many users may not see one at all on first run.

## Daily Usage

After the first successful login, all runs are headless by default:

```bash
# Windows CMD / PowerShell
.\run.bat

# Git Bash / Linux / macOS
./run.sh

# Direct Python (venv must be active)
source venv/Scripts/activate   # Windows Git Bash
# or
source venv/bin/activate        # Linux/macOS
python spin_wheel.py
```

## Automation Setup

### Option 1: Windows Task Scheduler

1. Open Task Scheduler: `Win + R` → `taskschd.msc`
2. Create Basic Task → "IndieGala Daily Spin"
3. Trigger: Daily at desired time (e.g., 9:00 AM)
4. Action: Start a program
   - Program: `%USERPROFILE%\Projects\indiegala-auto-spin\run.bat`
   - Start in: `%USERPROFILE%\Projects\indiegala-auto-spin`

### Option 2: Windows PowerShell Scheduled Task

```powershell
$projectPath = "$env:USERPROFILE\Projects\indiegala-auto-spin"

$action = New-ScheduledTaskAction -Execute "$projectPath\run.bat" `
    -WorkingDirectory $projectPath

$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

Register-ScheduledTask -TaskName "IndieGala Auto-Spin" -Action $action -Trigger $trigger
```

### Option 3: cron (WSL/Linux)

```bash
crontab -e

# Add line to run daily at 9 AM:
0 9 * * * cd ~/Projects/indiegala-auto-spin && ./run.sh >> /tmp/indiegala-spin.log 2>&1
```

## How It Works

1. **First-run detection**: Checks for an existing Chrome session (`~/.indiegala-session`). No session → opens visibly for login/CAPTCHA. Session exists → runs fully headless.
2. **Session management**: Uses persistent Chrome session stored in `~/.indiegala-session`
3. **Login**: Navigates to login page, fills credentials with human-like typing, waits for CAPTCHA if needed (first run only)
4. **Wheel detection**: Waits for the Spin button to appear (popup shows automatically when logged in)
5. **Spin**: Clicks the spin button and polls for the result element
6. **Result**: Captures and prints the prize won

## Troubleshooting

### "ERROR: Please set INDIEGALA_EMAIL and INDIEGALA_PASSWORD"
- Make sure `.env` file exists with correct credentials
- Or set environment variables manually

### CAPTCHA required on every run
- The browser session might not be saving properly
- Check permissions on `~/.indiegala-session`
- Delete `~/.indiegala-session` and run again to redo first-time setup

### "ERROR: CAPTCHA required but running headless"
- Session cookies were lost or expired
- Delete `~/.indiegala-session` and run again — it will open visibly for re-login

### "Wheel popup did not appear"
- You may have already spun the wheel today (once per 24 hours)
- Run with `--visible --debug` to inspect the page

### Login fails with correct credentials
- Solve CAPTCHA as prompted during first run
- Try manually logging in through a regular browser first

### Wheel result not printed
- A `debug_result.png` screenshot is saved automatically
- Run with `--visible --debug` to watch the spin live

## Command Line Options

| Flag | Description |
| ---- | ----------- |
| *(none)* | Auto-detect: headless if session exists, visible if first run |
| `--visible` | Force visible browser window |
| `--headless` | Force headless mode (even on first run) |
| `--debug` | Enable verbose debug output |

## Exit Codes

| Code | Meaning |
| ---- | ------- |
| `0` | Success — spun, or already spun today |
| `1` | Hard failure — login/UI/crash |
| `2` | Needs human — CAPTCHA / interactive setup |

Use these in Task Scheduler / cron / Docker health wrappers.

## Prize Log

Each run appends one line to `~/.indiegala-session/prizes.jsonl` (or `$INDIEGALA_SESSION_DIR/prizes.jsonl`):

```json
{"ts":"2026-08-12T22:00:00+00:00","date":"2026-08-13","status":"won","result":"50 Galagems"}
```

`status` is one of: `won`, `spun_unknown`, `already_spun`.

## Failure Notifications

On exit `1` or `2`:

1. **Webhook** (optional) — set `NOTIFY_WEBHOOK` to a Discord/Slack-compatible URL
2. **Windows toast** — balloon tip via PowerShell (no extra packages)

## Docker

Do first-run login on the host (CAPTCHA needs a real display), then reuse that session volume in Docker for daily headless runs.

```bash
# 1) Host first-run (creates ~/.indiegala-session)
./run.sh   # or run.bat

# 2) Seed the named volume from your host session (Linux/macOS / WSL example)
docker compose run --rm -v "$HOME/.indiegala-session:/seed:ro" --entrypoint bash spin \
  -c "cp -a /seed/. /data/session/"

# 3) Daily spin
docker compose run --rm spin
```

On Windows PowerShell, copy into the volume with:

```powershell
docker compose run --rm -v "${env:USERPROFILE}\.indiegala-session:/seed:ro" --entrypoint bash spin -c "cp -a /seed/. /data/session/"
docker compose run --rm spin
```

Build only: `docker compose build`

**Environment Variables (instead of .env file):**
```bash
export INDIEGALA_EMAIL="your-email@example.com"
export INDIEGALA_PASSWORD="your-password"
# optional:
# export INDIEGALA_SESSION_DIR="/path/to/session"
# export NOTIFY_WEBHOOK="https://discord.com/api/webhooks/..."
python spin_wheel.py
```

## Security Notes

- Never commit your `.env` file to git (it's in `.gitignore`)
- Your password is only used locally to log in
- Session cookies are stored locally in `~/.indiegala-session` (or `INDIEGALA_SESSION_DIR`)
- Prize history is local JSONL next to the session; do not commit it
