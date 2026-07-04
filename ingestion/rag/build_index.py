"""Build a persistent Chroma index from chunks.jsonl using OpenAI embeddings.

Usage (from ingestion/):
    python rag/build_index.py [--chunks rag/chunks/chunks.jsonl]
Requires OPENAI_API_KEY.
"""

import argparse
import json
from pathlib import Path

from llm_client import embed_texts, require_api_key

CHROMA_DIR = Path(__file__).parent / "chroma"
COLLECTION = "industry_docs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    args = parser.parse_args()

    require_api_key()

    records = [json.loads(line) for line in Path(args.chunks).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise SystemExit("chunks.jsonl 為空，請先執行 parse_documents.py")

    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(COLLECTION)

    texts = [r["text"] for r in records]
    embeddings = embed_texts(texts)
    collection.upsert(
        ids=[r["chunk_id"] for r in records],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {"source_id": r["source_id"], "file": r["file"],
             "company_id": r["company_id"] or "", "period": r["period"] or "", "seq": r["seq"]}
            for r in records
        ],
    )
    print(f"索引完成：{len(records)} 個 chunks → {CHROMA_DIR}（collection: {COLLECTION}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
