# src/spec2dv/models.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EnumValue(BaseModel):
    name: str
    value: int


class FieldDef(BaseModel):
    name: str
    lsb: int
    msb: int
    access: str = Field(..., description="RW/RO/WO/W1C etc.")
    reset: int = 0
    enum: Optional[List[EnumValue]] = None

    @field_validator("msb")
    @classmethod
    def _msb_ge_lsb(cls, v: int, info):
        lsb = info.data.get("lsb")
        if lsb is not None and v < lsb:
            raise ValueError("msb must be >= lsb")
        return v

    def width(self) -> int:
        return (self.msb - self.lsb) + 1


class RegisterDef(BaseModel):
    name: str
    offset: int
    width: int = 32
    fields: List[FieldDef]


class IPBlockDef(BaseModel):
    name: str
    base_addr: int
    registers: List[RegisterDef]


class ConstraintDef(BaseModel):
    name: str
    applies_to: str  # "field" | "reg" | "block"
    match: Dict[str, Any] = Field(default_factory=dict)  # stored as JSON
    rule: str
    severity: str = "ERROR"


class VariantOverrides(BaseModel):
    variant: str
    overrides: Dict[str, Any] = Field(default_factory=dict)


class SpecDoc(BaseModel):
    spec_version: str
    ip_blocks: List[IPBlockDef]
    constraints: List[ConstraintDef] = Field(default_factory=list)


class SpecBundle(BaseModel):
    """Merged base spec + variant overlay metadata."""
    spec_version: str
    variant_name: Optional[str]
    doc: SpecDoc
    variant_overrides: Dict[str, Any] = Field(default_factory=dict)