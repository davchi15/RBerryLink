import sys
import subprocess

# ==========================================
# --- DEPENDENCY BOOTSTRAP ---
# Checks for required packages on first run and installs them automatically.
# This runs before any other imports so a fresh install just works.
# ==========================================
_REQUIRED = {
    "customtkinter": "customtkinter>=5.2.0",
    "smbus2":        "smbus2>=0.4.3",
    "psutil":        "psutil>=5.9.0",
    "PIL":           "Pillow>=9.0.0",
}

_missing = []
for _mod, _pkg in _REQUIRED.items():
    try:
        __import__(_mod)
    except ImportError:
        _missing.append(_pkg)

if _missing:
    print(f"\n[RBerryLink] Missing dependencies: {', '.join(_missing)}")
    print("[RBerryLink] Installing now — this only happens once...\n")
    _result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--break-system-packages"] + _missing,
        check=False
    )
    if _result.returncode != 0:
        print("\n[RBerryLink] Auto-install failed. Please run manually:")
        print(f"  pip install --break-system-packages {' '.join(_missing)}")
        sys.exit(1)
    print("\n[RBerryLink] Dependencies installed. Starting...\n")
    import os
    os.execv(sys.executable, [sys.executable] + sys.argv)


import customtkinter as ctk
import smbus2
import struct
import psutil
import time
import socket
import subprocess
from collections import deque

# ==========================================
# --- BRANDING & THEME CONSTANTS ---
# ==========================================
BRAND_NAME = "DAVCHI INDUSTRIES"
OS_NAME    = "RBERRYLINK"
VERSION    = "v4.3"

# --- CALIBRATION CONSTANTS ---
HISTORY_SIZE  = 60   # battery history cycles (~2 min). Don't lower.
SPLASH_CYCLES = 60   # cycles before splash dismisses.

# --- POLL INTERVALS ---
FAST_INTERVAL =  2000   # ms — battery, CPU, RAM, uptime, net bandwidth
SLOW_INTERVAL = 30000   # ms — IP address, disk usage

# --- SHUTDOWN CONSTANTS ---
SHUTDOWN_CMD               = ["systemctl", "--no-block", "poweroff"]
SHUTDOWN_THRESHOLD_DEFAULT = 5     # % — default slider value
SHUTDOWN_WARNING_SECS      = 10    # seconds of footer flashing before popup
SHUTDOWN_COUNTDOWN_SECS    = 60    # seconds on the popup countdown
SHUTDOWN_COOLDOWN_SECS     = 300   # 5-min cooldown after a manual cancel
SHUTDOWN_SLIDER_COOLDOWN   = 5     # seconds cooldown after slider adjustment

# --- RATE ALGORITHM CONSTANTS ---
# How many ticks after a direction change to use the wider deadband.
# Each tick = 2s, so 8 ticks = 16 seconds of stability window.
DIRECTION_SETTLE_TICKS = 8
# Normal deadband — filters micro-fluctuations at rest
DEADBAND_NORMAL  = 0.02   # %/hr
# Wider deadband used immediately after a direction change.
# Prevents the label flickering between states during the noisy
# transition period when the chip is recalibrating.
DEADBAND_SETTLING = 0.5   # %/hr

# --- AUTOSTART ---
import os as _os
import json as _json
_SCRIPT_PATH     = _os.path.abspath(__file__)
_SCRIPT_DIR      = _os.path.dirname(_SCRIPT_PATH)
_USER            = _os.environ.get("USER", "pi")
_AUTOSTART_DIR   = _os.path.expanduser("~/.config/autostart")
_AUTOSTART_FILE  = _os.path.join(_AUTOSTART_DIR, "rberrylink.desktop")
_SETTINGS_FILE         = _os.path.join(_SCRIPT_DIR, "settings.json")
_SETTINGS_DEFAULT_FILE = _os.path.join(_SCRIPT_DIR, "settings.default.json")
_DESKTOP_CONTENT = f"""[Desktop Entry]
Type=Application
Name=RBerryLink Dashboard
Comment=Davchi Industries UPS Monitor
Exec=/usr/bin/python3 "{_SCRIPT_PATH}"
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
"""

# --- X1202 / INA219 I2C ADDRESSES ---
MAX17048_ADDR = 0x36
INA219_ADDR   = 0x41
# Note: Some X1202 boards use 0x40. If bus voltage reads 0.00 V, try 0x40.

# RobCo / Pip-Boy color palette
PIP_GREEN = "#1aff80"
PIP_WARN  = "#ffb300"
PIP_CRIT  = "#ff3333"
PIP_DIM   = "#004400"
PIP_BG    = "#000000"
PIP_FONT  = ("Courier", 14, "bold")

# ---------------------------------------------------------------------------
# Pi 5 board draw-animation segments.
# ---------------------------------------------------------------------------
_SC  = 4.0
_OX  = 30
_OY  = 28

def _mm(v):
    return int(v * _SC)

