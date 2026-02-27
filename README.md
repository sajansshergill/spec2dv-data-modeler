# Spec2DV Data Modeler (AMD-style Design Spec -> XML/SQL -> DV Outputs

Turn complex hardwre design specifications into **structured, machine-readable data** (SQL + XML) that can be consumed by **DV/verification**, **RTL/design**, **architecture**, and **documentation** workflows. Includes **ingestion**, **validation** , **tracebility**, and **auto-generated DV artifacts**.

---

## Why this project exists

Modern CPU/IP projects produce specs that evolve quickly across **variants** and **product lines**. DV teams need trusted, consistent data for:
- Register maps and field definitions
- Constraints (reserved bits, legal enum/opcode ranges)
- Random test configuration inputs
- Tracability: **what changed, when and why**

**Spec2DV** provides a single pipeline to:
1) ingest spec data
2) validate it with hardware-aware rules
3) store it in a relational model
4) export XML/JSON + DV-friendly stubs
5) track changes across versions/variants

---

## Key features
### 1) Spec ingestion
- Input spec format: **YAML** (recommended), JSON optional
- Extracts:
  - IP blocks, registers, fields, enums
  - ISA/opcode tables (optional)
  - Constraints and variant overrides
 
### 2) Structure Storage
- **SQLite** (Default) for portability
- Optional: postgres
- Normalized tables: `ip_block`, `reg`, `enum`, `constratint`, `variant`, `spec_version`

### 3) Validation (hardware-aware)
Built-in checks such as:
- No overlapping bitfields in a register
- Field reset value fits the field width
- Register offsets unique within an IP block
- Enum values fit the declared bit-width
- Reserved bits rules (e.g., must read as 0 / write ignored)

### 4) Exports
- **XML** exports suitable for tooling:
  - `registers.xml`
  - `isa.xml` (optional)
- **JSON** exports (for scripts / harnesses)
- **DV outputs**:
  - UVM resgiter model stubs (SystemVerifylog snippets) * (optional but recommended)*
  - Random config constraints (JSON)
  - Sanity test checklist report (Markdown)
 
### 5) Versioning & Traceability
- Records:
  - `spec_version` (semantic)
  - `git_commit`
  - timestamps
  - variant name
- Diff tool: compare two versions and produce a change report.

## Demo Use Case
A realistic "mini spec" for a CPU subsystem:
- `csr_block` (constrol/status regs)
- `timer` (config + counters)
- `interrupt_controller` (enable/status/pending)

Variants:
- `client_A`: 2 timers
- `client_B`: 4 timers + extra interrupt lines

---

## Repository Structure
<img width="629" height="662" alt="image" src="https://github.com/user-attachments/assets/3b04333c-3732-49a7-9abd-833b7fd1b62c" />

## Input Spec Format (YAML)
Minimal example (resgiters + fields):
spec_version: "1.0.0"
ip_blocks:
  - name: "timer"
    base_addr: 0x40000000
    registers:
      - name: "TMR_CTRL"
        offset: 0x0000
        width: 32
        fields:
          - name: "EN"
            lsb: 0
            msb: 0
            access: "RW"
            reset: 0
          - name: "MODE"
            lsb: 1
            msb: 2
            access: "RW"
            reset: 0
            enum:
              - { name: "ONE_SHOT", value: 0 }
              - { name: "PERIODIC", value: 1 }
              - { name: "PWM", value: 2 }
          - name: "RSVD"
            lsb: 3
            msb: 31
            access: "RO"
            reset: 0
constraints:
  - name: "reserved_bits_read_zero"
    applies_to: "field"
    match: { field_name: "RSVD" }
    rule: "READS_AS_ZERO"

Variant overlay example (client_B adds more timers or interrupts):
variant: "client_B"
overrides:
  timer:
    instances: 4
  interrupt_controller:
    irq_lines: 64

## Data Model (SQL)
Core entities:
- ip_block(id, name, base_addr, variant)
- reg(id, block_id, name, offset, width)
- field(id, reg_id, name, lsb, msb, access, reset)
- enum_value(id, field_id, name, value)
- constraint(id, scope, match_json, rule, severity)
- spec_version(id, version, git_commit, created_at, variant)

## CLI Commands (planned)
Implemented these in src/spec2dv/cli.py
# 1) Ingest base spec (and optionally a variant overlay)
spec2dv ingest spec/base_spec.yaml --variant spec/variants/client_A.yaml

# 2) Validate spec integrity
spec2dv validate --db spec2dv.sqlite

# 3) Export structured outputs
spec2dv export --db spec2dv.sqlite --xml --json

# 4) Export DV artifacts (constraints + UVM stubs)
spec2dv export-dv --db spec2dv.sqlite --uvm --constraints

# 5) Diff two versions
spec2dv diff --from 1.0.0 --to 1.1.0 --variant client_B

## Validation Rules (MVP)
### Register/Field intergrity
- Field ranges must be within register width
- No field overlap
- msb >= lsb
- Resest fits (msb-lsb+1) width

### Naming/Uniqueness
- Register name unique within block
- Field name unique within register
- Register offset unique within block

### Enums
- Enum values fit field width
- Enum values unique

### Reserved Bits
- If field name matchs RSVD (or spec marks reserved), enforce rule:
  - reads as zero, writes ignored(configurable)
 
## DV Outputs (MVP)
### A) DV Constraint Config (JSON)
Example output:
{
  "timer": {
    "TMR_CTRL.MODE": ["ONE_SHOT", "PERIODIC", "PWM"],
    "timer_reserved_bits": "MUST_BE_ZERO"
  }
}

### B) UVM Register Model Stub (SystemVerilog)
Generate skeletons like:
- uvm_reg classes per register
- uvm_reg_field definitions
- basic build() methods

## Setup
### Requirements
- Python 3.10+
- Recommended:
  - pydantic
  - pyyaml
  - typer (CLI)
  - lxml (XML export) or built-in xml.etree
  - pytest

### Install
python -m venv .venv
source .venv/bin/activate
pip install -e .

## Quickstart (Suggested Milestones)
### Milestone 1 - Ingestion + DB
- Define Pydantic models
- Parse YAML normalized objects
- Insert into SQLite

### Milestone 2 - Validation
- Implement overlap + reset-width checks
- Emit a validation report (Markdown)

### Milestone 3 - Export XML/JSON
- Generate registers.xml
- Generate registers.json

### Milestone 4 - DV Ouputs
- Constraint config JSON
- UVM regsiter stubs

### Milestone 5 - Versioning + Diff
- Store spec version + git commit
- Compare two versions and report changes:
  - added/removed registers
  - field bit range changes
  - reset changes
  - enum changes


## Testing
pytest -q

Test categories:
- parser correctness
- validation rule coverage
- export deterministic output (golden files)

## What this demonstrates
- **Spec** -> **structured formats**: YAML -> SQL + XML
- **DV/RTL compability**: generates DV-ready outputs + data intergrity checks
- **Automation**: ingestion + validation CLI pipelines
- **Traceability**: versioning + diffs across variants
- **Cross-functional mindset**: architecture/design data usable by multiple teams


