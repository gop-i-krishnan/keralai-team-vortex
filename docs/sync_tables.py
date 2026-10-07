"""
docs/sync_tables.py
Renders the sourced / assumed / simulated tables for docs/SPEC.md straight from
data/config.yaml and data/seed.json, so the documentation cannot drift from the data.

    python docs/sync_tables.py          # rewrite the generated blocks in docs/SPEC.md
    pytest backend/engine/tests/test_docs_sync.py   # fails if the blocks are out of date
"""
import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).parent.parent
SPEC = ROOT / "docs" / "SPEC.md"
CONFIG = ROOT / "data" / "config.yaml"
SEED = ROOT / "data" / "seed.json"

BLOCKS = {
    "CONFIG-TABLE": lambda: render_config_table(),
    "SEED-TABLE": lambda: render_seed_table(),
}


def _esc(x) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _walk(prefix, node):
    for k, v in node.items():
        if isinstance(v, dict) and "source_status" in v:
            yield f"{prefix}{k}", v.get("value"), v["source_status"], v.get("note", "")
        elif isinstance(v, dict):
            yield from _walk(f"{prefix}{k}.", v)


def config_rows() -> list[tuple]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rows = []
    for section, body in cfg.items():
        if isinstance(body, dict):
            rows += list(_walk(f"{section}.", body))
        elif isinstance(body, list) and section == "hazard_rules":
            for r in body:
                rows.append((f"hazard_rules.{r['class_id']}",
                             f"modes={r['allowed_modes']}, cert_required={r['certification_required']}, "
                             f"review_required={r['human_review_required']}", r["source_status"], r["notes"]))
        elif isinstance(body, list) and section == "notifications":
            for r in body:
                rows.append((f"notifications.{r['type']}", "message template (English)", r["source_status"], r["note"]))
    return rows


def render_config_table() -> str:
    rows = config_rows()
    counts = {}
    for _k, _v, s, _n in rows:
        counts[s] = counts.get(s, 0) + 1
    lines = [f"Config entries: **{len(rows)}** total — " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) + ".", "",
             "| Key | Value | Status | Note |", "|---|---|---|---|"]
    for k, v, s, n in rows:
        lines.append(f"| `{k}` | {_esc(v)} | {s} | {_esc(n)} |")
    return "\n".join(lines)


def render_seed_table() -> str:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    lines = ["| Seed collection | Records | source_status |", "|---|---|---|"]
    for name, items in seed.items():
        if not isinstance(items, list):
            continue
        counts = {}
        for it in items:
            s = it.get("source_status", "(none)")
            counts[s] = counts.get(s, 0) + 1
        lines.append(f"| `{name}` | {len(items)} | " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) + " |")
    return "\n".join(lines)


def _block_re(name):
    return re.compile(rf"(<!-- {name}:START -->\n)(.*?)(\n<!-- {name}:END -->)", re.S)


def current_blocks(text: str) -> dict:
    return {n: _block_re(n).search(text).group(2) for n in BLOCKS}


def update(text: str) -> str:
    for name, fn in BLOCKS.items():
        text = _block_re(name).sub(lambda m: m.group(1) + fn() + m.group(3), text)
    return text


if __name__ == "__main__":
    body = SPEC.read_text(encoding="utf-8")
    SPEC.write_text(update(body), encoding="utf-8")
    print("updated", SPEC)
