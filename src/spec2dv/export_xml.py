# src/spec2dv/export_xml.py
from __future__ import annotations

from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET


def export_registers_xml(conn: sqlite3.Connection, out_path: Path) -> None:
    root = ET.Element("spec")

    for b in conn.execute("SELECT id, name, base_addr, variant FROM ip_block ORDER BY name").fetchall():
        b_el = ET.SubElement(root, "ip_block", {
            "name": b["name"],
            "base_addr": hex(b["base_addr"]),
            "variant": b["variant"] or "",
        })

        regs = conn.execute(
            "SELECT id, name, offset, width FROM reg WHERE block_id=? ORDER BY offset",
            (b["id"],),
        ).fetchall()

        for r in regs:
            r_el = ET.SubElement(b_el, "register", {
                "name": r["name"],
                "offset": hex(r["offset"]),
                "width": str(r["width"]),
            })

            fields = conn.execute(
                "SELECT id, name, lsb, msb, access, reset FROM field WHERE reg_id=? ORDER BY lsb",
                (r["id"],),
            ).fetchall()

            for f in fields:
                f_el = ET.SubElement(r_el, "field", {
                    "name": f["name"],
                    "lsb": str(f["lsb"]),
                    "msb": str(f["msb"]),
                    "access": f["access"],
                    "reset": str(f["reset"]),
                })

                enums = conn.execute(
                    "SELECT name, value FROM enum_value WHERE field_id=? ORDER BY value",
                    (f["id"],),
                ).fetchall()
                if enums:
                    e_el = ET.SubElement(f_el, "enum")
                    for ev in enums:
                        ET.SubElement(e_el, "value", {"name": ev["name"], "value": str(ev["value"])})

    tree = ET.ElementTree(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)