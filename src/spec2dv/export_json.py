# src/spec2dv/export_json.py
from __future__ import annotations

import json
from pathlib import Path
import sqlite3


def export_registers_json(conn: sqlite3.Connection, out_path: Path) -> None:
    blocks = conn.execute("SELECT id, name, base_addr, variant FROM ip_block ORDER BY name").fetchall()
    out = {"ip_blocks": []}

    for b in blocks:
        regs = conn.execute(
            "SELECT id, name, offset, width FROM reg WHERE block_id=? ORDER BY offset",
            (b["id"],),
        ).fetchall()

        blk_obj = {
            "name": b["name"],
            "base_addr": b["base_addr"],
            "variant": b["variant"],
            "registers": [],
        }

        for r in regs:
            fields = conn.execute(
                "SELECT id, name, lsb, msb, access, reset FROM field WHERE reg_id=? ORDER BY lsb",
                (r["id"],),
            ).fetchall()

            reg_obj = {"name": r["name"], "offset": r["offset"], "width": r["width"], "fields": []}
            for f in fields:
                enums = conn.execute(
                    "SELECT name, value FROM enum_value WHERE field_id=? ORDER BY value",
                    (f["id"],),
                ).fetchall()
                field_obj = {
                    "name": f["name"],
                    "lsb": f["lsb"],
                    "msb": f["msb"],
                    "access": f["access"],
                    "reset": f["reset"],
                    "enum": [{"name": e["name"], "value": e["value"]} for e in enums] if enums else None,
                }
                reg_obj["fields"].append(field_obj)

            blk_obj["registers"].append(reg_obj)

        out["ip_blocks"].append(blk_obj)

    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")