_PI_SEGS = [
    ("rect",   0,        0,        _mm(85),  _mm(56),  2.5),
    ("circle", _mm(3.5), _mm(3.5), _mm(1.6), 1.2),
    ("circle", _mm(81.5),_mm(3.5), _mm(1.6), 1.2),
    ("circle", _mm(3.5), _mm(52.5),_mm(1.6), 1.2),
    ("circle", _mm(81.5),_mm(52.5),_mm(1.6), 1.2),
    ("rect",   _mm(3.5), -_mm(3.5), _mm(54.5), _mm(2.0), 1.5),
    *[("line", _mm(4.8 + i*2.54), -_mm(3.5),
               _mm(4.8 + i*2.54),  _mm(2.0), 0.8) for i in range(20)],
    ("text",   _mm(29),  -_mm(5.5), "HAT+ GPIO INTERFACE", 7),
    ("rect",   _mm(85),  _mm(2.5),  _mm(85)+14, _mm(15.5), 2.0),
    ("line",   _mm(85),  _mm(9.0),  _mm(85)+14, _mm(9.0),  0.8),
    ("text",   _mm(85)+7, _mm(10),  "USB2", 7),
    ("rect",   _mm(85),  _mm(17),   _mm(85)+14, _mm(30),   2.0),
    ("line",   _mm(85),  _mm(23.5), _mm(85)+14, _mm(23.5), 0.8),
    ("text",   _mm(85)+7, _mm(24.5),"USB3", 7),
    ("rect",   _mm(85),  _mm(32),   _mm(85)+16, _mm(54),   2.0),
    *[("line", _mm(85),  _mm(33.5 + i*2.8),
               _mm(85)+16, _mm(33.5 + i*2.8), 0.5) for i in range(7)],
    ("text",   _mm(85)+8, _mm(51),  "ETH", 7),
    ("rect",   -_mm(7),  _mm(2.5),  _mm(0.5),   _mm(7),    1.5),
    ("text",   -_mm(3),  _mm(9),    "PWR", 6),
    ("rect",   -_mm(1.5),_mm(12),   _mm(1.5),   _mm(29),   1.2),
    ("text",   _mm(4),   _mm(21),   "CAM", 6),
    ("rect",   _mm(7),   _mm(56),   _mm(14.5),  _mm(56)+7, 1.8),
    ("text",   _mm(10.7),_mm(56)+11,"HDMI0", 6),
    ("rect",   _mm(17),  _mm(56),   _mm(24.5),  _mm(56)+7, 1.8),
    ("text",   _mm(20.7),_mm(56)+11,"HDMI1", 6),
    ("rect",   _mm(27),  _mm(56),   _mm(32),    _mm(56)+5, 1.2),
    ("text",   _mm(29.5),_mm(56)+9, "UART", 6),
    ("rect",   _mm(36),  _mm(56),   _mm(54),    _mm(56)+4, 1.2),
    ("text",   _mm(45),  _mm(56)+9, "CAM/DSI0", 6),
    ("rect",   _mm(57),  _mm(56),   _mm(75),    _mm(56)+4, 1.2),
    ("text",   _mm(66),  _mm(56)+9, "CAM/DSI1", 6),
    ("rect",   _mm(44),  _mm(14),   _mm(60),    _mm(30),   2.0),
    *[("line", _mm(46 + i*2.8), _mm(14),
               _mm(46 + i*2.8), _mm(11),  0.6) for i in range(5)],
    *[("line", _mm(46 + i*2.8), _mm(30),
               _mm(46 + i*2.8), _mm(33),  0.6) for i in range(5)],
    *[("line", _mm(44), _mm(16 + i*3.5),
               _mm(41), _mm(16 + i*3.5),  0.6) for i in range(4)],
    *[("line", _mm(60), _mm(16 + i*3.5),
               _mm(63), _mm(16 + i*3.5),  0.6) for i in range(4)],
    ("text",   _mm(52),  _mm(21),   "BCM",  9),
    ("text",   _mm(52),  _mm(26),   "2712", 9),
    ("rect",   _mm(22),  _mm(5),    _mm(38),    _mm(17),   1.8),
    ("text",   _mm(30),  _mm(10),   "LPDDR5", 7),
    ("text",   _mm(30),  _mm(14),   "8GB",    7),
    ("rect",   _mm(26),  _mm(22),   _mm(39),    _mm(35),   1.5),
    ("text",   _mm(32.5),_mm(29.5), "RP1",   8),
    ("rect",   _mm(8),   _mm(34),   _mm(17),    _mm(43),   1.5),
    ("text",   _mm(12.5),_mm(39.5), "PMIC",  7),
    ("rect",   _mm(5),   _mm(18),   _mm(17),    _mm(28),   1.3),
    ("text",   _mm(11),  _mm(24),   "WiFi",  7),
    ("line",   _mm(39),  _mm(28),   _mm(26),    _mm(30),   0.5),
    ("line",   _mm(60),  _mm(20),   _mm(85),    _mm(10),   0.5),
    ("line",   _mm(60),  _mm(27),   _mm(85),    _mm(36),   0.5),
    ("line",   _mm(44),  _mm(33),   _mm(39),    _mm(35),   0.5),
]

_FADE_STEPS = 7
_FADE_PALETTE = []
for _i in range(_FADE_STEPS + 1):
    _t = _i / _FADE_STEPS
    _r = int(0x00 + _t * 0x1a)
    _g = int(0x38 + _t * (0xff - 0x38))
    _b = int(0x00 + _t * 0x80)
    _FADE_PALETTE.append(f"#{_r:02x}{_g:02x}{_b:02x}")


