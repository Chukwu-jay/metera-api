from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

IMAGE_TAG = os.getenv("METERA_DOCKER_IMAGE", "metera:semantic-validate")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    build_cmd = [
        "docker",
        "build",
        "-t",
        IMAGE_TAG,
        ".",
    ]
    _run(build_cmd, cwd=PROJECT_ROOT)

    import_cmd = (
        "import sentence_transformers; "
        "print('sentence_transformers_ok', sentence_transformers.__version__)"
    )
    _run([
        "docker",
        "run",
        "--rm",
        IMAGE_TAG,
        "python",
        "-c",
        import_cmd,
    ])

    metera_cmd = (
        "from app.embeddings.local_sentence_transformer import LocalSentenceTransformerEmbedder; "
        "embedder = LocalSentenceTransformerEmbedder(); "
        "print('metera_embedder_ok', embedder.model_name)"
    )
    _run([
        "docker",
        "run",
        "--rm",
        IMAGE_TAG,
        "python",
        "-c",
        metera_cmd,
    ])

    print("VALIDATED: Docker image builds and semantic dependencies import successfully")
    return 0


def _run(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, shell=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
