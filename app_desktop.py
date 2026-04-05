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
MONO = "Consolas"

# ---------------------------------------------------------------------------
# ffmpeg auto-setup
# ---------------------------------------------------------------------------
FFMPEG_DIR = os.path.join(Path.home(), ".paste-to", "ffmpeg")

def _get_ffmpeg_path():
    """Return path to ffmpeg, downloading a portable copy if needed."""
    # Check if ffmpeg is already on PATH
    if shutil.which("ffmpeg"):
        return None  # yt-dlp will find it

    # Check our bundled copy
    if platform.system() == "Windows":
        local = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
    else:
        local = os.path.join(FFMPEG_DIR, "ffmpeg")

    if os.path.isfile(local):
        return FFMPEG_DIR

    return None

def _download_ffmpeg(msg_queue):
    """Download portable ffmpeg in background. Sends status via queue."""
    if platform.system() != "Windows":
        return
    os.makedirs(FFMPEG_DIR, exist_ok=True)
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = os.path.join(FFMPEG_DIR, "ffmpeg.zip")
    try:
        import urllib.request
        msg_queue.put(("ffmpeg_status", "downloading ffmpeg..."))
        urllib.request.urlretrieve(url, zip_path)
        msg_queue.put(("ffmpeg_status", "extracting ffmpeg..."))
        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                fname = os.path.basename(member)
                if fname in ("ffmpeg.exe", "ffprobe.exe"):
                    with zf.open(member) as src:
                        dst = os.path.join(FFMPEG_DIR, fname)
                        with open(dst, "wb") as out:
                            out.write(src.read())
        os.remove(zip_path)
        msg_queue.put(("ffmpeg_status", "ffmpeg ready"))
    except Exception as e:
        msg_queue.put(("ffmpeg_status", f"ffmpeg download failed: {str(e)[:50]}"))

# ---------------------------------------------------------------------------
# Quality / Format maps
# ---------------------------------------------------------------------------
QUALITY_MAP = {
    "Best":  "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
}

VIDEO_FORMATS  = ["MP4", "MKV", "WEBM"]
AUDIO_FORMATS  = ["MP3", "M4A", "OPUS"]
THUMB_FORMATS  = ["JPG", "PNG", "WEBP"]

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
DARK = {
    "name": "Dark", "alpha": 1.0,
    "window_bg":       "#0d0f14",
    "titlebar_bg":     "#090b10",
    "toolbar_bg":      "#111318",
    "toolbar_sep":     "#1e2130",
    "separator":       "#1e2130",
    "card_bg":         "#13151c",
    "border":          "#1e2130",
    "accent":          "#d4a843",
    "accent_hover":    "#c49a35",
    "accent_text":     "#0d0f14",
    "paste_btn":       "#2d8a4e",
    "paste_btn_hover": "#24703f",
    "paste_btn_text":  "#ffffff",
    "dropdown_bg":     "#13151c",
    "dropdown_hover":  "#1e2130",
    "dropdown_border": "#1e2130",
    "text":            "#e0e0e0",
    "muted":           "#555566",
    "placeholder":     "#3a3a4a",
    "error":           "#ff4455",
    "success":         "#44cc88",
    "close_hover":     "#ff4444",
    "btn_hover":       "#1e2130",
    "list_item_bg":    "#13151c",
    "list_item_alt":   "#0f1118",
    "list_sep":        "#1a1c24",
    "progress_track":  "#1e2130",
    "del_btn":         "#555566",
    "del_btn_hover":   "#ff4455",
    "settings_bg":     "#0d0f14",
    "titlebar_text":   "#555566",
    "seg_selected":    "#1e2130",
    "seg_unselected":  "#13151c",
    "seg_hover":       "#252840",
}

