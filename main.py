import importlib.util
import subprocess
import sys
import threading
import tkinter as tk
from io import BytesIO
from pathlib import Path
from tkinter import colorchooser, filedialog


BASE_DIR = Path(__file__).resolve().parent
LOCAL_DEPS_DIR = BASE_DIR / ".deps"
if LOCAL_DEPS_DIR.exists():
    sys.path.insert(0, str(LOCAL_DEPS_DIR))

DEPENDENCIES = {
    "qrcode": "qrcode[pil]",
    "PIL": "pillow",
    "customtkinter": "customtkinter",
}


def ensure_dependencies():
    missing = [package for module, package in DEPENDENCIES.items() if importlib.util.find_spec(module) is None]
    if not missing:
        return

    LOCAL_DEPS_DIR.mkdir(exist_ok=True)
    print(f"Installing missing dependencies locally: {', '.join(missing)}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--target", str(LOCAL_DEPS_DIR), *missing]
    )
    if str(LOCAL_DEPS_DIR) not in sys.path:
        sys.path.insert(0, str(LOCAL_DEPS_DIR))
    importlib.invalidate_caches()


ensure_dependencies()

import customtkinter as ctk
from PIL import Image

from utils import (
    build_qr_payload,
    detect_input_type,
    generate_qr_code,
    save_qr_image,
    validate_input,
)


APP_NAME = "QRify Pro"
INPUT_TYPES = ["Text", "URL", "Email", "Phone"]
DEFAULT_QR_COLOR = "#111111"
DEFAULT_BG_COLOR = "#FFFFFF"
DEFAULT_QR_SIZE = 800
DEFAULT_BUTTON_COLOR = ("#3B8ED0", "#1F6AA5")


class QRifyPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x720")
        self.minsize(860, 600)

        self.qr_color = DEFAULT_QR_COLOR
        self.bg_color = DEFAULT_BG_COLOR
        self.logo_path = None
        self.current_image = None
        self.preview_photo = None
        self.history = []
        self.is_generating = False

        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")

        self._build_variables()
        self._build_layout()
        self._bind_events()
        self._set_status("Ready to create your next QR code.", "info")

    def _build_variables(self):
        self.input_type_var = tk.StringVar(value="Text")
        self.input_var = tk.StringVar()
        self.size_var = tk.IntVar(value=DEFAULT_QR_SIZE)
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.logo_label_var = tk.StringVar(value="No logo selected")

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1, minsize=420)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=ctk.CTkFont(size=34, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=28, pady=(22, 2))

        subtitle = ctk.CTkLabel(
            header,
            text="Create polished QR codes for text, links, email, and phone numbers.",
            font=ctk.CTkFont(size=14),
            text_color=("gray25", "gray78"),
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=30, pady=(0, 20))

        self.dark_switch = ctk.CTkSwitch(
            header,
            text="Dark mode",
            variable=self.dark_mode_var,
            command=self._toggle_dark_mode,
        )
        self.dark_switch.grid(row=0, column=1, rowspan=2, sticky="e", padx=28)

        controls = ctk.CTkScrollableFrame(self, corner_radius=0)
        controls.grid(row=1, column=0, sticky="nsew", padx=(18, 9), pady=18)
        controls.grid_columnconfigure(0, weight=1)

        preview = ctk.CTkFrame(self, corner_radius=0)
        preview.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=18)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)

        self._build_controls(controls)
        self._build_preview(preview)

    def _build_controls(self, parent):
        input_card = ctk.CTkFrame(parent, corner_radius=8)
        input_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        input_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(input_card, text="Input type", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 6)
        )
        self.type_menu = ctk.CTkOptionMenu(input_card, values=INPUT_TYPES, variable=self.input_type_var)
        self.type_menu.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))

        ctk.CTkLabel(input_card, text="Content", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=2, column=0, sticky="w", padx=18, pady=(0, 6)
        )
        self.input_entry = ctk.CTkTextbox(input_card, height=120, wrap="word")
        self.input_entry.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 8))

        self.suggestion_label = ctk.CTkLabel(
            input_card,
            text="",
            text_color=("gray35", "gray72"),
            anchor="w",
            justify="left",
        )
        self.suggestion_label.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))

        style_card = ctk.CTkFrame(parent, corner_radius=8)
        style_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        style_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(style_card, text="Style", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 10)
        )
        self.qr_color_button = ctk.CTkButton(
            style_card,
            text=f"QR Color {self.qr_color}",
            command=self._pick_qr_color,
            fg_color=DEFAULT_BUTTON_COLOR,
            corner_radius=8,
        )
        self.qr_color_button.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(0, 10))

        self.bg_color_button = ctk.CTkButton(
            style_card,
            text=f"Background {self.bg_color}",
            command=self._pick_bg_color,
            fg_color=DEFAULT_BUTTON_COLOR,
            corner_radius=8,
        )
        self.bg_color_button.grid(row=1, column=1, sticky="ew", padx=(8, 18), pady=(0, 10))

        ctk.CTkLabel(style_card, text="QR size", anchor="w").grid(
            row=2, column=0, sticky="w", padx=18, pady=(4, 0)
        )
        self.size_label = ctk.CTkLabel(style_card, text=f"{DEFAULT_QR_SIZE}px", anchor="e")
        self.size_label.grid(row=2, column=1, sticky="e", padx=18, pady=(4, 0))

        self.size_slider = ctk.CTkSlider(
            style_card,
            from_=256,
            to=1600,
            number_of_steps=21,
            command=self._update_size_label,
        )
        self.size_slider.set(DEFAULT_QR_SIZE)
        self.size_slider.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 18))

        logo_card = ctk.CTkFrame(parent, corner_radius=8)
        logo_card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        logo_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(logo_card, text="Center logo", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        ctk.CTkLabel(
            logo_card,
            textvariable=self.logo_label_var,
            text_color=("gray35", "gray72"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        logo_buttons = ctk.CTkFrame(logo_card, fg_color="transparent")
        logo_buttons.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        logo_buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(logo_buttons, text="Choose Logo", command=self._choose_logo, corner_radius=8).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ctk.CTkButton(logo_buttons, text="Remove Logo", command=self._remove_logo, corner_radius=8).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        action_card = ctk.CTkFrame(parent, corner_radius=8)
        action_card.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        action_card.grid_columnconfigure((0, 1), weight=1)

        self.generate_button = ctk.CTkButton(
            action_card,
            text="Generate",
            command=self._generate_async,
            height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=8,
        )
        self.generate_button.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 10))

        self.save_button = ctk.CTkButton(
            action_card,
            text="Save",
            command=self._save_image,
            state="disabled",
            corner_radius=8,
        )
        self.save_button.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(0, 10))

        self.copy_button = ctk.CTkButton(
            action_card,
            text="Copy to Clipboard",
            command=self._copy_to_clipboard,
            state="disabled",
            corner_radius=8,
        )
        self.copy_button.grid(row=1, column=1, sticky="ew", padx=(8, 18), pady=(0, 10))

        ctk.CTkButton(action_card, text="Reset", command=self._reset, corner_radius=8).grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18)
        )

        history_card = ctk.CTkFrame(parent, corner_radius=8)
        history_card.grid(row=4, column=0, sticky="ew")
        history_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(history_card, text="History", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 8)
        )
        self.history_frame = ctk.CTkFrame(history_card, fg_color="transparent")
        self.history_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.history_frame.grid_columnconfigure(0, weight=1)
        self._render_history()

    def _build_preview(self, parent):
        ctk.CTkLabel(parent, text="Preview", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(24, 10)
        )

        self.preview_frame = ctk.CTkFrame(parent, corner_radius=8)
        self.preview_frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(0, weight=1)

        self.preview_label = ctk.CTkLabel(
            self.preview_frame,
            text="Your QR code will appear here.",
            font=ctk.CTkFont(size=18),
            text_color=("gray45", "gray70"),
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.status_label = ctk.CTkLabel(parent, text="", anchor="w", justify="left")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 22))

    def _bind_events(self):
        self.input_entry.bind("<KeyRelease>", self._on_input_changed)
        self.preview_frame.bind("<Configure>", self._refresh_preview)

    def _pick_qr_color(self):
        color = colorchooser.askcolor(color=self.qr_color, title="Choose QR color")
        if color and color[1]:
            self.qr_color = color[1]
            self.qr_color_button.configure(text=f"QR Color {self.qr_color}", fg_color=self.qr_color)

    def _pick_bg_color(self):
        color = colorchooser.askcolor(color=self.bg_color, title="Choose background color")
        if color and color[1]:
            self.bg_color = color[1]
            self.bg_color_button.configure(text=f"Background {self.bg_color}", fg_color=self.bg_color)

    def _choose_logo(self):
        filetypes = [("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Choose center logo", filetypes=filetypes)
        if path:
            self.logo_path = path
            self.logo_label_var.set(Path(path).name)
            self._set_status("Logo selected. Generate again to apply it.", "info")

    def _remove_logo(self):
        self.logo_path = None
        self.logo_label_var.set("No logo selected")
        self._set_status("Logo removed. Generate again to update the QR code.", "info")

    def _update_size_label(self, value):
        size = int(round(float(value)))
        self.size_var.set(size)
        self.size_label.configure(text=f"{size}px")

    def _on_input_changed(self, _event=None):
        text = self._get_input_text()
        detected = detect_input_type(text)
        selected = self.input_type_var.get()

        if detected and detected != selected:
            self.suggestion_label.configure(text=f"Looks like {detected}. Select {detected} if that is what you want.")
        else:
            self.suggestion_label.configure(text="")

    def _generate_async(self):
        if self.is_generating:
            return

        raw_value = self._get_input_text()
        input_type = self.input_type_var.get()
        size = self.size_var.get()
        is_valid, message = validate_input(raw_value, input_type)
        if not is_valid:
            self._set_status(message, "error")
            return

        self.is_generating = True
        self.generate_button.configure(state="disabled", text="Generating...")
        self._set_status("Generating QR code...", "info")

        thread = threading.Thread(
            target=self._generate_worker,
            args=(raw_value, input_type, size, self.qr_color, self.bg_color, self.logo_path),
            daemon=True,
        )
        thread.start()

    def _generate_worker(self, raw_value, input_type, size, qr_color, bg_color, logo_path):
        try:
            payload = build_qr_payload(raw_value, input_type)
            image = generate_qr_code(
                payload,
                qr_color=qr_color,
                bg_color=bg_color,
                size=size,
                logo_path=logo_path,
            )
            self.after(0, lambda: self._finish_generation(image, raw_value, input_type))
        except Exception as exc:
            self.after(0, lambda: self._generation_failed(str(exc)))

    def _finish_generation(self, image, raw_value, input_type):
        self.current_image = image
        self._refresh_preview()
        self._add_history(raw_value, input_type)
        self.save_button.configure(state="normal")
        self.copy_button.configure(state="normal")
        self.generate_button.configure(state="normal", text="Generate")
        self.is_generating = False
        self._set_status("QR code generated successfully.", "success")

    def _generation_failed(self, message):
        self.generate_button.configure(state="normal", text="Generate")
        self.is_generating = False
        self._set_status(f"Could not generate QR code: {message}", "error")

    def _save_image(self):
        if self.current_image is None:
            self._set_status("Generate a QR code before saving.", "error")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save QR code",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg *.jpeg")],
        )
        if not file_path:
            return

        try:
            save_qr_image(self.current_image, file_path)
            self._set_status(f"Saved QR code to {file_path}", "success")
        except Exception as exc:
            self._set_status(f"Save failed: {exc}", "error")

    def _copy_to_clipboard(self):
        if self.current_image is None:
            self._set_status("Generate a QR code before copying.", "error")
            return

        if sys.platform.startswith("win"):
            try:
                self._copy_image_to_windows_clipboard(self.current_image)
                self._set_status("QR image copied to the clipboard.", "success")
                return
            except Exception:
                pass

        self.clipboard_clear()
        self.clipboard_append(self._get_input_text())
        self._set_status("Your QR content was copied to the clipboard.", "success")

    def _copy_image_to_windows_clipboard(self, image):
        import ctypes
        from ctypes import wintypes

        output = BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        CF_DIB = 8
        GMEM_MOVEABLE = 0x0002

        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE

        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise RuntimeError("Could not allocate clipboard memory.")

        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise RuntimeError("Could not lock clipboard memory.")
        ctypes.memmove(locked, data, len(data))
        kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(None):
            raise RuntimeError("Could not open clipboard.")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_DIB, handle):
                raise RuntimeError("Could not place image on clipboard.")
        finally:
            user32.CloseClipboard()

    def _reset(self):
        self.input_entry.delete("1.0", "end")
        self.input_type_var.set("Text")
        self.qr_color = DEFAULT_QR_COLOR
        self.bg_color = DEFAULT_BG_COLOR
        self.qr_color_button.configure(text=f"QR Color {self.qr_color}", fg_color=DEFAULT_BUTTON_COLOR)
        self.bg_color_button.configure(text=f"Background {self.bg_color}", fg_color=DEFAULT_BUTTON_COLOR)
        self.size_slider.set(DEFAULT_QR_SIZE)
        self.size_var.set(DEFAULT_QR_SIZE)
        self.size_label.configure(text=f"{DEFAULT_QR_SIZE}px")
        self.logo_path = None
        self.logo_label_var.set("No logo selected")
        self.current_image = None
        self.preview_photo = None
        self.preview_label.configure(image=None, text="Your QR code will appear here.")
        self.save_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.suggestion_label.configure(text="")
        self._set_status("Fields reset.", "info")

    def _toggle_dark_mode(self):
        ctk.set_appearance_mode("Dark" if self.dark_mode_var.get() else "Light")

    def _refresh_preview(self, _event=None):
        if self.current_image is None:
            return

        width = max(self.preview_frame.winfo_width() - 48, 220)
        height = max(self.preview_frame.winfo_height() - 48, 220)
        target = int(min(width, height))

        image = self.current_image.copy()
        image.thumbnail((target, target), Image.Resampling.LANCZOS)
        self.preview_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.preview_label.configure(image=self.preview_photo, text="")

    def _add_history(self, value, input_type):
        clean_value = " ".join(value.strip().split())
        item = {"type": input_type, "value": clean_value}
        self.history = [entry for entry in self.history if entry != item]
        self.history.insert(0, item)
        self.history = self.history[:5]
        self._render_history()

    def _render_history(self):
        for widget in self.history_frame.winfo_children():
            widget.destroy()

        if not self.history:
            ctk.CTkLabel(
                self.history_frame,
                text="Generated QR codes will appear here.",
                text_color=("gray40", "gray70"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            return

        for index, entry in enumerate(self.history):
            label = f"{entry['type']}: {entry['value'][:54]}"
            if len(entry["value"]) > 54:
                label += "..."
            button = ctk.CTkButton(
                self.history_frame,
                text=label,
                anchor="w",
                command=lambda item=entry: self._load_history(item),
                fg_color=("gray83", "gray24"),
                text_color=("gray10", "gray95"),
                hover_color=("gray75", "gray30"),
                corner_radius=8,
            )
            button.grid(row=index, column=0, sticky="ew", pady=(0, 8))

    def _load_history(self, item):
        self.input_type_var.set(item["type"])
        self.input_entry.delete("1.0", "end")
        self.input_entry.insert("1.0", item["value"])
        self._set_status("History item loaded. Generate to preview it again.", "info")

    def _get_input_text(self):
        return self.input_entry.get("1.0", "end").strip()

    def _set_status(self, message, kind):
        colors = {
            "info": ("gray25", "gray78"),
            "success": ("#166534", "#86efac"),
            "error": ("#991b1b", "#fca5a5"),
        }
        self.status_label.configure(text=message, text_color=colors.get(kind, colors["info"]))


def main():
    app = QRifyPro()
    app.mainloop()


if __name__ == "__main__":
    main()
