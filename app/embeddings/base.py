from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    text: str
    vector: list[float]
    model_name: str


class Embedder(Protocol):
    async def embed(self, text: str) -> EmbeddingResult: ...
