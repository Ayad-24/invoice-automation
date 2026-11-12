#!/usr/bin/env python3
"""
Offline sanity check for the extraction logic in invoices.py.

Needs NO accounts and NO third-party packages (the PDF case is skipped
automatically when pdfplumber is not installed).

    python test_extraction.py
"""
import os
import sys

from invoices import extract_regex

CASES = [
    ("US invoice: $ + month/day date",
     "Invoice No: INV-2024-0157\nInvoice Date: 05/13/2024\n"
     "Amount Due: $1,234.56\nPlease pay promptly.",
     {"invoice_no": "INV-2024-0157", "amount": "1234.56",
      "currency": "USD", "date": "2024-05-13"}),

    ("Swedish invoice: kr + space thousands",
     "Fakturanummer: 2024-456789\nFakturadatum 2024-05-13\n"
     "Totalt att betala: 12 345,67 kr\nMoms 25%: 2 469,13 kr",
     {"invoice_no": "2024-456789", "amount": "12345.67",
      "currency": "SEK", "date": "2024-05-13"}),

    ("Swedish month name (maj)",
     "Faktura nr: 9912\nFakturadatum: 13 maj 2024\nAtt betala: 1 024,00 SEK",
     {"invoice_no": "9912", "amount": "1024.00",
      "currency": "SEK", "date": "2024-05-13"}),

    ("Subtotal/VAT ignored, Totalt wins",
     "Subtotal: 900,00 kr\nMoms: 225,00 kr\nTotalt: 1 125,00 kr\n"
     "Invoice number: 55231",
     {"amount": "1125.00", "currency": "SEK", "invoice_no": "55231"}),

    ("Balance due with currency code",
     "Invoice # 445566\nBalance Due: USD 99.00\nInvoice Date: 2024-05-13",
     {"invoice_no": "445566", "amount": "99.00",
      "currency": "USD", "date": "2024-05-13"}),

    ("EUR with dot thousands + comma decimals",
     "Invoice Number: AB-123\nInvoice Date: 2024-05-13\nGrand Total: \u20ac2.499,00",
     {"invoice_no": "AB-123", "amount": "2499.00",
      "currency": "EUR", "date": "2024-05-13"}),

    ("KRW with comma decimal + won symbol",
     "Invoice No: 900\nInvoice Date: 2024-05-13\nAmount Due: 1.250,50 \u20a9\nTotal: 1250,50",
     {"invoice_no": "900", "amount": "1250.50", "currency": "KRW", "date": "2024-05-13"}),

    ("KRW with word code",
     "Invoice No: 901\nInvoice Date: 2024-05-13\nAmount Due: KRW 1250.50",
     {"invoice_no": "901", "amount": "1250.50", "currency": "KRW", "date": "2024-05-13"}),

    ("Amount in parentheses (varav moms) skipped",
     "Fakturanummer: 880077\nFakturadatum: 2024-05-13\n"
     "Att betala: 3 500,00 kr (varav moms 700,00 kr)",
     {"invoice_no": "880077", "amount": "3500.00",
      "currency": "SEK", "date": "2024-05-13"}),

    ("'total ... days' trap",
     "Invoice No: TRAP-1\nInvoice Date: 2024-05-13\n"
     "Total due in 30 days: $420.00",
     {"invoice_no": "TRAP-1", "amount": "420.00",
      "currency": "USD", "date": "2024-05-13"}),

    ("Invoice date preferred over due date",
     "Invoice No: DUE-9\nDue Date: 2024-06-12\nInvoice Date: 2024-05-13\n"
     "Total Due: $50.00",
     {"invoice_no": "DUE-9", "amount": "50.00",
      "currency": "USD", "date": "2024-05-13"}),

    ("INV number + slash-separated date",
     "Invoice No: 12345\nInvoice Date: 2024/05/13\nAmount: 100.00 USD",
     {"invoice_no": "12345", "date": "2024-05-13"}),

    ("Bare 'inv' keyword",
     "Inv: 100\nInvoice Date: 2024-06-01\nTotal Due: $50.00",
     {"invoice_no": "100", "amount": "50.00", "currency": "USD", "date": "2024-06-01"}),

    ("'Ref' keyword",
     "Ref: F-901\nInvoice Date: 2024-07-04\nTotal Due: $50.00",
     {"invoice_no": "F-901", "amount": "50.00", "currency": "USD", "date": "2024-07-04"}),
]


def run_text_cases():
    ok = True
    for title, text, expected in CASES:
        got = extract_regex(text)
        wrong = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
        status = "PASS" if not wrong else "FAIL"
        ok = ok and not wrong
        print(f"[{status}] {title}")
        if wrong:
            print(f"       expected: {expected}")
            print(f"       got     : {got}")
    return ok


def run_pdf_case():
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        print("[SKIP] pdfplumber not installed - sample PDF case skipped")
        return True
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sample", "sample_invoice.pdf")
    if not os.path.exists(path):
        print("[SKIP] sample/sample_invoice.pdf not found")
        return True
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    expected = {"invoice_no": "SAMPLE-2024-042", "amount": "1250.50",
                "currency": "USD", "date": "2024-05-13"}
    got = extract_regex(text)
    wrong = {k: (got.get(k), v) for k, v in expected.items() if got.get(k) != v}
    print(("[PASS]" if not wrong else "[FAIL]") + " sample PDF (sample/sample_invoice.pdf)")
    if wrong:
        print(f"       expected: {expected}")
        print(f"       got     : {got}")
    return not wrong


if __name__ == "__main__":
    success = run_text_cases() and run_pdf_case()
    print("\nALL TESTS PASSED" if success else "\nSOME TESTS FAILED")
    sys.exit(0 if success else 1)
