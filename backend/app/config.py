import os
from pathlib import Path

# 讀取 repo 根目錄 .env（OPENAI_API_KEY 等），已存在的環境變數優先
_env_file = Path(__file__).resolve().parents[2] / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "industrymap_dev")

CORE_NODE_LABELS = ["Company", "Product", "Industry", "Application"]

# Whitelist must stay in sync with docs/development/relationship-types.md
REL_TYPES = {
    "SUPPLIES_TO", "BUYS_FROM", "MANUFACTURES_FOR", "ASSEMBLES_FOR",
    "COMPETES_WITH", "OWNS", "INVESTS_IN",
    "PRODUCES", "SELLS", "USES", "DISTRIBUTES", "ASSEMBLES",
    "BELONGS_TO",
    "COMPONENT_OF", "INPUT_OF", "SUBSTITUTE_FOR", "USED_WITH",
    "USED_IN", "ENABLES",
    "DRIVES_DEMAND_FOR", "INCREASES_DEMAND_FOR", "DECREASES_DEMAND_FOR",
    "SUPPORTED_BY", "FROM_SOURCE",
}
