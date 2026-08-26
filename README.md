# Sync WOW Sheets — GitHub Actions Cron

Mirrors the `Student-Assign-WOW` tab from one Google Sheet into the
same-named tab of another, on a schedule.

- Source: `1-ZiZ5gyYKWK49GuFqqIDNobIr60Gek7DLsmfAhHbmTQ`
- Destination: `1knzRvmPqhvSudEJeXksQeXSZklAybIBfd_IMH7XLMK4`

## Files

```
.
├── .github/workflows/sync-wow-sheets.yml
├── sync_sheets.py
├── requirements.txt
└── README.md
```

## One-time setup

### 1. Google service account

If you already have one set up for another pipeline (e.g.
`Assignment_Pipeline_Automation.py`), you can reuse the same service
account and the same `SERVICE_ACCOUNT_JSON` secret — no need to create a
second one.

If starting fresh:
1. [Google Cloud Console](https://console.cloud.google.com/) → **IAM & Admin
   → Service Accounts → Create Service Account**.
2. Enable the **Google Sheets API** and **Google Drive API** for the project.
3. **Keys → Add Key → Create new key → JSON** — the full contents of this
   file become the `SERVICE_ACCOUNT_JSON` secret below.
4. **Share both the source and destination sheets** with the service
   account's email (`client_email` in the JSON) as **Editor**. Both need
   sharing — this script reads from one and writes to the other.

### 2. Add the GitHub repo secret

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret name            | Value                                   |
|--------------------------|------------------------------------------|
| `SERVICE_ACCOUNT_JSON`   | Full contents of the service account JSON |

### 3. Push these files

Commit `sync_sheets.py`, `requirements.txt`, and
`.github/workflows/sync-wow-sheets.yml` to your default branch.

## Scheduling

Default: every 4 hours, offset by 30 minutes (`30 */4 * * *`, always UTC).

**If this sync should run right after `Assignment_Pipeline_Automation.py`
updates the source sheet, and both live in the same repo**, swap the
`schedule:` trigger for a `workflow_run:` trigger — the workflow file has
the exact block commented in, ready to uncomment. This makes the sync fire
automatically right after that pipeline finishes, instead of guessing at a
time offset that might drift out of sync later.

**Manually**: **Actions** tab → **Sync WOW Sheets** → **Run workflow**.

## What the sync does

- Reads the *entire* `Student-Assign-WOW` tab from the source sheet
  (values as displayed — formulas are evaluated to their computed result,
  not copied as formulas).
- Clears the destination tab and writes an exact copy.
- Trims fully-empty trailing rows/columns so you don't end up with a huge
  block of blank cells past the real data.
- No filtering or transformation — this is a straight mirror. If you ever
  need the destination to be a *filtered* or *transformed* view instead of
  an exact copy, that logic would need to be added here.

## If a run fails

- **`SpreadsheetNotFound`** → the sheet ID is wrong, or it hasn't been
  shared with the service account (the error names the exact email to add).
- **`Tab 'Student-Assign-WOW' not found`** → the error lists the tabs that
  actually exist in that sheet, so you can check for a naming mismatch
  (extra space, different casing, etc.).
