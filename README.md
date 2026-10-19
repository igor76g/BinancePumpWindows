# Binance Pump Alerts (Windows)

Desktop app that monitors all Binance USDT-M perpetual futures and shows a Windows notification
with the coin ticker when:

- 24h quote volume >= **30 million USDT** (editable), AND
- price growth >= **4%** within **5 minutes** (editable).

Uses only PUBLIC Binance Futures endpoints. No API key is needed.

## Get the installer (.exe)

The installer is built automatically by GitHub (free):

1. Create a new GitHub repository and upload the contents of this folder (the `.github` folder must be included).
2. Open the **Actions** tab. The "Build Windows installer" workflow starts by itself (or run it manually: Run workflow).
3. When it finishes (about 3-5 minutes), open the run and download the artifact **BinancePumpAlerts-Setup**.
   Inside is `BinancePumpAlerts-Setup.exe`.

Or build locally on Windows: install Python 3.10+ and Inno Setup 6, then run `build.bat`.
The installer is created at `installer_output\BinancePumpAlerts-Setup.exe`.

## Use

1. Install and start the app. Adjust the settings, click **Save settings**, then **Start monitoring**.
2. Alerts appear as Windows notifications. Click **Test notification** to check they work.
   If you do not see them, make sure Windows "Do not disturb" / Focus assist is off.
3. Settings are re-read on every check, so saved changes apply immediately.
4. Keep the window open (it can be minimized). Tick "Start monitoring automatically when the app opens"
   and choose "Start with Windows" in the installer to run it all the time.

Settings are stored in `%APPDATA%\BinancePumpAlerts\settings.json`.

## Sound and alerts log

- The app plays its own two-tone beep on every alert ("Play a sound on every alert" checkbox),
  because Windows often mutes the sound of toast notifications. Use **Test notification** to check it.
  If you hear nothing, check the Windows volume mixer and the selected output device.
- Every alert is also written to `%APPDATA%\BinancePumpAlerts\alerts.log` (button **Alerts log**),
  including the time, coin, growth and price. If a toast could not be shown, the reason is written there too.
  Use it to compare with other alert sources: if the coin is in the log but you did not see a toast,
  Windows hid it (check Focus assist / Do not disturb and Settings > System > Notifications).

## Settings

| Setting | Default | Meaning |
|---|---|---|
| Minimum 24h volume (million USDT) | 30 | Volume filter |
| Volume list refresh interval (s) | 60 | How often the list of qualifying coins is refreshed |
| Minimum price growth (%) | 4 | Pump threshold |
| Time window (minutes) | 5 | Window used to measure growth |
| Price check interval (s) | 15 | How often prices are polled |
| Alert cooldown per coin (min) | 15 | No repeated alerts for the same coin within this time |

## Notes

- The installer is not code-signed, so Windows SmartScreen may show "Windows protected your PC".
  Click **More info -> Run anyway**.
- If the log shows HTTP 451/403 errors, Binance is blocked on your network; use another network or a VPN.

## Run from source (optional)

```
pip install -r requirements.txt
python run.py
python -m unittest discover -s tests -v
```
