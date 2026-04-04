import os
import sys
import json
import shutil
import tempfile
import threading
from queue import Queue, Empty
from pathlib import Path

import customtkinter as ctk
from yt_dlp import YoutubeDL

CONFIG_PATH = os.path.join(Path.home(), ".paste-to-config.json")


def load_config():
    defaults = {"save_dir": str(Path.home() / "Downloads")}
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            defaults.update(data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    os.makedirs(defaults["save_dir"], exist_ok=True)
    return defaults


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.msg_queue = Queue()
        self.downloading = False

        # Window setup
        self.title("paste.to")
        self.geometry("500x420")
        self.resizable(False, False)
        self.configure(fg_color="#0a0a0a")

        ctk.set_appearance_mode("dark")

        # --- Title ---
        ctk.CTkLabel(
            self, text="paste.to",
            font=ctk.CTkFont(size=28, weight="normal"),
            text_color="#ffffff",
        ).pack(pady=(40, 2))

        ctk.CTkLabel(
            self, text="paste a youtube link. get the file.",
            font=ctk.CTkFont(size=13),
            text_color="#666666",
        ).pack(pady=(0, 24))

        # --- URL Entry ---
        self.url_entry = ctk.CTkEntry(
            self, width=420, height=42,
            placeholder_text="https://youtube.com/watch?v=...",
            fg_color="#141414",
            border_color="#222222",
            text_color="#ffffff",
            placeholder_text_color="#444444",
            corner_radius=8,
            font=ctk.CTkFont(size=14),
        )
        self.url_entry.pack(pady=(0, 14))
        self.url_entry.bind("<FocusIn>", self._on_entry_focus)
        self.url_entry.bind("<KeyRelease>", self._on_input_change)
        self.url_entry.bind("<Return>", lambda e: self._start_download())

        # --- Mode Toggle ---
        self.mode_var = ctk.StringVar(value="Video")
        self.mode_toggle = ctk.CTkSegmentedButton(
            self, values=["Video", "Thumbnail"],
            variable=self.mode_var,
            font=ctk.CTkFont(size=13),
            fg_color="#141414",
            selected_color="#1a1a1a",
            selected_hover_color="#252525",
            unselected_color="#141414",
            unselected_hover_color="#1a1a1a",
            text_color="#ffffff",
            text_color_disabled="#666666",
            border_width=1,
            corner_radius=6,
        )
        self.mode_toggle.pack(pady=(0, 16))

        # --- Download Button ---
        self.dl_button = ctk.CTkButton(
            self, text="Download", width=420, height=42,
            fg_color="#ffffff",
            hover_color="#dddddd",
            text_color="#000000",
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            command=self._start_download,
        )
        self.dl_button.pack(pady=(0, 16))
        self.dl_button.configure(state="disabled")

        # --- Status Label ---
        self.status_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=13),
            text_color="#666666",
        )
        self.status_label.pack(pady=(0, 6))

        # --- Progress Bar ---
        self.progress_bar = ctk.CTkProgressBar(
            self, width=420, height=6,
            fg_color="#141414",
            progress_color="#ffffff",
            corner_radius=3,
        )
        self.progress_bar.pack(pady=(0, 20))
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()  # hidden initially

        # --- Save Location ---
        loc_frame = ctk.CTkFrame(self, fg_color="transparent")
        loc_frame.pack(pady=(0, 10))

        ctk.CTkLabel(
            loc_frame, text="Save to:",
            font=ctk.CTkFont(size=12),
            text_color="#555555",
        ).pack(side="left", padx=(0, 6))

        self.save_dir_label = ctk.CTkLabel(
            loc_frame,
            text=self._short_path(self.config["save_dir"]),
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.save_dir_label.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            loc_frame, text="Browse", width=60, height=26,
            fg_color="#1a1a1a",
            hover_color="#252525",
            border_color="#333333",
            border_width=1,
            text_color="#aaaaaa",
            font=ctk.CTkFont(size=11),
            corner_radius=6,
            command=self._browse_folder,
        ).pack(side="left")

        # Start polling
        self._poll_queue()

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

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url or self.downloading:
            return

        self.downloading = True
        self.dl_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 20))

        mode = "thumbnail" if self.mode_var.get() == "Thumbnail" else "video"
        self.status_label.configure(
            text="fetching thumbnail..." if mode == "thumbnail" else "downloading video...",
            text_color="#666666",
        )

        thread = threading.Thread(
            target=self._download_worker,
            args=(url, mode),
            daemon=True,
        )
        thread.start()

    def _download_worker(self, url, mode):
        tmp_dir = tempfile.mkdtemp()
        try:
            def progress_hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    downloaded = d.get("downloaded_bytes", 0)
                    if total > 0:
                        pct = downloaded / total
                        self.msg_queue.put(("progress", pct))
                elif d["status"] == "finished":
                    self.msg_queue.put(("progress", 1.0))
                    self.msg_queue.put(("status", "processing..."))

            if mode == "thumbnail":
                ydl_opts = {
                    "skip_download": True,
                    "writethumbnail": True,
                    "outtmpl": os.path.join(tmp_dir, "%(title).80s.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
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

            # Find downloaded file and move to save dir
            files = os.listdir(tmp_dir)
            if not files:
                self.msg_queue.put(("error", "Download failed — no file produced"))
                return

            src = os.path.join(tmp_dir, files[0])
            dst = os.path.join(self.config["save_dir"], files[0])

            # Avoid overwriting — append number if needed
            base, ext = os.path.splitext(dst)
            counter = 1
            while os.path.exists(dst):
                dst = f"{base} ({counter}){ext}"
                counter += 1

            shutil.move(src, dst)
            self.msg_queue.put(("done", title))

        except Exception as e:
            self.msg_queue.put(("error", str(e)))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "progress":
                    self.progress_bar.set(data)
                elif msg_type == "status":
                    self.status_label.configure(text=data, text_color="#666666")
                elif msg_type == "done":
                    self.status_label.configure(
                        text=f"saved: {data}",
                        text_color="#666666",
                    )
                    self.progress_bar.set(1.0)
                    self._finish_download()
                elif msg_type == "error":
                    self.status_label.configure(text=data[:80], text_color="#dd4444")
                    self._finish_download()
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
