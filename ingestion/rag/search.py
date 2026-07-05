"""Search the Chroma index.

Usage (from ingestion/):
    python rag/search.py "query text" [-k 5]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm_client import embed_texts

CHROMA_DIR = Path(__file__).parent / "chroma"
COLLECTION = "industry_docs"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(COLLECTION)

    embedding = embed_texts([args.query])[0]
    res = collection.query(query_embeddings=[embedding], n_results=args.k)

    for chunk_id, doc, meta, dist in zip(
        res["ids"][0],
        res["documents"][0],
        res["metadatas"][0],
        res["distances"][0],
    ):
        print(f"--- {chunk_id} (source: {meta['source_id']}, distance: {dist:.4f})")
        print(doc[:200].replace("\n", " "))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
