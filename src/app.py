"""CustomTkinter user interface for HyprWall."""

from __future__ import annotations

import queue
import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from tkinter import Menu, TclError, filedialog, messagebox, simpledialog
from typing import Callable

from PIL import Image

from .autostart import cleanup_legacy_service, disable, install_and_enable
from .config import APP_ICON, APP_NAME, DEFAULT_ROTATION_MINUTES, MEDIA_EXTENSIONS, MIN_ROTATION_MINUTES, WALLPAPER_DIR
from .dependencies import LinuxDependencies
from .i18n import Translator
from .media import MediaKind, classify_media
from .rotation_config import read_config as read_rotation_config, write_config as write_rotation_config
from .wallpaper import HyprlandWallpaper


class WallpaperApp:
    """Build and manage the desktop application window."""

    def __init__(self, ctk: object, translator: Translator) -> None:
        self.ctk = ctk
        self.translator = translator
        self.window = ctk.CTk()
        self.window.geometry("1080x760")
        self.window.minsize(850, 620)
        self.window.configure(fg_color="#0b1220")
        self._set_window_icon()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.dependencies = LinuxDependencies(self.log, self.t)
        self.wallpaper = HyprlandWallpaper(self.log, self.t)
        self.selected_path = ctk.StringVar()
        self.url = ctk.StringVar()
        self.language_value = ctk.StringVar(value="Tiếng Việt" if translator.language == "vi" else "English")
        self.status = ctk.StringVar(value=self.t("ready"))
        self.busy = False
        self.log_history: list[str] = []
        self.library_paths: list[Path] = []
        self.rotation_enabled = ctk.BooleanVar(value=False)
        self.rotation_interval = ctk.StringVar(value=str(DEFAULT_ROTATION_MINUTES))
        saved_rotation = read_rotation_config()
        self.rotation_enabled.set(saved_rotation["enabled"])
        self.rotation_interval.set(str(saved_rotation["fallback_minutes"]))
        WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
        cleanup_legacy_service(self.log)
        if self.rotation_enabled.get():
            install_and_enable(self.log)
        self._build_ui()
        self.refresh_library()
        self.window.after(100, self._process_events)

    def _set_window_icon(self) -> None:
        """Use the bundled ICO file when the current Tk window manager supports it."""
        if not APP_ICON.is_file():
            return
        try:
            self.window.iconbitmap(str(APP_ICON))
        except TclError:
            # Some Linux Tk/window-manager combinations cannot read ICO files.
            # The application remains usable while Windows and supported WMs use it.
            pass

    def t(self, key: str, **values: object) -> str:
        return self.translator.t(key, **values)

    def _build_ui(self) -> None:
        ctk = self.ctk
        for child in self.window.winfo_children():
            child.destroy()
        self.window.title(self.t("title"))

        shell = ctk.CTkFrame(self.window, corner_radius=0, fg_color="#0b1220")
        shell.pack(fill="both", expand=True)
        sidebar = ctk.CTkFrame(shell, width=248, corner_radius=0, fg_color="#101a2d")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(28, 26))
        brand_mark = self._brand_mark(brand)
        brand_mark.pack(side="left")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=12)
        ctk.CTkLabel(brand_text, text="HyprWall", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_text, text="LINUX  ·  HYPRLAND", text_color="#7d9ac7", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", pady=(1, 0))

        nav_label = ctk.CTkLabel(sidebar, text=self.t("workspace"), text_color="#6f83a6", font=ctk.CTkFont(size=11, weight="bold"))
        nav_label.pack(anchor="w", padx=26, pady=(4, 8))
        active_nav = ctk.CTkFrame(sidebar, height=46, corner_radius=12, fg_color="#1c3152")
        active_nav.pack(fill="x", padx=16)
        ctk.CTkLabel(active_nav, text="◈", width=38, text_color="#77adff", font=ctk.CTkFont(size=17)).pack(side="left")
        ctk.CTkLabel(active_nav, text=self.t("wallpaper"), font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        support = ctk.CTkFrame(sidebar, corner_radius=16, fg_color="#15233b")
        support.pack(fill="x", padx=16, pady=(24, 0))
        ctk.CTkLabel(support, text=self.t("hyprland_ready"), text_color="#87b9ff", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(13, 4))
        ctk.CTkLabel(support, text=self.t("note"), wraplength=180, justify="left", text_color="#b3c0d8", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14, pady=(0, 13))

        language_panel = ctk.CTkFrame(sidebar, corner_radius=14, fg_color="#15233b")
        language_panel.pack(side="bottom", fill="x", padx=16, pady=20)
        ctk.CTkLabel(language_panel, text=self.t("language"), text_color="#b3c0d8", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(12, 5))
        language_menu = ctk.CTkOptionMenu(
            language_panel,
            values=["Tiếng Việt", "English"],
            variable=self.language_value,
            command=self.change_language,
            fg_color="#253d63",
            button_color="#3b82f6",
            button_hover_color="#2563eb",
        )
        language_menu.pack(fill="x", padx=12, pady=(0, 12))

        main = ctk.CTkScrollableFrame(shell, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=30, pady=26)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x")

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text=self.t("dashboard"), font=ctk.CTkFont(size=27, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text=self.t("library_path", path=WALLPAPER_DIR), text_color="#8091af", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(2, 0))
        status_pill = ctk.CTkFrame(header, corner_radius=14, fg_color="#133625")
        status_pill.pack(side="right", pady=4)
        ctk.CTkLabel(status_pill, text="●", text_color="#6ee7a0", font=ctk.CTkFont(size=12)).pack(side="left", padx=(12, 5), pady=7)
        ctk.CTkLabel(status_pill, textvariable=self.status, text_color="#9df2bd", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 12), pady=7)

        hero = ctk.CTkFrame(main, corner_radius=20, fg_color="#152c4c")
        hero.pack(fill="x", pady=(24, 16))
        hero_text = ctk.CTkFrame(hero, fg_color="transparent")
        hero_text.pack(side="left", fill="both", expand=True, padx=22, pady=18)
        ctk.CTkLabel(hero_text, text=self.t("hero_eyebrow"), text_color="#8bb9ff", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(hero_text, text=self.t("hero_title"), font=ctk.CTkFont(size=19, weight="bold")).pack(anchor="w", pady=(3, 2))
        ctk.CTkLabel(hero_text, text=self.t("hero_description"), text_color="#b5c8e5", font=ctk.CTkFont(size=12), wraplength=530, justify="left").pack(anchor="w")
        ctk.CTkButton(hero, text=self.t("open_folder"), height=35, width=130, corner_radius=10, fg_color="#285d9d", hover_color="#3674bd", command=self.open_library).pack(side="right", padx=20, pady=20)

        selection = ctk.CTkFrame(main, corner_radius=18, fg_color="#111d30")
        selection.pack(fill="x")
        selection.columnconfigure(0, weight=1)
        selection_header = ctk.CTkFrame(selection, fg_color="transparent")
        selection_header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=(17, 8))
        ctk.CTkLabel(selection_header, text=self.t("current_selection"), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(selection_header, text=self.t("selection_help"), text_color="#8192ae", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 0))
        self.selected_entry = ctk.CTkEntry(selection, textvariable=self.selected_path, placeholder_text=str(WALLPAPER_DIR), height=40, border_color="#294464", fg_color="#0d1728", state="readonly")
        self.selected_entry.grid(row=1, column=0, sticky="ew", padx=(20, 8), pady=(0, 16))
        ctk.CTkButton(selection, text=self.t("choose"), width=105, height=40, corner_radius=10, fg_color="#273b5c", hover_color="#365378", command=self.choose_file).grid(row=1, column=1, padx=4, pady=(0, 16))
        ctk.CTkButton(selection, text=self.t("add"), width=125, height=40, corner_radius=10, fg_color="#273b5c", hover_color="#365378", command=self.copy_to_library).grid(row=1, column=2, padx=(4, 20), pady=(0, 16))
        ctk.CTkButton(selection, text="✦  " + self.t("set"), height=43, corner_radius=11, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=13, weight="bold"), command=self.set_selected).grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(0, 20))

        library = ctk.CTkFrame(main, corner_radius=18, fg_color="#111d30")
        library.pack(fill="both", expand=True, pady=(16, 0))
        library_header = ctk.CTkFrame(library, fg_color="transparent")
        library_header.pack(fill="x", padx=20, pady=(17, 8))
        library_title = ctk.CTkFrame(library_header, fg_color="transparent")
        library_title.pack(side="left")
        ctk.CTkLabel(library_title, text=self.t("library"), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        self.library_count = ctk.CTkLabel(library_title, text="", text_color="#8192ae", font=ctk.CTkFont(size=11))
        self.library_count.pack(anchor="w", pady=(1, 0))
        ctk.CTkButton(library_header, text="↻  " + self.t("refresh"), width=108, height=32, corner_radius=9, fg_color="#273b5c", hover_color="#365378", command=self.refresh_library).pack(side="right")
        self.library_list = ctk.CTkScrollableFrame(library, height=180, corner_radius=12, fg_color="#0d1728")
        self.library_list.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        rotation = ctk.CTkFrame(main, corner_radius=18, fg_color="#111d30")
        rotation.pack(fill="x", pady=(16, 0))
        rotation.columnconfigure(0, weight=1)
        ctk.CTkLabel(rotation, text=self.t("rotation"), font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(17, 2))
        ctk.CTkLabel(rotation, text=self.t("rotation_help"), text_color="#8192ae", font=ctk.CTkFont(size=11), wraplength=560, justify="left").grid(row=1, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 9))
        ctk.CTkSwitch(rotation, text=self.t("rotation_enable"), variable=self.rotation_enabled, onvalue=True, offvalue=False, command=self.toggle_rotation, progress_color="#2563eb").grid(row=2, column=0, sticky="w", padx=20, pady=(0, 18))
        rotation_entry = ctk.CTkEntry(rotation, textvariable=self.rotation_interval, width=70, height=36, border_color="#294464", fg_color="#0d1728")
        self._bind_edit_shortcuts(rotation_entry)
        rotation_entry.grid(row=2, column=1, padx=(0, 6), pady=(0, 18))
        ctk.CTkLabel(rotation, text=self.t("minutes")).grid(row=2, column=2, sticky="w", padx=(0, 20), pady=(0, 18))

        download = ctk.CTkFrame(main, corner_radius=18, fg_color="#111d30")
        download.pack(fill="x", pady=(16, 0))
        download.columnconfigure(0, weight=1)
        ctk.CTkLabel(download, text=self.t("download"), font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(17, 2))
        ctk.CTkLabel(download, text=self.t("download_help"), text_color="#8192ae", font=ctk.CTkFont(size=11)).grid(row=1, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 9))
        self.url_entry = ctk.CTkEntry(download, textvariable=self.url, placeholder_text="https://...", height=39, border_color="#294464", fg_color="#0d1728")
        self._bind_edit_shortcuts(self.url_entry)
        self.url_entry.grid(row=2, column=0, sticky="ew", padx=(20, 8), pady=(0, 18))
        ctk.CTkButton(download, text=self.t("download_button"), width=158, height=39, corner_radius=10, fg_color="#273b5c", hover_color="#365378", command=self.download_wallpaper).grid(row=2, column=1, padx=(0, 20), pady=(0, 18))

        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.pack(fill="x", pady=(15, 0))
        ctk.CTkLabel(footer, text=self.t("activity"), text_color="#9cadc7", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkButton(footer, text=self.t("install"), width=165, height=30, corner_radius=9, fg_color="transparent", border_width=1, border_color="#3b5579", text_color="#b7c7df", hover_color="#1c2d47", command=self.install_dependencies).pack(side="right")
        self.log_output = ctk.CTkTextbox(main, height=84, corner_radius=12, fg_color="#0d1728", border_width=1, border_color="#1d314d", activate_scrollbars=True)
        self.log_output.pack(fill="x", pady=(8, 0))
        self.log_output.configure(state="disabled")
        for item in self.log_history:
            self._append_log(item, record=False)

    @staticmethod
    def _bind_edit_shortcuts(entry: object) -> None:
        entry.bind("<Control-a>", lambda event: WallpaperApp._select_all(event), add="+")
        entry.bind("<Control-c>", lambda event: WallpaperApp._copy_selection(event), add="+")
        entry.bind("<Control-v>", lambda event: WallpaperApp._paste_clipboard(event), add="+")

    @staticmethod
    def _select_all(event: object) -> str:
        event.widget.select_range(0, "end")
        event.widget.icursor("end")
        return "break"

    @staticmethod
    def _copy_selection(event: object) -> str:
        try:
            selected = event.widget.selection_get()
        except TclError:
            return "break"
        event.widget.clipboard_clear()
        event.widget.clipboard_append(selected)
        return "break"

    @staticmethod
    def _paste_clipboard(event: object) -> str:
        try:
            value = event.widget.clipboard_get()
        except TclError:
            return "break"
        try:
            event.widget.delete("sel.first", "sel.last")
        except TclError:
            pass
        event.widget.insert("insert", value)
        return "break"

    def _brand_mark(self, parent: object) -> object:
        try:
            image = Image.open(APP_ICON)
            self.brand_image = self.ctk.CTkImage(light_image=image, dark_image=image, size=(40, 40))
            return self.ctk.CTkLabel(parent, text="", image=self.brand_image, width=40, height=40, corner_radius=14)
        except (OSError, TclError):
            return self.ctk.CTkLabel(
                parent,
                text="DL",
                width=40,
                height=40,
                corner_radius=14,
                fg_color="#3b82f6",
                font=self.ctk.CTkFont(size=16, weight="bold"),
            )

    def change_language(self, choice: str) -> None:
        self.translator.set_language("en" if choice == "English" else "vi")
        self.status.set(self.t("ready"))
        self._build_ui()
        self.refresh_library()

    def log(self, message: str) -> None:
        self.events.put(("log", message))

    def _append_log(self, message: str, record: bool = True) -> None:
        if record:
            self.log_history.append(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.configure(state="normal")
        self.log_output.insert("end", f"[{timestamp}] {message}\n")
        self.log_output.see("end")
        self.log_output.configure(state="disabled")

    def _run_background(self, status: str, job: Callable[[], object]) -> None:
        if self.busy:
            return
        self.busy = True
        self.status.set(status)

        def runner() -> None:
            try:
                self.events.put(("success", job()))
            except Exception as error:
                self.events.put(("error", error))
            finally:
                self.events.put(("done", None))

        threading.Thread(target=runner, daemon=True).start()

    def _process_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "log":
                    self._append_log(str(payload))
                elif event == "success":
                    if isinstance(payload, Path):
                        self.selected_path.set(str(payload))
                        self.refresh_library()
                    self._append_log(self.t("done"))
                elif event == "error":
                    self._append_log(self.t("error", error=payload))
                    messagebox.showerror(APP_NAME, str(payload), parent=self.window)
                elif event == "done":
                    self.busy = False
                    self.status.set(self.t("ready"))
        except queue.Empty:
            pass
        self.window.after(100, self._process_events)

    def choose_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title=self.t("choose_dialog"),
            filetypes=[(self.t("media_files"), "*.jpg *.jpeg *.png *.webp *.gif *.mp4 *.webm *.mkv *.mov *.avi"), (self.t("all_files"), "*.*")],
        )
        if file_path:
            self._select_library_item(Path(file_path))

    def copy_to_library(self) -> None:
        source = Path(self.selected_path.get()).expanduser()
        if not source.is_file():
            messagebox.showwarning(APP_NAME, self.t("invalid_file"), parent=self.window)
            return
        destination = WALLPAPER_DIR / source.name
        if destination.exists() and destination.resolve() != source.resolve():
            destination = WALLPAPER_DIR / f"{source.stem}-{datetime.now():%Y%m%d-%H%M%S}{source.suffix}"
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        self.selected_path.set(str(destination))
        self.refresh_library()
        self._append_log(self.t("added", file=destination.name))

    def refresh_library(self) -> None:
        paths = sorted(
            (path for path in WALLPAPER_DIR.iterdir() if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS),
            key=lambda path: path.name.lower(),
        )
        self.library_paths = paths
        self.library_count.configure(text=self.t("library_count", count=len(paths)))
        for child in self.library_list.winfo_children():
            child.destroy()
        if not paths:
            ctk = self.ctk
            ctk.CTkLabel(self.library_list, text="◌", text_color="#4c77aa", font=ctk.CTkFont(size=30)).pack(pady=(22, 2))
            ctk.CTkLabel(self.library_list, text=self.t("library_empty"), text_color="#8192ae", font=ctk.CTkFont(size=12)).pack(pady=(0, 22))
            return
        for path in paths:
            active = str(path) == self.selected_path.get()
            kind = classify_media(path)
            if kind is MediaKind.VIDEO:
                media_type, icon = self.t("video"), "▶"
            elif kind is MediaKind.ANIMATED_IMAGE:
                media_type, icon = self.t("gif"), "◉"
            else:
                media_type, icon = self.t("image"), "▣"
            item_button = self.ctk.CTkButton(
                self.library_list,
                text=f"{icon}  {path.name}\n     {media_type}",
                anchor="w",
                height=48,
                corner_radius=10,
                fg_color="#1b365b" if active else "#142238",
                hover_color="#24466f",
                text_color="#dce9ff",
                font=self.ctk.CTkFont(size=12, weight="bold" if active else "normal"),
                command=lambda item=path: self._select_library_item(item),
            )
            item_button.pack(fill="x", pady=4)
            item_button.bind("<Button-3>", lambda event, item=path: self._show_file_menu(event, item))

    def _show_file_menu(self, event: object, path: Path) -> str:
        menu = Menu(self.window, tearoff=False)
        menu.add_command(label=self.t("rename"), command=lambda: self.rename_file(path))
        menu.add_command(label=self.t("delete"), command=lambda: self.delete_file(path))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()
        return "break"

    def delete_file(self, path: Path) -> None:
        if not messagebox.askyesno(APP_NAME, self.t("delete_confirm", file=path.name), parent=self.window):
            return
        try:
            path.unlink()
        except OSError as error:
            messagebox.showerror(APP_NAME, self.t("file_action_error", error=error), parent=self.window)
            return
        if Path(self.selected_path.get()).resolve() == path.resolve():
            self.selected_path.set("")
        self.refresh_library()
        self._append_log(self.t("deleted", file=path.name))

    def rename_file(self, path: Path) -> None:
        new_name = simpledialog.askstring(
            APP_NAME,
            self.t("rename_prompt"),
            initialvalue=path.name,
            parent=self.window,
        )
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name or Path(new_name).name != new_name:
            messagebox.showwarning(APP_NAME, self.t("invalid_name"), parent=self.window)
            return
        if Path(new_name).suffix.lower() != path.suffix.lower():
            messagebox.showwarning(APP_NAME, self.t("keep_extension"), parent=self.window)
            return
        destination = path.with_name(new_name)
        if destination.exists() and destination.resolve() != path.resolve():
            messagebox.showwarning(APP_NAME, self.t("name_exists"), parent=self.window)
            return
        try:
            path.rename(destination)
        except OSError as error:
            messagebox.showerror(APP_NAME, self.t("file_action_error", error=error), parent=self.window)
            return
        if Path(self.selected_path.get()).resolve() == path.resolve():
            self.selected_path.set(str(destination))
        self.refresh_library()
        self._append_log(self.t("renamed", old=path.name, new=destination.name))

    def _select_library_item(self, path: Path) -> None:
        self.selected_path.set(str(path))
        self.refresh_library()

    def open_library(self) -> None:
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(WALLPAPER_DIR)])
        else:
            messagebox.showinfo(APP_NAME, str(WALLPAPER_DIR), parent=self.window)

    def install_dependencies(self) -> None:
        self._run_background(self.t("installing"), self.dependencies.install_all_dependencies)

    def toggle_rotation(self) -> None:
        minutes = self._rotation_minutes()
        write_rotation_config(enabled=self.rotation_enabled.get(), fallback_minutes=minutes)
        if self.rotation_enabled.get():
            install_and_enable(self.log)
            self._append_log(self.t("rotation_started", minutes=minutes))
        else:
            disable(self.log)
            self._append_log(self.t("rotation_stopped"))

    def _rotation_minutes(self) -> int:
        try:
            value = int(self.rotation_interval.get())
        except ValueError:
            value = DEFAULT_ROTATION_MINUTES
        value = max(MIN_ROTATION_MINUTES, value)
        self.rotation_interval.set(str(value))
        return value

    def set_selected(self) -> None:
        path = Path(self.selected_path.get()).expanduser()
        if not path.is_file():
            messagebox.showwarning(APP_NAME, self.t("invalid_file"), parent=self.window)
            return

        def job() -> Path:
            self.dependencies.install_system_dependencies()
            self.wallpaper.set_wallpaper(path)
            return path

        self._run_background(self.t("setting"), job)

    def download_wallpaper(self) -> None:
        url = self.url.get().strip()
        if not url.startswith(("https://", "http://")):
            messagebox.showwarning(APP_NAME, self.t("invalid_url"), parent=self.window)
            return
        if self._total_memory_bytes() <= 8 * 1024**3 and not messagebox.askyesno(
            APP_NAME,
            self.t("video_memory_warning"),
            parent=self.window,
        ):
            return

        def job() -> Path:
            yt_dlp = self.dependencies.get_ytdlp()
            self.log(self.t("downloading"))
            options = {
                "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
                "merge_output_format": "mp4",
                "noplaylist": True,
                "restrictfilenames": True,
                "outtmpl": str(WALLPAPER_DIR / "%(title).140B-%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
                filename = Path(downloader.prepare_filename(info))
            mp4_file = filename.with_suffix(".mp4")
            if not filename.exists() and mp4_file.exists():
                filename = mp4_file
            if not filename.exists():
                from .dependencies import DesktopLiveLinuxError

                raise DesktopLiveLinuxError(self.t("download_file_unknown"))
            self.log(self.t("downloaded", file=filename.name))
            return filename

        self._run_background(self.t("downloading"), job)

    @staticmethod
    def _total_memory_bytes() -> int:
        """Read total physical memory on Linux without adding a dependency."""
        try:
            with open("/proc/meminfo", encoding="utf-8") as meminfo:
                for line in meminfo:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
        try:
            return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError):
            return 0

    def run(self) -> None:
        self.window.mainloop()
