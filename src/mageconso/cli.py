"""Interface en ligne de commande.

Exemples
--------
    mageconso consolidate "MA - *.xlsx" -o out/consolide_2025.xlsx
    mageconso consolidate ma_japon.xlsx --entity MAGE_JAPON_KK --closing 2023-12-31
    mageconso inspect fichier.xlsx
    mageconso trace --run 1 --account "Cash Bank"
"""
from __future__ import annotations

import argparse
import glob
import sys
from decimal import Decimal
from pathlib import Path

from .audit import AuditJournal
from .config import load_config
from .controls import controls_summary, run_controls
from .engine import ConsolidationEngine
from .exporters.excel import export_workbook
from .formatting import formatter
from .importers.excel import ManagementAccountsReader
from .models import Severity, Statement
from .reports import build_by_cost_centre, build_statement


def _expand(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        hits = [Path(p) for p in glob.glob(pat)]
        if not hits and Path(pat).exists():
            hits = [Path(pat)]
        if not hits:
            print(f"  ! aucun fichier pour '{pat}'", file=sys.stderr)
        out.extend(sorted(hits))
    return out


def cmd_inspect(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    reader = ManagementAccountsReader(cfg)
    for path in _expand(args.files):
        wb = reader.read(path)
        print(f"\n=== {path.name} ===")
        print(f"  entite lue      : {wb.entity_name!r}")
        print(f"  devise          : {wb.currency}")
        print(f"  exercice        : {wb.fiscal_year}")
        print(f"  periode         : {wb.period_start} -> {wb.period_end}")
        print(f"  feuilles        : {', '.join(wb.sheet_names)}")
        if wb.hidden_sheets:
            print(f"  feuilles masquees: {', '.join(wb.hidden_sheets)}")
        print(f"  mapping interne : {len(wb.account_map)} correspondances")
        print(f"  plan groupe     : {len(wb.group_coa)} comptes")
        print(f"  lignes de balance: {len(wb.lines)}")
        total = sum((ln.amount for ln in wb.lines), Decimal(0))
        print(f"  somme algebrique: {total}")
        for d in wb.diagnostics:
            print(f"  [{d.severity.value}] {d.code}: {d.message}")
    return 0


def cmd_consolidate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    reader = ManagementAccountsReader(cfg)
    paths = _expand(args.files)
    if not paths:
        print("Aucun fichier source a traiter.", file=sys.stderr)
        return 2

    workbooks = []
    for path in paths:
        wb = reader.read(path, entity_code=args.entity)
        workbooks.append(wb)
        print(f"  lu : {path.name} ({len(wb.lines)} lignes, {wb.currency})")

    engine = ConsolidationEngine(cfg)
    result = engine.consolidate(workbooks, closing=args.closing)

    level = args.level
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level=level)
    pl = build_statement(cfg, result, Statement.PROFIT_AND_LOSS, level=level)
    result.controls = run_controls(cfg, result, bs=bs, pl=pl, workbooks=workbooks)

    fmt = formatter(
        cfg.presentation,
        scale=args.scale,
        decimals=args.decimals,
        negative_format=args.negatives,
        currency_position=args.currency_position,
    )

    reports = {"Consolidated BS": bs, "Consolidated PL": pl}
    if level != "detail":
        reports["Detailed BS"] = build_statement(
            cfg, result, Statement.BALANCE_SHEET, level="detail"
        )
        reports["Detailed PL"] = build_statement(
            cfg, result, Statement.PROFIT_AND_LOSS, level="detail"
        )
    if args.by_cost_centre:
        reports["BS by cost center"] = build_by_cost_centre(
            cfg, result, Statement.BALANCE_SHEET
        )
        reports["PL by cost center"] = build_by_cost_centre(
            cfg, result, Statement.PROFIT_AND_LOSS
        )

    out = export_workbook(args.output, reports, result, fmt, cfg.presentation)
    print(f"\nEtats consolides ecrits dans : {out}")

    if args.journal:
        journal = AuditJournal(args.journal)
        run_id = journal.record(
            result, config_dir=cfg.config_dir, sources=[p.name for p in paths]
        )
        journal.close()
        print(f"Journal d'audit : {args.journal} (run {run_id})")

    print("\n--- Synthese ---")
    print(f"  Revenue                    : {fmt.format(pl.total('Revenue'))}")
    print(f"  Gross Profit/(Loss)        : {fmt.format(pl.total('Gross Profit/(Loss)'))}")
    print(f"  Total Net/(loss) Profit    : {fmt.format(pl.total('Total Net/(loss) Profit'))}")
    print(f"  Total assets               : {fmt.format(bs.total('Total assets'))}")
    print(f"  {controls_summary(result.controls)}")

    for ctl in result.controls:
        if not ctl.passed:
            print(f"  [{ctl.severity.value}] {ctl.code} {ctl.label} -> {ctl.detail}")
    for d in result.diagnostics:
        if d.severity is Severity.ERROR:
            print(f"  [ERROR] {d.code}: {d.message}")

    return 1 if result.has_errors and args.strict else 0


def cmd_trace(args: argparse.Namespace) -> int:
    journal = AuditJournal(args.journal)
    rows = journal.trace(args.run, args.account)
    if not rows:
        print("Aucune ligne source pour ce compte.")
        return 0
    print(f"{'Entite':<20} {'Fichier':<28} {'Onglet':<16} {'Lig':>5} "
          f"{'Compte source':<38} {'Montant':>16} {'Dev':<4} {'Taux':>10} "
          f"{'EUR':>16}")
    total = Decimal(0)
    for (ent, f, sh, row, acct, amt, cur, rate, rtype, eur) in rows:
        total += Decimal(eur)
        print(f"{ent:<20} {f[:27]:<28} {sh[:15]:<16} {str(row or ''):>5} "
              f"{acct[:37]:<38} {Decimal(amt):>16.2f} {cur:<4} "
              f"{(rate or ''):>10} {Decimal(eur):>16.2f}")
    print(f"{'TOTAL':<20} {'':<28} {'':<16} {'':>5} {'':<38} {'':>16} {'':<4} "
          f"{'':>10} {total:>16.2f}")
    journal.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mageconso",
        description="Consolidation des management accounts Mage SAS.",
    )
    p.add_argument("--config", default=None, help="repertoire de configuration")
    sub = p.add_subparsers(dest="command", required=True)

    ins = sub.add_parser("inspect", help="analyser un fichier source sans consolider")
    ins.add_argument("files", nargs="+")
    ins.set_defaults(func=cmd_inspect)

    con = sub.add_parser("consolidate", help="produire les etats consolides")
    con.add_argument("files", nargs="+", help="fichiers de management accounts")
    con.add_argument("-o", "--output", default="out/consolidated.xlsx")
    con.add_argument("--entity", default=None,
                     help="force le code entite (sinon deduit de la feuille Cover)")
    con.add_argument("--closing", default=None,
                     help="date de cloture ISO pour le choix des taux (ex. 2025-12-31)")
    con.add_argument("--level", choices=["summary", "detail"], default="summary")
    con.add_argument("--by-cost-centre", action="store_true",
                     help="ajouter les etats par centre de couts")
    con.add_argument("--journal", default=None, help="chemin du journal SQLite")
    con.add_argument("--strict", action="store_true",
                     help="code retour non nul si un controle bloquant echoue")
    # surcharges de presentation
    con.add_argument("--scale", choices=["units", "thousands", "millions"], default=None)
    con.add_argument("--decimals", type=int, default=None)
    con.add_argument("--negatives", choices=["minus", "parentheses"], default=None)
    con.add_argument("--currency-position", choices=["prefix", "suffix", "none"],
                     default=None)
    con.set_defaults(func=cmd_consolidate)

    tr = sub.add_parser("trace", help="retrouver les sources d'un montant consolide")
    tr.add_argument("--journal", required=True)
    tr.add_argument("--run", type=int, required=True)
    tr.add_argument("--account", required=True, help="libelle du compte consolide")
    tr.set_defaults(func=cmd_trace)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
