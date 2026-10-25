"""Policy retrieval: metadata pre-filter → dense top-k (→ optional hybrid BM25 + RRF).

Store: Chroma (cosine) when installed, else an in-memory numpy index with identical behaviour
(25 clauses — the store is not the interesting part; the pre-filter and the ranking are).
Embeddings: fastembed (local, default) | openai | hash (tests only).
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

import numpy as np

from . import config
from .policy import Clause, load_clauses

ENTITY_TYPES = ["sole_trader", "bv", "nv", "foundation", "partnership", "other"]


# ---------------- embedders ----------------
class HashEmbedder:
    """Deterministic bag-of-words hashing embedder for offline tests. Not for real runs."""
    name = "hash"
    dim = 256

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
            n = np.linalg.norm(out[i]) or 1.0
            out[i] /= n
        return out


class FastEmbedEmbedder:
    name = "fastembed:BAAI/bge-small-en-v1.5"

    def __init__(self):
        from fastembed import TextEmbedding  # local ONNX model, downloaded on first use
        self.model = TextEmbedding("BAAI/bge-small-en-v1.5")

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.array(list(self.model.embed(texts)), dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


class OpenAIEmbedder:
    name = "openai:text-embedding-3-small"

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    def embed(self, texts: list[str]) -> np.ndarray:
        r = self.client.embeddings.create(model="text-embedding-3-small", input=texts)
        vecs = np.array([d.embedding for d in r.data], dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def make_embedder(kind: str | None = None):
    kind = kind or config.EMBEDDINGS
    return {"hash": HashEmbedder, "fastembed": FastEmbedEmbedder, "openai": OpenAIEmbedder}[kind]()


# ---------------- BM25 (small, dependency-free) ----------------
def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class BM25:
    def __init__(self, docs: list[str], k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [_tok(d) for d in docs]
        self.avgdl = sum(len(d) for d in self.docs) / max(1, len(self.docs))
        self.df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                self.df[t] = self.df.get(t, 0) + 1
        self.N = len(self.docs)

    def score(self, query: str) -> np.ndarray:
        q = _tok(query)
        scores = np.zeros(self.N)
        for i, d in enumerate(self.docs):
            dl = len(d)
            for t in q:
                tf = d.count(t)
                if not tf:
                    continue
                idf = math.log(1 + (self.N - self.df[t] + 0.5) / (self.df[t] + 0.5))
                scores[i] += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return scores


# ---------------- index ----------------
@dataclass
class ClauseRetriever:
    embedder: object
    hybrid: bool = False
    top_k: int = config.TOP_K
    rrf_k: int = 60
    clauses: list[Clause] = field(default_factory=load_clauses)
    last_hits: list[str] = field(default_factory=list)  # clause ids from the last search (for traces)

    def __post_init__(self):
        self._texts = [c.text for c in self.clauses]
        self._vecs = self.embedder.embed(self._texts)
        self._bm25 = BM25(self._texts)
        self._chroma = None
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
            name = "kyb_policy_" + re.sub(r"[^a-z0-9]", "_", self.embedder.name.lower())[:40]
            try:
                client.delete_collection(name)
            except Exception:  # noqa: BLE001
                pass
            col = client.create_collection(name, metadata={"hnsw:space": "cosine"})
            col.add(ids=[c.id for c in self.clauses], documents=self._texts, embeddings=self._vecs.tolist(),
                    metadatas=[self._meta(c) for c in self.clauses])
            self._chroma = col
        except Exception:  # noqa: BLE001 - chroma optional; numpy path is behaviourally identical
            self._chroma = None

    @staticmethod
    def _meta(c: Clause) -> dict:
        m = {"section": c.section}
        for e in ENTITY_TYPES:
            m[f"e_{e}"] = ("all" in c.entity_types) or (e in c.entity_types)
        return m

    def _mask(self, entity_type: str | None) -> np.ndarray:
        if not entity_type:
            return np.ones(len(self.clauses), dtype=bool)
        return np.array([c.applies_to(entity_type=entity_type) for c in self.clauses])

    def search(self, query: str, entity_type: str | None = None, k: int | None = None) -> list[Clause]:
        k = k or self.top_k
        mask = self._mask(entity_type)
        qv = self.embedder.embed([query])[0]
        dense = self._vecs @ qv
        dense[~mask] = -np.inf
        if self._chroma is not None and not self.hybrid:
            where = {f"e_{entity_type}": True} if entity_type else None
            res = self._chroma.query(query_embeddings=[qv.tolist()], n_results=k, where=where)
            ids = res["ids"][0]
        elif not self.hybrid:
            ids = [self.clauses[i].id for i in np.argsort(-dense)[:k]]
        else:
            sparse = self._bm25.score(query)
            sparse[~mask] = -np.inf
            rrf = np.zeros(len(self.clauses))
            for arr in (dense, sparse):
                order = np.argsort(-arr)
                for rank, i in enumerate(order):
                    if arr[i] == -np.inf:
                        continue
                    rrf[i] += 1.0 / (self.rrf_k + rank + 1)
            ids = [self.clauses[i].id for i in np.argsort(-rrf)[:k] if rrf[i] > 0]
        by_id = {c.id: c for c in self.clauses}
        hits = [by_id[i] for i in ids]
        self.last_hits = [c.id for c in hits]
        return hits


def retrieval_recall(retriever: ClauseRetriever, queries: list[tuple[str, str | None, list[str]]]) -> float:
    """queries: (query, entity_type, gold_clause_ids) → fraction of gold clauses found in top-k."""
    found = total = 0
    for q, et, gold in queries:
        ids = {c.id for c in retriever.search(q, entity_type=et)}
        found += len(ids & set(gold)); total += len(gold)
    return found / total if total else 0.0
