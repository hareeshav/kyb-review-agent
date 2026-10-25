"""The synthetic 'world' the tools query: a company registry, a sanctions list and a PEP list.
Stored as JSON next to the applications so runs are reproducible."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .config import SYNTH_DIR
from .schemas import RegistryRecord

SANCTIONED_COUNTRIES = {"KP", "IR", "SY", "CU", "RU", "BY"}
HIGH_RISK_COUNTRIES = {"AF", "MM", "YE", "HT", "SS", "VE", "PK", "NG"}
EEA_UK_CH = {
    "NL", "DE", "BE", "FR", "ES", "IT", "PT", "AT", "IE", "LU", "DK", "SE", "FI", "PL", "CZ", "SK", "HU",
    "RO", "BG", "HR", "SI", "EE", "LV", "LT", "GR", "CY", "MT", "NO", "IS", "LI", "GB", "CH",
}
PROHIBITED = {"adult_content", "weapons", "unlicensed_gambling", "unlicensed_money_services", "narcotics", "counterfeit"}
RESTRICTED = {"licensed_gambling", "crypto_exchange", "pharmaceuticals", "tobacco_alcohol", "cbd", "forex_cfd", "debt_collection"}
LOW_RISK = {"retail", "software_saas", "consulting", "hospitality", "education", "nonprofit_fundraising"}


class World(BaseModel):
    registry: dict[str, RegistryRecord] = Field(default_factory=dict)  # by company_id
    sanctioned_names: list[str] = Field(default_factory=list)
    pep_names: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "World":
        path = path or SYNTH_DIR / "world.json"
        return cls.model_validate_json(path.read_text())

    def save(self, path: Path | None = None) -> None:
        path = path or SYNTH_DIR / "world.json"
        path.write_text(self.model_dump_json(indent=2))

    def is_sanctioned(self, name: str) -> bool:
        return name.strip().lower() in {n.lower() for n in self.sanctioned_names}

    def is_pep(self, name: str) -> bool:
        return name.strip().lower() in {n.lower() for n in self.pep_names}
