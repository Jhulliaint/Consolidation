"""Interface en ligne de commande.

    mageconso ui                                      interface graphique locale
    mageconso inspect "MA - *.xlsx"                   examiner les fichiers sources
    mageconso rates   "MA - *.xlsx" -o taux.xlsx      fichier de taux a completer
    mageconso consolidate "MA - *.xlsx" --rates taux.xlsx -o out/consolide.xlsx
    mageconso consolidate ... --reference "EC+/2025.xlsx"   rapprochement
    mageconso check --closing 2025-12-31              verifier le parametrage
    mageconso trace --journal out/audit.db --run 1 --account "Cash Bank"
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from decimal import Decimal
from pathlib import Path

from .audit import AuditJournal
from .checks import check_config
from .config import load_config
from .models import Severity, eur
from .pipeline import (
    RunOptions,
    default_closing,
    export,
    prepare_rates,
    read_sources,
    run,
)
from .rates import rate_needs, write_rates_template
from .suggest import write_mapping_template

_COLOUR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOUR else text


def ok(t: str) -> str:
    return _c(t, "32")


def ko(t: str) -> str:
    return _c(t, "31;1")


def warn(t: str) -> str:
    return _c(t, "33")


def dim(t: str) -> str:
    return _c(t, "2")


def _expand(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        hits = [Path(p) for p in glob.glob(pat)]
        if not hits and Path(pat).exists():
            hits = [Path(pat)]
        if not hits:
            print(warn(f"  ! aucun fichier pour '{pat}'"), file=sys.stderr)
        out.extend(sorted(hits))
    seen, unique = set(), []
    for p in out:  # un meme fichier cite deux fois (motifs qui se recouvrent)
        if p.resolve() not in seen:
            seen.add(p.resolve())
            unique.append(p)
    return unique


def _entity_overrides(values: list[str] | None, paths: list[Path]) -> dict[str, str]:
    """--entity CODE (un seul fichier) ou --entity "fichier.xlsx=CODE"."""
    out: dict[str, str] = {}
    for v in values or []:
        if "=" in v:
            name, code = v.rsplit("=", 1)
            out[Path(name.strip()).name] = code.strip()
        elif len(paths) == 1:
            out[paths[0].name] = v.strip()
        else:
            raise SystemExit(
                "--entity CODE ne s'emploie qu'avec un seul fichier. Avec plusieurs "
                'fichiers : --entity "nom du fichier.xlsx=CODE" (option repetable).')
    return out


# --------------------------------------------------------------------- inspect
def cmd_inspect(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    paths = _expand(args.files)
    wbs = read_sources(cfg, paths, _entity_overrides(args.entity, paths))
    for wb in wbs:
        total = sum((ln.amount for ln in wb.lines), Decimal(0))
        print(f"\n=== {wb.path.name} ===")
        print(f"  entite            : {wb.entity_code or ko('NON RECONNUE')}"
              f"  {dim('(lu : ' + repr(wb.entity_name) + ')')}")
        print(f"  devise            : {wb.currency}")
        print(f"  periode           : {wb.period_start} -> {wb.period_end}")
        print(f"  feuilles          : {', '.join(wb.sheet_names)}")
        if wb.hidden_sheets:
            print(f"  feuilles masquees : {', '.join(wb.hidden_sheets)}")
        print(f"  mapping interne   : {len(wb.account_map)} correspondances")
        print(f"  lignes de balance : {len(wb.lines)}")
        state = ok("equilibree") if abs(total) < Decimal("0.01") else ko(f"DESEQUILIBREE ({eur(total)})")
        print(f"  balance           : {state}")
        for d in wb.diagnostics:
            print(f"  [{d.severity.value}] {d.code}: {d.message}")
    if wbs:
        closing = args.closing or default_closing(wbs)
        needs = rate_needs(cfg, wbs, closing)
        if needs:
            print(f"\nTaux necessaires au {closing} :")
            for n in needs:
                miss = n.missing
                state = ok("connus") if not miss else warn("manquant : " + ", ".join(miss))
                print(f"  {n.currency}  {state}  {dim('(' + ', '.join(n.entities) + ')')}")
    return 0


# ----------------------------------------------------------------------- rates
def cmd_rates(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    paths = _expand(args.files)
    wbs = read_sources(cfg, paths, _entity_overrides(args.entity, paths))
    closing = args.closing or default_closing(wbs)
    needs = rate_needs(cfg, wbs, closing)
    if not needs:
        print("Aucune devise a convertir : toutes les entites sont en euros.")
        return 0
    out = write_rates_template(args.output, needs, closing)
    print(f"Fichier de taux au {closing} : {out}")
    print("Les cellules surlignees sont pre-remplies avec le DERNIER taux connu : "
          "remplacez-les par les taux de la cloture (1 EUR = X devise).")
    print(f"Puis : mageconso consolidate ... --rates {out}")
    return 0


# ----------------------------------------------------------------- consolidate
def cmd_consolidate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    paths = _expand(args.files)
    if not paths:
        print(ko("Aucun fichier source a traiter."), file=sys.stderr)
        return 2
    wbs = read_sources(cfg, paths, _entity_overrides(args.entity, paths))
    for wb in wbs:
        tag = wb.entity_code or ko("entite non reconnue")
        print(f"  lu : {wb.path.name}  {dim('->')} {tag} ({len(wb.lines)} lignes, {wb.currency})")

    opts = RunOptions(
        closing=args.closing,
        level=args.level,
        by_entity=not args.no_by_entity,
        by_cost_centre=args.by_cost_centre,
        reference=Path(args.reference) if args.reference else None,
        reconciliation_tolerance=Decimal(str(args.tolerance)),
        rates_file=Path(args.rates) if args.rates else None,
        presentation={k: v for k, v in {
            "scale": args.scale, "decimals": args.decimals,
            "negative_format": args.negatives,
            "currency_position": args.currency_position,
        }.items() if v is not None},
    )

    # Pre-controle des taux : mieux vaut s'arreter avec une consigne claire que
    # produire un classeur dont des lignes n'ont pas ete converties.
    closing = args.closing or default_closing(wbs)
    cfg_rates, _ = prepare_rates(cfg, closing, opts)
    missing = [(n.currency, n.missing) for n in rate_needs(cfg_rates, wbs, closing)
               if [k for k in n.missing if k != "historical"]]
    if missing and not args.force:
        print(ko(f"\nTaux de change manquants au {closing} :"))
        for cur, kinds in missing:
            print(f"  {cur} : {', '.join(k for k in kinds if k != 'historical')}")
        print("\nPreparez un fichier de taux pre-rempli :")
        print(f'  mageconso rates {" ".join(repr(str(p)) for p in paths)} -o taux.xlsx')
        print("puis relancez avec --rates taux.xlsx  (ou --force pour continuer quand meme).")
        return 2

    out = run(cfg, paths, opts, workbooks=wbs)
    target = export(out, args.output)

    print("\n--- Synthese ---")
    for label, value in out.kpis():
        print(f"  {label:<32}: {out.fmt.format(value):>18}")

    res = out.result
    blocking = out.blocking
    others = [c for c in res.controls if not c.passed and c not in blocking]
    passed = sum(1 for c in res.controls if c.passed)
    head = f"{passed}/{len(res.controls)} controles OK"
    print("\n  " + (ko(head + f" - {len(blocking)} BLOQUANT(S) : ne pas diffuser")
                    if blocking else ok(head) if not others else warn(head)))
    for c in blocking:
        print(ko(f"    x {c.code} {c.label}") + f"\n      {c.detail}")
    for c in others:
        print(warn(f"    ! {c.code} {c.label}") + f"\n      {c.detail}")

    errors = [d for d in res.diagnostics if d.severity is Severity.ERROR]
    warns = [d for d in res.diagnostics if d.severity is Severity.WARNING]
    if errors or warns:
        print(f"\n  Diagnostics : {len(errors)} erreur(s), {len(warns)} avertissement(s)"
              " - detail dans l'onglet Diagnostics")
        for d in errors[:8]:
            print(ko(f"    [ERROR] {d.code}") + f": {d.message}")
        if len(errors) > 8:
            print(dim(f"    ... et {len(errors) - 8} autre(s)"))

    if out.reconciliation is not None:
        rec = out.reconciliation
        n = rec.counts()
        line = (f"Rapprochement {rec.reference_file} : {n.get('OK', 0)} conforme(s), "
                f"{len(rec.gaps)} ecart(s)")
        print("\n  " + (ok(line) if rec.ok else warn(line)))

    if res.unmapped:
        csv_path = Path(args.mapping_out or Path(target).with_name(
            Path(target).stem + " - mapping a completer.csv"))
        write_mapping_template(csv_path, res.unmapped)
        print(warn(f"\n  {len(res.unmapped)} compte(s) non mappe(s) : propositions dans {csv_path}"))

    print(f"\nClasseur : {target}")
    if args.journal:
        journal = AuditJournal(args.journal)
        run_id = journal.record(res, config_dir=cfg.config_dir, sources=[p.name for p in paths])
        journal.close()
        print(f"Journal d'audit : {args.journal} (run {run_id})")
    if args.open:
        _open(target)
    return 1 if (blocking or errors) and args.strict else 0


def _open(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
    except OSError:
        pass


# ----------------------------------------------------------------------- check
def cmd_check(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    findings = check_config(cfg, args.closing)
    by_sev = {s: [f for f in findings if f.severity is s] for s in Severity}
    for sev, colour in ((Severity.ERROR, ko), (Severity.WARNING, warn), (Severity.INFO, dim)):
        for f in by_sev[sev]:
            print(colour(f"[{sev.value}] {f.code}") + f": {f.message}")
    n_err = len(by_sev[Severity.ERROR])
    summary = (f"{len(cfg.entities)} entites, {len(cfg.group_coa)} comptes groupe, "
               f"{sum(len(m) for m in cfg.account_maps.values())} correspondances")
    print(("\n" + (ko(f"{n_err} erreur(s) de parametrage") if n_err
                   else ok("Parametrage coherent"))) + dim(f"  ({summary})"))
    return 1 if n_err else 0


# ----------------------------------------------------------------------- trace
def cmd_trace(args: argparse.Namespace) -> int:
    journal = AuditJournal(args.journal)
    rows = journal.trace(args.run, args.account)
    if not rows:
        print("Aucune ligne source pour ce compte.")
        return 0
    print(f"{'Entite':<20} {'Fichier':<28} {'Onglet':<16} {'Lig':>5} "
          f"{'Compte source':<38} {'Montant':>16} {'Dev':<4} {'Taux':>10} {'EUR':>16}")
    total = Decimal(0)
    for (ent, f, sh, row, acct, amt, cur, rate, rtype, eur_) in rows:
        total += Decimal(eur_)
        print(f"{ent:<20} {f[:27]:<28} {sh[:15]:<16} {str(row or ''):>5} "
              f"{acct[:37]:<38} {Decimal(amt):>16.2f} {cur:<4} "
              f"{(rate or ''):>10} {Decimal(eur_):>16.2f}")
    print(f"{'TOTAL':<20} {'':<28} {'':<16} {'':>5} {'':<38} {'':>16} {'':<4} "
          f"{'':>10} {total:>16.2f}")
    journal.close()
    return 0


# -------------------------------------------------------------------------- ui
def cmd_ui(args: argparse.Namespace) -> int:
    from .webui import serve

    serve(config_dir=args.config, port=args.port, open_browser=not args.no_browser)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mageconso",
        description="Consolidation des management accounts Mage SAS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--config", default=None, help="repertoire de configuration")
    sub = p.add_subparsers(dest="command", required=True)

    ui = sub.add_parser("ui", help="interface graphique dans le navigateur (locale)")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-browser", action="store_true")
    ui.set_defaults(func=cmd_ui)

    def add_sources(sp):
        sp.add_argument("files", nargs="+", help="fichiers de management accounts")
        sp.add_argument("--entity", action="append", metavar="[FICHIER=]CODE",
                        help="force l'entite d'un fichier non reconnu (repetable)")
        sp.add_argument("--closing", default=None,
                        help="date de cloture ISO (defaut : lue dans les fichiers)")

    ins = sub.add_parser("inspect", help="examiner des fichiers sources sans consolider")
    add_sources(ins)
    ins.set_defaults(func=cmd_inspect)

    rt = sub.add_parser("rates", help="generer le fichier de taux a completer")
    add_sources(rt)
    rt.add_argument("-o", "--output", default="taux.xlsx", help=".xlsx ou .csv")
    rt.set_defaults(func=cmd_rates)

    con = sub.add_parser("consolidate", help="produire les etats consolides")
    add_sources(con)
    con.add_argument("-o", "--output", default="out/consolidated.xlsx")
    con.add_argument("--rates", default=None, metavar="FICHIER",
                     help="taux de la cloture (.xlsx/.csv : devise ; cloture ; moyen ; historique)")
    con.add_argument("--reference", default=None, metavar="FICHIER",
                     help="classeur consolide de reference pour rapprochement ligne a ligne")
    con.add_argument("--tolerance", type=float, default=1.0,
                     help="tolerance du rapprochement, en EUR (defaut 1)")
    con.add_argument("--level", choices=["summary", "detail"], default="summary",
                     help="niveau des vues par entite / centre de couts")
    con.add_argument("--by-cost-centre", action="store_true",
                     help="ajouter les etats par centre de couts")
    con.add_argument("--no-by-entity", action="store_true",
                     help="ne pas produire les etats par entite")
    con.add_argument("--journal", default=None, help="journal d'audit SQLite")
    con.add_argument("--mapping-out", default=None,
                     help="CSV des comptes non mappes (defaut : a cote du classeur)")
    con.add_argument("--strict", action="store_true",
                     help="code retour 1 si un controle bloquant echoue")
    con.add_argument("--force", action="store_true",
                     help="consolider meme si des taux manquent")
    con.add_argument("--open", action="store_true", help="ouvrir le classeur produit")
    con.add_argument("--scale", choices=["units", "thousands", "millions"], default=None)
    con.add_argument("--decimals", type=int, default=None)
    con.add_argument("--negatives", choices=["minus", "parentheses"], default=None)
    con.add_argument("--currency-position", choices=["prefix", "suffix", "none"],
                     default=None)
    con.set_defaults(func=cmd_consolidate)

    chk = sub.add_parser("check", help="verifier la coherence du parametrage")
    chk.add_argument("--closing", default=None, help="verifier aussi les taux de cette cloture")
    chk.set_defaults(func=cmd_check)

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