class PiDashboard(ctk.CTk):
    """
    RBerryLink OS Dashboard — passive always-on monitor for Pi 5 + X1202 UPS.

    Loops
    -----
    fast_loop  (2 s)  — battery, CPU, RAM, uptime, net bandwidth, shutdown check
    slow_loop  (30 s) — IP address, disk usage / R-W totals

    Shutdown state machine
    ----------------------
    IDLE → (battery ≤ threshold & discharging & was above threshold) → WARNING (10 s flash)
    WARNING → (still low) → POPUP (60 s countdown floating window)
    POPUP → (countdown = 0 or SHUTDOWN NOW clicked) → execute shutdown
    Any state → (battery recovers above threshold) → IDLE

    Rate algorithm
    --------------
    EMA with direction-change flush and adaptive deadband.
    On direction flip: smoothed_rate is reset to raw_rate to eliminate
    carry-over inertia. For DIRECTION_SETTLE_TICKS after a flip, a wider
    DEADBAND_SETTLING is used so the label doesn't flicker during the
    chip's recalibration window.
    """

    def __init__(self):
        super().__init__()

        self.ideal_width  = 420
        self.ideal_height = 700
        self.title(f"{BRAND_NAME} - {OS_NAME} {VERSION}")
        self.configure(fg_color=PIP_BG)
        self.center_window()

        try:
            import tkinter as _tk
            _icon_path = _os.path.join(_SCRIPT_DIR, "icon.png")
            if _os.path.exists(_icon_path):
                _photo = _tk.PhotoImage(file=_icon_path)
                self.wm_iconphoto(True, _photo)
                self._icon_photo = _photo
        except Exception as e:
            print(f"Icon load error: {e}")

        self.wm_attributes("-topmost", False)

        # --- I2C ---
        try:
            self.bus = smbus2.SMBus(1)
        except OSError as e:
            self.bus = None
            print(f"Warning: I2C bus not found ({e}). Running in demo mode.")

        # --- Battery state ---
        self.read_cycles   = 0
        self.history       = deque(maxlen=HISTORY_SIZE)
        self.direction     = "Power Flow"
        self.calc_rate     = 0.0
        self.smoothed_rate = None
        # Direction transition tracking for EMA flush + adaptive deadband
        self._prev_direction    = "Power Flow"
        self._direction_settled = 0   # ticks since last direction change

        # --- Shutdown state ---
        self._sd_state         = "idle"
        self._sd_warning_tick  = 0
        self._sd_countdown     = SHUTDOWN_COUNTDOWN_SECS
        self._sd_flash_on      = False
        self._sd_armed         = False
        self._sd_above_thresh  = False
        self._sd_startup_below = False
        self._sd_advisory_open = False
        self._sd_cooldown_until        = 0
        self._sd_slider_cooldown_until = 0
        self._sd_popup_win             = None
        self._footer_warn_priority     = 0

        # --- Load persisted settings ---
        settings = self._load_settings()
        self._sd_safe_shutdown  = settings.get("safe_shutdown_enabled", True)
        self._saved_threshold   = settings.get("shutdown_threshold", SHUTDOWN_THRESHOLD_DEFAULT)

        if not _os.path.exists(_SETTINGS_FILE):
            self._sd_safe_shutdown = True
            self._saved_threshold  = SHUTDOWN_THRESHOLD_DEFAULT
            try:
                with open(_SETTINGS_FILE, "w") as f:
                    _json.dump({
                        "shutdown_threshold":    self._saved_threshold,
                        "safe_shutdown_enabled": self._sd_safe_shutdown,
                    }, f, indent=2)
            except OSError as e:
                print(f"Settings init error: {e}")

        # --- CPU baseline ---
        psutil.cpu_percent(interval=None)

        # --- Net baseline ---
        _net = psutil.net_io_counters()
        self._last_net_time = time.time()
        self._last_net_sent = _net.bytes_sent
        self._last_net_recv = _net.bytes_recv

        # --- IP / disk state ---
        self._ip_visible = False
        self._ip_value   = "--"

        # --- Build UI ---
        self.setup_ui()
        self.setup_splash()

        # --- Startup battery advisory ---
        startup_data = self.get_battery_data()
        if startup_data:
            startup_cap, _ = startup_data
            if startup_cap <= self._saved_threshold:
                self.after(400, lambda: self._show_startup_advisory(startup_cap))

        # --- Start loops ---
        self.blink_cursor()
        self.after(500, self.fast_loop)
        self.slow_loop()
        self.after(SLOW_INTERVAL, self.slow_loop)

    # =========================================================================
    # WINDOW
    # =========================================================================

    def center_window(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.width  = min(self.ideal_width,  sw)
        self.height = min(self.ideal_height, sh - 40)
        x = max(0, (sw // 2) - (self.width  // 2))
        y = max(0, (sh // 2) - (self.height // 2))
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")

    # =========================================================================
    # SPLASH
    # =========================================================================

    def setup_splash(self):
        self.splash_frame = ctk.CTkFrame(self, fg_color=PIP_BG, corner_radius=0)
        self.splash_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.splash_container = ctk.CTkFrame(self.splash_frame, fg_color=PIP_BG)
        self.splash_container.place(relx=0.5, rely=0.5, anchor="center")

        CANVAS_W = 400
        CANVAS_H = 270

        self._pi_canvas = ctk.CTkCanvas(
            self.splash_container,
            width=CANVAS_W, height=CANVAS_H,
            bg=PIP_BG, highlightthickness=0
        )
        self._pi_canvas.pack(pady=(0, 10))

        self._pi_items = []
        for seg in _PI_SEGS:
            kind = seg[0]
            lw   = seg[-1] if len(seg) > 4 else 1

            if kind == "rect":
                _, x1, y1, x2, y2, _lw = seg
                iid = self._pi_canvas.create_rectangle(
                    x1 + _OX, y1 + _OY, x2 + _OX, y2 + _OY,
                    outline=PIP_BG, fill="", width=_lw
                )
            elif kind == "line":
                _, x1, y1, x2, y2, _lw = seg
                iid = self._pi_canvas.create_line(
                    x1 + _OX, y1 + _OY, x2 + _OX, y2 + _OY,
                    fill=PIP_BG, width=_lw
                )
            elif kind == "circle":
                _, cx, cy, r, _lw = seg
                iid = self._pi_canvas.create_oval(
                    cx - r + _OX, cy - r + _OY,
                    cx + r + _OX, cy + r + _OY,
                    outline=PIP_BG, fill="", width=_lw
                )
            elif kind == "text":
                _, x, y, txt, fsz = seg
                iid = self._pi_canvas.create_text(
                    x + _OX, y + _OY,
                    text=txt, fill=PIP_BG,
                    font=("Courier", fsz, "bold"), anchor="center"
                )
            else:
                continue
            self._pi_items.append((iid, kind))

        self._pi_idx  = 0
        self._pi_fade = 0
        self._animate_pi()

        self.base_splash_text = (
            f"{BRAND_NAME} -- {OS_NAME}\n" + ("=" * 35) +
            "\n\n> INITIALIZING I2C BUS...\n> ANALYZING VOLTAGE SENSOR...\n"
            f"> BUFFERING TELEMETRY: 0%\n> TIME REMAINING: {HISTORY_SIZE * 2}s"
            "\n\nPLEASE STAND BY. "
        )
        self.cursor_state = True
        self.splash_label = ctk.CTkLabel(
            self.splash_container,
            text=self.base_splash_text + "█",
            font=("Courier", 14, "bold"), text_color=PIP_GREEN, justify="left"
        )
        self.splash_label.pack(pady=(0, 8))

        self.splash_progress = ctk.CTkProgressBar(
            self.splash_container, width=280, height=15, corner_radius=0,
            fg_color=PIP_DIM, progress_color=PIP_GREEN,
            border_width=1, border_color=PIP_GREEN
        )
        self.splash_progress.set(0)
        self.splash_progress.pack()

    def _animate_pi(self):
        if not (hasattr(self, 'splash_frame') and self.splash_frame):
            return
        if self._pi_idx >= len(self._pi_items):
            return

        iid, kind = self._pi_items[self._pi_idx]
        color = _FADE_PALETTE[self._pi_fade]

        if kind == "text":
            self._pi_canvas.itemconfig(iid, fill=color)
        elif kind in ("rect", "circle"):
            self._pi_canvas.itemconfig(iid, outline=color)
        else:
            self._pi_canvas.itemconfig(iid, fill=color)

        if self._pi_fade < _FADE_STEPS:
            self._pi_fade += 1
            self.after(65, self._animate_pi)
        else:
            self._pi_idx  += 1
            self._pi_fade  = 0
            self.after(85, self._animate_pi)

    def blink_cursor(self):
        if not (hasattr(self, 'splash_frame') and self.splash_frame):
            return
        self.cursor_state = not self.cursor_state
        self.splash_label.configure(
            text=self.base_splash_text + ("█" if self.cursor_state else " ")
        )
        self.after(500, self.blink_cursor)

    def _update_splash_progress(self, pct, secs_left):
        if not (hasattr(self, 'splash_frame') and self.splash_frame):
            return
        self.base_splash_text = (
            f"{BRAND_NAME} -- {OS_NAME}\n" + ("=" * 35) +
            "\n\n> INITIALIZING I2C BUS...\n> ANALYZING VOLTAGE SENSOR...\n"
            f"> BUFFERING TELEMETRY: {pct}%\n> TIME REMAINING: {secs_left}s"
            "\n\nPLEASE STAND BY. "
        )
        self.splash_progress.set(pct / 100.0)

    def _dismiss_splash(self):
        if hasattr(self, 'splash_frame') and self.splash_frame:
            self.splash_frame.destroy()
            self.splash_frame = None
            self._sd_armed = True

            if self._sd_startup_below or self._sd_advisory_open:
                current_data = self.get_battery_data()
                current_cap  = current_data[0] if current_data else 0
                charging     = self.direction == "Charge Rate"
                if current_cap <= self._sd_threshold() and not charging:
                    self._sd_state        = "warning"
                    self._sd_warning_tick = 0
                    self._sd_flash_on     = True
                    self._flash_warning()

    # =========================================================================
    # MAIN UI
    # =========================================================================

    def setup_ui(self):
        self.header = ctk.CTkLabel(
            self, text=f"{BRAND_NAME} UNIFIED\nOPERATING SYSTEM",
            font=("Courier", 20, "bold"), text_color=PIP_GREEN
        )
        self.header.pack(pady=(20, 10))

        self.main_container = ctk.CTkScrollableFrame(
            self, fg_color=PIP_BG,
            border_width=2, border_color=PIP_GREEN,
            corner_radius=0,
            scrollbar_button_color=PIP_DIM,
            scrollbar_button_hover_color=PIP_GREEN
        )
        self.main_container.pack(pady=(10, 0), padx=25, fill="both", expand=True)

        def sep():
            ctk.CTkFrame(self.main_container, height=2, fg_color=PIP_DIM).pack(
                fill="x", padx=30, pady=10
            )

        def lbl(text):
            w = ctk.CTkLabel(
                self.main_container, text=text,
                font=PIP_FONT, text_color=PIP_GREEN
            )
            w.pack(pady=5)
            return w

        def bar():
            b = ctk.CTkProgressBar(
                self.main_container, width=280, height=15, corner_radius=0,
                fg_color=PIP_DIM, progress_color=PIP_GREEN,
                border_width=1, border_color=PIP_GREEN
            )
            b.set(0)
            b.pack(pady=(0, 10))
            return b

        self.bat_cap_label  = lbl("[=] Battery Capacity : -- %")
        self.bat_progress   = bar()
        self.bat_vol_label  = lbl("[v] Battery Voltage  : -- V")
        self.ups_vol_label  = lbl("[+] UPS Bus Voltage  : -- V")
        self.ups_cur_label  = lbl("[~] Power Flow       : -- %/hr")
        self.bat_time_label = lbl("[>] Time Remaining   : --")
        sep()

        self.temp_label   = lbl("[^] CPU Temperature  : -- C")
        self.cpu_label    = lbl("[*] CPU Usage        : -- %")
        self.ram_label    = lbl("[#] Memory Usage     : -- %")
        self.uptime_label = lbl("[◷] System Uptime    : --")
        sep()

        self.disk_label    = lbl("[$] Disk Usage       : -- %")
        self.disk_progress = bar()
        self.disk_rw_label = lbl("[%] Disk R/W         : -- / --")
        sep()

        ip_row = ctk.CTkFrame(self.main_container, fg_color=PIP_BG)
        ip_row.pack(pady=5)
        self.net_ip_label = ctk.CTkLabel(
            ip_row, text="[@] IP Address       : ****",
            font=PIP_FONT, text_color=PIP_GREEN
        )
        self.net_ip_label.pack(side="left")
        self.ip_toggle_btn = ctk.CTkButton(
            ip_row, text="[SHOW]", width=70, height=26,
            font=("Courier", 11, "bold"),
            fg_color=PIP_BG, text_color=PIP_GREEN,
            hover_color=PIP_DIM, border_width=1, border_color=PIP_GREEN,
            corner_radius=0, command=self._toggle_ip
        )
        self.ip_toggle_btn.pack(side="left", padx=(8, 0))
        self.net_rx_label = lbl("[v] Net Download     : -- KB/s")
        self.net_tx_label = lbl("[^] Net Upload       : -- KB/s")
        ctk.CTkLabel(self.main_container, text="", font=PIP_FONT).pack(pady=5)

        # ---- FOOTER ----
        self.footer = ctk.CTkFrame(
            self, fg_color=PIP_BG,
            border_width=2, border_color=PIP_DIM,
            corner_radius=0
        )
        self.footer.pack(pady=(4, 8), padx=25, fill="x")

        self.footer_warn_label = ctk.CTkLabel(
            self.footer, text="",
            font=("Courier", 12, "bold"), text_color=PIP_CRIT
        )
        self.footer_warn_label.pack(pady=(6, 0))

        slider_row = ctk.CTkFrame(self.footer, fg_color=PIP_BG)
        slider_row.pack(pady=6, padx=12, fill="x")

        ctk.CTkLabel(
            slider_row, text="[!] SAFE SHUTDOWN AT:",
            font=("Courier", 12, "bold"), text_color=PIP_GREEN
        ).pack(side="left")

        self._sd_threshold_var = ctk.IntVar(value=self._saved_threshold)
        self.footer_threshold_label = ctk.CTkLabel(
            slider_row,
            text=f" {self._saved_threshold:2d}%",
            font=("Courier", 12, "bold"), text_color=PIP_GREEN
        )
        self.footer_threshold_label.pack(side="right")

        _ss_col = PIP_GREEN if self._sd_safe_shutdown else PIP_DIM
        self._safe_shutdown_btn = ctk.CTkButton(
            slider_row,
            text="[ ON  ]" if self._sd_safe_shutdown else "[ OFF ]",
            width=80, height=26,
            font=("Courier", 11, "bold"),
            fg_color=PIP_BG, text_color=_ss_col,
            hover_color=PIP_DIM, border_width=1, border_color=_ss_col,
            corner_radius=0, command=self._toggle_safe_shutdown
        )
        self._safe_shutdown_btn.pack(side="right", padx=(0, 6))

        self.footer_slider = ctk.CTkSlider(
            slider_row,
            from_=5, to=50, number_of_steps=45,
            variable=self._sd_threshold_var,
            fg_color=PIP_DIM, progress_color=PIP_GREEN,
            button_color=PIP_GREEN, button_hover_color=PIP_WARN,
            corner_radius=0,
            command=self._on_slider_change
        )
        self.footer_slider.pack(side="left", fill="x", expand=True, padx=(8, 8))

        self._safe_shutdown_status = ctk.CTkLabel(
            self.footer, text="",
            font=("Courier", 10, "bold"), text_color=PIP_GREEN
        )
        self._safe_shutdown_status.pack(pady=(0, 2))

        ctk.CTkFrame(self.footer, height=1, fg_color=PIP_DIM).pack(
            fill="x", padx=12, pady=(0, 6)
        )
        autostart_row = ctk.CTkFrame(self.footer, fg_color=PIP_BG)
        autostart_row.pack(pady=(0, 2), padx=12, fill="x")

        ctk.CTkLabel(
            autostart_row, text="[>] AUTOSTART ON BOOT:",
            font=("Courier", 12, "bold"), text_color=PIP_GREEN
        ).pack(side="left")

        self._autostart_btn = ctk.CTkButton(
            autostart_row,
            text=self._autostart_label(),
            width=90, height=26,
            font=("Courier", 11, "bold"),
            fg_color=PIP_BG,
            text_color=PIP_GREEN if self._autostart_enabled() else PIP_DIM,
            hover_color=PIP_DIM, border_width=1,
            border_color=PIP_GREEN if self._autostart_enabled() else PIP_DIM,
            corner_radius=0, command=self._toggle_autostart
        )
        self._autostart_btn.pack(side="right")

        self._autostart_status = ctk.CTkLabel(
            self.footer, text="",
            font=("Courier", 10, "bold"), text_color=PIP_GREEN
        )
        self._autostart_status.pack(pady=(0, 6))

    def _on_slider_change(self, val):
        pct = int(val)
        self.footer_threshold_label.configure(text=f" {pct:2d}%")

        if self._sd_state in ("warning", "popup"):
            if self._sd_popup_win and self._sd_popup_win.winfo_exists():
                self._sd_popup_win.destroy()
                self._sd_popup_win = None
            self._sd_state = "idle"
            self._set_footer_warn("", PIP_GREEN, 0)

        self._sd_slider_cooldown_until = time.time() + SHUTDOWN_SLIDER_COOLDOWN
        self._save_settings()

        self._safe_shutdown_status.configure(
            text=f"> Threshold set to {pct}%. Cooldown active.",
            text_color=PIP_GREEN
        )
        self._fade_slider_status(step=0)

    def _toggle_safe_shutdown(self):
        self._sd_safe_shutdown = not self._sd_safe_shutdown
        enabled = self._sd_safe_shutdown
        col = PIP_GREEN if enabled else PIP_DIM
        self._safe_shutdown_btn.configure(
            text="[ ON  ]" if enabled else "[ OFF ]",
            text_color=col,
            border_color=col
        )
        if not enabled:
            if self._sd_popup_win and self._sd_popup_win.winfo_exists():
                self._sd_popup_win.destroy()
                self._sd_popup_win = None
            if self._sd_state in ("popup", "warning"):
                self._sd_state = "idle"
                self._set_footer_warn(
                    f"[!] Battery critical — safe shutdown disabled ({self._sd_threshold()}%)",
                    PIP_WARN, priority=3
                )

        msg = ("> Safe shutdown enabled. Countdown active when critical."
               if enabled else
               "> Safe shutdown disabled. Footer warning only.")
        self._safe_shutdown_status.configure(text=msg, text_color=PIP_GREEN)
        self._fade_safe_shutdown_status(step=0)
        self._save_settings()

    def _fade_safe_shutdown_status(self, step=0):
        self._fade_shutdown_status_label(step)

    def _fade_slider_status(self, step=0):
        self._fade_shutdown_status_label(step)

    def _fade_shutdown_status_label(self, step=0):
        STEPS   = 12
        STEP_MS = 250
        if step > STEPS:
            self._safe_shutdown_status.configure(text="")
            return
        t = step / STEPS
        r = int(0x1a * (1 - t))
        g = int(0xff * (1 - t))
        b = int(0x80 * (1 - t))
        self._safe_shutdown_status.configure(text_color=f"#{r:02x}{g:02x}{b:02x}")
        self.after(STEP_MS, lambda: self._fade_shutdown_status_label(step + 1))

    # =========================================================================
    # SETTINGS PERSISTENCE
    # =========================================================================

    def _load_settings(self):
        for path in (_SETTINGS_FILE, _SETTINGS_DEFAULT_FILE):
            try:
                with open(path, "r") as f:
                    data = _json.load(f)
                if "shutdown_threshold" in data:
                    data["shutdown_threshold"] = max(5, min(50, int(data["shutdown_threshold"])))
                return data
            except (OSError, _json.JSONDecodeError, ValueError):
                continue
        return {}

    def _save_settings(self):
        data = {
            "shutdown_threshold":    self._sd_threshold(),
            "safe_shutdown_enabled": self._sd_safe_shutdown,
        }
        try:
            with open(_SETTINGS_FILE, "w") as f:
                _json.dump(data, f, indent=2)
        except OSError as e:
            print(f"Settings save error: {e}")

    # =========================================================================
    # AUTOSTART
    # =========================================================================

    def _autostart_enabled(self):
        return _os.path.exists(_AUTOSTART_FILE)

    def _autostart_label(self):
        return "[ ON  ]" if self._autostart_enabled() else "[ OFF ]"

    def _toggle_autostart(self):
        if self._autostart_enabled():
            try:
                _os.remove(_AUTOSTART_FILE)
                msg = "> Autostart disabled."
                enabled = False
            except OSError as e:
                print(f"Autostart disable error: {e}")
                return
        else:
            try:
                _os.makedirs(_AUTOSTART_DIR, exist_ok=True)
                with open(_AUTOSTART_FILE, "w") as f:
                    f.write(_DESKTOP_CONTENT)
                msg = "> Autostart enabled. Takes effect on next boot."
                enabled = True
            except OSError as e:
                print(f"Autostart enable error: {e}")
                return

        col = PIP_GREEN if enabled else PIP_DIM
        self._autostart_btn.configure(
            text=self._autostart_label(),
            text_color=col,
            border_color=col
        )
        self._autostart_status.configure(text=msg, text_color=PIP_GREEN)
        self._fade_autostart_status(step=0)

    def _fade_autostart_status(self, step=0):
        STEPS   = 12
        STEP_MS = 250
        if step > STEPS:
            self._autostart_status.configure(text="")
            return
        t = step / STEPS
        r = int(0x1a * (1 - t))
        g = int(0xff * (1 - t))
        b = int(0x80 * (1 - t))
        self._autostart_status.configure(text_color=f"#{r:02x}{g:02x}{b:02x}")
        self.after(STEP_MS, lambda: self._fade_autostart_status(step + 1))

    # =========================================================================
    # IP TOGGLE
    # =========================================================================

    def _toggle_ip(self):
        self._ip_visible = not self._ip_visible
        self.ip_toggle_btn.configure(text="[HIDE]" if self._ip_visible else "[SHOW]")
        self._refresh_ip_label()

    def _refresh_ip_label(self):
        display = self._ip_value if self._ip_visible else "****"
        self.net_ip_label.configure(text=f"[@] IP Address       : {display}")

    # =========================================================================
    # HARDWARE READS
    # =========================================================================

    def get_battery_data(self):
        if not self.bus:
            return None
        try:
            c_raw    = self.bus.read_word_data(MAX17048_ADDR, 0x04)
            capacity = struct.unpack("<H", struct.pack(">H", c_raw))[0] / 256.0
            v_raw    = self.bus.read_word_data(MAX17048_ADDR, 0x02)
            voltage  = struct.unpack("<H", struct.pack(">H", v_raw))[0] * 78.125 / 1_000_000
            return capacity, voltage
        except OSError as e:
            print(f"MAX17048 read error: {e}")
            return None

    def get_bus_voltage(self):
        if not self.bus:
            return None
        try:
            raw     = self.bus.read_word_data(INA219_ADDR, 0x02)
            swapped = struct.unpack("<H", struct.pack(">H", raw))[0]
            return (swapped >> 3) * 0.004
        except OSError:
            return None

    # =========================================================================
    # SHUTDOWN STATE MACHINE
    # =========================================================================

    def _sd_threshold(self):
        return int(self._sd_threshold_var.get())

    def _check_shutdown(self, raw_cap):
        if not self._sd_armed:
            return

        threshold   = self._sd_threshold()
        discharging = (self.direction == "Discharge Rate" or
                       (self._sd_startup_below and self.direction == "Power Flow"))
        balanced    = self.direction == "Power Flow" and not self._sd_startup_below
        below       = raw_cap <= threshold

        if raw_cap > threshold:
            self._sd_above_thresh = True

        if below and balanced:
            self._set_footer_warn(
                f"[~] POWER BALANCED AT CRITICAL LEVEL ({raw_cap:.1f}%)",
                PIP_WARN, priority=4
            )
            if self._sd_state != "idle":
                self._sd_reset()
            return

        if not below or self.direction == "Charge Rate":
            if raw_cap > threshold:
                cur = self.footer_warn_label.cget("text")
                if (cur.startswith("[~] POWER BALANCED") or
                        cur.startswith("[!] Battery critical")):
                    self._set_footer_warn("", PIP_GREEN, 0)
            if self._sd_state != "idle":
                self._sd_reset()
            return

        if self._sd_state == "idle":
            if not below or not discharging:
                return

            in_cooldown        = (self._sd_startup_below and
                                  time.time() < self._sd_cooldown_until)
            in_slider_cooldown = time.time() < self._sd_slider_cooldown_until
            if in_cooldown or in_slider_cooldown:
                return

            can_trigger = self._sd_above_thresh or self._sd_startup_below
            if not can_trigger:
                return

            self._sd_state        = "warning"
            self._sd_warning_tick = 0
            self._sd_flash_on     = True
            self._flash_warning()
            return

        if self._sd_state == "warning":
            self._sd_warning_tick += 1
            ticks_needed = max(1, SHUTDOWN_WARNING_SECS // 2)
            if self._sd_warning_tick >= ticks_needed:
                if self._sd_safe_shutdown:
                    self._sd_state     = "popup"
                    self._sd_countdown = SHUTDOWN_COUNTDOWN_SECS
                    self._show_shutdown_popup()
            return

    def _set_footer_warn(self, text, color, priority):
        if text == "" or priority >= self._footer_warn_priority:
            self._footer_warn_priority = priority if text else 0
            self.footer_warn_label.configure(text=text, text_color=color)

    def _flash_warning(self):
        if self._sd_state != "warning":
            self._set_footer_warn("", PIP_GREEN, 0)
            return
        self._sd_flash_on = not self._sd_flash_on
        color = PIP_CRIT if self._sd_flash_on else PIP_WARN
        self._set_footer_warn(
            "[!!] LOW BATTERY — SHUTDOWN IMMINENT [!!]", color, priority=5
        )
        self.after(500, self._flash_warning)

    def _sd_cancel_warning(self):
        self._sd_state = "idle"
        self._set_footer_warn("", PIP_GREEN, 0)

    def _sd_reset(self):
        self._sd_state             = "idle"
        self._sd_warning_tick      = 0
        self._sd_cooldown_until    = 0
        self._footer_warn_priority = 0
        self._set_footer_warn("", PIP_GREEN, 0)
        if self._sd_popup_win and self._sd_popup_win.winfo_exists():
            self._sd_popup_win.destroy()
            self._sd_popup_win = None

    def _show_startup_advisory(self, startup_cap):
        win = ctk.CTkToplevel(self)
        win.title(f"{BRAND_NAME} — STARTUP WARNING")
        win.configure(fg_color=PIP_BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        self._sd_advisory_open = True

        W, H = 380, 310
        px = self.winfo_x() + (self.winfo_width()  // 2) - (W // 2)
        py = self.winfo_y() + (self.winfo_height() // 2) - (H // 2)
        win.geometry(f"{W}x{H}+{px}+{py}")

        border = ctk.CTkFrame(win, fg_color=PIP_BG, border_width=3,
                              border_color=PIP_WARN, corner_radius=0)
        border.pack(fill="both", expand=True, padx=4, pady=4)

        title_bar = ctk.CTkFrame(border, fg_color=PIP_WARN, corner_radius=0, height=32)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(
            title_bar,
            text=f"  {BRAND_NAME}  —  STARTUP POWER ADVISORY",
            font=("Courier", 11, "bold"), text_color=PIP_BG
        ).pack(side="left", padx=8, pady=4)

        def _start_drag(e):
            win._drag_x = e.x_root - win.winfo_x()
            win._drag_y = e.y_root - win.winfo_y()
        def _do_drag(e):
            win.geometry(f"+{e.x_root - win._drag_x}+{e.y_root - win._drag_y}")
        title_bar.bind("<ButtonPress-1>", _start_drag)
        title_bar.bind("<B1-Motion>",     _do_drag)

        ctk.CTkLabel(border, text="[!]",
                     font=("Courier", 36, "bold"), text_color=PIP_WARN).pack(pady=(18, 4))
        ctk.CTkLabel(border, text="BATTERY CRITICALLY LOW AT STARTUP",
                     font=("Courier", 13, "bold"), text_color=PIP_WARN).pack(pady=(0, 8))
        ctk.CTkLabel(
            border,
            text=f"Current charge:   {startup_cap:.1f}%\nShutdown threshold:  {self._saved_threshold}%",
            font=("Courier", 12, "bold"), text_color=PIP_GREEN, justify="center"
        ).pack(pady=(0, 8), padx=20)
        ctk.CTkLabel(
            border,
            text="Connect power before use to\navoid unexpected shutdowns.",
            font=("Courier", 11), text_color=PIP_GREEN, justify="center"
        ).pack(pady=(0, 16), padx=20)
        ctk.CTkFrame(border, height=2, fg_color=PIP_WARN).pack(
            fill="x", padx=20, pady=(0, 14))

        def _dismiss():
            win.destroy()
            self._sd_advisory_open = False
            self._sd_startup_below = True

        ctk.CTkButton(
            border, text="[ OK — I UNDERSTAND ]", width=220, height=38,
            font=("Courier", 13, "bold"),
            fg_color=PIP_BG, text_color=PIP_WARN,
            hover_color="#1a1000", border_width=2, border_color=PIP_WARN,
            corner_radius=0, command=_dismiss
        ).pack(pady=(0, 18))

    def _show_shutdown_popup(self):
        self._set_footer_warn("", PIP_GREEN, 0)

        if self._sd_popup_win and self._sd_popup_win.winfo_exists():
            self._sd_popup_win.destroy()

        win = ctk.CTkToplevel(self)
        win.title(f"{BRAND_NAME} — POWER WARNING")
        win.configure(fg_color=PIP_BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.overrideredirect(True)

        W, H = 380, 300
        px = self.winfo_x() + (self.winfo_width()  // 2) - (W // 2)
        py = self.winfo_y() + (self.winfo_height() // 2) - (H // 2)
        win.geometry(f"{W}x{H}+{px}+{py}")

        self._sd_popup_win = win

        border = ctk.CTkFrame(win, fg_color=PIP_BG, border_width=3,
                              border_color=PIP_CRIT, corner_radius=0)
        border.pack(fill="both", expand=True, padx=4, pady=4)

        title_bar = ctk.CTkFrame(border, fg_color=PIP_CRIT, corner_radius=0, height=32)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(
            title_bar,
            text=f"  {BRAND_NAME}  —  CRITICAL POWER WARNING",
            font=("Courier", 11, "bold"), text_color=PIP_BG
        ).pack(side="left", padx=8, pady=4)

        def _start_drag(e):
            win._drag_x = e.x_root - win.winfo_x()
            win._drag_y = e.y_root - win.winfo_y()
        def _do_drag(e):
            win.geometry(f"+{e.x_root - win._drag_x}+{e.y_root - win._drag_y}")
        title_bar.bind("<ButtonPress-1>", _start_drag)
        title_bar.bind("<B1-Motion>",     _do_drag)

        ctk.CTkLabel(border, text="[!!]",
                     font=("Courier", 36, "bold"), text_color=PIP_CRIT).pack(pady=(18, 4))
        ctk.CTkLabel(
            border,
            text=f"Battery level critical — {self._sd_threshold()}% threshold reached.",
            font=("Courier", 11, "bold"), text_color=PIP_GREEN,
            wraplength=320, justify="center"
        ).pack(pady=(0, 4), padx=20)
        ctk.CTkLabel(
            border, text="Save your work immediately.",
            font=("Courier", 11, "bold"), text_color=PIP_WARN, justify="center"
        ).pack(pady=(0, 12))

        self._sd_countdown_label = ctk.CTkLabel(
            border,
            text=f"Shutting down in:  {self._sd_countdown:02d}s",
            font=("Courier", 16, "bold"), text_color=PIP_WARN
        )
        self._sd_countdown_label.pack(pady=(0, 16))

        ctk.CTkFrame(border, height=2, fg_color=PIP_CRIT).pack(
            fill="x", padx=20, pady=(0, 14))

        btn_row = ctk.CTkFrame(border, fg_color=PIP_BG)
        btn_row.pack(pady=(0, 18))

        ctk.CTkButton(
            btn_row, text="[ CANCEL ]", width=140, height=38,
            font=("Courier", 13, "bold"),
            fg_color=PIP_BG, text_color=PIP_GREEN,
            hover_color=PIP_DIM, border_width=2, border_color=PIP_GREEN,
            corner_radius=0, command=self._cancel_shutdown
        ).pack(side="left", padx=(0, 14))

        ctk.CTkButton(
            btn_row, text="[ SHUTDOWN NOW ]", width=160, height=38,
            font=("Courier", 13, "bold"),
            fg_color="#1a0000", text_color=PIP_CRIT,
            hover_color="#330000", border_width=2, border_color=PIP_CRIT,
            corner_radius=0, command=self._execute_shutdown
        ).pack(side="left")

        self._tick_countdown()

    def _tick_countdown(self):
        if self._sd_state != "popup":
            return
        if not (self._sd_popup_win and self._sd_popup_win.winfo_exists()):
            return

        self._sd_countdown_label.configure(
            text=f"Shutting down in:  {self._sd_countdown:02d}s"
        )

        if self._sd_countdown <= 0:
            self.after(300, self._execute_shutdown)
            return

        self._sd_countdown -= 1
        self.after(1000, self._tick_countdown)

    def _cancel_shutdown(self):
        if self._sd_popup_win and self._sd_popup_win.winfo_exists():
            self._sd_popup_win.destroy()
            self._sd_popup_win = None
        self._sd_state        = "idle"
        self._sd_above_thresh = False
        self._set_footer_warn("", PIP_GREEN, 0)
        if self._sd_startup_below:
            self._sd_cooldown_until = time.time() + SHUTDOWN_COOLDOWN_SECS
            self._tick_cooldown_display()

    def _tick_cooldown_display(self):
        remaining = self._sd_cooldown_until - time.time()
        if remaining <= 0:
            self._set_footer_warn("", PIP_GREEN, 0)
            return
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        self._set_footer_warn(
            f"[~] Snoozed. Warning returns in {mins}m {secs:02d}s",
            PIP_DIM, priority=2
        )
        self.after(1000, self._tick_cooldown_display)

    def _execute_shutdown(self):
        try:
            subprocess.run(SHUTDOWN_CMD, check=True)
        except Exception as e:
            print(f"Shutdown command failed: {e}")

    # =========================================================================
    # FAST LOOP — every 2 s
    # =========================================================================

    def fast_loop(self):
        now  = time.time()
        data = self.get_battery_data()

        if data:
            raw_cap, vol = data
            self.read_cycles += 1
            self.history.append((raw_cap, now))

            if self.read_cycles <= SPLASH_CYCLES:
                pct       = int((self.read_cycles / SPLASH_CYCLES) * 100)
                secs_left = (SPLASH_CYCLES - self.read_cycles) * 2
                self._update_splash_progress(pct, secs_left)
            if self.read_cycles == SPLASH_CYCLES:
                self._dismiss_splash()


            # -----------------------------------------------------------------
            # EMA rate calculation with direction-flush and adaptive deadband
            # -----------------------------------------------------------------
            n_history = len(self.history)
            if n_history >= 2:
                # To prevent massive float numbers from UNIX timestamps, 
                # we normalize time against the oldest entry in the window.
                t0 = self.history[0][1]
                
                sum_x = sum_y = sum_xy = sum_xx = 0.0
                
                for cap, t in self.history:
                    x = t - t0  # Time in seconds since window start
                    y = cap     # Capacity percentage
                    sum_x += x
                    sum_y += y
                    sum_xy += x * y
                    sum_xx += x * x
                
                denominator = (n_history * sum_xx) - (sum_x * sum_x)
                
                if denominator != 0:
                    # Slope is % capacity change per second
                    slope_per_second = ((n_history * sum_xy) - (sum_x * sum_y)) / denominator
                    # Convert to % per hour
                    raw_rate = slope_per_second * 3600
                else:
                    raw_rate = 0.0

                # Determine what direction the raw reading suggests
                raw_direction = (
                    "Charge Rate"    if raw_rate >  DEADBAND_NORMAL else
                    "Discharge Rate" if raw_rate < -DEADBAND_NORMAL else
                    "Power Flow"
                )

                # Direction changed — flush the EMA so carry-over inertia
                # from the previous charge/discharge period doesn't bleed in.
                # Reset the settle counter so the wider deadband kicks in.
                if raw_direction != self._prev_direction:
                    self.smoothed_rate      = raw_rate
                    self._direction_settled = 0
                    self._prev_direction    = raw_direction
                else:
                    self._direction_settled += 1
                    self.smoothed_rate = (
                        raw_rate if self.smoothed_rate is None
                        else self.smoothed_rate * 0.85 + raw_rate * 0.15
                    )

                self.calc_rate = self.smoothed_rate

            # Adaptive deadband — wider for the first DIRECTION_SETTLE_TICKS
            # after a transition to suppress label flicker during chip recal.
            deadband = (
                DEADBAND_SETTLING
                if self._direction_settled < DIRECTION_SETTLE_TICKS
                else DEADBAND_NORMAL
            )
            if   self.calc_rate >  deadband: self.direction = "Charge Rate"
            elif self.calc_rate < -deadband: self.direction = "Discharge Rate"
            else:                            self.direction = "Power Flow"

            # Battery labels
            self.bat_cap_label.configure(text=f"[=] Battery Capacity : {raw_cap:.1f} %")
            self.bat_vol_label.configure(text=f"[v] Battery Voltage  : {vol:.2f} V")

            bus_v = self.get_bus_voltage()
            if bus_v is not None and bus_v > 0.5:
                self.ups_vol_label.configure(text=f"[+] UPS Bus Voltage  : {bus_v:.2f} V")
            else:
                offset = 0.15 if self.direction == "Charge Rate" else 0
                self.ups_vol_label.configure(text=f"[+] UPS Bus Voltage  : {vol + offset:.2f} V")

            if self.read_cycles < HISTORY_SIZE:
                rate_text = "[~] Calculating...   : -- %/hr"
                eta_text  = "Buffering..."
            else:
                rate_text = f"[~] {self.direction:<14} : {abs(self.calc_rate):.1f} %/hr"
                if self.direction == "Discharge Rate" and abs(self.calc_rate) > DEADBAND_NORMAL:
                    hours = raw_cap / abs(self.calc_rate)
                    eta_text = (
                        "Holding Charge..." if hours > 99
                        else f"{int(hours)}h {int((hours % 1) * 60)}m until EMPTY"
                    )
                elif self.direction == "Charge Rate" and self.calc_rate > DEADBAND_NORMAL:
                    hours = (100 - raw_cap) / self.calc_rate
                    eta_text = (
                        "Trickle Charging..." if hours > 99
                        else f"{int(hours)}h {int((hours % 1) * 60)}m until FULL"
                    )
                else:
                    eta_text = "Power Flow Balanced"

            self.ups_cur_label.configure(text=rate_text)
            self.bat_time_label.configure(text=f"[>] {eta_text}")

            bar_color = PIP_GREEN if raw_cap > 50 else (PIP_WARN if raw_cap > 20 else PIP_CRIT)
            self.bat_progress.configure(progress_color=bar_color)
            self.bat_progress.set(raw_cap / 100.0)

            self._check_shutdown(raw_cap)

        self.cpu_label.configure(
            text=f"[*] CPU Usage        : {psutil.cpu_percent(interval=None):.1f} %"
        )
        self.ram_label.configure(
            text=f"[#] Memory Usage     : {psutil.virtual_memory().percent:.1f} %"
        )

        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                temp = int(f.read()) / 1000
            self.temp_label.configure(text=f"[^] CPU Temperature  : {temp:.1f} C")
        except OSError:
            pass

        upt    = now - psutil.boot_time()
        uh, ur = divmod(upt, 3600)
        um, _  = divmod(ur, 60)
        self.uptime_label.configure(text=f"[◷] System Uptime    : {int(uh)}h {int(um)}m")

        try:
            net     = psutil.net_io_counters()
            elapsed = now - self._last_net_time
            if elapsed > 0:
                rx = (net.bytes_recv - self._last_net_recv) / elapsed / 1024
                tx = (net.bytes_sent - self._last_net_sent) / elapsed / 1024
                self.net_rx_label.configure(text=f"[v] Net Download     : {rx:.1f} KB/s")
                self.net_tx_label.configure(text=f"[^] Net Upload       : {tx:.1f} KB/s")
            self._last_net_time = now
            self._last_net_sent = net.bytes_sent
            self._last_net_recv = net.bytes_recv
        except OSError as e:
            print(f"Network bandwidth error: {e}")

        self.after(FAST_INTERVAL, self.fast_loop)

    # =========================================================================
    # SLOW LOOP — every 30 s
    # =========================================================================

    def slow_loop(self):
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except OSError:
            pass

        if not ip:
            try:
                for iface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if (addr.family == socket.AF_INET and
                                not addr.address.startswith("127.")):
                            ip = addr.address
                            break
                    if ip:
                        break
            except OSError:
                pass

        self._ip_value = ip if ip else "Unable to locate"
        self._refresh_ip_label()

        try:
            disk     = psutil.disk_usage('/')
            disk_pct = disk.percent
            disk_color = (
                PIP_GREEN if disk_pct < 75 else
                PIP_WARN  if disk_pct < 90 else PIP_CRIT
            )
            self.disk_label.configure(
                text=(f"[$] Disk Usage       : {disk_pct:.1f} %"
                      f" ({disk.used/2**30:.1f}/{disk.total/2**30:.1f} GB)")
            )
            self.disk_progress.configure(progress_color=disk_color)
            self.disk_progress.set(disk_pct / 100.0)
        except OSError as e:
            print(f"Disk usage error: {e}")

        try:
            dio = psutil.disk_io_counters()
            self.disk_rw_label.configure(
                text=(f"[%] Disk R/W         :"
                      f" {dio.read_bytes/2**20:.1f} MB"
                      f" / {dio.write_bytes/2**20:.1f} MB")
            )
        except (OSError, AttributeError) as e:
            print(f"Disk I/O error: {e}")

        self.after(SLOW_INTERVAL, self.slow_loop)


if __name__ == "__main__":
    app = PiDashboard()
    app.mainloop()
