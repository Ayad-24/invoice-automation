# 🧾 Invoice Automation: Yahoo Mail → Google Sheets

PDF invoices arriving at your Yahoo address file themselves: the script reads
your mailbox, extracts the **date, company, invoice number, amount and
currency** from each invoice, adds a link back to the email, and appends one
sorted, de-duplicated row per PDF to a Google Sheet — no laptop left running.

**[الدليل العربي الكامل](README_AR.md) | English guide (this file)**

```
Yahoo Mail (IMAP + App Password)
        │
        ▼  GitHub Actions — runs every hour
invoices.py
        │  1) free general-purpose regex ($ / kr / € / £, Swedish number formats)
        │  2) missing amount or invoice number? → Claude AI reads the PDF (optional)
        ▼
Google Sheet «Invoices» (append + de-duplicate + sort by date)
        └─ a «Sorted» tab is created automatically - live =SORT view inside Google Sheets
```

## Why Python + GitHub Actions?

- **Completely free**: the GitHub Free tier includes 2,000 min/month for
  private repos; this job uses ~1–2 minutes, i.e. ~45–90 min/month when hourly.
- **No operation limits** (Make.com free is 1,000 ops/month ≈ 100 invoices).
- **Scheduled with no machine running**, plus a manual run button.

## Repository contents

| File | Purpose |
|---|---|
| `invoices.py` | Main script: IMAP → extraction → Google Sheet |
| `test_extraction.py` | Offline extraction tests, no accounts needed: `python test_extraction.py` |
| `requirements.txt` | Python dependencies |
| `.github/workflows/invoices.yml` | Hourly schedule + manual trigger |
| `template/invoice_template.xlsx` | Ready-to-import Google Sheet template |
| `sample/sample_invoice.pdf` | Fake invoice used by the tests |
| `.env.example` | Template for local runs |
| `HANDOVER_EN.md` | 🤝 Handover guide — for when you build this for **someone else** to use |

## Prerequisites

- A **Yahoo** account (can generate App Passwords — requires 2-step verification).
- A **Google** account (Google Sheets + free Google Cloud project).
- A **GitHub** account (free tier is enough).
- Optional: an **Anthropic API key** from <https://console.anthropic.com> for
  invoices the regex can't parse and scanned/image-only PDFs. A few cents per
  invoice at most (estimate); most invoices go through the free regex path.

---

## Setup (once)

### 1) Prepare the Google Sheet

1. Go to <https://drive.google.com> → **New → File upload** → upload `template/invoice_template.xlsx`.
2. Right-click the file → **Open with → Google Sheets** (or open it, then **File → Save as Google Sheets**).
3. You get one tab, **Invoices** — the 10-column data table (it contains one
   example row; delete it whenever you like).
   - The **Sorted** tab (live view sorted by date) is **created automatically
     on the script's first run**, inside Google Sheets itself, with a live
     `=SORT` formula — no manual step, works in any locale.
