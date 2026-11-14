"""PostgreSQL + pgvector store: exact cosine search with SQL metadata filters."""
from __future__ import annotations

from typing import Any

import psycopg

from .models import Chunk

ALLOWED_FILTERS = {"document_type", "document_id", "source_id", "chapter", "article"}


def _vec(values: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is empty")
        if not isinstance(dimensions, int) or dimensions <= 0:
            raise ValueError("dimensions must be a positive int")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, connect_timeout=5)

    def create_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_url TEXT,
                    page INT NOT NULL,
                    document_type TEXT,
                    chapter TEXT,
                    article INT,
                    text TEXT NOT NULL,
                    text_sha1 TEXT NOT NULL,
                    embedding vector({int(self.dimensions)}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )""")
            cur.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'")
            existing = cur.fetchone()[0]
            if existing != self.dimensions:
                raise RuntimeError(f"table 'chunks' has vector({existing}) but the model returns {self.dimensions}; "
                                   "drop the table deliberately before switching models")
            cur.execute("CREATE INDEX IF NOT EXISTS chunks_filter_idx ON chunks (strategy, document_type)")

    def existing_hashes(self, strategy: str) -> dict[str, str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT chunk_id, text_sha1 FROM chunks WHERE strategy = %s", (strategy,))
            return dict(cur.fetchall())

    def count(self, strategy: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,))
            return cur.fetchone()[0]

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]],
               keep_ids: set[str] | None = None) -> dict[str, int]:
        """Write chunks by stable (strategy, chunk_id); never duplicates.

        keep_ids = full set of chunk IDs that should exist for this strategy;
        anything else (obsolete chunks of changed/removed documents) is deleted.
        """
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors differ in length")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"vector dimension != {self.dimensions}")
        rows = [(strategy, c.chunk_id, c.document_id, c.source, c.metadata.get("source_url"), c.page,
                 c.metadata.get("document_type"), c.metadata.get("chapter"), c.metadata.get("article"),
                 c.text, c.metadata["text_sha1"], _vec(v)) for c, v in zip(chunks, vectors)]
        deleted = 0
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO chunks (strategy, chunk_id, document_id, source_id, source_url, page,
                                    document_type, chapter, article, text, text_sha1, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                    document_id = EXCLUDED.document_id, source_id = EXCLUDED.source_id,
                    source_url = EXCLUDED.source_url, page = EXCLUDED.page,
                    document_type = EXCLUDED.document_type, chapter = EXCLUDED.chapter,
                    article = EXCLUDED.article, text = EXCLUDED.text,
                    text_sha1 = EXCLUDED.text_sha1, embedding = EXCLUDED.embedding""", rows)
            if keep_ids is not None:
                cur.execute("DELETE FROM chunks WHERE strategy = %s AND NOT (chunk_id = ANY(%s))",
                            (strategy, list(keep_ids)))
                deleted = cur.rowcount
        return {"upserted": len(rows), "deleted_obsolete": deleted}

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError("query vector dimension mismatch")
        where, params = ["strategy = %s"], [strategy]
        for key, value in (filters or {}).items():
            if key not in ALLOWED_FILTERS:
                raise ValueError(f"filter '{key}' not allowed; use {sorted(ALLOWED_FILTERS)}")
            where.append(f"{key} = %s")  # column name from the allow-list, value parameterized
            params.append(value)
        vec = _vec(query_vector)
        sql = f"""
            SELECT chunk_id, text, 1 - (embedding <=> %s::vector) AS score, source_id, source_url, page,
                   document_id, document_type, chapter, article
            FROM chunks WHERE {' AND '.join(where)}
            ORDER BY embedding <=> %s::vector LIMIT %s"""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, [vec, *params, vec, top_k])
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