GLASS = {
    "name": "Glass", "alpha": 0.93,
    "window_bg":       "#e8e8ee",
    "titlebar_bg":     "#dddde4",
    "toolbar_bg":      "#e0e0e8",
    "toolbar_sep":     "#ccccdd",
    "separator":       "#ccccdd",
    "card_bg":         "#f4f4f8",
    "border":          "#ccccdd",
    "accent":          "#3a6fd8",
    "accent_hover":    "#2f5bb8",
    "accent_text":     "#ffffff",
    "paste_btn":       "#2d8a4e",
    "paste_btn_hover": "#24703f",
    "paste_btn_text":  "#ffffff",
    "dropdown_bg":     "#f0f0f6",
    "dropdown_hover":  "#e0e0ea",
    "dropdown_border": "#ccccdd",
    "text":            "#1a1a2e",
    "muted":           "#888899",
    "placeholder":     "#aaaabb",
    "error":           "#dd3344",
    "success":         "#22aa66",
    "close_hover":     "#ff4444",
    "btn_hover":       "#ccccdd",
    "list_item_bg":    "#f4f4f8",
    "list_item_alt":   "#ebebf2",
    "list_sep":        "#d8d8e4",
    "progress_track":  "#e0e0e8",
    "del_btn":         "#888899",
    "del_btn_hover":   "#dd3344",
    "settings_bg":     "#e8e8ee",
    "titlebar_text":   "#888899",
    "seg_selected":    "#ccccdd",
    "seg_unselected":  "#e0e0e8",
    "seg_hover":       "#d5d5de",
}

