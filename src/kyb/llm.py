"""LLM client abstraction used by approaches A and B and the judge.

- OpenAIClient: structured output via chat.completions.parse (Pydantic schema).
- FakeClient:   offline stand-in that answers from the rule checker. It exists ONLY to exercise
                the pipeline and the eval harness without a key. Never report its numbers.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from pydantic import BaseModel

from . import config

# USD per 1M tokens (input, output). Update if prices change; used for cost-per-application.
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5-mini": (0.25, 2.00),
}


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""

    @property
    def cost(self) -> float:
        return cost_usd(self.model, self.prompt_tokens, self.completion_tokens)


class OpenAIClient:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI
        self.model = model or config.GEN_MODEL
        self.client = OpenAI(api_key=api_key or config.OPENAI_API_KEY)

    def structured(self, system: str, user: str, schema: type[BaseModel], temperature: float = 0.0):
        t0 = time.perf_counter()
        r = self.client.chat.completions.parse(
            model=self.model, temperature=temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=schema,
        )
        u = Usage(r.usage.prompt_tokens, r.usage.completion_tokens, (time.perf_counter() - t0) * 1000, self.model)
        return r.choices[0].message.parsed, u


class FakeClient:
    """Answers from the rule checker. Offline plumbing only."""
    model = "fake"

    def __init__(self, world, applications: dict):
        self.world, self.applications = world, applications

    def structured(self, system: str, user: str, schema: type[BaseModel], temperature: float = 0.0):
        from .rules import check
        from .schemas import DecisionRecord
        app_id = next(a for a in self.applications if a in user)
        g = check(self.applications[app_id], self.world)
        rec = DecisionRecord(decision=g.decision, cited_clauses=g.clauses, reasoning=f"[fake] {g.explanation}",
                             missing_items=g.missing_items, risk_tier=g.risk_tier)
        return rec, Usage(len(user) // 4, 60, 1.0, "fake")
