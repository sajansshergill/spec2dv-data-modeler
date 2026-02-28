# src/spec2dv/ingest.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any, Dict

import yaml

from .models import SpecBundle, SpecDoc


def _load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _merge_variant(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep this intentionally conservative:
    - Base SpecDoc stays as-is (ip_blocks, registers, fields).
    - Variant overlay stored separately in SpecBundle.variant_overrides.
    This matches real flows where variants often influence *instances/params* rather than spec structure.
    """
    return base  # no structural merge for MVP


def load_spec_bundle(spec_path: Path, variant_path: Optional[Path]) -> SpecBundle:
    base_raw = _load_yaml(spec_path)

    variant_name = None
    variant_overrides: Dict[str, Any] = {}
    if variant_path:
        overlay_raw = _load_yaml(variant_path)
        variant_name = overlay_raw.get("variant")
        variant_overrides = overlay_raw.get("overrides", {}) or {}

    merged_raw = _merge_variant(base_raw, {"variant": variant_name, "overrides": variant_overrides})
    doc = SpecDoc.model_validate(merged_raw)

    return SpecBundle(
        spec_version=doc.spec_version,
        variant_name=variant_name,
        doc=doc,
        variant_overrides=variant_overrides,
    )