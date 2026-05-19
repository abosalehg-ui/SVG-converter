#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
محول SVG - تحويل الصور إلى صيغة SVG
تطوير: عبدالكريم العبود | abo.saleh.g@gmail.com
© 2024 محول SVG - All Rights Reserved
"""

import sys
import os

# التحقق من المتطلبات
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
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

import threading

from svg_core import create_svg


class SVGConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("محول SVG - تحويل الصور إلى SVG")
        self.root.geometry("900x650")
        self.root.minsize(800, 550)
        self.root.configure(bg='#FAF9F7')
        
        self.current_image_path = None
        self.current_image = None
        self.output_svg = None
        
        self.colors = {
            'bg': '#FAF9F7',
            'primary': '#D97757',
            'secondary': '#F5F4F2',
            'text': '#1A1915',
            'text_light': '#6B6963',
            'border': '#E5E4E2',
            'white': '#FFFFFF'
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # العنوان
        title_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(
            title_frame,
            text="🎨 محول SVG",
            font=('Arial', 24, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        ).pack()
        
        tk.Label(
            title_frame,
            text="تحويل الصور إلى رسومات متجهية SVG",
            font=('Arial', 11),
            bg=self.colors['bg'],
            fg=self.colors['text_light']
        ).pack()
        
        # المحتوى
        content_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # الإعدادات
        left_frame = tk.Frame(content_frame, bg=self.colors['white'], width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_frame.pack_propagate(False)
        
        settings_frame = tk.Frame(left_frame, bg=self.colors['white'], padx=15, pady=15)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            settings_frame,
            text="⚙️ إعدادات التحويل",
            font=('Arial', 12, 'bold'),
            bg=self.colors['white'],
            fg=self.colors['text']
        ).pack(anchor='w', pady=(0, 15))
        
        # نوع التحويل
        tk.Label(settings_frame, text="نوع التحويل:", font=('Arial', 10),
                 bg=self.colors['white'], fg=self.colors['text']).pack(anchor='w', pady=(5, 5))
        
        self.conversion_type = tk.StringVar(value="color")
        for text, value in [("🎨 ملون", "color"), ("⬛ أبيض وأسود", "bw"), ("🌫️ تدرج رمادي", "grayscale")]:
            tk.Radiobutton(settings_frame, text=text, variable=self.conversion_type, value=value,
                          bg=self.colors['white'], activebackground=self.colors['white'],
                          font=('Arial', 9)).pack(anchor='w', padx=10)
        
        # عدد الألوان
        tk.Label(settings_frame, text="عدد الألوان:", font=('Arial', 10),
                 bg=self.colors['white'], fg=self.colors['text']).pack(anchor='w', pady=(15, 5))
        
        self.num_colors = tk.IntVar(value=16)
        tk.Scale(settings_frame, from_=2, to=64, variable=self.num_colors, orient=tk.HORIZONTAL,
                bg=self.colors['white'], highlightthickness=0, length=180).pack(anchor='w')
        
        # دقة التفاصيل
        tk.Label(settings_frame, text="دقة التفاصيل:", font=('Arial', 10),
                 bg=self.colors['white'], fg=self.colors['text']).pack(anchor='w', pady=(15, 5))
        
        self.detail_level = tk.IntVar(value=5)
        tk.Scale(settings_frame, from_=1, to=10, variable=self.detail_level, orient=tk.HORIZONTAL,
                bg=self.colors['white'], highlightthickness=0, length=180).pack(anchor='w')
        
        # مقياس الإخراج
        tk.Label(settings_frame, text="مقياس الإخراج:", font=('Arial', 10),
                 bg=self.colors['white'], fg=self.colors['text']).pack(anchor='w', pady=(15, 5))
        
        self.output_scale = tk.DoubleVar(value=1.0)
        scale_frame = tk.Frame(settings_frame, bg=self.colors['white'])
        scale_frame.pack(anchor='w')
        for text, value in [("50%", 0.5), ("100%", 1.0), ("150%", 1.5), ("200%", 2.0)]:
            tk.Radiobutton(scale_frame, text=text, variable=self.output_scale, value=value,
                          bg=self.colors['white'], activebackground=self.colors['white'],
                          font=('Arial', 9)).pack(side=tk.LEFT)
        
        # معلومات الملف
        self.file_info = tk.Label(settings_frame, text="", font=('Arial', 9),
                                  bg=self.colors['white'], fg=self.colors['text_light'],
                                  wraplength=200, justify='right')
        self.file_info.pack(anchor='w', pady=(20, 0))
        
        # المعاينة
        right_frame = tk.Frame(content_frame, bg=self.colors['white'])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        preview_frame = tk.Frame(right_frame, bg=self.colors['white'], padx=15, pady=15)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        previews = tk.Frame(preview_frame, bg=self.colors['white'])
        previews.pack(fill=tk.BOTH, expand=True)
        
        # الصورة الأصلية
        orig_frame = tk.Frame(previews, bg=self.colors['white'])
        orig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Label(orig_frame, text="🖼️ الصورة الأصلية", font=('Arial', 10, 'bold'),
                bg=self.colors['white']).pack(pady=(0, 5))
        
        self.original_canvas = tk.Canvas(orig_frame, bg=self.colors['secondary'],
                                         highlightthickness=1, highlightbackground=self.colors['border'])
        self.original_canvas.pack(fill=tk.BOTH, expand=True)
        
        # معاينة SVG
        svg_frame = tk.Frame(previews, bg=self.colors['white'])
        svg_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tk.Label(svg_frame, text="✨ معاينة SVG", font=('Arial', 10, 'bold'),
                bg=self.colors['white']).pack(pady=(0, 5))
        
        self.svg_canvas = tk.Canvas(svg_frame, bg=self.colors['secondary'],
                                    highlightthickness=1, highlightbackground=self.colors['border'])
        self.svg_canvas.pack(fill=tk.BOTH, expand=True)
        
        # الأزرار
        buttons_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        tk.Button(buttons_frame, text="📂 اختيار صورة", font=('Arial', 10),
                 bg=self.colors['secondary'], fg=self.colors['text'], relief=tk.FLAT,
                 padx=15, pady=8, command=self.select_image).pack(side=tk.LEFT)
        
        self.convert_btn = tk.Button(buttons_frame, text="🔄 تحويل إلى SVG",
                                     font=('Arial', 10, 'bold'), bg=self.colors['primary'],
                                     fg='white', relief=tk.FLAT, padx=20, pady=8,
                                     command=self.convert_image, state=tk.DISABLED)
        self.convert_btn.pack(side=tk.LEFT, padx=10)
        
        self.save_btn = tk.Button(buttons_frame, text="💾 حفظ SVG", font=('Arial', 10),
                                  bg=self.colors['secondary'], fg=self.colors['text'],
                                  relief=tk.FLAT, padx=15, pady=8, command=self.save_svg,
                                  state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(buttons_frame, text="", font=('Arial', 9),
                                     bg=self.colors['bg'], fg=self.colors['text_light'])
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # التذييل
        footer = tk.Label(main_frame,
                         text="تطوير: عبدالكريم العبود | abo.saleh.g@gmail.com\n© 2024 محول SVG - All Rights Reserved",
                         font=('Arial', 8), bg=self.colors['bg'], fg=self.colors['text_light'])
        footer.pack(pady=(15, 0))
    
    def select_image(self):
        filepath = filedialog.askopenfilename(
            title="اختر صورة",
            filetypes=[("ملفات الصور", "*.png *.jpg *.jpeg *.bmp *.gif"), ("جميع الملفات", "*.*")]
        )
        if filepath:
            self.load_image(filepath)
    
    def load_image(self, filepath):
        try:
            self.current_image_path = filepath
            self.current_image = Image.open(filepath)
            
            size = os.path.getsize(filepath) / 1024
            self.file_info.config(
                text=f"📄 {os.path.basename(filepath)}\n📐 {self.current_image.width} × {self.current_image.height}\n💾 {size:.1f} KB"
            )
            
            self.display_image(self.current_image, self.original_canvas)
            
            self.svg_canvas.delete("all")
            self.svg_canvas.update()
            w, h = self.svg_canvas.winfo_width(), self.svg_canvas.winfo_height()
            self.svg_canvas.create_text(w//2, h//2, text="اضغط 'تحويل' للمعاينة",
                                        font=('Arial', 10), fill=self.colors['text_light'])
            
            self.convert_btn.config(state=tk.NORMAL)
            self.save_btn.config(state=tk.DISABLED)
            self.output_svg = None
            self.status_label.config(text="✅ تم تحميل الصورة")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل تحميل الصورة:\n{str(e)}")
    
    def display_image(self, img, canvas):
        canvas.update()
        cw = max(canvas.winfo_width(), 200)
        ch = max(canvas.winfo_height(), 200)
        
        ratio = min(cw / img.width, ch / img.height) * 0.9
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        
        display_img = img.copy()
        if display_img.mode not in ['RGB', 'RGBA']:
            display_img = display_img.convert('RGB')
        
        resized = display_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        
        canvas.delete("all")
        canvas.image = photo
        canvas.create_image(cw // 2, ch // 2, image=photo, anchor='center')
    
    def convert_image(self):
        if not self.current_image:
            return
        
        self.convert_btn.config(state=tk.DISABLED)
        self.status_label.config(text="⏳ جاري التحويل...")
        self.root.update()
        
        thread = threading.Thread(target=self._do_convert)
        thread.start()
    
    def _do_convert(self):
        try:
            img = self.current_image.copy()
            
            scale = self.output_scale.get()
            if scale != 1.0:
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            conv_type = self.conversion_type.get()
            if conv_type == "bw":
                img = img.convert('L').point(lambda x: 255 if x > 128 else 0, mode='1')
            elif conv_type == "grayscale":
                img = img.convert('L')
            
            img_rgb = img.convert('RGB')
            self.output_svg = create_svg(
                img_rgb,
                conversion_type=conv_type,
                num_colors=self.num_colors.get(),
                detail_level=self.detail_level.get(),
            )

            self.root.after(0, lambda: self._conversion_done(img_rgb))
        except Exception as e:
            self.root.after(0, lambda: self._conversion_error(str(e)))

    def _conversion_done(self, img):
        self.display_image(img, self.svg_canvas)
        self.convert_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)
        self.status_label.config(text="✅ تم التحويل بنجاح!")
    
    def _conversion_error(self, error):
        self.convert_btn.config(state=tk.NORMAL)
        self.status_label.config(text="❌ فشل التحويل")
        messagebox.showerror("خطأ", f"فشل التحويل:\n{error}")
    
    def save_svg(self):
        if not self.output_svg:
            messagebox.showwarning("تنبيه", "لا يوجد ملف SVG للحفظ")
            return
        
        default_name = "converted.svg"
        if self.current_image_path:
            default_name = os.path.splitext(os.path.basename(self.current_image_path))[0] + '.svg'
        
        filepath = filedialog.asksaveasfilename(
            title="حفظ ملف SVG",
            defaultextension=".svg",
            initialfile=default_name,
            filetypes=[("SVG Files", "*.svg"), ("All Files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.output_svg)
                self.status_label.config(text=f"✅ تم الحفظ: {os.path.basename(filepath)}")
                messagebox.showinfo("تم", f"تم حفظ الملف بنجاح:\n{filepath}")
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل الحفظ:\n{str(e)}")


def main():
    root = tk.Tk()
    app = SVGConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
