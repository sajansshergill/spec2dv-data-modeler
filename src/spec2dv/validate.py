# src/spec2dv/validate.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
import sqlite3


@dataclass
class ValidationIssue:
    severity: str  # ERROR/WARN
    code: str
    message: str
    context: str = ""


@dataclass
class ValidationResult:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.upper() == "ERROR")

    def summary(self) -> str:
        return f"Validation: {len(self.issues)} issues ({self.error_count} errors)"

    def to_markdown(self) -> str:
        lines = ["# Spec2DV Validation Report", "", self.summary(), ""]
        if not self.issues:
            lines.append("✅ No issues found.")
            return "\n".join(lines)

        lines.append("| Severity | Code | Context | Message |")
        lines.append("|---|---|---|---|")
        for i in self.issues:
            ctx = i.context.replace("\n", " ")
            msg = i.message.replace("\n", " ")
            lines.append(f"| {i.severity} | {i.code} | {ctx} | {msg} |")
        return "\n".join(lines)


def _field_width(lsb: int, msb: int) -> int:
    return (msb - lsb) + 1


def validate_db(conn: sqlite3.Connection) -> ValidationResult:
    res = ValidationResult()

    # Check: field ranges and resets
    rows = conn.execute(
        """
        SELECT b.name AS block_name, r.name AS reg_name, r.width AS reg_width,
               f.name AS field_name, f.lsb, f.msb, f.reset
        FROM field f
        JOIN reg r ON r.id=f.reg_id
        JOIN ip_block b ON b.id=r.block_id
        ORDER BY b.name, r.name, f.lsb
        """
    ).fetchall()

    for row in rows:
        blk = row["block_name"]
        reg = row["reg_name"]
        fw = _field_width(row["lsb"], row["msb"])

        # within reg width
        if row["lsb"] < 0 or row["msb"] >= row["reg_width"]:
            res.issues.append(
                ValidationIssue(
                    "ERROR",
                    "FIELD_RANGE",
                    f"{blk}.{reg}.{row['field_name']}",
                    f"Field bits [{row['msb']}:{row['lsb']}] outside register width {row['reg_width']}",
                )
            )

        # reset fits
        max_val = (1 << fw) - 1
        if row["reset"] < 0 or row["reset"] > max_val:
            res.issues.append(
                ValidationIssue(
                    "ERROR",
                    "RESET_WIDTH",
                    f"{blk}.{reg}.{row['field_name']}",
                    f"Reset {row['reset']} does not fit width {fw} (max {max_val})",
                )
            )

    # Check: overlap inside each register
    regs = conn.execute(
        """
        SELECT r.id, b.name AS block_name, r.name AS reg_name, r.width
        FROM reg r JOIN ip_block b ON b.id=r.block_id
        """
    ).fetchall()

    for rr in regs:
        fields = conn.execute(
            "SELECT name, lsb, msb FROM field WHERE reg_id=? ORDER BY lsb",
            (rr["id"],),
        ).fetchall()

        occupied = []
        for f in fields:
            # check overlap vs occupied ranges
            for (ol, om, oname) in occupied:
                if not (f["msb"] < ol or f["lsb"] > om):
                    res.issues.append(
                        ValidationIssue(
                            "ERROR",
                            "FIELD_OVERLAP",
                            f"{rr['block_name']}.{rr['reg_name']}",
                            f"Field {f['name']} [{f['msb']}:{f['lsb']}] overlaps {oname} [{om}:{ol}]",
                        )
                    )
            occupied.append((f["lsb"], f["msb"], f["name"]))

    return res