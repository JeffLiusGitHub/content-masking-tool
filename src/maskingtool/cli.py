"""CLI: mask / restore. The MCP server wraps the same pipeline functions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from maskingtool import __version__
from maskingtool import config
from maskingtool.denylist.loader import load_deny_lists, read_terms_csv
from maskingtool.engine import MaskingEngine
from maskingtool.pipeline import mask_file, restore_file
from maskingtool.textio import write_text_exact
from maskingtool.vault import Vault, VaultNotFoundError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="maskingtool-server")
    p.add_argument(
        "--version",
        action="version",
        version=f"maskingtool-server {__version__}",
    )
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("mask", help="mask a document, print vault_id")
    m.add_argument("input", type=Path)
    m.add_argument("-o", "--output", type=Path)
    m.add_argument("--format", choices=["markdown", "html"], default="markdown")
    m.add_argument("--companies", type=Path, help="companies CSV (default: app-data list)")
    m.add_argument("--people", type=Path, help="people CSV (default: app-data list)")
    m.add_argument("--vault-id", help="reuse an existing vault for consistent tokens")
    m.add_argument("--enable-ner", action="store_true",
                   help="force NER on (default: settings.json, ships enabled)")
    m.add_argument("--no-ner", action="store_true",
                   help="force NER off (deny-list only, fully deterministic)")
    m.add_argument(
        "--no-expand-names",
        action="store_true",
        help="mask full names only; do not also mask bare first names/surnames",
    )
    m.add_argument("--vaults-dir", type=Path, help=argparse.SUPPRESS)
    m.add_argument("--result-json", type=Path, help=argparse.SUPPRESS)

    g = sub.add_parser("gui", help=argparse.SUPPRESS)
    g.add_argument("--review-id")
    g.add_argument("--file")

    r = sub.add_parser("restore", help="restore original values into a masked file")
    r.add_argument("input", type=Path)
    r.add_argument("--vault-id", required=True)
    r.add_argument("-o", "--output", type=Path)
    r.add_argument("--vaults-dir", type=Path, help=argparse.SUPPRESS)
    return p


def _load_deny_lists(args) -> dict[str, list[str]]:
    if args.companies or args.people:
        lists: dict[str, list[str]] = {}
        if args.companies:
            lists["ORG"] = read_terms_csv(args.companies)
        if args.people:
            lists["PERSON"] = read_terms_csv(args.people)
        return lists
    return load_deny_lists()


def _cmd_mask(args) -> int:
    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1
    if args.enable_ner:
        enable_ner = True
    elif args.no_ner:
        enable_ner = False
    else:
        enable_ner = config.load_settings()["enable_ner"]
    engine = MaskingEngine(
        _load_deny_lists(args),
        enable_ner=enable_ner,
        expand_person_parts=not args.no_expand_names,
    )
    if args.vault_id:
        vault = Vault.load(args.vault_id, vaults_dir=args.vaults_dir)
    else:
        vault = Vault.create(args.input.name, vaults_dir=args.vaults_dir)
    result = mask_file(args.input, engine, vault, output_format=args.format)
    vault.save()

    output = args.output or args.input.with_name(
        args.input.stem + ".masked." + ("html" if args.format == "html" else "md")
    )
    write_text_exact(output, result.masked_text)

    info = {
        "vault_id": vault.vault_id,
        "output": str(output),
        "output_format": result.output_format,
        "entity_counts": vault.entity_counts(),
        "warnings": result.warnings,
    }
    if args.result_json:
        args.result_json.write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def _cmd_restore(args) -> int:
    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1
    vault = Vault.load(args.vault_id, vaults_dir=args.vaults_dir)
    output = args.output or args.input.with_name(
        args.input.stem + ".restored" + args.input.suffix
    )
    unresolved = restore_file(args.input, vault, output)
    print(json.dumps({"output": str(output), "unresolved_tokens": unresolved},
                     ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "gui":
            from maskingtool.gui import main as gui_main

            return gui_main(review_id=args.review_id, file=args.file) or 0
        if args.command == "mask":
            return _cmd_mask(args)
        return _cmd_restore(args)
    except VaultNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # surface a clean message, not a traceback
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
