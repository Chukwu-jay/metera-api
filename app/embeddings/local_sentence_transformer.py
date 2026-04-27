from __future__ import annotations

import hashlib

from app.embeddings.base import EmbeddingResult


class LocalSentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._backend = "uninitialized"

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def is_fallback(self) -> bool:
        return self._backend == "fallback"

    async def warmup(self) -> None:
        await self.embed("warmup")

    async def embed(self, text: str) -> EmbeddingResult:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                self._backend = "sentence-transformers"
            except Exception:
                self._model = False
                self._backend = "fallback"

        if self._model:
            vector = self._model.encode(text).tolist()
        else:
            vector = _fallback_embed(text)
        return EmbeddingResult(text=text, vector=vector, model_name=self.model_name)


def _fallback_embed(text: str, dimensions: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append(byte / 255.0)
    return values
