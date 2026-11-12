# 🧾 أتمتة الفواتير: Yahoo Mail ← Google Sheets

فواتير الـ PDF اللي بتوصل على إيميلك بـ Yahoo بتنفرز لحالها: السكربت بيقرأ الإيميلات، بيطلع من كل فاتورة **التاريخ، الشركة، رقم الفاتورة، المبلغ، والعملة**، وبيرجّع رابط للإيميل — وكل شي بينكتب بصف جديد بـ Google Sheet مرتّب حسب التاريخ، بدون تكرار، وبدون ما يكون جهازك مفتوح.

**[English guide](README_EN.md) | دليل عربي كامل (هذا الملف)**

```
Yahoo Mail (IMAP + App Password)
        │
        ▼  GitHub Actions — تشغيل كل ساعة
invoices.py
        │  1) regex عام ومجاني (يدعم $ / kr / € / £ وصيغ الأرقام السويدية)
        │  2) إذا نقص المبلغ أو رقم الفاتورة ← Claude AI يقرأ الـ PDF (اختياري)
        ▼
Google Sheet «Invoices» (إضافة + منع تكرار + ترتيب حسب التاريخ)
        └─ تاب «Sorted» بيتنشأ تلقائياً — عرض حي مرتّب بمعادلة SORT داخل Google Sheets
```

## ليش Python + GitHub Actions؟

- **مجاني بالكامل**: GitHub Free بيعطي 2000 دقيقة شهرياً للريبو الخاص، والوظيفة بتاخد دقيقة–دقيقتين، أي حوالي 45–90 دقيقة بالشهر بالجدولة كل ساعة.
- **بدون حد للعمليات** (على عكس Make.com المجاني: 1000 عملية/شهر ≈ 100 فاتورة بس).
- **مجدول بدون جهاز مفتوح**، وفيه زر تشغيل يدوي كمان.

## محتويات المشروع

| الملف | شو بيعمل |
|---|---|
| `invoices.py` | السكربت الرئيسي: IMAP ← استخراج ← Google Sheet |
| `test_extraction.py` | اختبار منطق الاستخراج بدون أي حسابات: `python test_extraction.py` |
| `requirements.txt` | المكتبات المطلوبة |
| `.github/workflows/invoices.yml` | الجدولة (كل ساعة) + زر التشغيل اليدوي |
| `template/invoice_template.xlsx` | قالب الـ Google Sheet جاهز للاستيراد |
| `sample/sample_invoice.pdf` | فاتورة وهمية للتجربة |
| `.env.example` | نموذج للقيم عند التشغيل المحلي |
| `HANDOVER_AR.md` | 🤝 دليل التسليم — لما تعمل المشروع **لشخص تاني** يستخدمه بدلاً منك |

## المتطلبات

- حساب **Yahoo** (مع إمكانية توليد App Password — بتفضّل مع التحقق بخطوتين).
- حساب **Google** (Google Sheet + Google Cloud المجاني).
- حساب **GitHub** (باقة مجانية كافية).
- اختياري: مفتاح **Anthropic API** من <https://console.anthropic.com> — للفواتير اللي الـ regex ما بيفهمها والفواتير الممسوحة (صور). بضعة سنتات للفاتورة كحد أقصى (تقديري)، ومعظم الفواتير بيمرّ مجاناً عالـ regex.

---

## الإعداد خطوة بخطوة (مرة وحدة)

### 1) جهّز الـ Google Sheet

1. افتح <https://drive.google.com> ← **جديد ← رفع ملف** ← ارفع `template/invoice_template.xlsx`.
2. كليك يمين على الملف ← **فتح باستخدام ← Google Sheets** (إذا ما ظهر: افتح الملف ثم **File ← Save as Google Sheets**).
3. بتحصل على شيت فيه تاب **Invoices** — جدول البيانات بالأعمدة العشرة، وفيه صف مثال واحد (احذفه متى ما بدك).
   - تاب **Sorted** (عرض حي مرتّب بالتاريخ) **بينشأ تلقائياً بأول تشغيل للسكربت** داخل Google Sheets نفسها بمعادلة `=SORT` حية — بدون أي خطوة يدوية منك، وبشتغل بأي إعداد لغة.
4. خد الـ **SHEET_ID** من رابط الشيت: `https://docs.google.com/spreadsheets/d/`**`هون الرقم`**`/edit` — نسخه، منحتاجه بالخطوة 5.

> بديل يدوي: اعمل شيت جديد وحط بالصف الأول نفس الأعمدة العشرة بالترتيب: `Date, Company, Invoice No., Amount, Currency, Sender, Subject, Email Link, Key, Source` (سمّي التاب الأول `Invoices`).

### 2) Google Cloud: Service Account (لتصريح الكتابة بالشيت)

