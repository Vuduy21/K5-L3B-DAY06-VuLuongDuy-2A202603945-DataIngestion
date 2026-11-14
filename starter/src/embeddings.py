"""Embeddings through the OpenRouter embeddings API (one real model, no fallback).

Raises EmbeddingError on any failure; it never returns mock or random vectors.
bge-m3 needs no query/document prefix, so both methods embed text unchanged.
"""
from __future__ import annotations

import os
import time
from typing import Protocol

import requests

API_URL = "https://openrouter.ai/api/v1/embeddings"


class EmbeddingError(RuntimeError):
    pass


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    """OpenRouter adapter. Tracks tokens, cost and request time for the report."""

    def __init__(self, model_name: str, batch_size: int = 32, max_retries: int = 4) -> None:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise EmbeddingError("OPENROUTER_API_KEY is empty; fill starter/.env")
        if not model_name:
            raise EmbeddingError("EMBEDDING_MODEL is empty; e.g. baai/bge-m3")
        self.model_name = model_name
        self._key = key
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.usage = {"requests": 0, "prompt_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "cost_reported": False,
                      "seconds": 0.0}
        probe = self._request(["kiểm tra kết nối"])
        self.dimensions = len(probe[0])

    def _request(self, texts: list[str]) -> list[list[float]]:
        body = {"model": self.model_name, "input": texts, "encoding_format": "float"}
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        last = ""
        for attempt in range(self.max_retries):
            started = time.perf_counter()
            try:
                resp = requests.post(API_URL, json=body, headers=headers, timeout=120)
            except requests.RequestException as exc:
                last = f"network error: {type(exc).__name__}"
            else:
                self.usage["seconds"] += time.perf_counter() - started
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("data")
                    if not rows or len(rows) != len(texts):
                        raise EmbeddingError(f"unexpected response shape: {str(data)[:200]}")
                    usage = data.get("usage") or {}
                    self.usage["requests"] += 1
                    self.usage["prompt_tokens"] += usage.get("prompt_tokens") or 0
                    self.usage["total_tokens"] += usage.get("total_tokens") or 0
                    if usage.get("cost") is not None:
                        self.usage["cost_usd"] += float(usage["cost"])
                        self.usage["cost_reported"] = True
                    return [r["embedding"] for r in sorted(rows, key=lambda r: r["index"])]
                last = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code not in (408, 429, 500, 502, 503, 504):
                    break  # auth / bad request: retrying will not help
            time.sleep(2 ** attempt)
        raise EmbeddingError(f"embedding request failed after retries: {last}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            vectors.extend(self._request(texts[i:i + self.batch_size]))
        return vectors

    def embed_query(self, question: str) -> list[float]:
        return self._request([question])[0]
