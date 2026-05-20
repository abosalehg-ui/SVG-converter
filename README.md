<div align="center">

# 🎨 محول SVG | SVG Converter

### تحويل الصور إلى رسومات متجهية

أداة متعددة المنصات لتحويل الصور إلى صيغة SVG مع واجهة سهلة الاستخدام

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![GitHub Pages](https://img.shields.io/badge/GitHub-Pages-222222?style=for-the-badge&logo=github)](https://abosalehg-ui.github.io/SVG-converter/)
[![CI](https://github.com/abosalehg-ui/SVG-converter/actions/workflows/ci.yml/badge.svg)](https://github.com/abosalehg-ui/SVG-converter/actions/workflows/ci.yml)

[🌐 تطبيق الويب](https://abosalehg-ui.github.io/SVG-converter/) · [📝 الإبلاغ عن مشكلة](https://github.com/abosalehg-ui/SVG-converter/issues)

</div>

---

<div dir="rtl">

## 📌 نظرة عامة

هذا المشروع يقدم **نسختين** من محول الصور إلى SVG:

| النسخة | الملف | الوصف |
|--------|-------|-------|
| 🖥️ **تطبيق سطح المكتب** | `svg_converter.py` | تطبيق Python بواجهة Tkinter |
| 🌐 **تطبيق الويب** | `index.html` | يعمل مباشرة في المتصفح |

> 💡 كلا التطبيقين يقدمان نفس الوظائف والخيارات!

---

## ✨ المميزات المشتركة

| الميزة | الوصف |
|--------|-------|
| 🖼️ **صيغ متعددة** | دعم PNG, JPG, BMP, GIF, WebP |
| 🎨 **ثلاثة أوضاع تحويل** | ملون، أبيض وأسود، تدرج رمادي |
| 🎛️ **تحكم بالجودة** | عدد الألوان، دقة التفاصيل، مقياس الإخراج |
| 👁️ **معاينة فورية** | مشاهدة النتيجة قبل الحفظ |
| 🌐 **واجهة عربية** | دعم كامل للغة العربية |
| ✒️ **Potrace** | تتبّع مسارات عالي الجودة للوضع الأبيض/الأسود (اختياري) |
| ✅ **مغطّى بالاختبارات** | اختبارات Python و JavaScript مع CI تلقائي |

### 🎨 أوضاع التحويل

| الوضع | الوصف | الاستخدام الأمثل |
|-------|-------|------------------|
| 🎨 **ملون** | الحفاظ على الألوان الأصلية | صور فوتوغرافية، رسومات ملونة |
| ⬛ **أبيض وأسود** | تحويل ثنائي | شعارات، أيقونات، توقيعات |
| 🌫️ **تدرج رمادي** | درجات الرمادي | صور فنية، رسومات بالقلم |

### 🎛️ خيارات التحكم

| الخيار | النطاق | التأثير |
|--------|--------|---------|
| 🎨 عدد الألوان | 2 - 64 | كلما زاد العدد، زادت الدقة وحجم الملف |
| 📊 دقة التفاصيل | منخفض - عالي | تحكم بمستوى التفاصيل الدقيقة |
| 📐 مقياس الإخراج | 50% - 200% | تكبير أو تصغير الناتج |

---

## 🖥️ تطبيق سطح المكتب (Python)

### 📋 المتطلبات

#### المكتبات الأساسية
```bash
pip install Pillow numpy
```

#### المكتبات الاختيارية (للميزات المتقدمة)
```bash
# لتتبع المسارات بدقة عالية (أبيض وأسود)
pip install pypotrace

# لمعاينة SVG داخل التطبيق
pip install cairosvg
```

### 🚀 التشغيل

```bash
# استنساخ المستودع
git clone https://github.com/abosalehg-ui/SVG-converter.git

# الانتقال للمجلد
cd SVG-converter

# تشغيل التطبيق
python svg_converter.py
```

### 📖 طريقة الاستخدام

1. **اختر صورة**: اضغط على منطقة الرفع أو اسحب صورة
2. **اضبط الإعدادات**: اختر نوع التحويل وعدد الألوان ومستوى التفاصيل
3. **حوّل**: اضغط "تحويل إلى SVG"
4. **احفظ**: اضغط "حفظ SVG" لتصدير الملف

### 🛠️ التقنيات المستخدمة

| التقنية | الاستخدام |
|---------|-----------|
| **Python 3.8+** | لغة البرمجة |
| **Tkinter** | واجهة المستخدم الرسومية |
| **Pillow** | معالجة الصور |
| **NumPy** | العمليات الحسابية |
| **Potrace** | تتبع المسارات (اختياري) |

---

## 🌐 تطبيق الويب

### 🚀 التشغيل

#### الطريقة الأولى: أونلاين مباشرة
```
https://abosalehg-ui.github.io/SVG-converter/
```

#### الطريقة الثانية: محلياً
```bash
# استنساخ المستودع
git clone https://github.com/abosalehg-ui/SVG-converter.git

# فتح الملف في المتصفح
open index.html
# أو على Windows
start index.html
```

### 📖 طريقة الاستخدام

1. **ارفع صورة**: اسحب الصورة إلى منطقة الرفع أو اضغط للاختيار
2. **اضبط الإعدادات**: اختر نوع التحويل والخيارات المطلوبة
3. **حوّل**: اضغط "🔄 تحويل إلى SVG"
4. **حمّل**: اضغط "💾 تحميل SVG" لحفظ الملف

### ⌨️ اختصارات لوحة المفاتيح

| الاختصار | الوظيفة |
|----------|---------|
| `Ctrl/⌘ + O` | فتح اختيار ملف |
| `Ctrl/⌘ + Enter` | تشغيل التحويل |
| `Ctrl/⌘ + S` | تحميل ملف SVG الناتج |
| `Ctrl/⌘ + D` | تبديل الوضع الفاتح/الداكن |

### 🌓 الوضع الداكن

زر تبديل في أعلى الصفحة يحفظ تفضيلك في `localStorage` ويحترم إعداد `prefers-color-scheme` للنظام.

### ♿ إمكانية الوصول

- خصائص ARIA كاملة على جميع عناصر التحكم
- إمكانية التنقل بلوحة المفاتيح بالكامل
- روابط Skip-to-content
- علامات `role` و `aria-live` للإشعارات وأشرطة التقدم

### ⚙️ الأداء — Web Worker

التحويل يعمل في **Web Worker** منفصل لتفادي تجميد الواجهة على الصور الكبيرة، مع رجوع تلقائي للخيط الرئيسي عند فتح الملف بـ `file://` أو في المتصفحات القديمة.

### 🛠️ التقنيات المستخدمة

| التقنية | الاستخدام |
|---------|-----------|
| **HTML5** | هيكلة الصفحة |
| **CSS3 (متغيرات)** | التصميم والحركات + ثيم داكن/فاتح |
| **JavaScript (ES6+)** | منطق التحويل والتفاعل |
| **Web Worker** | تحويل الصور خارج الخيط الرئيسي |
| **Canvas API** | معالجة الصور |
| **svg-core.js** | وحدة مشتركة بين الواجهة والـ Worker والاختبارات |
| **Potrace.js** | تتبّع المسارات للوضع الأبيض/الأسود (اختياري) |

---

## 🎯 نصائح للحصول على أفضل النتائج

| نوع الصورة | نوع التحويل | عدد الألوان | التفاصيل |
|------------|-------------|-------------|----------|
| 🏷️ شعارات | أبيض وأسود | - | عالي |
| 🎨 رسومات بسيطة | ملون | 8-16 | متوسط-عالي |
| 📷 صور فوتوغرافية | ملون | 32-64 | متوسط |
| 🔣 أيقونات | أبيض وأسود | - | عالي |
| ✍️ توقيعات | أبيض وأسود | - | عالي |
| 🖼️ رسومات فنية | تدرج رمادي | - | متوسط |

---

## 📁 هيكل المشروع

```
SVG-converter/
├── index.html               # 🌐 تطبيق الويب (الواجهة)
├── svg-core.js              # 🧠 منطق التحويل المشترك (JS)
├── svg-worker.js            # ⚙️ Web Worker للتحويل خارج الخيط الرئيسي
├── potrace-adapter.js       # ✒️ غلاف Potrace للوضع الأبيض/الأسود
├── svg_converter.py         # 🖥️ تطبيق سطح المكتب (Python/Tkinter)
├── svg_core.py              # 🧠 منطق التحويل المشترك (Python)
├── potrace_adapter.py       # ✒️ غلاف Potrace (Python)
├── tests/
│   ├── test_svg_core.py     # 🧪 اختبارات Python (pytest)
│   └── svg-core.test.js     # 🧪 اختبارات JavaScript (node --test)
├── .github/workflows/ci.yml # 🤖 CI: matrix Python 3.9/3.11/3.12 × Node 18/20/22
├── pyproject.toml           # ⚙️ إعداد pytest
├── requirements-dev.txt     # 📦 تبعيات التطوير
└── README.md                # 📖 التوثيق
```

---

## 🧪 الاختبارات والتطوير

### تشغيل اختبارات Python

```bash
pip install -r requirements-dev.txt
pytest
```

### تشغيل اختبارات JavaScript

```bash
node --test tests/svg-core.test.js
```

### CI تلقائي

كل push أو pull request يشغّل تلقائياً:
- **Python**: 3.9 / 3.11 / 3.12
- **Node.js**: 18.x / 20.x / 22.x

راجع [`.github/workflows/ci.yml`](.github/workflows/ci.yml) للتفاصيل.

---

## 🔄 مقارنة بين النسختين

| الميزة | تطبيق Python | تطبيق الويب |
|--------|--------------|-------------|
| 💻 التشغيل | يحتاج تثبيت Python | يعمل في المتصفح مباشرة |
| 🌐 الوصول | محلي فقط | من أي جهاز متصل بالإنترنت |
| 📦 التثبيت | يحتاج مكتبات | لا يحتاج شيء |
| 🚀 الأداء | أسرع للملفات الكبيرة | Web Worker يحافظ على استجابة الواجهة |
| 💾 الحفظ | مباشر للجهاز | تحميل من المتصفح |
| 🔌 العمل بدون إنترنت | ✅ نعم | ❌ لا (النسخة الأونلاين) |
| 🌓 وضع داكن | ❌ | ✅ |
| ⌨️ اختصارات لوحة مفاتيح | ❌ | ✅ |

---

## 🤝 المساهمة

المساهمات مرحب بها! يمكنك:

1. عمل Fork للمستودع
2. إنشاء فرع جديد (`git checkout -b feature/ميزة-جديدة`)
3. تنفيذ التغييرات (`git commit -m 'إضافة ميزة رائعة'`)
4. رفع التغييرات (`git push origin feature/ميزة-جديدة`)
5. فتح Pull Request

---

## 📄 الترخيص

© 2024 محول SVG - جميع الحقوق محفوظة

---

## 👨‍💻 المطور

</div>

<div align="center">

**عبدالكريم العبود | ABDULKARIM ALOBUD**

[![Email](https://img.shields.io/badge/Email-abo.saleh.g%40gmail.com-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:abo.saleh.g@gmail.com)
[![GitHub](https://img.shields.io/badge/GitHub-abosalehg--ui-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/abosalehg-ui)

---

### 🎨 حوّل صورك إلى رسومات متجهية احترافية!

[🌐 جرب تطبيق الويب الآن!](https://abosalehg-ui.github.io/SVG-converter/)

صُنع بـ ❤️

</div>
