#!/usr/bin/env python3
"""
Invoice automation: Yahoo Mail (IMAP) -> Google Sheets.

Every run (scheduled hourly by GitHub Actions):

  1. Connects to Yahoo Mail via IMAP using an App Password.
  2. Scans the last LOOKBACK_DAYS days for emails carrying PDF attachments.
  3. Extracts date / company / invoice number / amount / currency from each PDF:
       - a general-purpose regex first (free, no API key needed);
       - if the regex cannot find BOTH the amount and the invoice number,
         the Claude API is used as a fallback (optional - set ANTHROPIC_API_KEY;
         it also reads scanned/image-only PDFs).
  4. Appends one row per PDF to the "Invoices" tab of a Google Sheet,
     de-duplicates by Message-ID + filename (the "Key" column, never delete it),
     sorts the tab by date and keeps a "Sorted" live-view tab in place
     (created automatically on the first run).

Environment / GitHub secrets:
    YAHOO_USER        Yahoo email address            (required)
    YAHOO_APP_PASS    Yahoo app password             (required)
    GCP_JSON          Google service-account JSON    (required)
    SHEET_ID          Google Sheet id from its URL   (required)
    ANTHROPIC_API_KEY Claude API key                 (optional)
    ANTHROPIC_MODEL   e.g. claude-sonnet-4-6         (optional)
    LOOKBACK_DAYS     days of history to scan        (optional, default 60)
    IMAP_HOST         default imap.mail.yahoo.com    (optional; works with Gmail too)

Local quick sanity check of the extraction logic (no accounts needed):
    python test_extraction.py
"""

