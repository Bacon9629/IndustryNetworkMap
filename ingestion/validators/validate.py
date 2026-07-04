"""Seed data validation. Schema authority: docs/development/data-model.md, docs/development/relationship-types.md."""

import csv
import sys
from pathlib import Path

NODE_FILES = {
    "seed_companies.csv": ("Company", ["id", "name", "ticker", "exchange", "country", "is_listed_in_tw"]),
    "seed_products.csv": ("Product", ["id", "name", "category"]),
    "seed_industries.csv": ("Industry", ["id", "name"]),
    "seed_applications.csv": ("Application", ["id", "name"]),
    "seed_sources.csv": ("Source", ["id", "title", "type"]),
}

REL_FILE = "seed_relationships.csv"
REL_REQUIRED = ["id", "from_id", "to_id", "type", "confidence", "status"]

VALID_STATUS = {"candidate", "verified", "rejected", "stale", "deprecated"}
VALID_VALUE_TYPE = {"reported", "estimated", "inferred", "unknown", ""}
VALID_SOURCE_TYPE = {
    "annual_report", "financial_report", "investor_presentation", "company_website",
    "mops", "exchange_data", "news", "research_report", "manual",
}

# type -> (allowed from labels, allowed to labels); see docs/development/relationship-types.md
REL_TYPE_RULES = {
    "SUPPLIES_TO": ({"Company"}, {"Company"}),
    "BUYS_FROM": ({"Company"}, {"Company"}),
    "MANUFACTURES_FOR": ({"Company"}, {"Company"}),
    "ASSEMBLES_FOR": ({"Company"}, {"Company"}),
    "COMPETES_WITH": ({"Company"}, {"Company"}),
    "OWNS": ({"Company"}, {"Company"}),
    "INVESTS_IN": ({"Company"}, {"Company"}),
    "PRODUCES": ({"Company"}, {"Product"}),
    "SELLS": ({"Company"}, {"Product"}),
    "USES": ({"Company"}, {"Product"}),
    "DISTRIBUTES": ({"Company"}, {"Product"}),
    "ASSEMBLES": ({"Company"}, {"Product"}),
    "BELONGS_TO": ({"Company", "Industry"}, {"Industry"}),
    "COMPONENT_OF": ({"Product"}, {"Product"}),
    "INPUT_OF": ({"Product"}, {"Product"}),
    "SUBSTITUTE_FOR": ({"Product"}, {"Product"}),
    "USED_WITH": ({"Product"}, {"Product"}),
    "USED_IN": ({"Product"}, {"Application"}),
    "ENABLES": ({"Product"}, {"Application"}),
    "DRIVES_DEMAND_FOR": ({"Application"}, {"Product"}),
    "INCREASES_DEMAND_FOR": ({"Application"}, {"Product"}),
    "DECREASES_DEMAND_FOR": ({"Application"}, {"Product"}),
    "SUPPORTED_BY": ({"Company", "Product", "Industry", "Application"}, {"Evidence"}),
    "FROM_SOURCE": ({"Evidence"}, {"Source"}),
}

FORBIDDEN_TYPES = {"RELATED_TO", "LINKED_TO", "ASSOCIATED_WITH"}


