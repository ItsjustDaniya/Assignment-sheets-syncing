#!/usr/bin/env python3
"""Mirror displayed cell values between Google Sheets in bounded requests."""
import os
import sys
import json
import time
import random
import traceback
import gspread
from gspread.exceptions import APIError
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials
from requests.exceptions import ConnectionError, Timeout

SOURCE_SHEET_ID = '1-ZiZ5gyYKWK49GuFqqIDNobIr60Gek7DLsmfAhHbmTQ'
DEST_SHEET_ID = '1knzRvmPqhvSudEJeXksQeXSZklAybIBfd_IMH7XLMK4'
SOURCE_TAB_NAME = DEST_TAB_NAME = 'Student-Assign-WOW'
CHUNK_ROWS = 1000
CELL_LIMIT = 10_000_000
MAX_BYTES = 1_500_000
last_request = 0.0


def retry(fn):
    global last_request
    for attempt in range(7):
        time.sleep(max(0, 1.2 - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        try:
            return fn()
        except (APIError, ConnectionError, Timeout) as exc:
            if isinstance(exc, APIError) and exc.response.status_code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 6:
                raise
            delay = min(120, 5 * 2**attempt) + random.random()
            print(f'API request failed; retrying in {delay:.1f}s: {exc}', flush=True)
            time.sleep(delay)


def write_rows(ws, start, values, cols):
    if not values:
        return
    if len(values) > 1 and len(json.dumps(values, ensure_ascii=True).encode('utf-8')) > MAX_BYTES:
        mid = len(values) // 2
        write_rows(ws, start, values[:mid], cols)
        write_rows(ws, start + mid, values[mid:], cols)
        return
    target = f'A{start}:{rowcol_to_a1(start + len(values) - 1, cols)}'
    retry(lambda: ws.update(range_name=target, values=values, value_input_option='RAW'))


def main():
    started = time.monotonic()
    raw = os.environ.get('SERVICE_ACCOUNT_JSON')
    if not raw:
        raise RuntimeError('Missing SERVICE_ACCOUNT_JSON')
    info = json.loads(raw)
    gc = gspread.authorize(Credentials.from_service_account_info(info, scopes=[
        'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']))
    print(f"Service account: {info.get('client_email')}", flush=True)
    src = retry(lambda: gc.open_by_key(SOURCE_SHEET_ID))
    dst = retry(lambda: gc.open_by_key(DEST_SHEET_ID))
    sw = retry(lambda: src.worksheet(SOURCE_TAB_NAME))
    dw = retry(lambda: dst.worksheet(DEST_TAB_NAME))
    # Read before modifying destination; retain interior blank rows and columns.
    blocks = []
    rows = cols = 0
    for start in range(1, sw.row_count + 1, CHUNK_ROWS):
        end = min(sw.row_count, start + CHUNK_ROWS - 1)
        area = f'A{start}:{rowcol_to_a1(end, sw.col_count)}'
        values = retry(lambda: sw.get(area, value_render_option='FORMATTED_VALUE'))
        for i, row in enumerate(values):
            used = max((j+1 for j, v in enumerate(row) if v not in ('', None)), default=0)
            if used:
                rows = max(rows, start+i)
                cols = max(cols, used)
        blocks.append((start, values))
        print(f'Read source rows {start:,}-{end:,}', flush=True)
    if not rows or not cols:
        raise RuntimeError('Source is empty; destination left unchanged for safety.')
    old_rows, old_cols = dw.row_count, dw.col_count
    others = sum(w.row_count*w.col_count for w in retry(dst.worksheets) if w.id != dw.id)
    new_rows, new_cols = max(rows, old_rows), max(cols, old_cols)
    projected = others + new_rows*new_cols
    print(f'Source: {rows:,} rows x {cols} columns; projected workbook: {projected:,} cells', flush=True)
    if projected > CELL_LIMIT:
        raise RuntimeError(f'Workbook would exceed {CELL_LIMIT:,} cells. Reduce unused grid dimensions or other tabs before retrying. Destination unchanged.')
    if (new_rows, new_cols) != (old_rows, old_cols):
        retry(lambda: dw.resize(rows=new_rows, cols=new_cols))
    for start, values in blocks:
        if start > rows:
            break
        n = min(CHUNK_ROWS, rows-start+1)
        padded = []
        for i in range(n):
            row = list(values[i][:cols]) if i < len(values) else []
            padded.append(row + ['']*(cols-len(row)))
        write_rows(dw, start, padded, cols)
        print(f'Uploaded {start+n-1:,}/{rows:,} rows', flush=True)
    stale = []
    if new_rows > rows:
        stale.append(f'A{rows+1}:{rowcol_to_a1(new_rows,new_cols)}')
    if new_cols > cols:
        stale.append(f'{rowcol_to_a1(1,cols+1)}:{rowcol_to_a1(rows,new_cols)}')
    if stale:
        retry(lambda: dw.batch_clear(stale))
    print(f'Sync successful: {rows:,} rows including header, {cols} columns; {time.monotonic()-started:.1f}s', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Sync failed: {exc}', flush=True)
        traceback.print_exc()
        sys.exit(1)