THEMES = {"dark": DARK, "glass": GLASS}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config():
    defaults = {
        "save_dir":     str(Path.home() / "Downloads"),
        "theme":        "dark",
        "mode":         "Video",
        "quality":      "1080p",
        "format_video": "MP4",
        "format_audio": "MP3",
    }
    try:
        with open(CONFIG_PATH) as f:
            defaults.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    os.makedirs(defaults["save_dir"], exist_ok=True)
    return defaults

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.msg_queue = Queue()
        self.download_items = {}
        self._next_id = 0
        self._drag_x = self._drag_y = 0
        self.theme = THEMES.get(self.cfg.get("theme", "dark"), DARK)
        self._settings_visible = False

        # Window
        self.overrideredirect(True)
        self.geometry("760x560")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"760x560+{(sw-760)//2}+{(sh-560)//2}")

        self._build_titlebar()
        self._build_toolbar()
        self._build_list()
        self._build_settings()
        self._apply_theme()
        self.after(50, self._fix_taskbar)
        self._poll_queue()

        # Auto-download ffmpeg if not available
        if not shutil.which("ffmpeg") and not os.path.isfile(
                os.path.join(FFMPEG_DIR, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")):
            threading.Thread(target=_download_ffmpeg, args=(self.msg_queue,), daemon=True).start()

    # ------------------------------------------------------------------ title bar
    def _build_titlebar(self):
        self.title_bar = ctk.CTkFrame(self, height=32, corner_radius=0)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)

        self.title_label = ctk.CTkLabel(
            self.title_bar, text="paste.to",
            font=ctk.CTkFont(family=MONO, size=12))
        self.title_label.pack(side="left", padx=12)

        self.close_btn = ctk.CTkButton(
            self.title_bar, text="×", width=32, height=32,
            corner_radius=0, border_width=0,
            font=ctk.CTkFont(size=15), command=self.destroy)
        self.close_btn.pack(side="right")

        self.min_btn = ctk.CTkButton(
            self.title_bar, text="−", width=32, height=32,
            corner_radius=0, border_width=0,
            font=ctk.CTkFont(size=15), command=self._minimize)
        self.min_btn.pack(side="right")

        for w in (self.title_bar, self.title_label):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        self.tb_sep = ctk.CTkFrame(self, height=1, corner_radius=0)
        self.tb_sep.pack(fill="x")

    # ------------------------------------------------------------------ toolbar
    def _build_toolbar(self):
        self.toolbar = ctk.CTkFrame(self, height=48, corner_radius=0)
        self.toolbar.pack(fill="x")
        self.toolbar.pack_propagate(False)

        # Paste Link
        self.paste_btn = ctk.CTkButton(
            self.toolbar, text="⏐ Paste Link", width=120, height=34,
            corner_radius=6, border_width=0,
            font=ctk.CTkFont(family=MONO, size=12, weight="bold"),
            command=self._paste_and_download)
        self.paste_btn.pack(side="left", padx=(10, 6), pady=7)

        self._vsep(self.toolbar)

        # Mode
        self.mode_var = ctk.StringVar(value=self.cfg.get("mode", "Video"))
        self.mode_menu = self._option_menu(
            self.toolbar, self.mode_var, ["Video", "Audio", "Thumbnail"], 115,
            command=self._on_mode_change)
        self.mode_menu.pack(side="left", padx=3, pady=7)

        # Quality
        self.quality_var = ctk.StringVar(value=self.cfg.get("quality", "1080p"))
        self.quality_menu = self._option_menu(
            self.toolbar, self.quality_var, ["Best", "1080p", "720p", "480p"], 95)
        self.quality_menu.pack(side="left", padx=3, pady=7)

        # Format
        self.format_var = ctk.StringVar(value=self.cfg.get("format_video", "MP4"))
        self.format_menu = self._option_menu(
            self.toolbar, self.format_var, VIDEO_FORMATS, 85)
        self.format_menu.pack(side="left", padx=3, pady=7)

        self._vsep(self.toolbar)

        # Save to
        folder = os.path.basename(self.cfg["save_dir"]) or self.cfg["save_dir"]
        self.save_btn = ctk.CTkButton(
            self.toolbar, text=f"  {folder}", height=34,
            corner_radius=6, border_width=0, anchor="w",
            font=ctk.CTkFont(family=MONO, size=11),
            command=self._browse_folder)
        self.save_btn.pack(side="left", padx=3, pady=7)

        # Gear (right)
        self.gear_btn = ctk.CTkButton(
            self.toolbar, text="⚙", width=36, height=34,
            corner_radius=6, border_width=0,
            font=ctk.CTkFont(size=15),
            command=self._toggle_settings)
        self.gear_btn.pack(side="right", padx=(3, 10), pady=7)

        self.toolbar_sep = ctk.CTkFrame(self, height=1, corner_radius=0)
        self.toolbar_sep.pack(fill="x")

    def _option_menu(self, parent, var, values, width, command=None):
        kw = {}
        if command:
            kw["command"] = command
        return ctk.CTkOptionMenu(
            parent, variable=var, values=values,
            width=width, height=34, corner_radius=6,
            font=ctk.CTkFont(family=MONO, size=11),
            **kw)

    def _vsep(self, parent):
        ctk.CTkFrame(parent, width=1, height=30, corner_radius=0).pack(
            side="left", padx=5, pady=9)

    # ------------------------------------------------------------------ list
    def _build_list(self):
        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=0, border_width=0)
        self.list_frame.pack(fill="both", expand=True)

        self.empty_label = ctk.CTkLabel(
            self.list_frame,
            text="copy a YouTube link, then click  Paste Link",
            font=ctk.CTkFont(family=MONO, size=13))
        self.empty_label.pack(pady=100)

    # ------------------------------------------------------------------ settings
    def _build_settings(self):
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0)

        self.settings_back = ctk.CTkButton(
            self.settings_frame, text="← Back", width=80, height=28,
            corner_radius=6, border_width=0,
            font=ctk.CTkFont(family=MONO, size=12),
            command=self._toggle_settings)
        self.settings_back.pack(anchor="w", padx=18, pady=(16, 12))

        # Theme
        self._settings_section("THEME")
        self.theme_var = ctk.StringVar(
            value="Dark" if self.cfg.get("theme") == "dark" else "Glass")
        self.theme_toggle = ctk.CTkSegmentedButton(
            self.settings_frame, values=["Dark", "Glass"],
            variable=self.theme_var,
            font=ctk.CTkFont(family=MONO, size=12),
            border_width=0, corner_radius=6,
            command=self._on_theme_change)
        self.theme_toggle.pack(anchor="w", padx=22, pady=(0, 18))

        # Save location
        self._settings_section("SAVE LOCATION")
        loc_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        loc_row.pack(anchor="w", padx=22, pady=(0, 18))
        self.save_dir_label = ctk.CTkLabel(
            loc_row, text=self._short(self.cfg["save_dir"]),
            font=ctk.CTkFont(family=MONO, size=12))
        self.save_dir_label.pack(side="left", padx=(0, 10))
        self.browse_btn = ctk.CTkButton(
            loc_row, text="Browse", width=72, height=28,
            corner_radius=6, border_width=1,
            font=ctk.CTkFont(family=MONO, size=11),
            command=self._browse_folder)
        self.browse_btn.pack(side="left")

        # yt-dlp
        self._settings_section("YT-DLP")
        ytdlp_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        ytdlp_row.pack(anchor="w", padx=22, pady=(0, 6))
        self.ytdlp_ver = ctk.CTkLabel(
            ytdlp_row, text=f"v{yt_dlp.version.__version__}",
            font=ctk.CTkFont(family=MONO, size=12))
        self.ytdlp_ver.pack(side="left", padx=(0, 12))
        self.update_btn = ctk.CTkButton(
            ytdlp_row, text="Update", width=72, height=28,
            corner_radius=6, border_width=1,
            font=ctk.CTkFont(family=MONO, size=11),
            command=self._update_ytdlp)
        if getattr(sys, "frozen", False):
            self.update_btn.configure(state="disabled")
        self.update_btn.pack(side="left")
        self.update_status = ctk.CTkLabel(
            self.settings_frame, text="",
            font=ctk.CTkFont(family=MONO, size=11))
        self.update_status.pack(anchor="w", padx=22)

    def _settings_section(self, text):
        ctk.CTkLabel(
            self.settings_frame, text=text,
            font=ctk.CTkFont(family=MONO, size=10)).pack(
            anchor="w", padx=22, pady=(0, 6))

    # ------------------------------------------------------------------ item row
    def _create_item_row(self, item_id):
        item = self.download_items[item_id]
        t = self.theme
        self.empty_label.pack_forget()

        row = ctk.CTkFrame(self.list_frame, height=64, corner_radius=0)
        row.pack(fill="x")
        row.pack_propagate(False)

        # separator line
        sep = ctk.CTkFrame(row, height=1, corner_radius=0)
        sep.pack(fill="x", side="bottom")

        # Icon
        icons = {"video": "▶", "audio": "♪", "thumbnail": "▣"}
        colors = {"video": "#3a5fd8", "audio": "#d4a843", "thumbnail": "#2d8a4e"}
        mode = item["mode"]
        icon = ctk.CTkLabel(
            row, text=icons.get(mode, "▶"), width=44, height=44,
            corner_radius=6,
            font=ctk.CTkFont(size=17),
            fg_color=colors.get(mode, "#3a5fd8"),
            text_color="#ffffff")
        icon.pack(side="left", padx=(10, 10), pady=10)

        # Center
        center = ctk.CTkFrame(row, fg_color="transparent")
        center.pack(side="left", fill="both", expand=True, pady=8)

        title_lbl = ctk.CTkLabel(
            center, text=item["title"],
            font=ctk.CTkFont(family=MONO, size=12, weight="bold"),
            anchor="w", justify="left")
        title_lbl.pack(fill="x", anchor="w")

        meta_lbl = ctk.CTkLabel(
            center, text=self._fmt_meta(item),
            font=ctk.CTkFont(family=MONO, size=10),
            anchor="w")
        meta_lbl.pack(fill="x", anchor="w", pady=(1, 0))

        prog = ctk.CTkProgressBar(center, height=3, corner_radius=2)
        prog.set(0)
        prog.pack(fill="x", pady=(4, 0))

        # Right
        right = ctk.CTkFrame(row, fg_color="transparent", width=54)
        right.pack(side="right", padx=(0, 8), pady=10)
        right.pack_propagate(False)

        status_lbl = ctk.CTkLabel(
            right, text="",
            font=ctk.CTkFont(family=MONO, size=10))
        status_lbl.pack(anchor="e")

        del_btn = ctk.CTkButton(
            right, text="×", width=24, height=24,
            corner_radius=4, border_width=0,
            font=ctk.CTkFont(size=14),
            command=lambda iid=item_id: self._delete_item(iid))
        del_btn.pack(anchor="e", pady=(3, 0))

        item.update({
            "frame": row, "sep": sep,
            "title_label": title_lbl, "meta_label": meta_lbl,
            "progress_bar": prog, "status_label": status_lbl,
            "delete_btn": del_btn, "icon_label": icon,
        })
        self._theme_item(item)

    def _fmt_meta(self, item):
        parts = []
        if item.get("size_mb"):
            parts.append(f"{item['size_mb']:.1f} MB")
        fmt = item.get("format", "")
        if fmt:
            parts.append(fmt.upper())
        qual = item.get("quality", "")
        if qual and item["mode"] == "video":
            parts.append(qual)
        if item["status"] == "downloading":
            if item.get("speed_mbps"):
                parts.append(f"{item['speed_mbps']:.1f} MB/s")
            if item.get("eta"):
                m, s = divmod(int(item["eta"]), 60)
                parts.append(f"ETA {m}:{s:02d}")
        return "  ·  ".join(parts) if parts else item.get("mode", "")

    # ------------------------------------------------------------------ theme
    def _apply_theme(self):
        t = self.theme
        self.configure(fg_color=t["window_bg"])
        self.attributes("-alpha", t["alpha"])

        # Title bar
        self.title_bar.configure(fg_color=t["titlebar_bg"])
        self.title_label.configure(text_color=t["titlebar_text"])
        self.tb_sep.configure(fg_color=t["separator"])
        self.close_btn.configure(fg_color="transparent",
            hover_color=t["close_hover"], text_color=t["titlebar_text"])
        self.min_btn.configure(fg_color="transparent",
            hover_color=t["btn_hover"], text_color=t["titlebar_text"])

        # Toolbar
        self.toolbar.configure(fg_color=t["toolbar_bg"])
        self.toolbar_sep.configure(fg_color=t["toolbar_sep"])
        self.paste_btn.configure(fg_color=t["paste_btn"],
            hover_color=t["paste_btn_hover"], text_color=t["paste_btn_text"])
        for menu in (self.mode_menu, self.quality_menu, self.format_menu):
            menu.configure(fg_color=t["dropdown_bg"],
                button_color=t["dropdown_bg"],
                button_hover_color=t["dropdown_hover"],
                text_color=t["text"],
                dropdown_fg_color=t["dropdown_bg"],
                dropdown_hover_color=t["dropdown_hover"],
                dropdown_text_color=t["text"])
        self.save_btn.configure(fg_color="transparent",
            hover_color=t["btn_hover"], text_color=t["muted"])
        self.gear_btn.configure(fg_color="transparent",
            hover_color=t["btn_hover"], text_color=t["muted"])

        # List
        self.list_frame.configure(fg_color=t["window_bg"],
            scrollbar_button_color=t["toolbar_sep"],
            scrollbar_button_hover_color=t["btn_hover"])
        self.empty_label.configure(text_color=t["muted"])

        for item in self.download_items.values():
            self._theme_item(item)

        # Settings
        self.settings_frame.configure(fg_color=t["settings_bg"])
        self.settings_back.configure(fg_color="transparent",
            hover_color=t["btn_hover"], text_color=t["text"])
        self.theme_toggle.configure(
            fg_color=t["card_bg"],
            selected_color=t["seg_selected"],
            selected_hover_color=t["seg_hover"],
            unselected_color=t["seg_unselected"],
            unselected_hover_color=t["seg_hover"],
            text_color=t["text"])
        self.save_dir_label.configure(text_color=t["text"])
        self.browse_btn.configure(fg_color=t["card_bg"],
            hover_color=t["btn_hover"], border_color=t["border"],
            text_color=t["text"])
        self.ytdlp_ver.configure(text_color=t["muted"])
        self.update_btn.configure(fg_color=t["card_bg"],
            hover_color=t["btn_hover"], border_color=t["border"],
            text_color=t["text"])
        self.update_status.configure(text_color=t["muted"])

    def _theme_item(self, item):
        t = self.theme
        item["frame"].configure(fg_color=t["list_item_bg"])
        item["sep"].configure(fg_color=t["list_sep"])
        item["title_label"].configure(text_color=t["text"])
        item["meta_label"].configure(text_color=t["muted"])
        item["progress_bar"].configure(fg_color=t["progress_track"],
            progress_color=t["accent"])
        item["delete_btn"].configure(fg_color="transparent",
            hover_color=t["del_btn_hover"], text_color=t["del_btn"])
        if item["status"] == "error":
            item["status_label"].configure(text_color=t["error"])
        elif item["status"] == "done":
            item["status_label"].configure(text_color=t["success"])
        else:
            item["status_label"].configure(text_color=t["muted"])

    # ------------------------------------------------------------------ helpers
    def _short(self, path):
        h = str(Path.home())
        return "~" + path[len(h):] if path.startswith(h) else path

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        self.geometry(f"+{self.winfo_x()+e.x-self._drag_x}+{self.winfo_y()+e.y-self._drag_y}")

    def _minimize(self):
        self.overrideredirect(False)
        self.iconify()
        self.after(200, self._restore_override)

    def _restore_override(self):
        if self.state() == "iconic":
            self.after(200, self._restore_override)
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

    def _toggle_settings(self):
        if self._settings_visible:
            self.settings_frame.place_forget()
            self._settings_visible = False
        else:
            self.settings_frame.place(x=0, y=33, relwidth=1, relheight=1)
            self._settings_visible = True

    def _on_theme_change(self, value):
        key = "dark" if value == "Dark" else "glass"
        self.cfg["theme"] = key
        save_config(self.cfg)
        self.theme = THEMES[key]
        self._apply_theme()

    def _on_mode_change(self, value):
        self.cfg["mode"] = value
        save_config(self.cfg)
        if value == "Video":
            self.format_menu.configure(values=VIDEO_FORMATS)
            self.format_var.set(self.cfg.get("format_video", "MP4"))
            self.quality_menu.configure(state="normal")
        elif value == "Audio":
            self.format_menu.configure(values=AUDIO_FORMATS)
            self.format_var.set(self.cfg.get("format_audio", "MP3"))
            self.quality_menu.configure(state="disabled")
        else:
            self.format_menu.configure(values=THUMB_FORMATS)
            self.format_var.set("JPG")
            self.quality_menu.configure(state="disabled")

    def _browse_folder(self):
        folder = ctk.filedialog.askdirectory(
            initialdir=self.cfg["save_dir"], title="Choose download folder")
        if folder:
            self.cfg["save_dir"] = folder
            save_config(self.cfg)
            name = os.path.basename(folder) or folder
            self.save_btn.configure(text=f"  {name}")
            if hasattr(self, "save_dir_label"):
                self.save_dir_label.configure(text=self._short(folder))

    def _delete_item(self, item_id):
        item = self.download_items.pop(item_id, None)
        if item:
            item["frame"].destroy()
        if not self.download_items:
            self.empty_label.pack(pady=100)

    # ------------------------------------------------------------------ download
    def _paste_and_download(self):
        try:
            url = self.clipboard_get().strip()
        except Exception:
            return
        if not url or not ("youtube" in url or "youtu.be" in url or url.startswith("http")):
            return

        mode_map = {"Video": "video", "Audio": "audio", "Thumbnail": "thumbnail"}
        mode = mode_map.get(self.mode_var.get(), "video")
        quality = self.quality_var.get()
        fmt = self.format_var.get()

        item_id = self._next_id
        self._next_id += 1

        self.download_items[item_id] = {
            "id": item_id, "url": url, "title": "Fetching...",
            "status": "queued", "progress": 0.0,
            "size_mb": 0, "speed_mbps": 0, "eta": None,
            "mode": mode, "quality": quality, "format": fmt,
            "file_path": None, "error_msg": None,
        }
        self._create_item_row(item_id)
        threading.Thread(
            target=self._download_worker, args=(item_id,), daemon=True).start()

    def _build_ydl_opts(self, mode, quality, fmt, tmp_dir, hook):
        opts = {
            "outtmpl": os.path.join(tmp_dir, "%(title).80s.%(ext)s"),
            "quiet": True, "no_warnings": True,
        }
        # Point yt-dlp to our bundled ffmpeg if system ffmpeg not found
        ffmpeg_loc = _get_ffmpeg_path()
        if ffmpeg_loc:
            opts["ffmpeg_location"] = ffmpeg_loc

        if mode == "thumbnail":
            opts["skip_download"] = True
            opts["writethumbnail"] = True
            return opts

        opts["progress_hooks"] = [hook]

        if mode == "audio":
            opts["format"] = "bestaudio/best"
            codec = {"MP3": "mp3", "M4A": "m4a", "OPUS": "opus"}.get(fmt.upper(), "mp3")
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": "192",
            }]
        else:
            opts["format"] = QUALITY_MAP.get(quality, QUALITY_MAP["Best"])
            merge = {"MP4": "mp4", "MKV": "mkv", "WEBM": "webm"}.get(fmt.upper(), "mp4")
            opts["merge_output_format"] = merge
        return opts

    def _download_worker(self, item_id):
        item = self.download_items.get(item_id)
        if not item:
            return
        tmp = tempfile.mkdtemp()
        try:
            def hook(d):
                if not self.download_items.get(item_id):
                    return
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    dl = d.get("downloaded_bytes", 0)
                    self.msg_queue.put(("item_progress", item_id, {
                        "pct": dl / total if total else 0,
                        "downloaded_mb": dl / 1048576,
                        "total_mb": total / 1048576 if total else 0,
                        "speed_mbps": (d.get("speed") or 0) / 1048576,
                        "eta": d.get("eta"),
                    }))
                elif d["status"] == "finished":
                    self.msg_queue.put(("item_progress", item_id,
                        {"pct": 1.0, "finished": True}))
                    self.msg_queue.put(("item_status", item_id, "processing"))

            opts = self._build_ydl_opts(
                item["mode"], item["quality"], item["format"], tmp, hook)

            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(item["url"], download=True)
                title = info.get("title", "download")

            self.msg_queue.put(("item_title", item_id, title))

            files = os.listdir(tmp)
            if not files:
                self.msg_queue.put(("item_error", item_id, "no file produced"))
                return

            src = os.path.join(tmp, files[0])
            dst = os.path.join(self.cfg["save_dir"], files[0])
            base, ext = os.path.splitext(dst)
            n = 1
            while os.path.exists(dst):
                dst = f"{base} ({n}){ext}"; n += 1
            shutil.move(src, dst)
            self.msg_queue.put(("item_done", item_id, dst))

        except Exception as e:
            err = str(e)
            if "ffmpeg" in err.lower():
                err = "ffmpeg required for audio extraction"
            self.msg_queue.put(("item_error", item_id, err[:90]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------ poll
    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                mtype = msg[0]

                if mtype == "item_progress":
                    _, iid, data = msg
                    item = self.download_items.get(iid)
                    if not item:
                        continue
                    item["status"] = "downloading"
                    item["progress"] = data["pct"]
                    if not data.get("finished"):
                        item["size_mb"] = data.get("total_mb", 0)
                        item["speed_mbps"] = data.get("speed_mbps", 0)
                        item["eta"] = data.get("eta")
                    item["progress_bar"].set(data["pct"])
                    item["meta_label"].configure(text=self._fmt_meta(item))
                    pct_int = int(data["pct"] * 100)
                    item["status_label"].configure(
                        text=f"{pct_int}%", text_color=self.theme["muted"])

                elif mtype == "item_status":
                    _, iid, status = msg
                    item = self.download_items.get(iid)
                    if item:
                        item["status"] = status
                        item["status_label"].configure(
                            text="...", text_color=self.theme["muted"])

                elif mtype == "item_title":
                    _, iid, title = msg
                    item = self.download_items.get(iid)
                    if item:
                        item["title"] = title
                        item["title_label"].configure(text=title)

                elif mtype == "item_done":
                    _, iid, fpath = msg
                    item = self.download_items.get(iid)
                    if item:
                        item["status"] = "done"
                        item["file_path"] = fpath
                        item["speed_mbps"] = 0
                        item["eta"] = None
                        item["progress_bar"].set(1.0)
                        item["progress_bar"].pack_forget()
                        item["meta_label"].configure(text=self._fmt_meta(item))
                        item["status_label"].configure(
                            text="✓", text_color=self.theme["success"])

                elif mtype == "item_error":
                    _, iid, err = msg
                    item = self.download_items.get(iid)
                    if item:
                        item["status"] = "error"
                        item["error_msg"] = err
                        item["progress_bar"].pack_forget()
                        item["meta_label"].configure(text=err)
                        item["status_label"].configure(
                            text="✗", text_color=self.theme["error"])
                        item["meta_label"].configure(text_color=self.theme["error"])

                elif mtype == "update_done":
                    self.ytdlp_ver.configure(text=f"v{msg[1]}")
                    self.update_status.configure(
                        text=f"updated  v{msg[1]}", text_color=self.theme["success"])
                    self.update_btn.configure(state="normal")

                elif mtype == "update_error":
                    self.update_status.configure(
                        text=msg[1], text_color=self.theme["error"])
                    self.update_btn.configure(state="normal")

                elif mtype == "ffmpeg_status":
                    pass  # silent background download

        except Empty:
            pass
        self.after(100, self._poll_queue)

    # ------------------------------------------------------------------ yt-dlp update
    def _update_ytdlp(self):
        self.update_status.configure(
            text="updating...", text_color=self.theme["muted"])
        self.update_btn.configure(state="disabled")

        def worker():
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                    capture_output=True, text=True, timeout=60)
                if r.returncode == 0:
                    import importlib
                    importlib.reload(yt_dlp.version)
                    self.msg_queue.put(("update_done", yt_dlp.version.__version__))
                else:
                    self.msg_queue.put(("update_error", "update failed"))
            except Exception as e:
                self.msg_queue.put(("update_error", str(e)[:60]))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
