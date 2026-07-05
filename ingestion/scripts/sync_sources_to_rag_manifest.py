"""Download seeded source URLs into rag/documents and maintain manifest.csv.

The graph stores source metadata, while the RAG pipeline needs local files.
This script bridges the two in a repeatable way.

Usage:
    python ingestion/scripts/sync_sources_to_rag_manifest.py
    python ingestion/scripts/sync_sources_to_rag_manifest.py --refresh
"""

from __future__ import annotations

import argparse
import csv
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SEEDS = ROOT / "ingestion" / "seeds"
DOCS = ROOT / "ingestion" / "rag" / "documents"
MANIFEST = DOCS / "manifest.csv"
OFFICIAL_DIR = DOCS / "official"

USER_AGENT = "IndustryNetworkMap/0.1 contact: local-research@example.com"
MANIFEST_FIELDS = ["file", "source_id", "company_id", "period", "type", "url", "title", "language"]
DOWNLOAD_TYPES = {"annual_report", "financial_report", "company_website", "exchange_data", "mops"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write_manifest(rows: list[dict[str, str]]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def extension_for(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".txt", ".html", ".htm", ".pdf", ".json"}:
        return suffix
    content_type = content_type.lower()
    if "pdf" in content_type:
        return ".pdf"
    if "json" in content_type:
        return ".json"
    if "text/plain" in content_type:
        return ".txt"
    return ".html"


def open_url(req: urllib.request.Request):
    try:
        return urllib.request.urlopen(req, timeout=45)
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLError):
            context = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=45, context=context)
        raise


def download(url: str, out_stem: Path) -> tuple[Path | None, str | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json,application/pdf,text/plain,*/*",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with open_url(req) as resp:
            data = resp.read()
            content_type = resp.headers.get("content-type", "")
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, str(exc)

    ext = extension_for(url, content_type)
    out_path = out_stem.with_suffix(ext)
    out_path.write_bytes(data)
    return out_path, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Redownload files even if already present.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max downloads for testing.")
    parser.add_argument("--include-mops", action="store_true", help="Download MOPS search pages too.")
    args = parser.parse_args()

    sources = read_csv(SEEDS / "seed_sources.csv")
    existing_manifest = read_csv(MANIFEST) if MANIFEST.exists() else []
    manifest_by_source = {row["source_id"]: row for row in existing_manifest}
    OFFICIAL_DIR.mkdir(parents=True, exist_ok=True)

    attempted = downloaded = skipped = failed = 0
    for source in sources:
        source_id = source.get("id", "")
        url = source.get("url", "")
        source_type = source.get("type", "")
        if not source_id or not url or source_type not in DOWNLOAD_TYPES:
            continue
        if source_type == "mops" and not args.include_mops:
            continue
        if source_id in manifest_by_source and not args.refresh:
            skipped += 1
            continue
        if args.limit and attempted >= args.limit:
            break

        attempted += 1
        out_stem = OFFICIAL_DIR / source_id
        existing_files = list(OFFICIAL_DIR.glob(source_id + ".*"))
        if existing_files and not args.refresh:
            out_path = existing_files[0]
            error = None
        else:
            if "sec.gov" in url:
                time.sleep(0.12)
            out_path, error = download(url, out_stem)
        if error or not out_path:
            failed += 1
            print(f"FAILED {source_id}: {error}")
            continue

        rel_file = out_path.relative_to(DOCS).as_posix()
        manifest_by_source[source_id] = {
            "file": rel_file,
            "source_id": source_id,
            "company_id": source.get("company_id", ""),
            "period": source.get("period", ""),
            "type": source_type,
            "url": url,
            "title": source.get("title", ""),
            "language": source.get("language", ""),
        }
        downloaded += 1
        print(f"OK {source_id} -> {rel_file}")

    rows = list(manifest_by_source.values())
    rows.sort(key=lambda row: row["source_id"])
    write_manifest(rows)
    print(f"manifest rows: {len(rows)}; attempted: {attempted}; downloaded/linked: {downloaded}; skipped: {skipped}; failed: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
