#!/usr/bin/env python3
"""
Sync a tab from one Google Sheet into the same-named tab of another.

Source: https://docs.google.com/spreadsheets/d/1-ZiZ5gyYKWK49GuFqqIDNobIr60Gek7DLsmfAhHbmTQ  (tab: Student-Assign-WOW)
Dest:   https://docs.google.com/spreadsheets/d/1knzRvmPqhvSudEJeXksQeXSZklAybIBfd_IMH7XLMK4  (tab: Student-Assign-WOW)

Copies the source tab's full contents (values only — as displayed, not raw
formulas) into the destination tab, clearing it first so the destination is
an exact mirror of the source each run. No filtering/transformation — this
is a straight copy.

Auth: a Google service account, same as the other pipelines in this repo.
Both sheets must be shared with the service account's email as Editor.
"""

import os
import sys
import json
import time
import traceback

import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials

start_time = time.time()

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG — edit these if the source/destination sheet or tab ever changes
# ═══════════════════════════════════════════════════════════════════════════
SOURCE_SHEET_ID = "1-ZiZ5gyYKWK49GuFqqIDNobIr60Gek7DLsmfAhHbmTQ"
SOURCE_TAB_NAME = "Student-Assign-WOW"

DEST_SHEET_ID = "1knzRvmPqhvSudEJeXksQeXSZklAybIBfd_IMH7XLMK4"
DEST_TAB_NAME = "Student-Assign-WOW"

# ═══════════════════════════════════════════════════════════════════════════
# ENV & AUTH
# ═══════════════════════════════════════════════════════════════════════════
service_account_json = os.getenv("SERVICE_ACCOUNT_JSON")
if not service_account_json:
    raise ValueError("❌ Missing environment variable: SERVICE_ACCOUNT_JSON")

service_info = json.loads(service_account_json)
creds = Credentials.from_service_account_info(
    service_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
gc = gspread.authorize(creds)


def safe_open_by_key(key, label=""):
    try:
        return gc.open_by_key(key)
    except gspread.exceptions.SpreadsheetNotFound:
        raise RuntimeError(
            f"❌ Could not open {label or 'sheet'} with key '{key}'. Share it with "
            f"this service account as Editor: {service_info.get('client_email')}"
        )


def safe_worksheet(sheet, tab_name, label=""):
    try:
        return sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        available = [ws.title for ws in sheet.worksheets()]
        raise RuntimeError(
            f"❌ Tab '{tab_name}' not found in {label or 'sheet'}. "
            f"Tabs actually present: {available}"
        )


print("🔎 ENV CHECK")
print(f"   SA client_email : {service_info.get('client_email')}")
print(f"   Source          : {SOURCE_SHEET_ID} / '{SOURCE_TAB_NAME}'")
print(f"   Destination     : {DEST_SHEET_ID} / '{DEST_TAB_NAME}'")

try:
    # ── READ SOURCE ─────────────────────────────────────────────────
    source_sheet = safe_open_by_key(SOURCE_SHEET_ID, "source sheet")
    source_ws = safe_worksheet(source_sheet, SOURCE_TAB_NAME, "source sheet")

    df = get_as_dataframe(source_ws, evaluate_formulas=True, dtype=str)
    # get_as_dataframe pads to the sheet's full grid size — drop fully-empty
    # trailing rows/columns so we don't write a huge block of blanks.
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    print(f"✓ Read {len(df)} rows, {len(df.columns)} columns from source")

    # ── WRITE DESTINATION ────────────────────────────────────────────
    dest_sheet = safe_open_by_key(DEST_SHEET_ID, "destination sheet")
    dest_ws = safe_worksheet(dest_sheet, DEST_TAB_NAME, "destination sheet")

    dest_ws.clear()
    set_with_dataframe(dest_ws, df, include_index=False, include_column_header=True)
    print(f"✅ Synced {len(df)} rows, {len(df.columns)} columns to destination")

except Exception as e:
    print(f"❌ Sync failed: {e}")
    traceback.print_exc()
    sys.exit(1)

mins, secs = divmod(time.time() - start_time, 60)
print(f"\n🎯 Sheet sync completed in {int(mins)}m {int(secs)}s")
sys.exit(0)