def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate(seeds_dir: Path) -> tuple[list[str], dict[str, str]]:
    """Returns (errors, id_to_label). Errors reference file and row number (1-based data rows)."""
    errors: list[str] = []
    id_to_label: dict[str, str] = {}

    for filename, (label, required) in NODE_FILES.items():
        path = seeds_dir / filename
        if not path.exists():
            errors.append(f"{filename}: 檔案不存在")
            continue
        for i, row in enumerate(load_csv(path), start=1):
            loc = f"{filename} row {i}"
            for col in required:
                if not (row.get(col) or "").strip():
                    errors.append(f"{loc}: 必要欄位 '{col}' 為空")
            node_id = (row.get("id") or "").strip()
            if not node_id:
                continue
            if node_id in id_to_label:
                errors.append(f"{loc}: id '{node_id}' 重複（已存在於 {id_to_label[node_id]}）")
            else:
                id_to_label[node_id] = label
            if label == "Company" and (row.get("is_listed_in_tw") or "").strip().lower() not in {"true", "false"}:
                errors.append(f"{loc}: is_listed_in_tw 必須是 true/false")
            if label == "Source" and (row.get("type") or "").strip() not in VALID_SOURCE_TYPE:
                errors.append(f"{loc}: source type '{row.get('type')}' 不合法")

    rel_path = seeds_dir / REL_FILE
    if not rel_path.exists():
        errors.append(f"{REL_FILE}: 檔案不存在")
        return errors, id_to_label

    seen_rel_ids: set[str] = set()
    for i, row in enumerate(load_csv(rel_path), start=1):
        loc = f"{REL_FILE} row {i}"
        for col in REL_REQUIRED:
            if not (row.get(col) or "").strip():
                errors.append(f"{loc}: 必要欄位 '{col}' 為空")

        rel_id = (row.get("id") or "").strip()
        if rel_id in seen_rel_ids:
            errors.append(f"{loc}: relationship id '{rel_id}' 重複")
        seen_rel_ids.add(rel_id)

        rel_type = (row.get("type") or "").strip()
        from_id = (row.get("from_id") or "").strip()
        to_id = (row.get("to_id") or "").strip()

        if rel_type in FORBIDDEN_TYPES:
            errors.append(f"{loc}: 禁止使用模糊關係 '{rel_type}'")
        elif rel_type and rel_type not in REL_TYPE_RULES:
            errors.append(f"{loc}: 未知 relationship type '{rel_type}'（需先更新 docs/development/relationship-types.md）")

        for side, node_id in (("from", from_id), ("to", to_id)):
            if node_id and node_id not in id_to_label:
                errors.append(f"{loc}: {side} node '{node_id}' 不存在於任何 seed 檔")

        if rel_type in REL_TYPE_RULES and from_id in id_to_label and to_id in id_to_label:
            allowed_from, allowed_to = REL_TYPE_RULES[rel_type]
            if id_to_label[from_id] not in allowed_from:
                errors.append(f"{loc}: {rel_type} 的 from 必須是 {sorted(allowed_from)}，但 '{from_id}' 是 {id_to_label[from_id]}")
            if id_to_label[to_id] not in allowed_to:
                errors.append(f"{loc}: {rel_type} 的 to 必須是 {sorted(allowed_to)}，但 '{to_id}' 是 {id_to_label[to_id]}")

        conf = (row.get("confidence") or "").strip()
        if conf:
            try:
                if not 0.0 <= float(conf) <= 1.0:
                    errors.append(f"{loc}: confidence {conf} 不在 0 到 1 之間")
            except ValueError:
                errors.append(f"{loc}: confidence '{conf}' 不是數字")

        status = (row.get("status") or "").strip()
        if status and status not in VALID_STATUS:
            errors.append(f"{loc}: status '{status}' 不合法，允許值 {sorted(VALID_STATUS)}")

        if (row.get("value_type") or "").strip() not in VALID_VALUE_TYPE:
            errors.append(f"{loc}: value_type '{row.get('value_type')}' 不合法")

        for sid in (row.get("source_ids") or "").split(";"):
            sid = sid.strip()
            if sid and (id_to_label.get(sid) != "Source"):
                errors.append(f"{loc}: source_id '{sid}' 不存在於 seed_sources.csv")

        if (row.get("product_id") or "").strip() and id_to_label.get(row["product_id"].strip()) != "Product":
            errors.append(f"{loc}: product_id '{row['product_id']}' 不存在於 seed_products.csv")

    return errors, id_to_label


def main() -> int:
    seeds_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "seeds"
    errors, id_to_label = validate(seeds_dir)
    if errors:
        print(f"驗證失敗，共 {len(errors)} 個錯誤：")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"驗證通過：{len(id_to_label)} 個節點 id，seed 資料合法。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
