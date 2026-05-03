

# RBerryLink Monitor
**By Davchi15**

> 📺 Built on the **Davchi15** YouTube channel — 
> subscribe for the full build guide and more Pi projects.

[youtube.com](https://www.youtube.com/@Davchi15) 

RBerryLink Monitor is a passive always-on system dashboard for the 
**Raspberry Pi 5** with the **Waveshare X1202 UPS HAT**. It displays 
real-time battery, system, disk, and network stats in a retro 
Pip-Boy terminal aesthetic — and will safely shut your Pi down 
before the battery runs out.

---

## ✨ Features

- **Battery monitoring** — capacity, voltage, charge/discharge rate, 
  and time-to-empty or time-to-full estimates
- **System stats** — CPU usage, temperature, RAM, and uptime
- **Disk stats** — usage percentage with GB breakdown, read/write totals
- **Network** — local IP address (with show/hide toggle), 
  live download and upload speeds
- **Safe shutdown** — configurable battery threshold slider, 
  warning flash, 60-second countdown popup, and 
  `systemctl poweroff` execution (no password needed)
- **Autostart** — toggle boot-on-login directly from the dashboard
- **Animated splash screen** — Raspberry Pi 5 board draws itself 
  on startup
- **Self-installing** — missing Python packages install automatically 
  on first run

---

## 🛒 What You Need

| Component | Where to Get |
|-----------|-------------|
| Raspberry Pi 5 | [amazon.com](https://amzn.to/4w3PfQr)|
| Waveshare X1202 UPS HAT | [amazon.com](https://amzn.to/4tWOHKL) |
| MicroSD card (16GB+) |[amazon.com](https://amzn.to/49pIWwO)|

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/RBerryLink_Monitor.git
cd RBerryLink_Monitor
```

### 2. Enable I2C on your Pi

The UPS HAT communicates over I2C. Enable it with:

```bash
sudo raspi-config
```

Navigate to **Interface Options → I2C → Enable**, then reboot.

> ⚠️ If you skip this step, RBerryLink will show a helpful popup 
> reminding you when it launches.

### 3. Run it

```bash
python3 pi_dashboard.py
```

That's it. Missing packages (like `customtkinter`) will install 
automatically on the first run — no manual `pip install` needed.

---

## ⚙️ Configuration

All tunable settings are at the top of `pi_dashboard.py`:

| Constant | Default | What it does |
|----------|---------|-------------|
| `SHUTDOWN_THRESHOLD_DEFAULT` | `5%` | Battery % that triggers safe shutdown |
| `SHUTDOWN_WARNING_SECS` | `10s` | How long the footer flashes before popup |
| `SHUTDOWN_COUNTDOWN_SECS` | `60s` | Countdown on the shutdown popup |
| `SHUTDOWN_COOLDOWN_SECS` | `300s` | Cooldown after cancelling shutdown |
| `HISTORY_SIZE` | `60` | Battery readings to keep (~2 min). Don't lower. |
| `INA219_ADDR` | `0x41` | I2C address for power monitor chip |

> 💡 The shutdown threshold and safe shutdown toggle are also 
> adjustable directly from the dashboard footer — no editing needed.

---
## ⏱️ Changing the Splash Screen Duration
The splash screen stays visible while RBerryLink buffers battery  

readings to build an accurate discharge rate estimate. By default  

this takes 2 minutes (60 cycles × 2 seconds each).  

To change it, open pi_dashboard.py and find this section near  

the top of the file — it's clearly marked:  
```
# ==========================================
# --- BRANDING & THEME CONSTANTS ---
# ==========================================

...

# --- CALIBRATION CONSTANTS ---
HISTORY_SIZE  = 60   # battery history cycles (~2 min). Don't lower.
SPLASH_CYCLES = 60   # cycles before splash dismisses.
```
Change SPLASH_CYCLES to adjust how long the splash shows:  

| Splashscreen Time Configuration | Outcome |
|---------------------------------|---------|
| `60 seconds ~ 2 minutes` | `Default — best accuracy on start` |
| `30 seconds ~ 1 minute` | `Good balance` |
| `10 ~ 20 seconds` | `Fast but less accurate on first launch` | 
| `1 ~ 2 seconds` | `Skip splash entirely (testing only)` |   

⚠️ Do not lower HISTORY_SIZE — this controls how many readings  

are kept in memory for the rate calculation. Lowering it will make  

your discharge rate and time-remaining estimates unreliable and jumpy.  

SPLASH_CYCLES and HISTORY_SIZE are independent — you can set  

SPLASH_CYCLES to 1 to skip the splash while keeping  

HISTORY_SIZE at 60 for accurate estimates after the first  

2 minutes of running.  



## 🔌 I2C Address Note

Some Waveshare X1202 boards use address `0x40` instead of `0x41` 
for the INA219 power monitor. If your UPS bus voltage always shows 
`0.00 V`, change this line near the top of `pi_dashboard.py`:

```python
INA219_ADDR = 0x41  # try 0x40 if bus voltage reads 0.00 V
```

---

## 🔁 Autostart on Boot

To have the dashboard launch automatically when your Pi boots:

1. Make sure your Pi is set to **auto-login to the desktop**:
```bash
sudo raspi-config
# System Options → Boot / Auto Login → Desktop Autologin
```

2. Toggle **AUTOSTART ON BOOT** to `[ ON ]` in the dashboard footer.

That's it — it will launch automatically on the next boot.

---

## 📁 File Structure
RBerryLink_Monitor/
├── pi_dashboard.py          # Main application  

├── icon.png                 # Taskbar icon  

├── settings.default.json    # Default settings reference  

├── settings.json            # Your saved settings (auto-created)  

├── requirements.txt         # Python dependencies  

├── README.md  

└── .gitignore  


---

## 🐍 Python Dependencies

Installed automatically on first run. Or manually:

```bash
pip install -r requirements.txt --break-system-packages
```

- `customtkinter` — UI framework
- `smbus2` — I2C communication with UPS HAT
- `psutil` — system stats (CPU, RAM, disk, network)
- `Pillow` — icon rendering

---

## 📺 Watch the Video

> 🔗 [youtube.com](https://www.youtube.com/@Davchi15)

---

## 📄 License

MIT License — free to use, modify, and share.

---

*Davchi Industries — RBerryLink Monitor*
