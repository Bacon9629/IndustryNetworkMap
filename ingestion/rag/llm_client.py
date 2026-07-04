"""Shared OpenAI client wrapper. Env: OPENAI_API_KEY (required), OPENAI_MODEL, OPENAI_EMBEDDING_MODEL."""

import os
from pathlib import Path

# 讀取 repo 根目錄 .env，已存在的環境變數優先
_env_file = Path(__file__).resolve().parents[2] / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def require_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "缺少 OPENAI_API_KEY 環境變數。此步驟需要 OpenAI API；"
            "parsing / chunking 等不需 LLM 的步驟可先執行。"
        )
    return key


def get_client():
    from openai import OpenAI
    require_api_key()
    return OpenAI()


def embed_texts(texts: list[str], model: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
    client = get_client()
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]
