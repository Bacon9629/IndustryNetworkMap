"""Extract candidate graph relationships from parsed chunks with an LLM.

Usage (from ingestion/):
    python rag/extract.py --company-id US_MSFT --max-chunks 20
    python rag/extract.py --source-id source_sec_msft_2025_10k --start-offset 80 --max-chunks 10

Output is JSONL candidate data. It is not written to Neo4j here; use load_candidates.py.
All extracted relationships must remain candidate until reviewed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.validate import FORBIDDEN_TYPES, REL_TYPE_RULES  # noqa: E402

from llm_client import DEFAULT_MODEL, get_client  # noqa: E402

EXTRACTABLE_TYPES = sorted(t for t in REL_TYPE_RULES if t not in {"SUPPORTED_BY", "FROM_SOURCE"})

CURRENT_COMPANY_TERMS = {
    "company",
    "the company",
    "our company",
    "we",
    "us",
    "our",
    "ours",
    "registrant",
}

VAGUE_ENTITY_TERMS = {
    "competitor",
    "competitors",
    "customer",
    "customers",
    "client",
    "clients",
    "supplier",
    "suppliers",
    "vendor",
    "vendors",
    "partner",
    "partners",
    "ai companies",
    "software companies",
    "hardware manufacturers",
    "semiconductor companies",
    "domestic equipment manufacturers",
    "operating system developers",
    "social media companies",
}

EXTRACTION_SCHEMA = {
    "name": "relationship_extraction",
    "schema": {
        "type": "object",
        "properties": {
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_name": {"type": "string"},
                        "to_name": {"type": "string"},
                        "type": {"type": "string", "enum": EXTRACTABLE_TYPES},
                        "product": {"type": ["string", "null"]},
                        "evidence": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "period": {"type": ["string", "null"]},
                    },
                    "required": ["from_name", "to_name", "type", "product", "evidence", "confidence", "period"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["relationships"],
        "additionalProperties": False,
    },
    "strict": True,
}

SYSTEM_PROMPT = f"""You extract concrete industry-graph relationships from official company filings.

Rules:
1. Only emit a relationship when the supplied text explicitly supports it.
2. Use only these relationship types: {", ".join(EXTRACTABLE_TYPES)}.
3. Do not invent vague relationships such as RELATED_TO, LINKED_TO, ASSOCIATED_WITH, PARTNERS_WITH, or CONNECTED_TO.
4. Prefer concrete Company/Product/Application names that already appear in the graph.
5. If the text says a company buys from another company, emit BUYS_FROM; this pipeline will normalize it to SUPPLIES_TO.
6. Keep confidence at or below 0.8 because all output is candidate data awaiting review.
7. If no concrete relationship is supported, return an empty relationships array.
8. Evidence must be a short paraphrase or short quote from the supplied text, not outside knowledge.
9. The supplied text is from the reporting company's own filing. If the text says "we", "our", or "the Company",
   use the reporting company name provided by the user message.
10. Do not emit relationships to vague groups such as competitors, customers, suppliers, vendors, AI companies,
    software companies, or hardware manufacturers unless a specific existing company name is explicitly given.
"""


def normalize_name(name: str | None) -> str:
    return " ".join((name or "").strip().lower().replace(".", "").split())


def is_current_company_term(name: str | None) -> bool:
    return normalize_name(name) in CURRENT_COMPANY_TERMS


def is_vague_entity(name: str | None) -> bool:
    return normalize_name(name) in VAGUE_ENTITY_TERMS


def load_node_catalog(session) -> dict[str, dict]:
    rows = session.run(
        """
        MATCH (n)
        WHERE labels(n)[0] IN ['Company', 'Product', 'Industry', 'Application']
        RETURN n.id AS id,
               n.name AS name,
               n.english_name AS english_name,
               n.ticker AS ticker,
               coalesce(n.aliases, []) AS aliases,
               labels(n)[0] AS label
        ORDER BY labels(n)[0], n.id
        """
    )
    return {row["id"]: dict(row) for row in rows}


def catalog_lines(catalog: dict[str, dict], label: str, limit: int = 200) -> str:
    lines = []
    for node in catalog.values():
        if node["label"] != label:
            continue
        bits = [node["name"]]
        if node.get("english_name") and node["english_name"] != node["name"]:
            bits.append(node["english_name"])
        if node.get("ticker"):
            bits.append(node["ticker"])
        aliases = [a for a in node.get("aliases", []) if a]
        if aliases:
            bits.append("/".join(aliases[:3]))
        lines.append(f"- {node['id']}: {' | '.join(bits)}")
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def relationship_rule_lines() -> str:
    lines = []
    for rel_type in EXTRACTABLE_TYPES:
        allowed_from, allowed_to = REL_TYPE_RULES[rel_type]
        lines.append(f"- {rel_type}: {'/'.join(sorted(allowed_from))} -> {'/'.join(sorted(allowed_to))}")
    return "\n".join(lines)


def build_user_prompt(rec: dict, current_company: dict | None, catalog: dict[str, dict]) -> str:
    company_name = current_company["name"] if current_company else rec.get("company_id", "")
    company_bits = [
        f"id={rec.get('company_id', '')}",
        f"name={company_name}",
        f"source_id={rec.get('source_id', '')}",
        f"period={rec.get('period') or ''}",
    ]
    if current_company:
        if current_company.get("english_name"):
            company_bits.append(f"english_name={current_company['english_name']}")
        if current_company.get("ticker"):
            company_bits.append(f"ticker={current_company['ticker']}")

    return f"""Reporting company: {'; '.join(company_bits)}

