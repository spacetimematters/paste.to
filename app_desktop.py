import os
import sys
import json
import shutil
import subprocess
import tempfile
import threading
import platform
from queue import Queue, Empty
from pathlib import Path

import customtkinter as ctk
from yt_dlp import YoutubeDL
import yt_dlp.version

CONFIG_PATH = os.path.join(Path.home(), ".paste-to-config.json")

# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------
DARK = {
    "name": "Dark",
    "alpha": 1.0,
    "window_bg": "#0d0f14",
    "titlebar_bg": "#090b10",
    "titlebar_text": "#555566",
    "separator": "#1e2130",
    "card_bg": "#13151c",
    "border": "#1e2130",
    "accent": "#d4a843",
    "accent_hover": "#c49a35",
    "accent_text": "#0d0f14",
    "text": "#e0e0e0",
    "muted": "#555566",
    "placeholder": "#3a3a4a",
    "error": "#ff4455",
    "success": "#44cc88",
    "close_hover": "#ff4444",
    "btn_hover": "#1e2130",
    "seg_selected": "#1e2130",
    "seg_unselected": "#13151c",
    "seg_hover": "#252840",
    "settings_bg": "#0d0f14",
}

GLASS = {
    "name": "Glass",
    "alpha": 0.93,
    "window_bg": "#e8e8ee",
    "titlebar_bg": "#dddde4",
    "titlebar_text": "#888899",
    "separator": "#ccccdd",
    "card_bg": "#f4f4f8",
    "border": "#ccccdd",
    "accent": "#3a6fd8",
    "accent_hover": "#2f5bb8",
    "accent_text": "#ffffff",
    "text": "#1a1a2e",
    "muted": "#888899",
    "placeholder": "#aaaabb",
    "error": "#dd3344",
    "success": "#22aa66",
    "close_hover": "#ff4444",
    "btn_hover": "#ccccdd",
    "seg_selected": "#ccccdd",
    "seg_unselected": "#e0e0e8",
    "seg_hover": "#d5d5de",
    "settings_bg": "#e8e8ee",
}

THEMES = {"dark": DARK, "glass": GLASS}

