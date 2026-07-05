"""Parse manifest documents (txt / html / pdf) into retrievable chunks.

Usage (from ingestion/):
    python rag/parse_documents.py [--manifest rag/documents/manifest.csv] [--out rag/chunks/chunks.jsonl]

Chunking: about 800 characters with 100 characters of overlap.
Each chunk keeps source_id, file, company_id, period, and sequence metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {".html", ".htm"}:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        return soup.get_text(separator="\n")
    return path.read_text(encoding="utf-8")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(Path(__file__).parent / "documents" / "manifest.csv"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(manifest_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    n_chunks = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for row in rows:
            doc_path = manifest_path.parent / row["file"]
            text = read_text(doc_path)
            chunks = chunk_text(text)
            for seq, chunk in enumerate(chunks):
                record = {
                    "chunk_id": f"{row['source_id']}_chunk_{seq:03d}",
                    "source_id": row["source_id"],
                    "file": row["file"],
                    "company_id": (row.get("company_id") or "").strip() or None,
                    "period": (row.get("period") or "").strip() or None,
                    "seq": seq,
                    "text": chunk,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_chunks += 1
            print(f"{row['file']}: {len(chunks)} chunks")
    print(f"Parsed {len(rows)} documents into {n_chunks} chunks: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
