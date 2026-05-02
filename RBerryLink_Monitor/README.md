# RBerryLink Monitor
### By Davchi Industries

A passive always-on system dashboard for the **Raspberry Pi 5** with the **Waveshare X1202 UPS HAT**. Displays real-time battery, system, disk, and network stats in a retro Pip-Boy inspired terminal aesthetic. Features safe shutdown logic, autostart management, persistent settings, and an animated Pi 5 board splash screen.

---

## Screenshots

> *(Add screenshots here)*

---

## Hardware Requirements

| Component | Details |
|-----------|---------|
| Raspberry Pi 5 | Any RAM variant |
| Waveshare X1202 UPS HAT | I2C address `0x36` (MAX17048) + `0x41` (INA219) |
| Display | Any — optimised for small displays (3.5"–7") |

---

## Dependencies

Install Python dependencies with:

```bash
pip install -r requirements.txt --break-system-packages
```

| Package | Purpose |
|---------|---------|
| `customtkinter` | UI framework |
| `smbus2` | I2C communication with UPS HAT |
| `psutil` | CPU, RAM, disk, and network stats |
| `Pillow` | Taskbar icon rendering |

---

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/RBerryLink_Monitor.git
```

2. Install dependencies:
```bash
cd RBerryLink_Monitor
pip install -r requirements.txt --break-system-packages
```

3. Enable I2C on your Pi if not already enabled:
```bash
sudo raspi-config nonint do_i2c 0
```

4. Run the dashboard:
```bash
python3 pi_dashboard.py
```

---

## File Structure

```
RBerryLink_Monitor/
├── pi_dashboard.py          # Main application
├── requirements.txt         # Python dependencies
├── settings.default.json    # Default settings reference (committed)
├── settings.json            # Your personal settings (gitignored, auto-created)
├── README.md
└── .gitignore
```

---

## Configuration

All tunable constants are at the top of `pi_dashboard.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `HISTORY_SIZE` | `60` | Battery reading history (cycles). Controls ETA smoothing — do not lower. |
| `SPLASH_CYCLES` | `60` | How many cycles before the splash screen dismisses (~2 minutes). |
| `FAST_INTERVAL` | `2000` | Fast poll interval in ms (battery, CPU, RAM, network). |
| `SLOW_INTERVAL` | `30000` | Slow poll interval in ms (IP address, disk usage). |
| `SHUTDOWN_THRESHOLD_DEFAULT` | `5` | Default safe shutdown threshold (%). Persisted in `settings.json`. |
| `SHUTDOWN_WARNING_SECS` | `10` | Seconds of footer flashing before the shutdown popup appears. |
| `SHUTDOWN_COUNTDOWN_SECS` | `60` | Seconds on the shutdown countdown popup. |
| `SHUTDOWN_COOLDOWN_SECS` | `300` | Cooldown in seconds after a manual snooze before re-triggering. |
| `SHUTDOWN_SLIDER_COOLDOWN` | `5` | Seconds cooldown after adjusting the threshold slider. |
| `INA219_ADDR` | `0x41` | I2C address of the INA219 power monitor. Some X1202 boards use `0x40`. |

---

## Features

### Dashboard
- **Battery** — capacity %, voltage, UPS bus voltage, charge/discharge rate (%/hr), time-to-empty or time-to-full with EMA smoothing
- **System** — CPU temperature, CPU usage (non-blocking), RAM usage, system uptime
- **Disk** — usage % with GB breakdown, cumulative R/W totals
- **Network** — IP address with show/hide toggle, live download and upload KB/s

### Splash Screen
- Animated Raspberry Pi 5 board drawing with per-segment fade-in
- Telemetry buffering progress bar and countdown
- Retro terminal text with blinking cursor
- Startup advisory popup if battery is already below threshold on launch

### Safe Shutdown
Always-visible footer bar with a priority-based state machine:

| Priority | State | Condition | Behaviour |
|----------|-------|-----------|-----------|
| 5 | Flash warning | Discharging below threshold | Red/amber flashing footer for 10s |
| 4 | Balanced advisory | Power Balanced below threshold | Static amber footer message |
| 3 | Disabled advisory | Safe Shutdown OFF during warning | Static amber "shutdown disabled" message |
| 2 | Snooze cooldown | After snoozing popup | Dim countdown timer in footer |
| 0 | Clear | Battery recovered | Footer empty |

- **Threshold slider** (5–50%) — persisted in `settings.json`
- **Safe Shutdown toggle** — OFF suppresses countdown popup, shows persistent advisory instead
- **Snooze button** — dismisses popup with a 5-minute cooldown before re-triggering
- **Slider cooldown** — 5s pause after adjusting threshold to prevent mid-drag triggers
- Uses `systemctl --no-block poweroff` — no sudo or password required

### Autostart
- Toggle autostart on/off directly from the GUI footer
- Writes a standard XDG `.desktop` file to `~/.config/autostart/`
- Works on Pi OS (LXDE/Wayfire) and Ubuntu (GNOME)
- Fading status confirmation message after each toggle

### Settings Persistence
- `settings.json` saved next to the script (gitignored)
- Persists: shutdown threshold, safe shutdown toggle state
- Falls back to `settings.default.json` if `settings.json` is missing
- Falls back to hardcoded defaults if both files are missing

### Taskbar Icon
- Embedded RBL gear logo — no separate asset file required
- Set via `wm_iconphoto()` on launch

---

## I2C Address Note

Some Waveshare X1202 boards ship with the INA219 at address `0x40` instead of `0x41`. If your UPS bus voltage always reads `0.00 V`, change this line near the top of `pi_dashboard.py`:

```python
INA219_ADDR = 0x41  # change to 0x40 if bus voltage reads 0.00 V
```

---

## Autostart Note

For autostart to work, your Pi must be configured to **auto-login to the desktop**.

On Pi OS:
```bash
sudo raspi-config nonint do_boot_behaviour B4
```

On Ubuntu, enable auto-login via **Settings → Users → Automatic Login**.

---

## License

MIT License — free to use, modify, and distribute.

---

*Built for the Raspberry Pi 5 + Waveshare X1202 UPS HAT. Davchi Industries.*
