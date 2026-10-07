"""Docs must describe the data that actually ships: docs/SPEC.md tables are generated from config and seed."""
import importlib.util
import pathlib

_ROOT = pathlib.Path(__file__).parents[3]
_spec = importlib.util.spec_from_file_location("sync_tables", _ROOT / "docs" / "sync_tables.py")
sync_tables = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_tables)

TEXT = (_ROOT / "docs" / "SPEC.md").read_text(encoding="utf-8")


def test_spec_config_table_matches_config_yaml():
    assert sync_tables.current_blocks(TEXT)["CONFIG-TABLE"] == sync_tables.render_config_table(), \
        "docs/SPEC.md is out of date: run `python docs/sync_tables.py`"


def test_spec_seed_table_matches_seed_json():
    assert sync_tables.current_blocks(TEXT)["SEED-TABLE"] == sync_tables.render_seed_table(), \
        "docs/SPEC.md is out of date: run `python docs/sync_tables.py`"


def test_every_config_entry_is_tagged_sourced_or_assumed():
    statuses = {s for _k, _v, s, _n in sync_tables.config_rows()}
    assert statuses <= {"sourced", "assumed"}, statuses   # P13: 'simulated' belongs in seed.json only


def test_every_config_entry_has_a_note():
    missing = [k for k, _v, _s, n in sync_tables.config_rows() if not str(n).strip()]
    assert missing == []
