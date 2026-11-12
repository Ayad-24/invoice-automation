# 🤝 Handover Guide — Building This for Someone Else

This guide is for **you** (the person who set the project up) when **someone
else** will actually use it: a friend, a client, a family member, anyone who
wants their invoices to organise themselves.

**The golden rule: not a single line of code changes.** The whole project is
driven by 5 values (secrets) — whoever's Yahoo email and app password go into
the secrets, that's whose mailbox gets scanned and whose sheet gets written.
The "other person" enters the equation through **configuration**, never code.

For the full technical setup steps see **[README_EN.md](README_EN.md)**
(Arabic: [README_AR.md](README_AR.md)).

---

## Before you start: ask them 3 questions

| Question | Why it matters |
|---|---|
| Is their mailbox Yahoo or something else? | The project ships ready for Yahoo. Gmail works too: set `IMAP_HOST=imap.gmail.com` plus a Google app password |
| Do they want the Claude AI key? | No key = free regex-only mode (enough for most invoices). With a key = wider coverage at a few cents — who pays, you or them? |
| Who owns the Sheet? | Decides which of the two scenarios below fits you |

---

## Scenario 1 (recommended): they own everything

Works when the person can follow the setup guide themselves (or with you
walking them through it on a call):

**You hand over:**
- The complete project folder (or the ZIP) — it contains **no credentials**.
- The guide: `README_EN.md`.

**They do, on their own accounts** (same steps as the setup guide):
- Their own GitHub repo + the 5 secrets under **their** account.
- An app password from **their own** Yahoo.
- Their own Google Cloud project + sheet.

**Result:** every credential stays in their account, you never see any of
their mail, and you carry no maintenance duty. If something breaks, they read
the logs (or ask you for a favour).

---

## Scenario 2: you run it on their behalf (for a non-technical person)

They only want the result (a tidy sheet with links back to the invoices);
you manage all the technology.

### What you need from them (once)

1. **An app password from *their* Yahoo** — never ask for their real password.
   They generate it themselves in two steps:
   - <https://login.yahoo.com/account/security> → enable **two-step
     verification** first if it's off.
   - **Generate app password** → name it e.g. `invoices` → **Generate** → copy
     the 16 characters.
   - 📌 Ask them to send it securely (in person or via a password manager —
     not a plain chat message).
2. **The sheet** — pick one of two options:
   - **(a) Best — the sheet lives in their account:** they upload
     `template/invoice_template.xlsx` to their own Drive, open it as Google
     Sheets (step 1 of the setup guide), then share it with **your service
     account email** (the `client_email` inside *your* `GCP_JSON`) as
     **Editor**. Their data stays theirs, and they can revoke you with one
     click if you ever part ways.
   - **(b) Easiest — the sheet lives in your account:** you create it from
     the template in your account and share it with them as **Editor**. They
     just get a link. But remember: the sheet stays yours.

### What you do

- In the secrets (on **a repo you own**):
  - `YAHOO_USER` = **their** full email address.
  - `YAHOO_APP_PASS` = the app password they generated.
  - `GCP_JSON` = **your** service-account JSON (that's why the sheet must be
    shared with *your* client_email).
  - `SHEET_ID` = the agreed sheet (option a or b above).
  - `ANTHROPIC_API_KEY` = your key (your cost) — or leave empty for the free
    regex-only mode.
- **Optional:** add them as a **collaborator** on the repo (Settings ←
  Collaborators) so they can read the logs and press the manual run button
  themselves, without ever touching a credential.

### Long-term duties (yours)

- The **60-day inactivity notice** (GitHub disabling schedules) goes to
  **you**, because the repo is yours. Any small commit every ~45 days keeps
  the schedule alive — set yourself a reminder.
- Any code or schedule change goes through you.
- Each installation serves **one mailbox** — a second person needs a separate
  repo/run.
- They can migrate to Scenario 1 anytime: same folder, their accounts.

### Security, honestly

- An app password **grants full read access to the mailbox over IMAP** — so
  only hand one to someone you trust. On your side: the script only reads
  (and uses `BODY.PEEK`, so it never flips any email's read/unread state),
  but the credential itself is powerful.
- **The kill switch:** they can revoke the app password at any moment from
  the same security page (Manage app passwords → delete) — instant cutoff,
  without changing their real password.
- GitHub secrets are encrypted and never appear in logs.

---

## After handover: their daily use

(You can copy this section and send it to them as-is)

- There is nothing to do — they just open the sheet; rows arrive and sort
  themselves every hour.
- Once a month (or when they spot a coloured row): review rows whose `Source`
  says `partial` and complete them manually — a rare exception, not the rule.
- **Never delete the `Key` column** or edit its values (it's the
  de-duplication key).
- Don't delete the `Sorted` tab — if it disappears by accident, the next run
  recreates it automatically.
- If the schedule stops or an error appears: come back to you (Scenario 2) or
  follow the troubleshooting table in the setup guide (Scenario 1).

---

## Ready-made handover checklist (copy and use)

**You (the builder):**
- [ ] Tested the project before handing it over (at least one manual run from the Actions tab).
- [ ] Handed over the full project folder with **zero credentials inside** (check: no `.env`, no JSON key of yours).
- [ ] Agreed on the scenario (1 or 2) and on who owns the sheet.
- [ ] Scenario 2: put *their* values in the secrets, and *yours* (GCP_JSON, AI key) where they belong.
- [ ] Scenario 2: added a monthly calendar reminder to commit (the 60-day rule).

**They (the end user):**
- [ ] Generated an app password from their own Yahoo (never shared their real password with anyone).
- [ ] Sheet created and shared correctly (with the builder's client_email under Scenario 2-a).
- [ ] Saw the sheet after the first run and confirmed rows are arriving.
- [ ] Knows who to contact when something breaks (you, or the troubleshooting table).