MONO = "Consolas"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config():
    defaults = {"save_dir": str(Path.home() / "Downloads"), "theme": "dark"}
    try:
        with open(CONFIG_PATH, "r") as f:
            defaults.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    os.makedirs(defaults["save_dir"], exist_ok=True)
    return defaults


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.msg_queue = Queue()
        self.downloading = False
        self.theme = THEMES.get(self.config.get("theme", "dark"), DARK)
        self._drag_x = 0
        self._drag_y = 0

        # Window setup
        self.overrideredirect(True)
        self.geometry("520x500")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"520x500+{(sw - 520) // 2}+{(sh - 500) // 2}")

        # --- Custom Title Bar ---
        self.title_bar = ctk.CTkFrame(self, height=36, corner_radius=0)
        self.title_bar.pack(fill="x", side="top")
        self.title_bar.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            self.title_bar, text="paste.to",
            font=ctk.CTkFont(family=MONO, size=13),
        )
        self.title_label.pack(side="left", padx=14)

        self.close_btn = ctk.CTkButton(
            self.title_bar, text="\u00d7", width=36, height=36,
            corner_radius=0, border_width=0,
            font=ctk.CTkFont(size=16),
            command=self.destroy,
        )
        self.close_btn.pack(side="right")

        self.min_btn = ctk.CTkButton(
            self.title_bar, text="\u2212", width=36, height=36,
            corner_radius=0, border_width=0,
            font=ctk.CTkFont(size=16),
            command=self._minimize,
        )
        self.min_btn.pack(side="right")

        self.gear_btn = ctk.CTkButton(
            self.title_bar, text="\u2699", width=36, height=36,
            corner_radius=0, border_width=0,
            font=ctk.CTkFont(size=16),
            command=self._toggle_settings,
        )
        self.gear_btn.pack(side="right")

        # Title bar drag
        for w in (self.title_bar, self.title_label):
            w.bind("<Button-1>", self._on_title_press)
            w.bind("<B1-Motion>", self._on_title_drag)

        # Separator
        self.sep = ctk.CTkFrame(self, height=1, corner_radius=0)
        self.sep.pack(fill="x")

        # --- Main Content Frame ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)

        # Title
        self.app_title = ctk.CTkLabel(
            self.main_frame, text="paste.to",
            font=ctk.CTkFont(family=MONO, size=26, weight="bold"),
        )
        self.app_title.pack(pady=(30, 2))

        self.subtitle = ctk.CTkLabel(
            self.main_frame, text="paste a youtube link. get the file.",
            font=ctk.CTkFont(family=MONO, size=12),
        )
        self.subtitle.pack(pady=(0, 20))

        # URL Entry
        self.url_entry = ctk.CTkEntry(
            self.main_frame, width=440, height=42,
            placeholder_text="https://youtube.com/watch?v=...",
            corner_radius=8,
            font=ctk.CTkFont(family=MONO, size=13),
        )
        self.url_entry.pack(pady=(0, 12))
        self.url_entry.bind("<FocusIn>", self._on_entry_focus)
        self.url_entry.bind("<KeyRelease>", self._on_input_change)
        self.url_entry.bind("<Return>", lambda e: self._start_download())

        # Mode Toggle
        self.mode_var = ctk.StringVar(value="Video")
        self.mode_toggle = ctk.CTkSegmentedButton(
            self.main_frame, values=["Video", "Audio", "Thumbnail"],
            variable=self.mode_var,
            font=ctk.CTkFont(family=MONO, size=12),
            border_width=0,
            corner_radius=6,
        )
        self.mode_toggle.pack(pady=(0, 14))

        # Download Button
        self.dl_button = ctk.CTkButton(
            self.main_frame, text="Download", width=440, height=42,
            font=ctk.CTkFont(family=MONO, size=14, weight="bold"),
            corner_radius=8,
            command=self._start_download,
        )
        self.dl_button.pack(pady=(0, 14))
        self.dl_button.configure(state="disabled")

        # Status Label
        self.status_label = ctk.CTkLabel(
            self.main_frame, text="",
            font=ctk.CTkFont(family=MONO, size=12),
        )
        self.status_label.pack(pady=(0, 6))

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(
            self.main_frame, width=440, height=5,
            corner_radius=3,
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 4))
        self.progress_bar.pack_forget()

        # Stats Row
        self.stats_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", width=440)
        self.stats_left = ctk.CTkLabel(
            self.stats_frame, text="",
            font=ctk.CTkFont(family=MONO, size=11),
        )
        self.stats_left.pack(side="left", padx=(0, 0))

        self.stats_center = ctk.CTkLabel(
            self.stats_frame, text="",
            font=ctk.CTkFont(family=MONO, size=11),
        )
        self.stats_center.pack(side="left", expand=True)

        self.stats_right = ctk.CTkLabel(
            self.stats_frame, text="",
            font=ctk.CTkFont(family=MONO, size=11),
        )
        self.stats_right.pack(side="right", padx=(0, 0))

        # --- Settings Panel (overlay, hidden) ---
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0)
        self._settings_visible = False
        self._build_settings()

        # Apply theme
        self._apply_theme()

        # Windows taskbar fix
        self.after(50, self._fix_taskbar)

        # Start polling
        self._poll_queue()

    # --- Title bar ---
    def _on_title_press(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_title_drag(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _minimize(self):
        self.overrideredirect(False)
        self.iconify()
        self.after(100, self._restore_override)

    def _restore_override(self):
        if self.state() == "iconic":
            self.after(100, self._restore_override)
            return
        self.overrideredirect(True)
        self._fix_taskbar()

    def _fix_taskbar(self):
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.withdraw()
            self.after(20, self.deiconify)
        except Exception:
            pass

    # --- Settings ---
    def _build_settings(self):
        f = self.settings_frame

        # Back button
        self.settings_back_btn = ctk.CTkButton(
            f, text="\u2190  Back", width=80, height=30,
            corner_radius=6, border_width=0,
            font=ctk.CTkFont(family=MONO, size=12),
            command=self._toggle_settings,
        )
        self.settings_back_btn.pack(anchor="w", padx=20, pady=(20, 20))

        # Theme section
        self.settings_theme_header = ctk.CTkLabel(
            f, text="THEME",
            font=ctk.CTkFont(family=MONO, size=10),
        )
        self.settings_theme_header.pack(anchor="w", padx=24, pady=(0, 8))

        self.theme_var = ctk.StringVar(
            value="Dark" if self.config.get("theme") == "dark" else "Glass"
        )
        self.theme_toggle = ctk.CTkSegmentedButton(
            f, values=["Dark", "Glass"],
            variable=self.theme_var,
            font=ctk.CTkFont(family=MONO, size=12),
            border_width=0, corner_radius=6,
            command=self._on_theme_change,
        )
        self.theme_toggle.pack(anchor="w", padx=24, pady=(0, 24))

        # Save location section
        self.settings_save_header = ctk.CTkLabel(
            f, text="SAVE LOCATION",
            font=ctk.CTkFont(family=MONO, size=10),
        )
        self.settings_save_header.pack(anchor="w", padx=24, pady=(0, 8))

        loc_frame = ctk.CTkFrame(f, fg_color="transparent")
        loc_frame.pack(anchor="w", padx=24, pady=(0, 24))

        self.save_dir_label = ctk.CTkLabel(
            loc_frame,
            text=self._short_path(self.config["save_dir"]),
            font=ctk.CTkFont(family=MONO, size=12),
        )
        self.save_dir_label.pack(side="left", padx=(0, 10))

        self.browse_btn = ctk.CTkButton(
            loc_frame, text="Browse", width=70, height=28,
            corner_radius=6, border_width=1,
            font=ctk.CTkFont(family=MONO, size=11),
            command=self._browse_folder,
        )
        self.browse_btn.pack(side="left")

        # yt-dlp section
        self.settings_ytdlp_header = ctk.CTkLabel(
            f, text="YT-DLP",
            font=ctk.CTkFont(family=MONO, size=10),
        )
        self.settings_ytdlp_header.pack(anchor="w", padx=24, pady=(0, 8))

        ytdlp_frame = ctk.CTkFrame(f, fg_color="transparent")
        ytdlp_frame.pack(anchor="w", padx=24, pady=(0, 10))

        self.ytdlp_ver_label = ctk.CTkLabel(
            ytdlp_frame,
            text=f"v{yt_dlp.version.__version__}",
            font=ctk.CTkFont(family=MONO, size=12),
        )
        self.ytdlp_ver_label.pack(side="left", padx=(0, 14))

        self.update_btn = ctk.CTkButton(
            ytdlp_frame, text="Update", width=70, height=28,
            corner_radius=6, border_width=1,
            font=ctk.CTkFont(family=MONO, size=11),
            command=self._update_ytdlp,
        )
        if getattr(sys, "frozen", False):
            self.update_btn.configure(state="disabled")
        self.update_btn.pack(side="left")

        self.update_status_label = ctk.CTkLabel(
            f, text="",
            font=ctk.CTkFont(family=MONO, size=11),
        )
        self.update_status_label.pack(anchor="w", padx=24, pady=(0, 10))

    def _toggle_settings(self):
        if self._settings_visible:
            self.settings_frame.place_forget()
            self._settings_visible = False
        else:
            self.settings_frame.place(x=0, y=37, relwidth=1, relheight=1)
            self._settings_visible = True

    def _on_theme_change(self, value):
        theme_key = "dark" if value == "Dark" else "glass"
        self.config["theme"] = theme_key
        save_config(self.config)
        self.theme = THEMES[theme_key]
        self._apply_theme()

    def _update_ytdlp(self):
        self.update_status_label.configure(text="updating...", text_color=self.theme["muted"])
        self.update_btn.configure(state="disabled")

        def worker():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    import importlib
                    importlib.reload(yt_dlp.version)
                    ver = yt_dlp.version.__version__
                    self.msg_queue.put(("update_done", ver))
                else:
                    self.msg_queue.put(("update_error", "update failed"))
            except Exception as e:
                self.msg_queue.put(("update_error", str(e)[:60]))

        threading.Thread(target=worker, daemon=True).start()

    # --- Theme ---
    def _apply_theme(self):
        t = self.theme

        # Window
        self.configure(fg_color=t["window_bg"])
        self.attributes("-alpha", t["alpha"])

        # Title bar
        self.title_bar.configure(fg_color=t["titlebar_bg"])
        self.title_label.configure(text_color=t["titlebar_text"])
        self.sep.configure(fg_color=t["separator"])

        for btn in (self.gear_btn, self.min_btn):
            btn.configure(
                fg_color="transparent", hover_color=t["btn_hover"],
                text_color=t["titlebar_text"],
            )
        self.close_btn.configure(
            fg_color="transparent", hover_color=t["close_hover"],
            text_color=t["titlebar_text"],
        )

        # Main content
        self.main_frame.configure(fg_color=t["window_bg"])
        self.app_title.configure(text_color=t["accent"])
        self.subtitle.configure(text_color=t["muted"])

        # Entry
        self.url_entry.configure(
            fg_color=t["card_bg"], border_color=t["border"],
            text_color=t["text"], placeholder_text_color=t["placeholder"],
        )

        # Mode toggle
        self.mode_toggle.configure(
            fg_color=t["card_bg"],
            selected_color=t["seg_selected"],
            selected_hover_color=t["seg_hover"],
            unselected_color=t["seg_unselected"],
            unselected_hover_color=t["seg_hover"],
            text_color=t["text"],
        )

        # Download button
        self.dl_button.configure(
            fg_color=t["accent"], hover_color=t["accent_hover"],
            text_color=t["accent_text"],
        )

        # Status
        self.status_label.configure(text_color=t["muted"])

        # Progress bar
        self.progress_bar.configure(
            fg_color=t["card_bg"], progress_color=t["accent"],
        )

        # Stats
        for lbl in (self.stats_left, self.stats_center, self.stats_right):
            lbl.configure(text_color=t["muted"])

        # Settings
        self.settings_frame.configure(fg_color=t["settings_bg"])
        self.settings_back_btn.configure(
            fg_color="transparent", hover_color=t["btn_hover"],
            text_color=t["text"],
        )
        for hdr in (self.settings_theme_header, self.settings_save_header, self.settings_ytdlp_header):
            hdr.configure(text_color=t["muted"])

        self.theme_toggle.configure(
            fg_color=t["card_bg"],
            selected_color=t["seg_selected"],
            selected_hover_color=t["seg_hover"],
            unselected_color=t["seg_unselected"],
            unselected_hover_color=t["seg_hover"],
            text_color=t["text"],
        )

        self.save_dir_label.configure(text_color=t["text"])
        self.browse_btn.configure(
            fg_color=t["card_bg"], hover_color=t["btn_hover"],
            border_color=t["border"], text_color=t["text"],
        )
        self.ytdlp_ver_label.configure(text_color=t["muted"])
        self.update_btn.configure(
            fg_color=t["card_bg"], hover_color=t["btn_hover"],
            border_color=t["border"], text_color=t["text"],
        )
        self.update_status_label.configure(text_color=t["muted"])

    # --- Helpers ---
    def _short_path(self, path):
        home = str(Path.home())
        if path.startswith(home):
            return "~" + path[len(home):]
        return path

    def _on_entry_focus(self, event):
        if not self.url_entry.get():
            try:
                text = self.clipboard_get()
                if "youtube.com" in text or "youtu.be" in text:
                    self.url_entry.insert(0, text)
                    self._on_input_change()
            except Exception:
                pass

    def _on_input_change(self, event=None):
        has_text = bool(self.url_entry.get().strip())
        if not self.downloading:
            self.dl_button.configure(state="normal" if has_text else "disabled")

    def _browse_folder(self):
        folder = ctk.filedialog.askdirectory(
            initialdir=self.config["save_dir"],
            title="Choose download folder",
        )
        if folder:
            self.config["save_dir"] = folder
            save_config(self.config)
            self.save_dir_label.configure(text=self._short_path(folder))

    # --- Download ---
    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url or self.downloading:
            return

        self.downloading = True
        self.dl_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 4))
        self.stats_frame.pack(pady=(0, 10))
        self.stats_left.configure(text="")
        self.stats_center.configure(text="")
        self.stats_right.configure(text="")

        mode_map = {"Video": "video", "Audio": "audio", "Thumbnail": "thumbnail"}
        mode = mode_map[self.mode_var.get()]

        status_map = {
            "video": "downloading video...",
            "audio": "downloading audio...",
            "thumbnail": "fetching thumbnail...",
        }
        self.status_label.configure(text=status_map[mode], text_color=self.theme["muted"])

        threading.Thread(
            target=self._download_worker, args=(url, mode), daemon=True,
        ).start()

    def _download_worker(self, url, mode):
        tmp_dir = tempfile.mkdtemp()
        try:
            def progress_hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    downloaded = d.get("downloaded_bytes", 0)
                    speed = d.get("speed")
                    eta = d.get("eta")
                    pct = downloaded / total if total > 0 else 0
                    self.msg_queue.put(("progress", {
                        "pct": pct,
                        "downloaded_mb": downloaded / (1024 * 1024),
                        "total_mb": total / (1024 * 1024) if total else 0,
                        "speed_mbps": speed / (1024 * 1024) if speed else 0,
                        "eta": eta,
                    }))
                elif d["status"] == "finished":
                    self.msg_queue.put(("progress", {"pct": 1.0, "finished": True}))
                    self.msg_queue.put(("status", "processing..."))

            if mode == "thumbnail":
                ydl_opts = {
                    "skip_download": True,
                    "writethumbnail": True,
                    "outtmpl": os.path.join(tmp_dir, "%(title).80s.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                }
            elif mode == "audio":
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(tmp_dir, "%(title).80s.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                    "progress_hooks": [progress_hook],
                }
            else:
                ydl_opts = {
                    "format": "best[ext=mp4]/best",
                    "outtmpl": os.path.join(tmp_dir, "%(title).80s.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                    "progress_hooks": [progress_hook],
                }

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "download")

            files = os.listdir(tmp_dir)
            if not files:
                self.msg_queue.put(("error", "Download failed — no file produced"))
                return

            src = os.path.join(tmp_dir, files[0])
            dst = os.path.join(self.config["save_dir"], files[0])

            base, ext = os.path.splitext(dst)
            counter = 1
            while os.path.exists(dst):
                dst = f"{base} ({counter}){ext}"
                counter += 1

            shutil.move(src, dst)
            self.msg_queue.put(("done", title))

        except Exception as e:
            err = str(e)
            if "ffmpeg" in err.lower() or "ffprobe" in err.lower():
                self.msg_queue.put(("error", "ffmpeg required for audio extraction"))
            else:
                self.msg_queue.put(("error", err))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "progress":
                    if isinstance(data, dict):
                        self.progress_bar.set(data["pct"])
                        if not data.get("finished"):
                            dl = data["downloaded_mb"]
                            total = data["total_mb"]
                            speed = data["speed_mbps"]
                            eta = data.get("eta")

                            self.stats_left.configure(
                                text=f"{dl:.1f} / {total:.1f} MB" if total > 0 else f"{dl:.1f} MB"
                            )
                            self.stats_center.configure(
                                text=f"{speed:.1f} MB/s" if speed > 0 else ""
                            )
                            if eta and eta > 0:
                                m, s = divmod(int(eta), 60)
                                self.stats_right.configure(text=f"ETA {m}:{s:02d}")
                            else:
                                self.stats_right.configure(text="")
                elif msg_type == "status":
                    self.status_label.configure(text=data, text_color=self.theme["muted"])
                elif msg_type == "done":
                    self.status_label.configure(
                        text=f"saved: {data}", text_color=self.theme["success"],
                    )
                    self.progress_bar.set(1.0)
                    self.stats_left.configure(text="")
                    self.stats_center.configure(text="")
                    self.stats_right.configure(text="")
                    self._finish_download()
                elif msg_type == "error":
                    self.status_label.configure(
                        text=data[:80], text_color=self.theme["error"],
                    )
                    self._finish_download()
                elif msg_type == "update_done":
                    self.ytdlp_ver_label.configure(text=f"v{data}")
                    self.update_status_label.configure(
                        text=f"updated to v{data}", text_color=self.theme["success"],
                    )
                    self.update_btn.configure(state="normal")
                elif msg_type == "update_error":
                    self.update_status_label.configure(
                        text=data, text_color=self.theme["error"],
                    )
                    self.update_btn.configure(state="normal")
        except Empty:
            pass
        self.after(100, self._poll_queue)

    def _finish_download(self):
        self.downloading = False
        has_text = bool(self.url_entry.get().strip())
        self.dl_button.configure(state="normal" if has_text else "disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