import base64
import email
import imaplib
import io
import json
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from urllib.parse import quote

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def _load_dotenv(path=None):
    """Load a local .env file (if present) so the script can run outside CI."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

YAHOO_USER = os.environ.get("YAHOO_USER", "")
YAHOO_APP_PASS = os.environ.get("YAHOO_APP_PASS", "")
GCP_JSON = os.environ.get("GCP_JSON", "")
SHEET_ID = os.environ.get("SHEET_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.mail.yahoo.com")

try:
    LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS") or 60)
except ValueError:
    LOOKBACK_DAYS = 60

HEADERS = ["Date", "Company", "Invoice No.", "Amount", "Currency",
           "Sender", "Subject", "Email Link", "Key", "Source"]

# symbol / code -> ISO 4217.  Add your own (e.g. "\u20aa": "ILS") if needed.
CURRENCY_MAP = {
    "$": "USD", "\u00a3": "GBP", "\u20ac": "EUR",
    "\u20a9": "KRW",
    "kr": "SEK", "kronor": "SEK", "krona": "SEK",
    "usd": "USD", "eur": "EUR", "gbp": "GBP", "sek": "SEK",
}

# --------------------------------------------------------------------------
# Regex extraction (free tier - handles USD / EUR / GBP / SEK layouts)
# --------------------------------------------------------------------------

# "final amount" keywords, tried first (Swedish + English)
STRONG_TOTAL = re.compile(
    r"\b(?:att\s+betala|total(?:\s+amount)?\s+due|amount\s+due|balance\s+due|"
    r"grand\s+total|total\s+payable)\b", re.I)

# generic totals, tried only if no strong keyword produced a number
WEAK_TOTAL = re.compile(
    r"\b(?:totalt|total|summa|belopp|\u0627\u0644\u0645\u0628\u0644\u063a|"
    r"\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a|\u0627\u0644\u0627\u062c\u0645\u0627\u0644\u064a)\b", re.I)

# one number, optionally wrapped by a currency symbol or code
AMOUNT_RE = re.compile(
    r"(?P<pre>[\$\u00a3\u20ac\u20a9]|\bUSD\b|\bEUR\b|\bGBP\b|\bSEK\b|\bkr\b|\bKRW\b|\bJPY\b|\bkronor\b|\bkrona\b)?\s*"
    r"(?:(?P<groups>\d{1,3}(?:[.,\s\xa0]\d{3})+)(?:[.,](?P<dec1>\d{1,2}))?"
    r"|(?P<plain>\d+)[.,](?P<dec2>\d{1,2})"
    r"|(?P<int>\d+))"
    r"\s*(?P<post>[\$\u00a3\u20ac\u20a9]|\bUSD\b|\bEUR\b|\bGBP\b|\bSEK\b|\bkr\b|\bKRW\b|\bJPY\b|"
    r"\bkronor\b|\bkrona\b)?", re.I)

# "net 30", "within 30 days" -> not the amount we want
AFTER_AMOUNT_SKIP = re.compile(r"\s*(?:days?|dagar|net)\b", re.I)

INVNO_RE = re.compile(
    r"(?:invoice\s*(?:no\.?|number|#|id|nr\.?)|"
    r"\binv\b\s*[:#.-]?\s*|ref(?:erence)?\s*[:#.]?|"
    r"faktura\s*(?:nr\.?|nummer|no\.?))"
    r"[\s:#.\-]*"
    r"([A-Za-z0-9][A-Za-z0-9\-/_.]{2,})", re.I)

DATE_KW_STRONG = re.compile(
    r"fakturadatum|faktura\s*datum|invoice\s*date|date\s*of\s*issue|issue\s*date", re.I)
DATE_KW_WEAK = re.compile(r"\bdate\b|\bdatum\b", re.I)

_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_ISO_SLASH = re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b")
_DATE_DMY = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_DATE_D_MON = re.compile(r"\b(\d{1,2})\.?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b")
_DATE_MON_D = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b")

_MONTH_NAMES = [
    ("january", "januari", "jan"),
    ("february", "februari", "feb"),
    ("march", "mars", "mar"),
    ("april", "apr"),
    ("may", "maj"),
    ("june", "juni", "jun"),
    ("july", "juli", "jul"),
    ("august", "augusti", "aug"),
    ("september", "sept", "sep"),
    ("october", "oktober", "oct", "okt"),
    ("november", "nov"),
    ("december", "dec"),
]
MONTHS = {name: idx for idx, names in enumerate(_MONTH_NAMES, start=1) for name in names}


def _num_from(match):
    """Rebuild a clean dot-decimal amount string from an AMOUNT_RE match."""
    if match.group("groups"):
        whole = re.sub(r"\D", "", match.group("groups"))
        return f"{whole}.{match.group('dec1')}" if match.group("dec1") else whole
    if match.group("plain"):
        return f"{match.group('plain')}.{match.group('dec2')}"
    return match.group("int")


def _pick_amount(segment):
    """Pick the most plausible amount inside a text segment."""
    first_plain = None
    for m in AMOUNT_RE.finditer(segment):
        num = _num_from(m)
        if not num:
            continue
        inside_parens = (segment.count("(", 0, m.start())
                         > segment.count(")", 0, m.start()))
        if inside_parens:                       # e.g. "(varav moms 700,00 kr)"
            continue
        cur = m.group("post") or m.group("pre") or ""
        if cur:
            return num, CURRENCY_MAP.get(cur.lower(), cur.upper())
        if first_plain is None and not AFTER_AMOUNT_SKIP.match(segment[m.end():]):
            first_plain = (num, "")
    return first_plain


def extract_amount(text):
    """Return {'amount': '1234.56', 'currency': 'SEK'} or {}."""
    for keyword_rx in (STRONG_TOTAL, WEAK_TOTAL):
        for m in reversed(list(keyword_rx.finditer(text))):
            found = _pick_amount(text[m.end():m.end() + 80])
            if found:
                return {"amount": found[0], "currency": found[1]}
    return {}


def extract_invoice_no(text):
    m = INVNO_RE.search(text)
    return m.group(1).strip(".,-/ _") if m else ""


def _month(word):
    w = word.lower()
    return MONTHS.get(w) or MONTHS.get(w[:3])


def _first_date(segment):
    """First parseable date inside a segment (ISO, d/m/y, 13 maj 2024, May 13, 2024)."""
    for m in _DATE_ISO.finditer(segment):
        try:
            return datetime(int(m.group(1)), int(m.group(2)),
                            int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    for m in _DATE_ISO_SLASH.finditer(segment):
        try:
            return datetime(int(m.group(1)), int(m.group(2)),
                            int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    for m in _DATE_DMY.finditer(segment):
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12:                       # 13/05/2024 -> day first
            day, month = a, b
        elif b > 12:                     # 05/13/2024 -> month first (US style)
            day, month = b, a
        else:                            # ambiguous -> day first (European/Swedish)
            day, month = a, b
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            continue
    for m in _DATE_D_MON.finditer(segment):
        month = _month(m.group(2))
        if month:
            try:
                return datetime(int(m.group(3)), month,
                                int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    for m in _DATE_MON_D.finditer(segment):
        month = _month(m.group(1))
        if month:
            try:
                return datetime(int(m.group(3)), month,
                                int(m.group(2))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return ""


def extract_date(text):
    """Invoice date preferred over due date; falls back to the first date found."""
    for keyword_rx in (DATE_KW_STRONG, DATE_KW_WEAK):
        for m in keyword_rx.finditer(text):
            prefix = text[max(0, m.start() - 12):m.start()].lower()
            if "due" in prefix or "f\u00f6rfall" in prefix:   # due date / förfallodatum
                continue
            found = _first_date(text[m.end():m.end() + 45])
            if found:
                return found
    return _first_date(text)


def extract_regex(text):
    """All regex fields in one call. Keys: date, invoice_no, amount, currency."""
    out = {}
    if not text:
        return out
    out.update(extract_amount(text))
    invoice_no = extract_invoice_no(text)
    if invoice_no:
        out["invoice_no"] = invoice_no
    found = extract_date(text)
    if found:
        out["date"] = found
    return out


# --------------------------------------------------------------------------
# AI fallback (optional - only for PDFs the regex could not fully read)
# --------------------------------------------------------------------------

def extract_with_ai(pdf_bytes):
    """Ask Claude to read the PDF and return the same fields as JSON."""
    if not ANTHROPIC_API_KEY:
        return {}
    try:
        import anthropic
    except ImportError:
        print("  [ai] 'anthropic' package not installed - skipping AI fallback")
        return {}
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document",
                     "source": {"type": "base64", "media_type": "application/pdf",
                                "data": base64.b64encode(pdf_bytes).decode()}},
                    {"type": "text",
                     "text": ("Extract the invoice details. Return ONLY minified "
                              "JSON, no markdown, no explanations: "
                              '{"company":"","invoice_no":"","date":"YYYY-MM-DD",'
                              '"amount":"number only, dot as decimal separator",'
                              '"currency":"ISO 4217 code"}')},
                ],
            }])
        raw = (resp.content[0].text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        out = {}
        for key in ("company", "invoice_no", "date", "amount", "currency"):
            value = data.get(key)
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (int, float)):
                value = str(value)
            if isinstance(value, str) and value.strip():
                out[key] = value.strip()
        amount = re.sub(r"[\s\xa0]", "", out.get("amount", ""))
        if re.fullmatch(r"\d+,\d{1,2}", amount):     # "1234,56" -> "1234.56"
            amount = amount.replace(",", ".")
        if amount:
            out["amount"] = amount
        return out
    except Exception as exc:
        print("  [ai] extraction failed:", exc)
        return {}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def dh(value):
    """Decode a MIME header value safely."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _safe_text(value):
    """Prevent Google Sheets from interpreting a value as a formula."""
    value = (value or "").strip()
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def _keep_leading_zeros(value):
    """Force text type for purely numeric invoice numbers (keeps '0012')."""
    value = (value or "").strip()
    return "'" + value if value.isdigit() else value


