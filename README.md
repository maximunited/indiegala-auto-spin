# IndieGala Auto-Spin Bot

Automatically logs in to IndieGala and spins the daily Wheel of Fortune.

**Features:**
- ✅ Stealth browser mode to minimize CAPTCHA detection
- ✅ Human-like typing and delays
- ✅ Persistent session (login once, automated forever)
- ✅ Automatic wheel spinning
- ✅ Works with Windows Task Scheduler or cron

## Setup

1. **Install Python dependencies:**
   ```bash
   cd indiegala-auto-spin
   pip install -r requirements.txt
   ```
   The script uses `undetected-chromedriver` which automatically manages ChromeDriver.

2. **Set up credentials:**
   
   Create a `.env` file with your IndieGala credentials:
   ```bash
   cp .env.example .env
   # Then edit .env with your email and password
   ```

## First Run - Important!

The script uses **stealth techniques** to avoid CAPTCHA, but you may still need to solve it once on first login:

```bash
# Activate virtual environment
source venv/Scripts/activate  # Windows Git Bash
# OR
venv\Scripts\activate  # Windows CMD

# Run in visible mode with debug
python spin_wheel.py --visible --debug
```

**What will happen:**
1. Browser opens in **stealth mode** (harder to detect as bot)
2. Script fills in your email and password with **human-like typing delays**
3. **IF CAPTCHA APPEARS** - Script will pause and ask you to solve it
4. Solve the "I'm not a robot" CAPTCHA in the browser window
5. Press ENTER in the terminal to continue
6. Script logs in and spins the wheel
7. Your session is saved for future automated runs

**After the first successful login**, the browser session is saved in `~/.indiegala-session`. Future runs will be **fully automated** without needing CAPTCHA solving!

**Note:** The stealth mode (using `undetected-chromedriver`) significantly reduces CAPTCHA appearances. Many users may not see CAPTCHA at all on first run!

## Daily Usage

### Run manually (headless):
```bash
source venv/Scripts/activate
python spin_wheel.py
```

### Run with visible browser:
```bash
source venv/Scripts/activate
python spin_wheel.py --visible
```

### Quick run (Windows):
```bash
run.bat
```

## Automation Setup

### Option 1: Windows Task Scheduler

1. Open Task Scheduler: `Win + R` → `taskschd.msc`
2. Create Basic Task → "IndieGala Daily Spin"
3. Trigger: Daily at desired time (e.g., 9:00 AM)
4. Action: Start a program
   - Program: `%USERPROFILE%\Projects\indiegala-auto-spin\venv\Scripts\python.exe`
   - Arguments: `spin_wheel.py`
   - Start in: `%USERPROFILE%\Projects\indiegala-auto-spin`
   
   **Note:** Replace the path above with your actual project location.

### Option 2: Windows PowerShell Scheduled Task

```powershell
$projectPath = "$env:USERPROFILE\Projects\indiegala-auto-spin"

$action = New-ScheduledTaskAction -Execute "$projectPath\venv\Scripts\python.exe" `
    -Argument "spin_wheel.py" `
    -WorkingDirectory $projectPath

$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

Register-ScheduledTask -TaskName "IndieGala Auto-Spin" -Action $action -Trigger $trigger
```

**Note:** Update `$projectPath` to match your actual project location.

### Option 3: cron (WSL/Linux)

```bash
# Edit crontab
crontab -e

# Add line to run daily at 9 AM (update the path to your project location):
0 9 * * * cd ~/Projects/indiegala-auto-spin && source venv/Scripts/activate && python spin_wheel.py >> /tmp/indiegala-spin.log 2>&1
```

## How It Works

1. **Session Management**: Uses persistent Chrome session stored in `~/.indiegala-session`
2. **Login**: Navigates to login page, fills credentials, waits for CAPTCHA (first run only)
3. **Wheel Detection**: Waits for the "Spin" button to appear (popup shows automatically when logged in)
4. **Spin**: Clicks the spin button and waits for animation
5. **Result**: Captures and displays the prize won

## Troubleshooting

### "ERROR: Please set INDIEGALA_EMAIL and INDIEGALA_PASSWORD"
- Make sure `.env` file exists with correct credentials
- Or set environment variables manually

### CAPTCHA required every time
- The browser session might not be saving properly
- Check permissions on `~/.indiegala-session` directory
- Try deleting `~/.indiegala-session` and running first-time setup again

### "Wheel popup did not appear"
- You may have already spun the wheel today (once per 24 hours)
- The site might have changed - run with `--visible --debug` to inspect

### Login fails with correct credentials
- Solve CAPTCHA as prompted during first run
- Check if IndieGala is accessible from your location
- Try manually logging in through a regular browser first

### Wheel selectors not working
- IndieGala may have updated their HTML structure
- Run with `--visible --debug` and inspect the page
- Update selectors in `spin_wheel.py` (search for "spin_button" section)

## Advanced Options

**Environment Variables (instead of .env file):**
```bash
export INDIEGALA_EMAIL="your-email@example.com"
export INDIEGALA_PASSWORD="your-password"
python spin_wheel.py
```

**Command Line Options:**
- `--visible` : Show browser window (default: headless)
- `--debug` : Enable verbose debug output

## Security Notes

- Never commit your `.env` file to git (it's in `.gitignore`)
- Your password is only used locally to log in
- Session cookies are stored locally in `~/.indiegala-session`
- Use a strong, unique password for IndieGala

## Support

If you encounter issues:
1. Run with `--visible --debug` to see what's happening
2. Check the screenshots saved in the project directory (debug_*.png)
3. Make sure you're using the latest version of Chrome/Chromium
4. Verify your `.env` credentials are correct
