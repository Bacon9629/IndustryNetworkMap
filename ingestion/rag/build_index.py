"""Build a persistent Chroma index from chunks.jsonl using OpenAI embeddings.

Usage (from ingestion/):
    python rag/build_index.py [--chunks rag/chunks/chunks.jsonl]

Requires OPENAI_API_KEY only when new chunks need embeddings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_client import embed_texts, require_api_key

CHROMA_DIR = Path(__file__).parent / "chroma"
COLLECTION = "industry_docs"
DEFAULT_BATCH_SIZE = 64


def get_existing_ids(collection, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    try:
        existing = collection.get(ids=ids, include=[])
    except TypeError:
        existing = collection.get(ids=ids)
    return set(existing.get("ids") or [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--start-offset", type=int, default=0, help="Skip this many chunk records before indexing.")
    parser.add_argument("--max-chunks", type=int, default=0, help="Optional cap after --start-offset for staged indexing.")
    parser.add_argument(
        "--rebuild-existing",
        action="store_true",
        help="Re-embed chunks even when the chunk_id already exists in Chroma.",
    )
    args = parser.parse_args()

    if args.start_offset < 0:
        raise SystemExit("--start-offset must be >= 0")

    chunks_path = Path(args.chunks)
    all_records = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = all_records[args.start_offset:]
    if args.max_chunks:
        records = records[:args.max_chunks]
    if not records:
        raise SystemExit("No chunks selected. Run parse_documents.py first or adjust --start-offset/--max-chunks.")

    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(COLLECTION)

    batch_size = max(1, args.batch_size)
    embedded = 0
    skipped = 0
    checked_api_key = False

    for start in range(0, len(records), batch_size):
        raw_batch = records[start:start + batch_size]
        batch_ids = [r["chunk_id"] for r in raw_batch]
        if args.rebuild_existing:
            batch = raw_batch
        else:
            existing_ids = get_existing_ids(collection, batch_ids)
            batch = [r for r in raw_batch if r["chunk_id"] not in existing_ids]
            skipped += len(raw_batch) - len(batch)

        selected_total = min(start + batch_size, len(records))
        absolute_total = args.start_offset + selected_total
        if not batch:
            print(
                f"skipped existing chunks {selected_total}/{len(records)} "
                f"(absolute {absolute_total}/{len(all_records)})",
                flush=True,
            )
            continue

        if not checked_api_key:
            require_api_key()
            checked_api_key = True

        texts = [r["text"] for r in batch]
        embeddings = embed_texts(texts)
        collection.upsert(
            ids=[r["chunk_id"] for r in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "source_id": r["source_id"],
                    "file": r["file"],
                    "company_id": r["company_id"] or "",
                    "period": r["period"] or "",
                    "seq": r["seq"],
                }
                for r in batch
            ],
        )
        embedded += len(batch)
        print(
            f"indexed {selected_total}/{len(records)} selected chunks "
            f"(absolute {absolute_total}/{len(all_records)}; embedded {embedded}, skipped {skipped})",
            flush=True,
        )

    print(
        f"Indexed run complete: selected={len(records)}, embedded={embedded}, skipped={skipped}, "
        f"collection_count={collection.count()}, chroma_dir={CHROMA_DIR}, collection={COLLECTION}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
