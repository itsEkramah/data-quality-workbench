"""Local-first FastAPI application; SQLite keeps input and outputs together."""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .engine import Rules, clean_csv, export_csv

STATIC = Path(__file__).parent / "static"


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(min_length=1, max_length=1_000_000)
    rules: Rules = Field(default_factory=Rules)


def create_app(db_path: str | Path | None = None) -> FastAPI:
    db_path = Path(db_path or os.environ.get("QUALITYDESK_DB", ".data/qualitydesk.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect():
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created TEXT NOT NULL, source TEXT NOT NULL, result TEXT NOT NULL)")

    app = FastAPI(title="Data Quality Workbench", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    @app.post("/api/jobs", status_code=201)
    def create_job(payload: JobRequest):
        try:
            result = clean_csv(payload.csv_text, payload.rules)
        except (ValueError, csv.Error) as exc:
            raise HTTPException(422, str(exc)) from exc
        job_id = uuid.uuid4().hex
        with connect() as conn:
            conn.execute("INSERT INTO jobs VALUES (?, ?, ?, ?)",
                         (job_id, datetime.now(timezone.utc).isoformat(), payload.csv_text, json.dumps(result)))
        return {"id": job_id, **result}

    def get_job(job_id):
        with connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Job not found")
        return row

    @app.get("/api/jobs/{job_id}")
    def read_job(job_id: str):
        row = get_job(job_id)
        return {"id": job_id, "created": row["created"], **json.loads(row["result"])}

    @app.get("/api/jobs/{job_id}/export")
    def download(job_id: str, kind: Literal["clean", "rejected", "source", "report"] = "clean"):
        row = get_job(job_id)
        result = json.loads(row["result"])
        body = (row["source"] if kind == "source" else
                json.dumps(result, indent=2, ensure_ascii=False) if kind == "report" else
                export_csv(result, rejected=kind == "rejected"))
        extension = "json" if kind == "report" else "csv"
        return Response(body, media_type="application/json" if extension == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{kind}.{extension}"'})

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str):
        get_job(job_id)
        with connect() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return Response(status_code=204)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
