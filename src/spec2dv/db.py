# src/spec2dv/db.py
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .models import SpecBundle

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS spec_version (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  version TEXT NOT NULL,
  variant TEXT,
  git_commit TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ip_block (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  base_addr INTEGER NOT NULL,
  variant TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_block_name_variant ON ip_block(name, ifnull(variant,''));

CREATE TABLE IF NOT EXISTS reg (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  block_id INTEGER NOT NULL REFERENCES ip_block(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  offset INTEGER NOT NULL,
  width INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_reg_block_name ON reg(block_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS ux_reg_block_offset ON reg(block_id, offset);

CREATE TABLE IF NOT EXISTS field (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reg_id INTEGER NOT NULL REFERENCES reg(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  lsb INTEGER NOT NULL,
  msb INTEGER NOT NULL,
  access TEXT NOT NULL,
  reset INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_field_reg_name ON field(reg_id, name);

CREATE TABLE IF NOT EXISTS enum_value (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_id INTEGER NOT NULL REFERENCES field(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  value INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_enum_field_value ON enum_value(field_id, value);

CREATE TABLE IF NOT EXISTS constraint_def (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  applies_to TEXT NOT NULL,
  match_json TEXT NOT NULL,
  rule TEXT NOT NULL,
  severity TEXT NOT NULL
);
"""


@contextmanager
def connect_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect_db(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def _get_or_create_block(conn: sqlite3.Connection, name: str, base_addr: int, variant: Optional[str]) -> int:
    row = conn.execute(
        "SELECT id FROM ip_block WHERE name=? AND ifnull(variant,'')=ifnull(?, '')",
        (name, variant),
    ).fetchone()
    if row:
        # update base addr in case spec changed
        conn.execute("UPDATE ip_block SET base_addr=? WHERE id=?", (base_addr, row["id"]))
        return int(row["id"])

    cur = conn.execute(
        "INSERT INTO ip_block(name, base_addr, variant) VALUES(?,?,?)",
        (name, base_addr, variant),
    )
    return int(cur.lastrowid)


def upsert_spec_bundle(conn: sqlite3.Connection, bundle: SpecBundle) -> None:
    # For MVP: write blocks/registers/fields exactly as provided
    # In real flows you might key by spec_version and keep historical copies.
    variant = bundle.variant_name
    doc = bundle.doc

    for blk in doc.ip_blocks:
        block_id = _get_or_create_block(conn, blk.name, blk.base_addr, variant)

        # Remove existing regs under this block to avoid partial updates for MVP
        conn.execute("DELETE FROM reg WHERE block_id=?", (block_id,))

        for r in blk.registers:
            reg_cur = conn.execute(
                "INSERT INTO reg(block_id, name, offset, width) VALUES(?,?,?,?)",
                (block_id, r.name, int(r.offset), int(r.width)),
            )
            reg_id = int(reg_cur.lastrowid)

            for f in r.fields:
                field_cur = conn.execute(
                    "INSERT INTO field(reg_id, name, lsb, msb, access, reset) VALUES(?,?,?,?,?,?)",
                    (reg_id, f.name, int(f.lsb), int(f.msb), f.access, int(f.reset)),
                )
                field_id = int(field_cur.lastrowid)

                if f.enum:
                    for ev in f.enum:
                        conn.execute(
                            "INSERT INTO enum_value(field_id, name, value) VALUES(?,?,?)",
                            (field_id, ev.name, int(ev.value)),
                        )

    # Constraints
    conn.execute("DELETE FROM constraint_def")
    for c in doc.constraints:
        conn.execute(
            "INSERT INTO constraint_def(name, applies_to, match_json, rule, severity) VALUES(?,?,?,?,?)",
            (c.name, c.applies_to, json.dumps(c.match, sort_keys=True), c.rule, c.severity),
        )


def write_spec_version(conn: sqlite3.Connection, version: str, variant: Optional[str], git_commit: Optional[str]) -> None:
    conn.execute(
        "INSERT INTO spec_version(version, variant, git_commit) VALUES(?,?,?)",
        (version, variant, git_commit),
    )