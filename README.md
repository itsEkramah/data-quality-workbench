# Data Quality Workbench

A small full-stack application for cleaning CSV data under explicit rules. The browser interface sends a job to a FastAPI backend; SQLite preserves the original input and the result so that every export can be traced to its source.

**Portfolio demonstration, not paid client work.** Built with AI assistance and validated with the tests described in [VALIDATION.md](VALIDATION.md). Uses synthetic examples. It is a local development app, not a hosted production service.

## The problem

A spreadsheet assembled from multiple sources can contain duplicate identifiers, inconsistent spacing, invalid numbers and ambiguous dates. Deleting rows without a change record makes the result difficult to trust. This app separates accepted rows from a quarantine report and never invents missing values.

## Try it locally

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn qualitydesk.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Select **Load demo**, then **Validate & clean**. The bundled example has eight data rows: four accepted and four quarantined. Download the cleaned CSV, rejected rows, exact source and JSON report.

For the interactive API documentation, open <http://127.0.0.1:8000/docs>.

## What it does

- Trim cell whitespace and header whitespace.
- Validate required columns, finite decimal numbers and ISO dates (`YYYY-MM-DD`).
- Keep the first valid row for an exact composite key. A rejected row does not reserve a key.
- Flag malformed row widths and preserve their original values in the rejection report.
- Store input, applied rules and results in SQLite; support job lookup and deletion.
- Neutralize formula-like cells in cleaned CSV exports. This intentionally adds a leading apostrophe to those export cells; the original input and JSON report remain unchanged.

No fuzzy matching, date guessing, imputation, Excel formula preservation or joins are implemented. Empty numeric/date values are allowed unless the column is also required. Blank lines are ignored. The limits are one million input characters, 50,000 data rows and 100 columns; these are demo limits, not a performance guarantee.

## API example

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"csv_text":"id,amount\na,5\na,7\n","rules":{"key":["id"],"numeric":["amount"]}}'
```

Use the returned `id` with `GET /api/jobs/{id}` or `GET /api/jobs/{id}/export?kind=clean`. Export kinds are `clean`, `rejected`, `source` and `report`. `DELETE /api/jobs/{id}` removes the stored record. SQLite deletion is not secure erasure of disk sectors or backups.

## Structure

```text
qualitydesk/engine.py       deterministic cleaning and export rules
qualitydesk/app.py          HTTP endpoints and persistence
qualitydesk/static/        browser interface, no frontend build tools
tests/                     engine and API integration tests
```

Run checks with `python -m unittest discover -s tests -v`. The tests cover quarantine accounting, invalid schemas, duplicate handling, formula-like exports, persistence, downloads and deletion.

## Deployment boundary

Keep the default loopback binding for local use. There is no authentication, multi-user isolation, production upload gateway, background job queue, backup policy or encryption layer. Before any public deployment, add those controls, HTTPS, request-size enforcement at the server, retention rules and appropriate monitoring. Do not put real customer or patient data into this demonstration.

Set `QUALITYDESK_DB` to choose another database path. Runtime databases and environment files are ignored by Git.

## What this demonstrates

Python data processing, explicit validation, a frontend connected to an API, SQLite persistence, downloadable results and testable error handling. It does not establish production experience or client outcomes.

Reference: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/).