Existing graph Product nodes:
{catalog_lines(catalog, 'Product')}

Existing graph Application nodes:
{catalog_lines(catalog, 'Application')}

Existing graph Industry nodes:
{catalog_lines(catalog, 'Industry')}

Allowed relationship endpoints:
{relationship_rule_lines()}

Extraction constraints:
- Every Company-to-Company relationship must involve the reporting company.
- Company-to-Product relationships should use the reporting company as the Company side.
- Use existing Product/Application/Industry names from the catalog when possible.
- If a named competitor, supplier, customer, distributor, or partner is not explicit in the text, omit it.
- If the text only names a vague group, return no relationship for that sentence.

Text:
{rec["text"]}"""


def resolve_node(session, name: str | None, current_company: dict | None = None) -> dict | None:
    if not name or not name.strip():
        return None
    if current_company and is_current_company_term(name):
        return {
            "id": current_company["id"],
            "name": current_company["name"],
            "label": current_company["label"],
        }
    rows = session.run(
        """
        MATCH (n)
        WHERE labels(n)[0] IN ['Company', 'Product', 'Industry', 'Application']
          AND (
            n.id = $name OR n.name = $name OR n.english_name = $name OR n.ticker = $name
            OR $name IN coalesce(n.aliases, [])
            OR toLower(n.name) = toLower($name)
            OR toLower(n.english_name) = toLower($name)
            OR toLower(n.id) = toLower($name)
            OR ANY(alias IN coalesce(n.aliases, []) WHERE toLower(alias) = toLower($name))
          )
        RETURN n.id AS id, n.name AS name, labels(n)[0] AS label
        LIMIT 1
        """,
        name=name.strip(),
    ).single()
    return dict(rows) if rows else None


def relationship_matches_reporting_company(rel_type: str, frm: dict, to: dict, company_id: str | None) -> bool:
    if not company_id:
        return True
    allowed_from, allowed_to = REL_TYPE_RULES[rel_type]
    if allowed_from == {"Company"} and allowed_to == {"Company"}:
        return frm["id"] == company_id or to["id"] == company_id
    if "Company" in allowed_from and frm["label"] == "Company":
        return frm["id"] == company_id
    if "Company" in allowed_to and to["label"] == "Company":
        return to["id"] == company_id
    return True


def load_records(path: Path, company_id: str | None, source_id: str | None) -> list[dict]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if company_id:
        records = [r for r in records if r.get("company_id") == company_id]
    if source_id:
        records = [r for r in records if r.get("source_id") == source_id]
    return records


def existing_chunk_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("chunk_id"):
            ids.add(rec["chunk_id"])
    return ids


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "extracted" / "candidates.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--company-id", help="Only process chunks for this company_id.")
    parser.add_argument("--source-id", help="Only process chunks for this source_id.")
    parser.add_argument("--start-offset", type=int, default=0, help="Skip this many selected chunks.")
    parser.add_argument("--max-chunks", type=int, default=0, help="Maximum selected chunks to process.")
    parser.add_argument("--append", action="store_true", help="Append to the output files instead of replacing them.")
    parser.add_argument("--skip-existing-chunks", action="store_true", help="Skip chunks already present in the output JSONL.")
    parser.add_argument("--unresolved-out", help="Write unresolved or rejected extraction records to this JSONL file.")
    args = parser.parse_args()

    if args.start_offset < 0:
        raise SystemExit("--start-offset must be >= 0")

    records = load_records(Path(args.chunks), args.company_id, args.source_id)
    if args.skip_existing_chunks:
        done = existing_chunk_ids(Path(args.out))
        records = [r for r in records if r.get("chunk_id") not in done]
    records = records[args.start_offset:]
    if args.max_chunks:
        records = records[: args.max_chunks]
    if not records:
        raise SystemExit("No chunks selected for extraction.")

    client = get_client()

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "industrymap_dev")),
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    unresolved_path = Path(args.unresolved_out) if args.unresolved_out else out_path.parent / "unresolved_entities.jsonl"
    unresolved_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"

    n_ok = 0
    n_unresolved = 0
    n_invalid = 0
    with (
        open(out_path, mode, encoding="utf-8") as out,
        open(unresolved_path, mode, encoding="utf-8") as unres,
        driver.session() as session,
    ):
        catalog = load_node_catalog(session)
        for index, rec in enumerate(records, start=1):
            current_company = catalog.get(rec.get("company_id"))
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(rec, current_company, catalog)},
                ],
                response_format={"type": "json_schema", "json_schema": EXTRACTION_SCHEMA},
            )
            rels = json.loads(resp.choices[0].message.content)["relationships"]
            for rel in rels:
                rel_type = rel["type"]
                if rel_type in FORBIDDEN_TYPES or rel_type not in REL_TYPE_RULES:
                    n_invalid += 1
                    continue
                if rel_type == "BUYS_FROM":
                    rel_type = "SUPPLIES_TO"
                    rel["from_name"], rel["to_name"] = rel["to_name"], rel["from_name"]

                if (
                    not is_current_company_term(rel["from_name"])
                    and is_vague_entity(rel["from_name"])
                ) or (
                    not is_current_company_term(rel["to_name"])
                    and is_vague_entity(rel["to_name"])
                ):
                    unres.write(
                        json.dumps(
                            {
                                **rel,
                                "chunk_id": rec["chunk_id"],
                                "source_id": rec["source_id"],
                                "reason": "vague_entity",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    n_invalid += 1
                    continue

                frm = resolve_node(session, rel["from_name"], current_company)
                to = resolve_node(session, rel["to_name"], current_company)
                if not to and rel.get("product"):
                    product_to = resolve_node(session, rel["product"], current_company)
                    if product_to and product_to["label"] == "Product":
                        to = product_to
                if not frm or not to:
                    unres.write(
                        json.dumps(
                            {
                                **rel,
                                "chunk_id": rec["chunk_id"],
                                "source_id": rec["source_id"],
                                "from_resolved": frm,
                                "to_resolved": to,
                                "reason": "unresolved_node",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    n_unresolved += 1
                    continue

                allowed_from, allowed_to = REL_TYPE_RULES[rel_type]
                if frm["label"] not in allowed_from or to["label"] not in allowed_to:
                    n_invalid += 1
                    continue
                if not relationship_matches_reporting_company(rel_type, frm, to, rec.get("company_id")):
                    unres.write(
                        json.dumps(
                            {
                                **rel,
                                "chunk_id": rec["chunk_id"],
                                "source_id": rec["source_id"],
                                "from_resolved": frm,
                                "to_resolved": to,
                                "reason": "does_not_involve_reporting_company",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    n_invalid += 1
                    continue

                product = resolve_node(session, rel["product"], current_company) if rel.get("product") else None
                out.write(
                    json.dumps(
                        {
                            "from_id": frm["id"],
                            "from_label": frm["label"],
                            "to_id": to["id"],
                            "to_label": to["label"],
                            "type": rel_type,
                            "product_id": product["id"] if product and product["label"] == "Product" else None,
                            "evidence": rel["evidence"],
                            "confidence": min(float(rel["confidence"]), 0.8),
                            "period": rel.get("period") or rec.get("period"),
                            "source_id": rec["source_id"],
                            "chunk_id": rec["chunk_id"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                n_ok += 1
            print(f"{index}/{len(records)} {rec['chunk_id']}: extracted={len(rels)}", flush=True)

    driver.close()
    print(
        f"Extraction complete: candidates={n_ok}, unresolved={n_unresolved}, invalid={n_invalid}, "
        f"out={out_path}, unresolved_out={unresolved_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
