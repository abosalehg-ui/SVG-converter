#!/usr/bin/env python3
"""محول SVG - تحويل الصور إلى صيغة SVG (تطبيق سطح المكتب).

تطوير: عبدالكريم العبود | abo.saleh.g@gmail.com
© 2024 محول SVG - All Rights Reserved

The window is laid out right-to-left to match its Arabic interface. Note that
Tk does not implement Arabic shaping or the bidi algorithm on every platform;
on Linux in particular the text may render with disconnected letters. That is a
Tk limitation, not a layout bug — the web app in ``index.html`` renders Arabic
correctly everywhere.
"""

from __future__ import annotations

import io
import os
import sys
import threading
import warnings
from dataclasses import dataclass

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    print("خطأ: مكتبة tkinter غير موجودة!")
    print("على Windows: أعد تثبيت Python مع تفعيل خيار tcl/tk")
    print("على Linux: sudo apt-get install python3-tk")
    input("اضغط Enter للخروج...")
    sys.exit(1)

try:
    from PIL import Image, ImageTk
except ImportError:
    print("خطأ: مكتبة Pillow غير مثبتة!")
    print("قم بتثبيتها باستخدام: pip install Pillow")
    input("اضغط Enter للخروج...")
    sys.exit(1)

try:  # Optional: renders the real SVG in the preview pane instead of a bitmap.
    import cairosvg

    _HAS_CAIROSVG = True
except Exception:  # pragma: no cover - cairosvg needs system Cairo libraries
    cairosvg = None
    _HAS_CAIROSVG = False

import potrace_adapter
from svg_core import (
    BW_THRESHOLD,
    DEFAULT_COLOR_LEVELS,
    DEFAULT_DETAIL_LEVEL,
    MAX_COLOR_LEVELS,
    MAX_DETAIL_LEVEL,
    MIN_COLOR_LEVELS,
    MIN_DETAIL_LEVEL,
    create_svg,
)

SUPPORTED_EXTENSIONS = "*.png *.jpg *.jpeg *.bmp *.gif *.webp"

#: Refuse images larger than this instead of letting Pillow expand a small
#: crafted file into gigabytes of RAM (decompression bomb).
MAX_IMAGE_PIXELS = 64_000_000  # 64 megapixels, e.g. 8000x8000

#: Arabic-capable families, best first. Tk silently falls back to a default
#: font for any name it does not know, so ordering here is what matters.
ARABIC_FONT_CANDIDATES = (
    "Segoe UI",
    "Noto Sans Arabic",
    "Noto Naskh Arabic",
    "Cairo",
    "Tahoma",
    "DejaVu Sans",
    "Arial",
)


@dataclass(frozen=True)
class ConversionSettings:
    """Snapshot of the UI controls, read on the main thread.

    Tk variables are not thread-safe: calling ``.get()`` from a worker thread
    can crash the interpreter. The worker gets this frozen copy instead.
    """

    conversion_type: str
    color_levels: int
    detail_level: int
    output_scale: float
    use_potrace: bool


def _pick_font_family(root: tk.Misc) -> str:
    """Return the first installed family that can render Arabic."""
    try:
        from tkinter import font as tkfont

        available = {name.lower() for name in tkfont.families(root)}
    except Exception:  # pragma: no cover - depends on the Tk build
        return "Arial"
    for candidate in ARABIC_FONT_CANDIDATES:
        if candidate.lower() in available:
            return candidate
    return "Arial"


class SVGConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("محول SVG - تحويل الصور إلى SVG")
        self.root.geometry("900x680")
        self.root.minsize(800, 580)
        self.root.configure(bg="#FAF9F7")

        self.current_image_path = None
        self.current_image = None
        self.output_svg = None

        self.colors = {
            "bg": "#FAF9F7",
            "primary": "#B85A3C",  # 4.6:1 against white — WCAG AA for body text
            "secondary": "#F5F4F2",
            "text": "#1A1915",
            "text_light": "#6B6963",
            "border": "#E5E4E2",
            "white": "#FFFFFF",
        }
        self.font_family = _pick_font_family(root)

        self.setup_ui()

    # ------------------------------------------------------------------ UI --

    def _font(self, size: int, weight: str = "normal") -> tuple:
        return (self.font_family, size, weight)

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        self._build_title(main_frame)

        content_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        content_frame.pack(fill=tk.BOTH, expand=True)

        # RTL layout: settings on the right, previews on the left.
        self._build_settings(content_frame)
        self._build_previews(content_frame)
        self._build_actions(main_frame)
        self._build_footer(main_frame)

    def _build_title(self, parent):
        title_frame = tk.Frame(parent, bg=self.colors["bg"])
        title_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            title_frame,
            text="🎨 محول SVG",
            font=self._font(24, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack()

        tk.Label(
            title_frame,
            text="تحويل الصور إلى رسومات متجهية SVG",
            font=self._font(11),
            bg=self.colors["bg"],
            fg=self.colors["text_light"],
        ).pack()

    def _build_settings(self, parent):
        right_frame = tk.Frame(parent, bg=self.colors["white"], width=260)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        right_frame.pack_propagate(False)

        panel = tk.Frame(right_frame, bg=self.colors["white"], padx=15, pady=15)
        panel.pack(fill=tk.BOTH, expand=True)

        def label(text, size=10, weight="normal", pady=(5, 5)):
            tk.Label(
                panel,
                text=text,
                font=self._font(size, weight),
                bg=self.colors["white"],
                fg=self.colors["text"],
                anchor="e",
                justify="right",
            ).pack(anchor="e", fill=tk.X, pady=pady)

        label("⚙️ إعدادات التحويل", size=12, weight="bold", pady=(0, 15))

        # نوع التحويل
        label("نوع التحويل:")
        self.conversion_type = tk.StringVar(value="color")
        for text, value in (
            ("🎨 ملون", "color"),
            ("⬛ أبيض وأسود", "bw"),
            ("🌫️ تدرج رمادي", "grayscale"),
        ):
            tk.Radiobutton(
                panel,
                text=text,
                variable=self.conversion_type,
                value=value,
                bg=self.colors["white"],
                activebackground=self.colors["white"],
                font=self._font(9),
                anchor="e",
                justify="right",
                command=self._on_conversion_type_changed,
            ).pack(anchor="e", fill=tk.X, padx=10)

        # Potrace — only meaningful for BW, hidden otherwise.
        potrace_available = potrace_adapter.is_available()
        self.use_potrace = tk.BooleanVar(value=potrace_available)
        self.potrace_check = tk.Checkbutton(
            panel,
            text=(
                "✨ تتبّع بمنحنيات (Potrace)"
                if potrace_available
                else "✨ Potrace غير متوفر (pip install pypotrace)"
            ),
            variable=self.use_potrace,
            bg=self.colors["white"],
            activebackground=self.colors["white"],
            font=self._font(9),
            anchor="e",
            justify="right",
            state=tk.NORMAL if potrace_available else tk.DISABLED,
        )

        # عدد مستويات الألوان
        self.colors_label = tk.Label(
            panel,
            text="",
            font=self._font(10),
            bg=self.colors["white"],
            fg=self.colors["text"],
            anchor="e",
            justify="right",
        )
        self.colors_label.pack(anchor="e", fill=tk.X, pady=(15, 5))

        self.color_levels = tk.IntVar(value=DEFAULT_COLOR_LEVELS)
        self.colors_scale = tk.Scale(
            panel,
            from_=MIN_COLOR_LEVELS,
            to=MAX_COLOR_LEVELS,
            variable=self.color_levels,
            orient=tk.HORIZONTAL,
            bg=self.colors["white"],
            highlightthickness=0,
            length=190,
            showvalue=False,
            command=lambda _=None: self._update_colors_label(),
        )
        self.colors_scale.pack(anchor="e")
        self._update_colors_label()

        # دقة التفاصيل
        label("دقة التفاصيل:", pady=(15, 5))
        self.detail_level = tk.IntVar(value=DEFAULT_DETAIL_LEVEL)
        tk.Scale(
            panel,
            from_=MIN_DETAIL_LEVEL,
            to=MAX_DETAIL_LEVEL,
            variable=self.detail_level,
            orient=tk.HORIZONTAL,
            bg=self.colors["white"],
            highlightthickness=0,
            length=190,
        ).pack(anchor="e")

        # مقياس الإخراج
        label("مقياس الإخراج:", pady=(15, 5))
        self.output_scale = tk.DoubleVar(value=1.0)
        scale_frame = tk.Frame(panel, bg=self.colors["white"])
        scale_frame.pack(anchor="e")
        for text, value in (("200%", 2.0), ("150%", 1.5), ("100%", 1.0), ("50%", 0.5)):
            tk.Radiobutton(
                scale_frame,
                text=text,
                variable=self.output_scale,
                value=value,
                bg=self.colors["white"],
                activebackground=self.colors["white"],
                font=self._font(9),
            ).pack(side=tk.RIGHT)

        self.file_info = tk.Label(
            panel,
            text="",
            font=self._font(9),
            bg=self.colors["white"],
            fg=self.colors["text_light"],
            wraplength=210,
            justify="right",
            anchor="e",
        )
        self.file_info.pack(anchor="e", fill=tk.X, pady=(20, 0))

    def _build_previews(self, parent):
        left_frame = tk.Frame(parent, bg=self.colors["white"])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        preview_frame = tk.Frame(left_frame, bg=self.colors["white"], padx=15, pady=15)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        previews = tk.Frame(preview_frame, bg=self.colors["white"])
        previews.pack(fill=tk.BOTH, expand=True)

        # الصورة الأصلية (على اليمين ضمن هذه اللوحة، اتساقاً مع اتجاه RTL)
        orig_frame = tk.Frame(previews, bg=self.colors["white"])
        orig_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        tk.Label(
            orig_frame,
            text="🖼️ الصورة الأصلية",
            font=self._font(10, "bold"),
            bg=self.colors["white"],
        ).pack(pady=(0, 5))

        self.original_canvas = tk.Canvas(
            orig_frame,
            bg=self.colors["secondary"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.original_canvas.pack(fill=tk.BOTH, expand=True)

        svg_frame = tk.Frame(previews, bg=self.colors["white"])
        svg_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Honest labelling: without cairosvg this pane shows the filtered
        # bitmap, which is an approximation of the SVG, not the SVG itself.
        self.svg_preview_title = tk.Label(
            svg_frame,
            text=("✨ معاينة SVG" if _HAS_CAIROSVG else "✨ معاينة تقريبية (بدون cairosvg)"),
            font=self._font(10, "bold"),
            bg=self.colors["white"],
        )
        self.svg_preview_title.pack(pady=(0, 5))

        self.svg_canvas = tk.Canvas(
            svg_frame,
            bg=self.colors["secondary"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.svg_canvas.pack(fill=tk.BOTH, expand=True)

    def _build_actions(self, parent):
        buttons_frame = tk.Frame(parent, bg=self.colors["bg"])
        buttons_frame.pack(fill=tk.X, pady=(15, 0))

        # RTL: primary action first from the right.
        self.convert_btn = tk.Button(
            buttons_frame,
            text="🔄 تحويل إلى SVG",
            font=self._font(10, "bold"),
            bg=self.colors["primary"],
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self.convert_image,
            state=tk.DISABLED,
        )
        self.convert_btn.pack(side=tk.RIGHT, padx=10)

        tk.Button(
            buttons_frame,
            text="📂 اختيار صورة",
            font=self._font(10),
            bg=self.colors["secondary"],
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=15,
            pady=8,
            command=self.select_image,
        ).pack(side=tk.RIGHT)

        self.save_btn = tk.Button(
            buttons_frame,
            text="💾 حفظ SVG",
            font=self._font(10),
            bg=self.colors["secondary"],
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=15,
            pady=8,
            command=self.save_svg,
            state=tk.DISABLED,
        )
        self.save_btn.pack(side=tk.RIGHT, padx=(0, 10))

        self.status_label = tk.Label(
            buttons_frame,
            text="",
            font=self._font(9),
            bg=self.colors["bg"],
            fg=self.colors["text_light"],
            anchor="e",
            justify="right",
        )
        self.status_label.pack(side=tk.RIGHT, padx=20)

        # Conversion can take a while on large images; show that it is alive.
        self.progress = ttk.Progressbar(parent, mode="indeterminate", length=200)

    def _build_footer(self, parent):
        tk.Label(
            parent,
            text=(
                "تطوير: عبدالكريم العبود | abo.saleh.g@gmail.com\n"
                "© 2024 محول SVG - All Rights Reserved"
            ),
            font=self._font(8),
            bg=self.colors["bg"],
            fg=self.colors["text_light"],
        ).pack(pady=(15, 0))

    # ------------------------------------------------------------ handlers --

    def _update_colors_label(self):
        levels = self.color_levels.get()
        self.colors_label.config(text=f"مستويات الألوان: {levels} ({levels**3} لون)")

    def _on_conversion_type_changed(self):
        """Colour levels are meaningless for BW; Potrace only applies to BW."""
        is_bw = self.conversion_type.get() == "bw"
        if is_bw:
            self.colors_scale.config(state=tk.DISABLED)
            self.potrace_check.pack(anchor="e", fill=tk.X, padx=10, pady=(5, 0))
        else:
            self.colors_scale.config(state=tk.NORMAL)
            self.potrace_check.pack_forget()

    def select_image(self):
        filepath = filedialog.askopenfilename(
            title="اختر صورة",
            filetypes=[("ملفات الصور", SUPPORTED_EXTENSIONS), ("جميع الملفات", "*.*")],
        )
        if filepath:
            self.load_image(filepath)

    def load_image(self, filepath):
        try:
            image = self._open_image_safely(filepath)
        except Exception as exc:
            messagebox.showerror("خطأ", f"فشل تحميل الصورة:\n{exc}")
            return

        self.current_image_path = filepath
        self.current_image = image

        size_kb = os.path.getsize(filepath) / 1024
        self.file_info.config(
            text=(
                f"📄 {os.path.basename(filepath)}\n"
                f"📐 {image.width} × {image.height}\n"
                f"💾 {size_kb:.1f} KB"
            )
        )

        self.display_image(image, self.original_canvas)

        self.svg_canvas.delete("all")
        self.svg_canvas.update()
        width = self.svg_canvas.winfo_width()
        height = self.svg_canvas.winfo_height()
        self.svg_canvas.create_text(
            width // 2,
            height // 2,
            text="اضغط 'تحويل' للمعاينة",
            font=self._font(10),
            fill=self.colors["text_light"],
        )

        self.convert_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)
        self.output_svg = None
        self.status_label.config(text="✅ تم تحميل الصورة")

    @staticmethod
    def _open_image_safely(filepath):
        """Open an image, refusing decompression bombs.

        Pillow only *warns* about suspiciously large images by default, so a
        few-kilobyte file can still expand into gigabytes of RAM. Promote that
        warning to an error and add an explicit pixel budget on top.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(filepath)
            image.load()

        pixels = image.width * image.height
        if pixels > MAX_IMAGE_PIXELS:
            raise ValueError(
                f"الصورة كبيرة جداً ({image.width}×{image.height}). "
                f"الحد الأقصى {MAX_IMAGE_PIXELS // 1_000_000} ميجابكسل."
            )
        return image

    def display_image(self, img, canvas):
        canvas.update()
        canvas_w = max(canvas.winfo_width(), 200)
        canvas_h = max(canvas.winfo_height(), 200)

        ratio = min(canvas_w / img.width, canvas_h / img.height) * 0.9
        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))

        display_img = img.copy()
        if display_img.mode not in ("RGB", "RGBA"):
            display_img = display_img.convert("RGB")

        photo = ImageTk.PhotoImage(display_img.resize(new_size, Image.Resampling.LANCZOS))

        canvas.delete("all")
        canvas.image = photo  # keep a reference so Tk does not garbage-collect it
        canvas.create_image(canvas_w // 2, canvas_h // 2, image=photo, anchor="center")

    # ---------------------------------------------------------- conversion --

    def convert_image(self):
        if not self.current_image:
            return

        # Read every Tk variable HERE, on the main thread — Tk variables are not
        # thread-safe and reading them from the worker can crash the process.
        settings = ConversionSettings(
            conversion_type=self.conversion_type.get(),
            color_levels=self.color_levels.get(),
            detail_level=self.detail_level.get(),
            output_scale=self.output_scale.get(),
            use_potrace=self.use_potrace.get(),
        )
        source = self.current_image.copy()

        self.convert_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.status_label.config(text="⏳ جاري التحويل...")
        self.progress.pack(pady=(10, 0))
        self.progress.start(12)

        # daemon=True so closing the window during a long conversion actually exits.
        threading.Thread(target=self._do_convert, args=(source, settings), daemon=True).start()

    def _do_convert(self, img, settings: ConversionSettings):
        try:
            svg, preview = self._render(img, settings)
        except Exception as exc:
            # Bind the message NOW: `exc` is unbound by the time a deferred
            # callback runs, which used to turn every failure into a NameError.
            message = str(exc)
            self.root.after(0, lambda: self._conversion_error(message))
            return

        self.root.after(0, lambda: self._conversion_done(svg, preview))

    @staticmethod
    def _render(img, settings: ConversionSettings):
        """Produce (svg_string, preview_image). Runs off the main thread."""
        if settings.output_scale != 1.0:
            new_size = (
                max(1, int(img.width * settings.output_scale)),
                max(1, int(img.height * settings.output_scale)),
            )
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        conversion_type = settings.conversion_type
        use_potrace = (
            conversion_type == "bw" and settings.use_potrace and potrace_adapter.is_available()
        )

        if use_potrace:
            svg = potrace_adapter.trace_bw(img, threshold=BW_THRESHOLD)
            # Fallback preview mirrors what Potrace traced, not the source image.
            img = img.convert("L").point(lambda v: 255 if v >= BW_THRESHOLD else 0, mode="1")
        else:
            if conversion_type == "bw":
                img = img.convert("L").point(lambda v: 255 if v >= BW_THRESHOLD else 0, mode="1")
            elif conversion_type == "grayscale":
                img = img.convert("L")

            svg = create_svg(
                img.convert("RGB"),
                conversion_type=conversion_type,
                color_levels=settings.color_levels,
                detail_level=settings.detail_level,
            )

        return svg, SVGConverterApp._svg_preview(svg, img)

    @staticmethod
    def _svg_preview(svg: str, fallback_img):
        """Rasterize the SVG so the preview shows the real output.

        Falls back to the filtered bitmap when cairosvg is unavailable; the
        pane title says so, rather than passing an approximation off as the
        actual result.
        """
        if not _HAS_CAIROSVG:
            return fallback_img.convert("RGB")
        try:
            png = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
            return Image.open(io.BytesIO(png)).convert("RGB")
        except Exception:  # pragma: no cover - depends on the Cairo build
            return fallback_img.convert("RGB")

    def _conversion_done(self, svg, preview):
        self.output_svg = svg
        self.progress.stop()
        self.progress.pack_forget()
        self.display_image(preview, self.svg_canvas)
        self.convert_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        size_kb = len(svg.encode("utf-8")) / 1024
        self.status_label.config(text=f"✅ تم التحويل بنجاح! ({size_kb:.1f} KB)")

    def _conversion_error(self, message: str):
        self.progress.stop()
        self.progress.pack_forget()
        self.convert_btn.config(state=tk.NORMAL)
        self.status_label.config(text="❌ فشل التحويل")
        messagebox.showerror("خطأ", f"فشل التحويل:\n{message}")

    # --------------------------------------------------------------- save --

    def save_svg(self):
        if not self.output_svg:
            messagebox.showwarning("تنبيه", "لا يوجد ملف SVG للحفظ")
            return

        default_name = "converted.svg"
        if self.current_image_path:
            default_name = os.path.splitext(os.path.basename(self.current_image_path))[0] + ".svg"

        filepath = filedialog.asksaveasfilename(
            title="حفظ ملف SVG",
            defaultextension=".svg",
            initialfile=default_name,
            filetypes=[("SVG Files", "*.svg"), ("All Files", "*.*")],
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write(self.output_svg)
        except OSError as exc:
            messagebox.showerror("خطأ", f"فشل الحفظ:\n{exc}")
            return

        self.status_label.config(text=f"✅ تم الحفظ: {os.path.basename(filepath)}")
        messagebox.showinfo("تم", f"تم حفظ الملف بنجاح:\n{filepath}")


def main():
    root = tk.Tk()
    SVGConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
