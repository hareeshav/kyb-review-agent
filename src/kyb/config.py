"""Central configuration. Everything is read from environment / .env so the
same code runs offline (generator, rules, gate, metrics) and online (A/B/C, judge)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
POLICY_FILE = DATA_DIR / "policy" / "kyb_policy.md"
SYNTH_DIR = DATA_DIR / "synthetic"
RUNS_DIR = ROOT / "runs"
CHROMA_DIR = ROOT / ".chroma"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEN_MODEL = os.getenv("KYB_GEN_MODEL", "gpt-4o-mini")
EMBEDDINGS = os.getenv("KYB_EMBEDDINGS", "fastembed")  # fastembed | openai
JUDGE_PROVIDER = os.getenv("KYB_JUDGE_PROVIDER", "openai")  # openai | anthropic
JUDGE_MODEL = os.getenv("KYB_JUDGE_MODEL", "gpt-4.1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

GATE_SECRET = os.getenv("KYB_GATE_SECRET", "dev-secret-change-me")
GATE_TTL_SECONDS = int(os.getenv("KYB_GATE_TTL_SECONDS", "600"))

MAX_MODEL_CALLS = int(os.getenv("KYB_MAX_MODEL_CALLS", "8"))
MAX_TOOL_CALLS = int(os.getenv("KYB_MAX_TOOL_CALLS", "12"))

# Retrieval
TOP_K = int(os.getenv("KYB_TOP_K", "6"))

# Context budget (tokens, approximated as chars/4 when no tokenizer is available)
BUDGET_APPLICATION_TOKENS = 2000
BUDGET_CLAUSES_TOKENS = 1500
BUDGET_TOOL_OUTPUT_TOKENS = 800