1. ادخل <https://console.cloud.google.com> واعمل **مشروع جديد** (مثلاً `invoice-automation`) — مجاني.
2. من القائمة ☰: **APIs & Services ← Library** ← دوّر على **Google Sheets API** ← **Enable**.
3. من ☰: **IAM & Admin ← Service Accounts** ← **Create service account** (اسم مثل `sheet-writer`، مش ضروري تعطيه دور).
4. افتح حساب الخدمة اللي عملته ← تبويب **Keys** ← **Add key ← Create new key ← JSON** ← بينزل ملف JSON. **خبّيه بمكان آمن — هو بمثابة كلمة سر.**
5. افتح ملف الـ JSON وانسخ قيمة حقل **`client_email`** (شكله `xxx@your-project.iam.gserviceaccount.com`).
6. ارجع لشيت الفواتير ← **مشاركة (Share)** ← الصق إيميل حساب الخدمة ← دوره **Editor**.

### 3) Yahoo: App Password

1. ادخل <https://login.yahoo.com/account/security> — إذا **التحقق بخطوتين** مش مفعّل، فعّله أولاً (شرط أساسي).
2. اضغط **Generate app password** (أو Manage app passwords) ← سمّيه مثل `github-invoices` ← **Generate**.
3. انسخ كلمة السر (16 خانة). إذا فشل تسجيل الدخول بعدها، انتظر 10 دقايق أو ولّد واحدة جديدة.

### 4) ارفع المشروع على GitHub

1. اعمل repository **خاص (Private)** جديد — مهم يكون خاص.
2. ارفع الملفات: **Add file ← Upload files** ← اسحب مجلد المشروع كامل.
   - ⚠️ المجلد المخفي `.github` أحياناً ما بينرفع بالسحب والإفلات. للتأكد: **Add file ← Create new file** واكتب المسار بنفسك `.github/workflows/invoices.yml` (كتابة `/` بتولّد المجلدات) والصق محتوى الملف من المشروع.
   - أو من التيرمنال: `git clone` الريبو، انسخ الملفات، ثم `git add . && git commit -m "invoice automation" && git push`.

### 5) أضف الـ Secrets

من إعدادات الريبو: **Settings ← Secrets and variables ← Actions ← New repository secret**:

| الاسم | القيمة |
|---|---|
| `YAHOO_USER` | بريدك الكامل `you@yahoo.com` |
| `YAHOO_APP_PASS` | كلمة السر من الخطوة 3 |
| `GCP_JSON` | **محتوى ملف الـ JSON كامل** (كل الأسطر، زي ما هو) |
| `SHEET_ID` | رقم الشيت من الخطوة 1 |
| `ANTHROPIC_API_KEY` | اختياري — من console.anthropic.com. اتركه فاضياً لوضع regex المجاني |

اختياري من تبويب **Variables** (نفس الصفحة): `ANTHROPIC_MODEL` (افتراضي `claude-sonnet-4-6`) و `LOOKBACK_DAYS` (افتراضي 60).

### 6) أول تشغيل

1. بتب الريبو ← تبويب **Actions** ← إذا طلب تفعيل اضغط **I understand my workflows, go ahead and enable them**.
2. من القائمة يسار اختر **invoices** ← زر **Run workflow** ← **Run workflow**.
3. افتح التشغيل وراقب الـ log — المفروض تشوف بسطر النهاية شي مثل:
   `[done] emails=42 new_rows=3 duplicates_skipped=1 ai_rows=0 needs_review=0`
4. افتح الشيت وتأكد إنو الصفوف انضافت وترتبت.

---

## الجدولة

- الوظيفة بتشتغل **كل ساعة** بالضبط (`cron: "0 * * * *"` بتوقيت **UTC** — بتوقيت بريطانيا نفس الشي شتاءً). تأخير دقايق أحياناً طبيعي.
- لتغيير التكرار: عدّل سطر الـ cron بملف `.github/workflows/invoices.yml` (مثلاً `"0 6 * * *"` = كل يوم 6 صباحاً UTC) ثم اعمل commit.
- ⚠️ **GitHub بيعطّل الجدولة تلقائياً إذا ما في أي نشاط بالريبو 60 يوماً** — بيبعتلك إيميل تنبيه. أي commit (أو إعادة تفعيل يدوية من Actions) بيرجّعها.
- كل تشغيل بيفحص آخر 60 يوم وبيتجاهل الصفوف الموجودة أصلاً (منع التكرار) — فما في أي ضرر لو اشتغل مرتين.

## أعمدة الشيت

