"""
============================================================================
 run.py  -  Packsize Module orchestrator
 Power Stop LLC / HK1

 Usage
   python run.py                 ingest both drop folders, rebuild dashboard
   python run.py --open          ... and open it in the default browser
   python run.py --recalibrate   re-derive the standard, print YAML to paste
   python run.py --check         validate config and folders, ingest nothing
   python run.py --config PATH   use a config.yaml somewhere else

 Exit codes:  0 success   1 failure  (so the .bat can react)
============================================================================
"""

from __future__ import annotations

import argparse
import sys
import traceback
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from packsize_etl import _MdLog, load_config, resolve, run as etl_run, recalibrate  # noqa: E402
import build_dashboard  # noqa: E402


def check(cfg: dict, log: _MdLog) -> bool:
    ok = True
    log.h("Configuration check")
    log.info(f"config: {cfg['_config_path']}")

    root = Path(cfg["paths"]["root"])
    if root.exists():
        log.ok(f"root: {root}")
    else:
        log.err(f"root does not exist: {root}")
        ok = False

    for key, label in (("production_drop", "Carton production drop"),
                       ("error_drop", "Error file drop")):
        p = resolve(cfg, key)
        if not p.exists():
            log.err(f"{label} missing: {p}")
            ok = False
            continue
        files = [f for f in p.iterdir()
                 if f.is_file() and not f.name.startswith("~$")]
        if files:
            newest = max(files, key=lambda f: f.stat().st_mtime)
            log.ok(f"{label}: {len(files)} file(s), newest '{newest.name}'")
        else:
            log.warn(f"{label}: folder is empty - drop today's export in {p}")
            if key == "production_drop":
                ok = False

    out = resolve(cfg, "output_html")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        log.ok(f"output target writable: {out}")
    except Exception as exc:
        log.err(f"cannot write to {out.parent}: {exc}")
        ok = False

    std = cfg["standard"]
    basis = str(std.get("basis", "best-demonstrated"))
    if basis == "engineered":
        detail = f"engineered rate, {std.get('source', 'vendor')}"
    else:
        detail = (f"best demonstrated, {std.get('basis_clean_days', '?')} clean days, "
                  f"derived {std.get('derived_on', '?')}")
    log.info(f"standard in force: {std['cartons_per_day']} cartons/day "
             f"({std['throughput_cph']} per labor-hr) - {detail}")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Packsize Module daily build")
    ap.add_argument("--config", default=None, help="path to config.yaml")
    ap.add_argument("--open", action="store_true", help="open the dashboard when done")
    ap.add_argument("--recalibrate", action="store_true", help="re-derive the standard and print it")
    ap.add_argument("--check", action="store_true", help="validate setup only")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    log = _MdLog(echo_file=resolve(cfg, "log"))
    try:
        if not check(cfg, log):
            log.err("pre-flight failed - nothing was built")
            return 1
        if args.check:
            log.ok("check complete")
            return 0

        res = etl_run(args.config, log=log)

        if args.recalibrate:
            recalibrate(res["daily"], res["cfg"], log)
            log.warn("standard NOT written automatically - paste the block above into config.yaml")

        log.h("Dashboard")
        out = build_dashboard.build(res["payload"], res["cfg"], log)

        latest = res["payload"].get("latest")
        if latest:
            log.h("Latest day")
            verdict = ("ABOVE STRETCH" if latest["met_stretch"]
                       else "MET STANDARD" if latest["met_standard"] else "BELOW STANDARD")
            log.info(f"{latest['date']}  {latest['cartons']:,} cartons  "
                     f"{latest['cph']:.1f} per labor-hr  ->  {verdict}")

        if args.open:
            webbrowser.open(out.resolve().as_uri())
        log.ok("done")
        return 0

    except Exception:
        log.err("run failed")
        log.info(traceback.format_exc())
        return 1
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
