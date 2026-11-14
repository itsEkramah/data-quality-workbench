"""Small, deterministic CSV cleaning engine. No imputation or fuzzy matching."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field


class Rules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: list[str] = Field(default_factory=list, max_length=50)
    key: list[str] = Field(default_factory=list, max_length=10)
    numeric: list[str] = Field(default_factory=list, max_length=30)
    dates: list[str] = Field(default_factory=list, max_length=30)
    nonnegative: list[str] = Field(default_factory=list, max_length=30)


def clean_csv(text: str, rules: Rules) -> dict:
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    try:
        header = [v.strip() for v in next(reader)]
    except StopIteration:
        raise ValueError("The CSV is empty.") from None
    if not header or any(not v for v in header) or len(set(header)) != len(header):
        raise ValueError("Headers must be non-empty and unique after trimming.")
    if len(header) > 100:
        raise ValueError("At most 100 columns are supported.")
    requested = set(rules.required + rules.key + rules.numeric + rules.dates + rules.nonnegative)
    missing = requested - set(header)
    if missing:
        raise ValueError("Rule columns not found: " + ", ".join(sorted(missing)))
    if not set(rules.nonnegative).issubset(rules.numeric):
        raise ValueError("Nonnegative columns must also be numeric columns.")
    if set(rules.numeric) & set(rules.dates):
        raise ValueError("A column cannot be both numeric and a date.")
    accepted, rejected, seen = [], [], set()
    changed_cells = 0
    for row_number, raw in enumerate(reader, 2):
        if not raw:
            continue
        if len(accepted) + len(rejected) >= 50000:
            raise ValueError("At most 50,000 data rows are supported.")
        if len(raw) != len(header):
            rejected.append({"row": row_number, "values": raw, "errors": ["column count mismatch"]})
            continue
        row = dict(zip(header, [v.strip() for v in raw]))
        errors = []
        for col in sorted(set(rules.required + rules.key)):
            if not row[col]:
                errors.append(f"{col}: required value missing")
        for col in rules.numeric:
            if not row[col] and col not in rules.required:
                continue
            try:
                number = Decimal(row[col])
                if not number.is_finite():
                    raise InvalidOperation
                if col in rules.nonnegative and number < 0:
                    errors.append(f"{col}: negative value")
                else:
                    row[col] = format(number, "f")
            except InvalidOperation:
                errors.append(f"{col}: invalid finite number")
        for col in rules.dates:
            if not row[col] and col not in rules.required:
                continue
            try:
                if len(row[col]) != 10:
                    raise ValueError
                row[col] = date.fromisoformat(row[col]).isoformat()
            except ValueError:
                errors.append(f"{col}: expected YYYY-MM-DD")
        key = tuple(row[col] for col in rules.key)
        if rules.key and key in seen:
            errors.append("duplicate accepted key")
        if errors:
            rejected.append({"row": row_number, "values": raw, "errors": errors})
        else:
            if rules.key:
                seen.add(key)
            changed_cells += sum(old != row[col] for col, old in zip(header, raw))
            accepted.append(row)
    if not accepted and not rejected:
        raise ValueError("The CSV has no data rows.")
    return {"columns": header, "accepted": accepted, "rejected": rejected,
            "summary": {"input_rows": len(accepted) + len(rejected),
                        "accepted_rows": len(accepted), "rejected_rows": len(rejected),
                        "changed_cells_in_accepted_rows": changed_cells},
            "rules": rules.model_dump()}


def spreadsheet_safe(value: object) -> str:
    """Prefix potential spreadsheet formulas in downloadable text fields."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r")) else text


def export_csv(result: dict, rejected: bool = False) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if rejected:
        writer.writerow(["source_row", "errors", "original_values_json"])
        import json
        for row in result["rejected"]:
            writer.writerow([row["row"], "; ".join(row["errors"]), json.dumps(row["values"], ensure_ascii=False)])
    else:
        writer.writerow(result["columns"])
        for row in result["accepted"]:
            writer.writerow([spreadsheet_safe(row[col]) for col in result["columns"]])
    return output.getvalue()