def _col_letter(number):
    """1 -> A, 10 -> J, 27 -> AA (stdlib-only, for the sort range)."""
    letters = ""
    while number:
        number, rest = divmod(number - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


# --------------------------------------------------------------------------
# Google Sheet
# --------------------------------------------------------------------------

SORT_FORMULA = "=SORT('{name}'!A2:J,1,TRUE)"   # live view, created in Sheets


def open_sheet():
    """Connect to the spreadsheet. Returns (spreadsheet, worksheet)."""
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        json.loads(GCP_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    spreadsheet = gspread.authorize(creds).open_by_key(SHEET_ID)
    try:
        worksheet = spreadsheet.worksheet("Invoices")
    except Exception:
        worksheet = spreadsheet.get_worksheet(0)
    if not worksheet.get_all_values():
        worksheet.append_row(HEADERS)
    return spreadsheet, worksheet


def ensure_sorted_view(spreadsheet, data_tab):
    """Create (or repair) a 'Sorted' tab: a live view sorted by date.

    The formula is written inside Google Sheets, where =SORT always works
    (any locale). The script also sorts the data tab itself on every run,
    so this view is a convenience, never a dependency.
    """
    formula = SORT_FORMULA.format(name=data_tab.title)
    try:
        try:
            ws = spreadsheet.worksheet("Sorted")
            current = ws.acell("A1", value_render_option="FORMULA").value
            if current and str(current).startswith("="):
                return
        except Exception:                     # tab missing -> create it
            ws = spreadsheet.add_worksheet("Sorted", rows=5000, cols=12)
        ws.update("A1", [[formula]], value_input_option="USER_ENTERED")
        print("[sheet] 'Sorted' tab ready - live view sorted by date")
    except Exception as exc:
        print("[sheet] could not set up the 'Sorted' tab:", exc)


# --------------------------------------------------------------------------
# IMAP
# --------------------------------------------------------------------------

def fetch_invoice_rows(seen):
    """Return (new_rows, stats). Each new PDF attachment becomes one row."""
    stats = {"emails": 0, "dupes": 0, "ai": 0, "partial": 0}

    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(YAHOO_USER, YAHOO_APP_PASS)
    mail.select("INBOX")

    since = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
    status, data = mail.search(None, "SINCE", since)
    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status}")
    message_ids = data[0].split()
    stats["emails"] = len(message_ids)
    print(f"[imap] {len(message_ids)} message(s) in the last {LOOKBACK_DAYS} days")

    rows = []
    for num in message_ids:
        try:
            status, fetched = mail.fetch(num, "(BODY.PEEK[])")   # PEEK: keep unread state
            if status != "OK" or not fetched:
                continue
            raw = next((part[1] for part in fetched if isinstance(part, tuple)), None)
            if raw is None:
                continue
            msg = email.message_from_bytes(raw)
        except Exception as exc:
            print("  [imap] fetch failed:", exc)
            continue

        message_id = (msg.get("Message-ID") or "").strip()
        if not message_id:
            continue
        name, addr = parseaddr(dh(msg.get("From")))
        sender = f"{name} <{addr}>" if name else addr
        subject = dh(msg.get("Subject"))
        try:
            mail_date = parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d")
        except Exception:
            mail_date = ""
        # Yahoo has no stable "open this exact message" URL - use a search link
        link = "https://mail.yahoo.com/d/search/keyword=" + quote(message_id.strip("<>"))

        for part in msg.walk():
            filename = dh(part.get_filename())
            if not filename or not filename.lower().endswith(".pdf"):
                continue
            key = f"{message_id}|{filename}"
            if key in seen:
                stats["dupes"] += 1
                continue

            pdf_bytes = part.get_payload(decode=True)
            if not pdf_bytes:
                continue

            text = ""
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            except Exception as exc:
                print("  [pdf] parse failed:", exc)

            info = extract_regex(text)
            if info.get("amount") and info.get("invoice_no"):
                source = "regex"
            else:
                source = "partial"
                ai_info = extract_with_ai(pdf_bytes)
                if ai_info:
                    info = {**info, **{k: v for k, v in ai_info.items() if v}}
                    if info.get("amount") and info.get("invoice_no"):
                        source = "ai"
                        stats["ai"] += 1
            if source == "partial":
                stats["partial"] += 1

            company = info.get("company") or name or (addr.split("@")[-1] if addr else "")
            rows.append([
                info.get("date") or mail_date,
                _safe_text(company),
                _keep_leading_zeros(info.get("invoice_no", "")),
                info.get("amount", ""),
                info.get("currency", ""),
                _safe_text(sender),
                _safe_text(subject),
                link,
                key,
                source,
            ])
            seen.add(key)
            print(f"  [new] {info.get('date') or mail_date} | {company} | "
                  f"no={info.get('invoice_no', '')} | {info.get('amount', '')} "
                  f"{info.get('currency', '')} | [{source}] {filename}")

    try:
        mail.close()
    finally:
        mail.logout()
    return rows, stats


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    required = {"YAHOO_USER": YAHOO_USER, "YAHOO_APP_PASS": YAHOO_APP_PASS,
                "GCP_JSON": GCP_JSON, "SHEET_ID": SHEET_ID}
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise SystemExit("Missing required secrets/env vars: " + ", ".join(missing))

    ai_mode = f"ON ({ANTHROPIC_MODEL})" if ANTHROPIC_API_KEY else "OFF (regex only)"
    print(f"[config] imap={IMAP_HOST} lookback={LOOKBACK_DAYS}d ai={ai_mode}")

    spreadsheet, worksheet = open_sheet()
    ensure_sorted_view(spreadsheet, worksheet)
    seen = set(worksheet.col_values(9))
    print(f"[sheet] connected - {len(seen)} existing key(s)")

    rows, stats = fetch_invoice_rows(seen)

    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        try:
            header_width = len(worksheet.row_values(1)) or len(HEADERS)
            last_col = _col_letter(header_width)
            total_rows = len(worksheet.col_values(1))
            worksheet.sort((1, "asc"), range=f"A2:{last_col}{max(total_rows, 2)}")
            print(f"[sheet] sorted by date (A2:{last_col}{max(total_rows, 2)})")
        except Exception as exc:
            print("[sheet] sort skipped:", exc)

    print(f"[done] emails={stats['emails']} new_rows={len(rows)} "
          f"duplicates_skipped={stats['dupes']} ai_rows={stats['ai']} "
          f"needs_review={stats['partial']}")


if __name__ == "__main__":
    main()
