# Company Data Enrichment Workflow

Purpose: keep the graph growing in a repeatable way without losing source traceability. This workflow is the staging ground for a future Codex skill.

## Scope

Maintain two reusable company universes:

- Taiwan large-cap universe: `ingestion/seeds/universe_tw_top100.csv`
- US large-cap research universe: `ingestion/seeds/universe_us_large_cap.csv`

Maintain one progress table:

- `ingestion/progress/company_update_progress.csv`

The progress table is the shared handoff point for future agents. Update it whenever sources are refreshed, filings are parsed, relationships are extracted, or review depth changes.

## One Command

Refresh the company universe and official source pointers:

```powershell
python ingestion/scripts/refresh_company_universe.py --write
```

Then validate and import:

```powershell
python ingestion/validators/validate.py ingestion/seeds
python ingestion/scripts/import_graph.py --seeds ingestion/seeds
```

Download registered official source URLs into the RAG document store:

```powershell
python ingestion/scripts/sync_sources_to_rag_manifest.py
python ingestion/rag/parse_documents.py
```

Build a staged Chroma index. Existing chunk IDs are skipped by default, so the command is safe to rerun:

```powershell
python ingestion/rag/build_index.py --batch-size 32 --max-chunks 512
python ingestion/rag/build_index.py --batch-size 32
```

For explicit staged continuation, use `--start-offset` and `--max-chunks`:

```powershell
python ingestion/rag/build_index.py --batch-size 32 --start-offset 9536 --max-chunks 1024
```

Use `--rebuild-existing` only when the source documents changed and existing embeddings must be refreshed.

Dry run first when changing the universe:

```powershell
python ingestion/scripts/refresh_company_universe.py
```

## Data Depth

Use `data_depth` consistently:

- `company_seed`: Company node only.
- `company_seed; some manual_seed relationships`: Company exists with partial seed relationships.
- `official_sources_registered`: Company has official annual/quarterly source pointers.
- `company+latest_sec_sources+candidate_product_edges`: Company has official SEC filing pointers and basic candidate product/service edges.
- `documents_parsed`: Official filings are downloaded/parsed into chunks.
- `company+official_sources+local_documents+rag_chunks`: Company has official source pointers, local documents, and parsed RAG chunks.
- `company+official_sources+local_documents+rag_chunks+chroma_index`: Parsed chunks are fully indexed in Chroma for RAG search/extraction.
- `relationships_extracted`: Candidate relationships were extracted from filings.
- `reviewed_verified`: Human review accepted relationships into verified status.

## Source Rules

- Prefer official sources: SEC, TWSE, MOPS, company investor relations.
- Every relationship must have `source_ids`.
- New extracted or agent-curated relationships must be `status=candidate`.
- Do not use vague relationship types such as `RELATED_TO`, `LINKED_TO`, or `ASSOCIATED_WITH`.
- Do not change schema to force data in. Report schema mismatch first.
- If a node already exists, reuse it. IDs are globally unique across Company/Product/Industry/Application/Source.
- For technical terms, keep English terms in display text: `data center`, `HBM`, `IC`, `GPU`, `cloud`, `AI`.

## Taiwan Company Flow

1. Start from `ingestion/seeds/universe_tw_top100.csv`.
2. Confirm the company exists in `seed_companies.csv`; add missing companies using `TWSE_xxxx` or `TPEX_xxxx`.
3. Register official sources in `seed_sources.csv`: MOPS, company IR, TWSE/TPEX market data.
4. Download or register report documents in `ingestion/rag/documents/manifest.csv` when using the RAG pipeline.
5. Extract candidate relationships only after source registration.
6. Update `ingestion/progress/company_update_progress.csv`.

MOPS note: direct scripted access to individual report query endpoints can return the MOPS security block page. Prefer company IR report URLs when available, and keep MOPS rows as official source indexes unless a stable document URL is resolved.

## US Company Flow

The current automation uses official SEC data:

- Company/ticker/exchange map: `https://www.sec.gov/files/company_tickers_exchange.json`
- Company submissions JSON: `https://data.sec.gov/submissions/CIK##########.json`
- Latest 10-K and 10-Q filing documents from SEC Archives.

`refresh_company_universe.py --write` adds:

- Missing US company nodes.
- SEC source rows for company submissions, latest 10-K, and latest 10-Q.
- Basic candidate `SELLS` / `PRODUCES` product exposure edges.
- Progress rows.

These candidate product edges are first-pass exposure mapping. They are not verified supply-chain relationships.

## Next Extraction Step

For deeper updates, use official filings:

```powershell
cd ingestion
python rag/parse_documents.py
python rag/build_index.py --batch-size 32
python rag/select_extraction_chunks.py --company-id US_MSFT --limit 30
python rag/extract.py --chunks rag/extracted/selected_chunks.jsonl --out rag/extracted/candidates_raw.jsonl --unresolved-out rag/extracted/unresolved_raw.jsonl
python rag/load_candidates.py --candidates rag/extracted/candidates_reviewed.jsonl --dry-run
python rag/load_candidates.py --candidates rag/extracted/candidates_reviewed.jsonl
```

Useful extraction controls:

```powershell
python rag/select_extraction_chunks.py --universe US_LARGE_CAP_RESEARCH_UNIVERSE --limit-per-company 2 --out rag/extracted/us_round1_selected_chunks.jsonl
python rag/extract.py --source-id source_sec_msft_2025_10k --start-offset 80 --max-chunks 10
python rag/extract.py --company-id US_NVDA --max-chunks 50 --append --unresolved-out rag/extracted/us_nvda_unresolved.jsonl
python rag/load_candidates.py --candidates rag/extracted/candidates_reviewed.jsonl --dry-run
```

Always review `candidates_raw.jsonl` before loading. Copy only concrete, schema-valid, source-backed relationships into a reviewed JSONL file. Keep rejected or unresolved records for the next node/product expansion pass.

`load_candidates.py --dry-run` validates candidate JSONL against Neo4j before writing:

- endpoint nodes exist;
- `source_id` exists;
- relationship type and endpoint labels are allowed;
- confidence is between `0` and `0.8`;
- duplicate candidate keys are reported.

Loaded RAG/LLM relationships are always `status=candidate`, `created_by=llm_extraction`, and `value_type=inferred`. Then review in `/review` before any verification.

## Review Checklist

- Source exists and URL is official.
- Relationship type is allowed by `docs/development/relationship-types.md`.
- Source IDs are present.
- Candidate relationships are not accidentally marked `verified`.
- No duplicate node ID was created.
- Product/Application names are concrete, not vague.
- `company_update_progress.csv` has updated `last_updated_at`, `data_depth`, and notes.

## Current Starting Point

As of the first workflow setup:

- Taiwan top 100 universe exists and is tracked in progress.
- Taiwan top 100 companies have MOPS annual-report and financial-report source index rows.
- Taiwan top 100 companies have seed industry and product/service exposure relationships.
- 68 US companies are tracked in the US large-cap research universe, including previously seeded US companies.
- SEC official source pointers were registered for those US companies.
- 118 US product/service exposure relationships were added as candidate data.
- 66 US industry classification relationships were added as candidate `BELONGS_TO` data.
- `company_update_progress.csv` covers every company currently in `seed_companies.csv`.
- 220 official/source documents are registered in the RAG manifest.
- 102,830 chunks were parsed from local official documents.
- The Chroma index contains all 102,830 parsed chunks.
- First guarded US RAG extraction round selected 136 chunks, produced raw candidate/unresolved files, and loaded 6 reviewed `llm_extraction` candidate relationships for AMD, Costco, PepsiCo, and Tesla.
