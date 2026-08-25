from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class Sample:
    hole_no: int
    sample_no: str
    depth: str
    wet_density: Optional[str] = None
    dry_density: Optional[str] = None
    particle_density: Optional[str] = None
    water_content: Optional[str] = None
    void_ratio: Optional[str] = None
    saturation: Optional[str] = None
    gravel: Optional[str] = None
    sand: Optional[str] = None
    silt: Optional[str] = None
    clay: Optional[str] = None
    combined_fines: Optional[str] = None
    max_size: Optional[str] = None
    d50: Optional[str] = None
    d20: Optional[str] = None
    d10: Optional[str] = None
    classification_name: Optional[str] = None
    classification_symbol: Optional[str] = None
    liquid_limit: Optional[str] = None
    plastic_limit: Optional[str] = None
    plasticity_index: Optional[str] = None
    consistency_index: Optional[str] = None
    qu1: Optional[str] = None
    qu2: Optional[str] = None
    qu3: Optional[str] = None
    cu: Optional[str] = None
    phi_u: Optional[str] = None
    pc: Optional[str] = None
    cc: Optional[str] = None
    source_page: Optional[int] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def fc(self) -> Optional[str]:
        if self.combined_fines not in (None, ""):
            return self.combined_fines
        if self.silt in (None, "") or self.clay in (None, ""):
            return None
        try:
            a = Decimal(self.silt)
            b = Decimal(self.clay)
            places = max(_decimal_places(self.silt), _decimal_places(self.clay))
            value = a + b
            return f"{value:.{places}f}"
        except (InvalidOperation, ValueError):
            self.warnings.append("Fcを計算できませんでした")
            return None


@dataclass
class Hole:
    hole_no: int
    samples: list[Sample] = field(default_factory=list)


def _decimal_places(value: str) -> int:
    if "." not in value:
        return 0
    return len(value.rsplit(".", 1)[1])