4. Copy the **SHEET_ID** from the sheet URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`.

> Manual alternative: create a blank sheet and type the same ten headers in
> row 1, in order: `Date, Company, Invoice No., Amount, Currency, Sender,
> Subject, Email Link, Key, Source` (name the first tab `Invoices`).

### 2) Google Cloud: service account (write access to the sheet)

1. Open <https://console.cloud.google.com> and create a new project (e.g. `invoice-automation`) — free.
2. Menu ☰ → **APIs & Services → Library** → search **Google Sheets API** → **Enable**.
3. ☰ → **IAM & Admin → Service Accounts** → **Create service account** (e.g. `sheet-writer`; no role needed).
4. Open it → **Keys** tab → **Add key → Create new key → JSON**. A JSON file downloads — **treat it like a password**.
5. Open the JSON and copy the **`client_email`** value (`xxx@project.iam.gserviceaccount.com`).
6. In your invoice sheet: **Share** → paste that email → role **Editor**.

### 3) Yahoo: app password

1. Go to <https://login.yahoo.com/account/security>. Enable **two-step
   verification** first if it is off (required for app passwords).
2. Click **Generate app password** (or Manage app passwords) → name it e.g.
   `github-invoices` → **Generate**.
3. Copy the 16-character password. If login later fails, wait 10 minutes or
   generate a new one.

### 4) Upload the project to GitHub

1. Create a new **Private** repository.
2. Upload the files: **Add file → Upload files** → drag the whole project folder.
   - ⚠️ The hidden `.github` folder sometimes doesn't survive drag & drop.
     To be safe use **Add file → Create new file**, type
     `.github/workflows/invoices.yml` (typing `/` creates the folders) and
     paste the file contents.
   - Or from a terminal: `git clone` the repo, copy the files in, then
     `git add . && git commit -m "invoice automation" && git push`.

### 5) Add the secrets

Repo **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `YAHOO_USER` | your full email `you@yahoo.com` |
| `YAHOO_APP_PASS` | the password from step 3 |
| `GCP_JSON` | the **entire JSON file contents** (all lines, as-is) |
| `SHEET_ID` | the sheet id from step 1 |
| `ANTHROPIC_API_KEY` | optional — leave empty for free regex-only mode |

Optional **Variables** (same page): `ANTHROPIC_MODEL` (default
`claude-sonnet-4-6`) and `LOOKBACK_DAYS` (default 60).

### 6) First run

1. Repo → **Actions** tab → if prompted, click **I understand my workflows, go ahead and enable them**.
2. Select **invoices** on the left → **Run workflow** → **Run workflow**.
3. Open the run and check the log — the final line looks like:
   `[done] emails=42 new_rows=3 duplicates_skipped=1 ai_rows=0 needs_review=0`
4. Open the sheet and confirm the rows arrived sorted.

---

## Scheduling

- The job runs **hourly** (`cron: "0 * * * *"`, in **UTC**; a few minutes of
  delay is normal).
- To change it, edit the cron line in `.github/workflows/invoices.yml`
  (e.g. `"0 6 * * *"` = daily at 06:00 UTC) and commit.
- ⚠️ **GitHub disables schedules in repositories with no activity for 60
  days** (you get a warning email). Any commit — or a manual re-enable under
  Actions — brings it back.
- Every run rescans the last 60 days and skips rows already present, so
  double runs are harmless.

## Sheet columns

| Column | Meaning |
|---|---|
| Date | invoice date (ISO `YYYY-MM-DD`); falls back to the email date |
| Company | from the AI, or the sender's display name |
| Invoice No. | leading zeros preserved |
| Amount / Currency | dot-decimal amount and ISO code (`USD`, `SEK`, `EUR`, `GBP`) |
| Sender / Subject | email sender and subject |
| Email Link | Yahoo search link built from the Message-ID — it opens the search results, not the exact message (Yahoo has no stable per-message URL) |
| **Key** | `Message-ID + filename` — **the de-duplication key: never delete or edit it** |
| Source | `regex` (free, complete) / `ai` (AI was used) / `partial` (incomplete — review manually) |

## Cost

| Item | Cost |
|---|---|
| GitHub Actions (private repo, Free plan) | free within 2,000 min/month (we use ~45–90) |
| Google Sheets API + service account | free at this scale |
| Regex extraction | free |
| Claude AI fallback (optional) | a few cents per invoice at most (estimate) — most invoices stay on the free regex path |

## Troubleshooting

| Problem | Fix |
|---|---|
| `LOGIN failed` | use the **app password**, not your normal password; make sure 2-step verification is on; regenerate and wait 10 minutes |
| Google `PERMISSION_DENIED` (403) | share the sheet with the `client_email` as **Editor**, or fix `SHEET_ID` |
| `Spreadsheet not found` | wrong `SHEET_ID` — copy it from the sheet URL |
| No new rows | (1) the row already exists (check the Key column). (2) the email links to the invoice instead of attaching a PDF. (3) read the run log line by line |
| `Source = partial` | regex + AI couldn't get everything — fix the row manually, or set `ANTHROPIC_API_KEY` if missing |
| Sorted tab missing or empty | delete the whole tab — the next script run recreates it with the right formula |
| Wrong date (`04/03/2024`) | ambiguous dates default to day-first (European); correct manually — most dates are unambiguous (one number > 12) |
| Scanned (image) PDF | the regex can't read it — a Claude API key solves it (it reads image PDFs) |
| One vendor always `partial` | rely on the AI, or add its wording to the keyword lists at the top of `invoices.py` (`STRONG_TOTAL` / `INVNO_RE`) |
| Schedule not running | files must be on the default branch at `.github/workflows/`; remember the 60-day inactivity rule |

## Customising

- **New currency**: add a line to `CURRENCY_MAP` at the top of `invoices.py`
  (e.g. `"\u20aa": "ILS"`; note `kr` currently means Swedish krona).
- **Scan window**: change `LOOKBACK_DAYS` via repository Variables (no code edit).
- **Yahoo/Gmail/other**: works with any IMAP provider — for Gmail set
  `IMAP_HOST=imap.gmail.com` plus a Google app password.
- **Frequency**: edit the cron expression in the workflow file.

## Security

- Keep the repo **private**; all credentials live in **GitHub encrypted
  secrets** (masked in logs).
- A local `.env` is covered by `.gitignore` and never committed.
- The service-account key can only touch the sheets you share with it —
  share only the invoice sheet.
- If a key leaks: delete it under **IAM & Admin → Service Accounts → Keys**
  and create a fresh one.

## Local testing (no accounts needed)

```bash
python test_extraction.py          # 10 extraction cases (USD/SEK/EUR)
```

Full local run:

```bash
pip install -r requirements.txt
cp .env.example .env               # then fill it in
python invoices.py
```
