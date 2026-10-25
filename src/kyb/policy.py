"""Load the policy pack and split it into one clause per chunk with metadata.
This is the structure-aware chunker from the course: clause boundaries are the chunk boundaries."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .config import POLICY_FILE

_CLAUSE_RE = re.compile(
    r"^### (?P<id>C\d{2}) — (?P<title>.+?)\n"
    r"<!-- section: (?P<section>[\w-]+) \| entity_type: (?P<entity>[\w,]+) \| risk_tier: (?P<tier>[\w,]+) -->\n"
    r"(?P<body>.*?)(?=^### |^## |\Z)",
    re.M | re.S,
)


@dataclass(frozen=True)
class Clause:
    id: str
    title: str
    section: str
    entity_types: tuple[str, ...]  # ("all",) or specific
    risk_tiers: tuple[str, ...]  # ("any",) or specific
    body: str

    @property
    def text(self) -> str:
        return f"{self.id} — {self.title}\n{self.body.strip()}"

    def applies_to(self, entity_type: str | None = None, risk_tier: str | None = None) -> bool:
        ok_e = entity_type is None or "all" in self.entity_types or entity_type in self.entity_types
        ok_t = risk_tier is None or "any" in self.risk_tiers or risk_tier in self.risk_tiers
        return ok_e and ok_t


@lru_cache(maxsize=1)
def load_clauses() -> list[Clause]:
    text = POLICY_FILE.read_text(encoding="utf-8")
    clauses = []
    for m in _CLAUSE_RE.finditer(text):
        clauses.append(Clause(
            id=m["id"], title=m["title"].strip(), section=m["section"],
            entity_types=tuple(m["entity"].split(",")), risk_tiers=tuple(m["tier"].split(",")),
            body=m["body"].strip(),
        ))
    if len(clauses) != 25:
        raise RuntimeError(f"expected 25 clauses, parsed {len(clauses)}")
    return clauses


def clause_map() -> dict[str, Clause]:
    return {c.id: c for c in load_clauses()}


def full_policy_text() -> str:
    """The whole policy as one string — what approach A stuffs into the prompt."""
    return "\n\n".join(c.text for c in load_clauses())