| العمود | المعنى |
|---|---|
| Date | تاريخ الفاتورة (ISO `YYYY-MM-DD`)؛ إذا ما لقاه بيستخدم تاريخ الإيميل |
| Company | اسم الشركة — من الـ AI، أو اسم المرسل |
| Invoice No. | رقم الفاتورة (الأصفار البادئة محفوظة) |
| Amount / Currency | المبلغ (نقطة عشرية) والعملة (`USD`, `SEK`, `EUR`, `GBP`) |
| Sender / Subject | مرسل وعنوان الإيميل |
| Email Link | رابط بحث Yahoo بالـ Message-ID — بيفتح نتائج البحث مش الرسالة مباشرة (Yahoo ما إله رابط ثابت للرسالة) |
| **Key** | `Message-ID + اسم الملف` — **عمود منع التكرار، لا تحذفه ولا تعدّله** |
| Source | `regex` (مجاني كامل) / `ai` (استخدم الذكاء الاصطناعي) / `partial` (ناقص — راجعه يدوياً) |

## التكلفة

| البند | التكلفة |
|---|---|
| GitHub Actions (ريبو خاص، باقة Free) | مجاني ضمن 2000 دقيقة/شهر (استهلاكنا ≈ 45–90) |
| Google Sheets API + Service Account | مجاني تماماً بهالحجم |
| الاستخراج بـ regex | مجاني |
| الاستخراج بـ Claude AI (اختياري) | بضعة سنتات للفاتورة كحد أقصى (تقديري) — والغالبية بتمر عالـ regex مجاناً |

## استكشاف الأخطاء

| المشكلة | الحل |
|---|---|
| `LOGIN failed` | استخدم **App Password** مش كلمة السر العادية؛ تأكد إن التحقق بخطوتين مفعّل؛ ولّد كلمة جديدة وانتظر 10 دقائق |
| Google `PERMISSION_DENIED` (403) | ما شاركت الشيت مع إيميل الـ `client_email` بدور **Editor**، أو الـ `SHEET_ID` غلط |
| `Spreadsheet not found` | `SHEET_ID` غلط — خده من رابط الشيت |
| ما ينضاف صف جديد | (1) الصف موجود أصلاً (شوف عمود Key). (2) الإيميل فيه **رابط** للفاتورة مش مرفق PDF. (3) شوف الـ log سطر سطر |
| `Source = partial` | الـ regex والـ AI ما طلعوا كل البيانات — عدّل الصف يدوياً بالشيت، أو فعّل `ANTHROPIC_API_KEY` إذا مش مفعّل |
| تاب Sorted اختفى أو طلع فاضي | احذف التاب كامل — أول تشغيل للسكربت رح يعيد إنشائه بالمعادلة الصحيحة |
| تاريخ غلط (مثل `04/03`) | التواريخ الملتبسة بتفضّل صيغة يوم-أولاً (أوروبية)؛ صحّحها يدوياً — الأغلب واضح لأن أحد الرقمين أكبر من 12 |
| فاتورة ممسوحة (صورة) | الـ regex ما بيقراها — مفتاح Claude API بيحلها (بيقرأ الـ PDF المصوّر) |
| شركة جديدة دايماً `partial` | اعتمد عالـ AI، أو ضيف نمطها بقوائم الكلمات بأعلى `invoices.py` (`STRONG_TOTAL` / `INVNO_RE`) |
| الجدولة ما بتشتغل | تأكد إن الملفات عالفرع الرئيسي `main` وبالمسار الصحيح `.github/workflows/`؛ وتذكر قاعدة الـ 60 يوم |

## تخصيص

- **عملة جديدة**: ضيف سطر بقاموس `CURRENCY_MAP` بأعلى `invoices.py` (مثلاً `"\u20aa": "ILS"` أو `"dkr": "DKK"` — انتبه: `kr` حالياً = كرون سويدية).
- **نافذة الفحص**: غيّر `LOOKBACK_DAYS` من تبويب Variables (بدون تعديل كود).
- **مزود Yahoo/Gmail**: بيشتغل مع أي IMAP — للجيميل: `IMAP_HOST=imap.gmail.com` + App Password من حساب Google.
- **كثافة الفحص**: عدّل الـ cron بملف الـ workflow.

## الأمان

- الريبو **خاص** والقيم كلها بـ **GitHub encrypted secrets** (مشفّرة، ومستحيلة تظهر بالـ logs).
- ملف `.env` محلي محمي بـ `.gitignore` — ما بينرفع أبداً.
- مفتاح الـ Service Account صلاحياته محصورة بالشيتات اللي بتشاركها معه — شارك **شيت الفواتير بس**.
- إذا انسرّب مفتاح: احذفه من **IAM & Admin ← Service Accounts ← Keys** وولّد غيره.

## اختبار محلي بدون أي حسابات

```bash
python test_extraction.py          # يختبر منطق الاستخراج — 10 حالات (USD/SEK/EUR)
```

ولتشغيل السكربت كامل محلياً:

```bash
pip install -r requirements.txt
cp .env.example .env               # واملأ القيم
python invoices.py
```
