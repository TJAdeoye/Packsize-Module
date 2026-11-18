"""
============================================================================
 packsize_etl.py  -  Packsize Module data pipeline
 Power Stop LLC / HK1

 Reads every file in the two manual drop folders, normalizes them, and
 computes daily / monthly / quarterly / yearly metrics scored against the
 standard in config.yaml.

 Designed to be pasted straight into a Jupyter cell OR imported:
     from packsize_etl import run
     result = run()

 No state is kept between runs. Dropping a full re-export or a single day
 both work - overlapping rows are de-duplicated on ingest.
============================================================================
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# _MdLog - dual-mode logger. Renders markdown in Jupyter, plain text in a
# terminal or .bat run. Same class used across the HK1 modules.
# ---------------------------------------------------------------------------
class _MdLog:
    def __init__(self, echo_file: str | os.PathLike | None = None):
        try:
            from IPython.display import display, Markdown  # noqa
            self._rich = True
            self._display, self._Markdown = display, Markdown
        except Exception:
            self._rich = False
        self._fh = None
        if echo_file:
            try:
                Path(echo_file).parent.mkdir(parents=True, exist_ok=True)
                self._fh = open(echo_file, "a", encoding="utf-8")
                self._fh.write(f"\n===== run {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            except Exception:
                self._fh = None

    def _emit(self, md: str, plain: str):
        if self._rich:
            self._display(self._Markdown(md))
        else:
            print(plain)
        if self._fh:
            self._fh.write(plain + "\n")
            self._fh.flush()

    def h(self, text):    self._emit(f"### {text}", f"\n--- {text} ---")
    def ok(self, text):   self._emit(f"&#9989; {text}", f"[ OK ] {text}")
    def warn(self, text): self._emit(f"&#9888;&#65039; {text}", f"[WARN] {text}")
    def err(self, text):  self._emit(f"&#10060; {text}", f"[FAIL] {text}")
    def info(self, text): self._emit(text, f"       {text}")

    def table(self, df: pd.DataFrame, n: int = 12):
        if self._rich:
            self._display(df.head(n))
        else:
            print(df.head(n).to_string())
        if self._fh:
            self._fh.write(df.head(n).to_string() + "\n")

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config(path: str | os.PathLike | None = None) -> dict:
    """Load config.yaml. Defaults to the file sitting next to this script."""
    if path is None:
        here = Path(__file__).parent if "__file__" in globals() else Path.cwd()
        path = here / "config.yaml"
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {path}. Pass an explicit path: load_config(r'...')"
        )
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_config_path"] = str(path)
    return cfg


def resolve(cfg: dict, key: str) -> Path:
    """Resolve a path from config against paths.root unless it is absolute."""
    root = Path(cfg["paths"]["root"])
    val = Path(cfg["paths"][key])
    return val if val.is_absolute() else root / val


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
def _discover(folder: Path, patterns: list[str], ignore: list[str]) -> list[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Drop folder does not exist: {folder}")
    hits: list[Path] = []
    for p in sorted(folder.iterdir()):
        if not p.is_file():
            continue
        if any(fnmatch.fnmatch(p.name, ig) for ig in ignore):
            continue
        if any(fnmatch.fnmatch(p.name.lower(), pat.lower()) for pat in patterns):
            hits.append(p)
    return hits


def _read_any(path: Path) -> pd.DataFrame:
    """Read a CSV or Excel drop file. Excel is common in the Error folder."""
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path.name} with any known encoding")


def _require(df: pd.DataFrame, mapping: dict, label: str, src: str):
    missing = [src_col for src_col in mapping.values() if src_col not in df.columns]
    if missing:
        raise KeyError(
            f"{label} file '{src}' is missing expected column(s): {missing}. "
            f"If PackNet renamed a header, update columns.{label} in config.yaml."
        )


def load_production(cfg: dict, log: _MdLog) -> pd.DataFrame:
    folder = resolve(cfg, "production_drop")
    files = _discover(folder, cfg["file_patterns"]["production"], cfg["file_patterns"]["ignore"])
    if not files:
        raise FileNotFoundError(f"No production files found in {folder}")

    m = cfg["columns"]["production"]
    frames = []
    for f in files:
        df = _read_any(f)
        _require(df, m, "production", f.name)
        out = pd.DataFrame({
            "ts":        pd.to_datetime(df[m["timestamp"]], errors="coerce"),
            "cartons":   pd.to_numeric(df[m["cartons"]], errors="coerce"),
            "machine":   pd.to_numeric(df[m["machine"]], errors="coerce").astype("Int64"),
            "sku":       df[m["sku"]].astype(str).str.strip(),
            "design":    df[m["design"]].astype(str),
            "zfold":     df[m["zfold"]].astype(str),
            "box_w":     pd.to_numeric(df[m["box_w"]], errors="coerce"),
            "box_l":     pd.to_numeric(df[m["box_l"]], errors="coerce"),
            "box_h":     pd.to_numeric(df[m["box_h"]], errors="coerce"),
            "zfold_area": pd.to_numeric(df[m["zfold_area"]], errors="coerce"),
            "trim_area": pd.to_numeric(df[m["trim_area"]], errors="coerce"),
            "optimal":   df[m["optimal"]].astype(str).str.strip().str.lower().eq("true"),
            "cycle_sec": pd.to_numeric(df[m["cycle_sec"]], errors="coerce"),
            "successful": df[m["successful"]].astype(str).str.strip().str.lower().eq("true"),
        })
        out["_src"] = f.name
        frames.append(out)
        log.info(f"production  <- {f.name}  ({len(out):,} rows)")

    prod = pd.concat(frames, ignore_index=True)
    before = len(prod)
    # A cycle is uniquely identified by when it ran, on which machine, at what size.
    prod = prod.drop_duplicates(subset=["ts", "machine", "cycle_sec", "box_w", "box_l", "box_h"])
    prod = prod.dropna(subset=["ts", "machine"]).sort_values("ts").reset_index(drop=True)
    if before != len(prod):
        log.info(f"de-duplicated {before - len(prod):,} overlapping production rows")

    prod["date"] = prod["ts"].dt.date
    log.ok(f"production: {len(prod):,} cycles across {prod['date'].nunique()} dates "
           f"({prod['ts'].min():%d-%b-%Y} to {prod['ts'].max():%d-%b-%Y})")
    return prod


def load_errors(cfg: dict, log: _MdLog) -> pd.DataFrame:
    folder = resolve(cfg, "error_drop")
    files = _discover(folder, cfg["file_patterns"]["error"], cfg["file_patterns"]["ignore"])
    if not files:
        log.warn(f"No error files found in {folder} - fault metrics will be blank")
        return pd.DataFrame(columns=["ts", "machine", "code", "message", "status", "date"])

    m = cfg["columns"]["error"]
    frames = []
    for f in files:
        df = _read_any(f)
        _require(df, m, "error", f.name)
        out = pd.DataFrame({
            "ts_raw":  pd.to_datetime(df[m["timestamp"]], errors="coerce"),
            "machine": pd.to_numeric(df[m["machine"]], errors="coerce").astype("Int64"),
            "code":    pd.to_numeric(df[m["code"]], errors="coerce").astype("Int64"),
            "message": df[m["message"]].astype(str),
            "status":  df[m["status"]].astype(str),
        })
        out["_src"] = f.name
        frames.append(out)
        log.info(f"errors      <- {f.name}  ({len(out):,} rows)")

    err = pd.concat(frames, ignore_index=True)
    before = len(err)
    err = err.drop_duplicates(subset=["ts_raw", "machine", "code", "status"])
    err = err.dropna(subset=["ts_raw"]).reset_index(drop=True)
    if before != len(err):
        log.info(f"de-duplicated {before - len(err):,} overlapping error rows")

    # PackNet exports the event log in UTC and the production file in local time.
    # Without this conversion every fault lands 5 hours after the cycle it stopped.
    if cfg["rules"]["error_log_is_utc"]:
        tz = cfg["meta"]["timezone"]
        err["ts"] = (err["ts_raw"].dt.tz_localize("UTC")
                                 .dt.tz_convert(tz)
                                 .dt.tz_localize(None))
        log.info(f"error log converted UTC -> {tz} (DST-aware)")
    else:
        err["ts"] = err["ts_raw"]

    err["date"] = err["ts"].dt.date
    err["hour_dec"] = err["ts"].dt.hour + err["ts"].dt.minute / 60.0

    # Shift-boundary e-stops are the crew powering the machine on and off.
    b = cfg["rules"]["boundary_estop"]
    err["is_boundary"] = (
        err["message"].eq(b["message"])
        & ((err["hour_dec"] < b["before_hour"]) | (err["hour_dec"] > b["after_hour"]))
    )
    err["is_fault"] = ~err["is_boundary"]

    log.ok(f"errors: {len(err):,} events - {int(err['is_boundary'].sum()):,} shift-boundary "
           f"e-stops excluded, {int(err['is_fault'].sum()):,} genuine faults retained")
    return err.sort_values("ts").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_gaps(prod: pd.DataFrame, err: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Per machine-day: running hours, and idle time split into fault-caused vs
    starvation. A gap is 'fault-caused' when a logged fault event falls inside
    it; otherwise the machine was waiting on work.
    """
    thresh = cfg["rules"]["idle_gap_threshold_sec"]
    faults = err[err["is_fault"]] if len(err) else err
    rows = []

    for (d, mach), g in prod.groupby(["date", "machine"], sort=True):
        g = g.sort_values("ts")
        t = g["ts"].values
        cyc = g["cycle_sec"].fillna(0).values
        ev = faults.loc[(faults["date"] == d) & (faults["machine"] == mach), "ts"].values

        fault_s = starve_s = 0.0
        for i in range(1, len(t)):
            gap = (t[i] - t[i - 1]) / np.timedelta64(1, "s") - cyc[i]
            if gap > thresh:
                if len(ev) and ((ev >= t[i - 1]) & (ev <= t[i])).any():
                    fault_s += gap
                else:
                    starve_s += gap

        rows.append({
            "date": d,
            "machine": mach,
            "run_h": float(np.nansum(cyc)) / 3600.0,
            "fault_h": fault_s / 3600.0,
            "starve_h": starve_s / 3600.0,
        })

    return pd.DataFrame(rows)


def machine_concurrency(prod: pd.DataFrame) -> pd.DataFrame:
    """
    Per day: how many machines ran, and for how many minutes they ran at the
    same time. Derived from the cycle timestamps rather than assumed, so a day
    where the crew doubled up is detected instead of inferred from totals.
    """
    rows = []
    for d, g in prod.groupby("date"):
        occ = {}
        for mach, gm in g.groupby("machine"):
            mins = set()
            for t, c in zip(gm["ts"], gm["cycle_sec"].fillna(0)):
                for k in range(int(c // 60) + 1):
                    mins.add((t + pd.Timedelta(seconds=60 * k)).floor("min"))
            occ[mach] = mins
        machines = [m for m, v in occ.items() if v]
        conc = 0
        if len(machines) >= 2:
            sets = [occ[m] for m in machines]
            for i in range(len(sets)):
                for j in range(i + 1, len(sets)):
                    conc = max(conc, len(sets[i] & sets[j]))
        rows.append({"date": d, "machines_used": len(machines), "concurrent_min": conc})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Scopes
#   The line is reported three ways: both machines combined, and each machine
#   on its own. A scope carries its own machine list, its own scheduled hours,
#   its own labour denominator and its own target, so a single-machine tab is
#   scored against 1,400/day while the overview is scored against 2,800.
# ---------------------------------------------------------------------------
def machine_alias(cfg: dict, mid) -> str:
    al = (cfg.get("machine", {}).get("aliases") or {})
    return str(al.get(mid, al.get(str(mid), f"M{mid}")))


def build_scopes(cfg: dict) -> list[dict]:
    mc = cfg.get("machine", {})
    sh = cfg["shift"]
    installed = list(mc.get("installed") or sh["machines"])
    per_mach = float(mc.get("associates_per_machine", 1) or 1)
    rated = float(mc.get("rated_boxes_per_hour", 0) or 0)
    paid = float(sh["paid_hours"])
    sched_per = float(sh["scheduled_hours_per_machine"])

    def mk(key, label, machines, sublabel):
        n = len(machines)
        return {
            "key": key,
            "label": label,
            "sublabel": sublabel,
            "machines": machines,
            "n_machines": n,
            # Spec staffing: one associate per machine.
            "associates": n * per_mach,
            "labor_h": n * per_mach * paid,
            "sched_h": n * sched_per,          # machine-hours available
            "target_day": rated * n * sched_per,
            "rated_bph": rated,
        }

    scopes = [mk("combined", "Combined",
                 installed,
                 f"both machines \u00b7 {len(installed)} associates")]
    for mid in installed:
        scopes.append(mk(str(mid), machine_alias(cfg, mid), [mid],
                         f"machine {mid} \u00b7 1 associate"))
    return scopes


def daily_metrics(prod: pd.DataFrame, err: pd.DataFrame, cfg: dict,
                  log: _MdLog, scope: dict | None = None) -> pd.DataFrame:
    """
    One row per production day for the given scope. With no scope, behaves as
    the combined view across every installed machine.
    """
    if scope is None:
        scope = build_scopes(cfg)[0]

    p = prod[prod["machine"].isin(scope["machines"])].copy()
    e = err[err["machine"].isin(scope["machines"])].copy() if len(err) else err

    if p.empty:
        return pd.DataFrame()

    labor_h = float(scope["labor_h"])
    sched_line = float(scope["sched_h"])
    target_day = float(scope["target_day"])

    d = p.groupby("date").agg(
        cartons=("cartons", "sum"),
        cycles=("ts", "size"),
        first_ts=("ts", "min"),
        last_ts=("ts", "max"),
        run_sec=("cycle_sec", "sum"),
        zfold_area=("zfold_area", "sum"),
        trim_area=("trim_area", "sum"),
        optimal_n=("optimal", "sum"),
        fail_n=("successful", lambda s: (~s).sum()),
    ).reset_index()

    # A production day is defined on the whole line, so that a machine that sat
    # idle on a running day still shows up as a zero rather than vanishing.
    line_daily = prod.groupby("date")["cartons"].sum()
    min_c = cfg["rules"]["min_cartons_production_day"]
    keep = set(line_daily[line_daily >= min_c].index)
    d = d[d["date"].isin(keep)].copy()
    if d.empty:
        return pd.DataFrame()

    gaps = compute_gaps(p, e, cfg)
    gday = gaps.groupby("date").agg(fault_h=("fault_h", "sum"),
                                    starve_h=("starve_h", "sum")).reset_index()
    d = d.merge(gday, on="date", how="left").fillna({"fault_h": 0.0, "starve_h": 0.0})

    if len(e):
        fc = e[e["is_fault"]].groupby("date").size().rename("fault_events").reset_index()
        d = d.merge(fc, on="date", how="left")
    else:
        d["fault_events"] = np.nan
    d["fault_events"] = d["fault_events"].fillna(0).astype(int)

    d["run_h"] = d["run_sec"] / 3600.0
    d["labor_h"] = labor_h
    d["cph"] = d["cartons"] / labor_h
    d["availability_pct"] = (1 - d["fault_h"] / sched_line) * 100
    d["utilization_pct"] = d["run_h"] / sched_line * 100
    d["trim_pct"] = np.where(d["zfold_area"] > 0,
                             d["trim_area"] / d["zfold_area"] * 100, np.nan)
    d["optimal_pct"] = d["optimal_n"] / d["cycles"] * 100
    d["failure_pct"] = d["fail_n"] / d["cycles"] * 100
    d["theoretical_day"] = target_day
    d["capacity_pct"] = (d["cartons"] / target_day * 100) if target_day else np.nan

    end_h, end_m = [int(x) for x in str(cfg["shift"]["end"]).split(":")]
    end_dec = end_h + end_m / 60.0
    d["end_hour"] = d["last_ts"].dt.hour + d["last_ts"].dt.minute / 60.0
    d["overrun_h"] = (d["end_hour"] - end_dec).clip(lower=0)

    # Concurrency only means something on the combined view.
    if scope["n_machines"] > 1:
        conc = machine_concurrency(p)
        d = d.merge(conc, on="date", how="left")
        d["machines_used"] = d["machines_used"].fillna(1).astype(int)
        d["concurrent_min"] = d["concurrent_min"].fillna(0).astype(int)
    else:
        d["machines_used"] = 1
        d["concurrent_min"] = 0
    d["multi_machine"] = d["concurrent_min"] >= 15

    std = cfg["standard"]
    d["met_standard"] = d["cartons"] >= target_day
    d["met_stretch"] = d["cph"] >= float(std["throughput_stretch_cph"])
    d["clean_day"] = d["fault_events"] <= int(cfg["rules"]["clean_day_max_faults"])
    d["date"] = pd.to_datetime(d["date"])
    return d.sort_values("date").reset_index(drop=True)


def rollup(daily: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Aggregate to M / Q / Y. Rates are recomputed from their own numerator and
    denominator; averaging a daily ratio across days of different size is wrong.
    """
    if daily is None or daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    d["period"] = d["date"].dt.to_period(freq)

    g = d.groupby("period").agg(
        days=("date", "size"),
        cartons=("cartons", "sum"),
        cycles=("cycles", "sum"),
        run_h=("run_h", "sum"),
        fault_h=("fault_h", "sum"),
        starve_h=("starve_h", "sum"),
        labor_h=("labor_h", "sum"),
        zfold_area=("zfold_area", "sum"),
        trim_area=("trim_area", "sum"),
        optimal_n=("optimal_n", "sum"),
        fail_n=("fail_n", "sum"),
        fault_events=("fault_events", "sum"),
        overrun_h=("overrun_h", "sum"),
        days_met_standard=("met_standard", "sum"),
        days_met_stretch=("met_stretch", "sum"),
        clean_days=("clean_day", "sum"),
        best_day=("cartons", "max"),
        target_day=("theoretical_day", "first"),
    ).reset_index()

    sched_total = d.groupby("period").apply(
        lambda x: (x["run_h"] * 0).sum(), include_groups=False)  # placeholder shape
    # scheduled machine-hours per period = days x per-day scheduled hours
    per_day_sched = (daily["run_h"] / (daily["utilization_pct"] / 100)).replace(
        [np.inf, -np.inf], np.nan).dropna()
    sched_per_day = float(per_day_sched.iloc[0]) if len(per_day_sched) else np.nan
    g["sched_h"] = g["days"] * sched_per_day

    g["cph"] = g["cartons"] / g["labor_h"]
    g["availability_pct"] = (1 - g["fault_h"] / g["sched_h"]) * 100
    g["utilization_pct"] = g["run_h"] / g["sched_h"] * 100
    g["trim_pct"] = np.where(g["zfold_area"] > 0, g["trim_area"] / g["zfold_area"] * 100, np.nan)
    g["optimal_pct"] = g["optimal_n"] / g["cycles"] * 100
    g["failure_pct"] = g["fail_n"] / g["cycles"] * 100
    g["cartons_per_day"] = g["cartons"] / g["days"]
    g["faults_per_day"] = g["fault_events"] / g["days"]
    g["pct_days_met"] = g["days_met_standard"] / g["days"] * 100
    g["capacity_pct"] = np.where(g["target_day"] > 0,
                                 g["cartons_per_day"] / g["target_day"] * 100, np.nan)
    g["label"] = g["period"].astype(str)
    return g


def recalibrate(daily: pd.DataFrame, cfg: dict, log: _MdLog) -> dict:
    """
    Re-derive the diagnostics from recent history. Prints a YAML block to paste
    back; never writes. Throughput is left alone when the basis is engineered.
    """
    std = cfg["standard"]
    engineered = str(std.get("basis", "")).lower() == "engineered"
    if engineered:
        log.warn("Standard basis is 'engineered' (%s) - throughput comes from the "
                 "machine rating, not from history. Recalibrating diagnostics only."
                 % std.get("source", "vendor"))
    start = pd.Timestamp(std.get("basis_window_start", daily["date"].min()))
    w = daily[daily["date"] >= start]
    clean = w[w["clean_day"]]
    if len(w) < 10:
        log.warn(f"only {len(w)} days in window - too few to re-derive")
        return {}

    out = {
        "derived_on": datetime.now().strftime("%Y-%m-%d"),
        "basis_window_start": str(start.date()),
        "basis_window_end": str(w["date"].max().date()),
        "basis_clean_days": int(len(clean)),
    }
    if not engineered and len(clean) >= 5:
        out.update({
            "throughput_cph": round(float(np.percentile(clean["cph"], 75)), 1),
            "throughput_stretch_cph": round(float(np.percentile(clean["cph"], 90)), 1),
            "cartons_per_day": int(round(np.percentile(clean["cartons"], 75))),
        })
    out.update({
        "availability_pct": min(99.0, round(float(np.percentile(w["availability_pct"], 75)), 1)),
        "utilization_pct": round(float(np.percentile(w["utilization_pct"], 90)), 1),
        "max_fault_events": int(round(np.percentile(w["fault_events"], 25))),
        "max_trim_pct": round(float(w["trim_pct"].mean()), 1),
        "min_optimal_pct": round(float(w["optimal_pct"].mean()), 1),
    })
    log.h("Re-derived - paste into config.yaml under `standard:`")
    log.info(f"basis: {len(clean)} clean of {len(w)} days; availability p75 (capped 99), "
             f"utilization p90, faults p25")
    log.info("\n" + yaml.safe_dump(out, sort_keys=False, default_flow_style=False))
    log.warn("Review before pasting. These are combined-scope figures.")
    return out


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
def _clean(v):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 3)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    return v


def sku_breakdown(prod: pd.DataFrame, date, machines: list, top_n: int) -> list[dict]:
    g = prod.loc[(prod["date"] == date) & (prod["machine"].isin(machines))]
    if g.empty:
        return []
    t = (g.groupby("sku").agg(cartons=("cartons", "sum"), cycles=("ts", "size"))
          .sort_values("cartons", ascending=False))
    t = t[t["cartons"] > 0]
    total = t["cartons"].sum()
    if not total:
        return []
    rows = []
    for name, r in t.head(top_n).iterrows():
        rows.append({"sku": str(name), "cartons": int(r["cartons"]),
                     "cycles": int(r["cycles"]),
                     "pct": round(float(r["cartons"]) / total * 100, 1)})
    if len(t) > top_n:
        rest = t.iloc[top_n:]
        rows.append({"sku": f"Other ({len(rest)} SKUs)", "cartons": int(rest["cartons"].sum()),
                     "cycles": int(rest["cycles"].sum()),
                     "pct": round(float(rest["cartons"].sum()) / total * 100, 1)})
    return rows


DAILY_KEYS = ["cartons", "cycles", "cph", "run_h", "fault_h", "starve_h",
              "availability_pct", "utilization_pct", "trim_pct", "optimal_pct",
              "failure_pct", "fault_events", "overrun_h", "met_standard",
              "met_stretch", "clean_day", "capacity_pct", "multi_machine",
              "machines_used", "concurrent_min"]

PERIOD_KEYS = ["days", "cartons", "cph", "cartons_per_day", "availability_pct",
               "utilization_pct", "trim_pct", "optimal_pct", "failure_pct",
               "faults_per_day", "pct_days_met", "days_met_standard",
               "days_met_stretch", "clean_days", "best_day", "overrun_h",
               "fault_h", "starve_h", "run_h", "capacity_pct"]


def scope_payload(scope: dict, daily: pd.DataFrame, err: pd.DataFrame,
                  prod: pd.DataFrame, cfg: dict) -> dict:
    n_trend = int(cfg["dashboard"]["daily_trend_days"])
    top_n = int(cfg["dashboard"].get("sku_top_n", 8))

    if daily is None or daily.empty:
        return {**{k: scope[k] for k in ("key", "label", "sublabel", "machines",
                                         "n_machines", "associates", "labor_h",
                                         "sched_h", "target_day", "rated_bph")},
                "latest": None, "trend": [], "daily": [],
                "monthly": [], "quarterly": [], "yearly": [], "pareto": []}

    rows = []
    sku_counts = (prod[(prod["cartons"] > 0) & (prod["machine"].isin(scope["machines"]))]
                  .groupby("date")["sku"].nunique().to_dict())
    for _, r in daily.iterrows():
        rows.append({k: _clean(r[k]) for k in DAILY_KEYS} | {
            "date": r["date"].strftime("%Y-%m-%d"),
            "weekday": r["date"].strftime("%a"),
            "first": r["first_ts"].strftime("%H:%M"),
            "last": r["last_ts"].strftime("%H:%M"),
            "sku_count": int(sku_counts.get(r["date"].date(), 0)) or None,
        })

    def roll(freq):
        g = rollup(daily, freq)
        if g.empty:
            return []
        return [{k: _clean(r[k]) for k in PERIOD_KEYS} | {"label": r["label"]}
                for _, r in g.iterrows()]

    e = err[err["machine"].isin(scope["machines"])] if len(err) else err
    pareto = []
    if len(e):
        f = e[e["is_fault"]]
        if len(f):
            top = f.groupby("message").size().sort_values(ascending=False).head(8)
            by_m = f.groupby(["message", "machine"]).size().unstack(fill_value=0)
            for msg, n in top.items():
                row = {"message": str(msg), "count": int(n)}
                if msg in by_m.index:
                    row["by_machine"] = {str(k): int(v) for k, v in by_m.loc[msg].items()}
                pareto.append(row)

    latest = rows[-1] if rows else None
    if latest is not None:
        latest["skus"] = sku_breakdown(prod, daily["date"].iloc[-1].date(),
                                       scope["machines"], top_n)

    return {**{k: scope[k] for k in ("key", "label", "sublabel", "machines",
                                     "n_machines", "associates", "labor_h",
                                     "sched_h", "target_day", "rated_bph")},
            "latest": latest,
            "trend": rows[-n_trend:],
            "daily": rows,
            "monthly": roll("M"),
            "quarterly": roll("Q"),
            "yearly": roll("Y"),
            "pareto": pareto}


def build_payload(prod: pd.DataFrame, err: pd.DataFrame, cfg: dict,
                  scope_daily: dict) -> dict:
    std = cfg["standard"]
    scopes = build_scopes(cfg)
    out_scopes = [scope_payload(sc, scope_daily.get(sc["key"]), err, prod, cfg)
                  for sc in scopes]

    combined = scope_daily.get("combined")
    coverage = {"days": 0, "first": None, "last": None}
    if combined is not None and not combined.empty:
        coverage = {"days": int(len(combined)),
                    "first": combined["date"].min().strftime("%Y-%m-%d"),
                    "last": combined["date"].max().strftime("%Y-%m-%d")}

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "site": cfg["meta"]["site"],
        "title": cfg["dashboard"]["title"],
        "subtitle": cfg["dashboard"]["subtitle"],
        "default_view": cfg["dashboard"]["default_view"],
        "standard": {k: _clean(v) for k, v in std.items()},
        "thresholds": cfg["thresholds"],
        "shift": {
            "count": cfg["shift"].get("count", 1),
            "name": cfg["shift"].get("name", "1st Shift"),
            "start": cfg["shift"]["start"], "end": cfg["shift"]["end"],
            "associates": cfg["shift"]["associates"],
            "paid_hours": cfg["shift"]["paid_hours"],
        },
        "machine": {
            "rated_bph": cfg.get("machine", {}).get("rated_boxes_per_hour"),
            "rating_source": cfg.get("machine", {}).get("rating_source"),
            "associates_per_machine": cfg.get("machine", {}).get("associates_per_machine", 1),
            "installed": cfg.get("machine", {}).get("installed", cfg["shift"]["machines"]),
            "aliases": {str(k): v for k, v in
                        (cfg.get("machine", {}).get("aliases") or {}).items()},
        },
        "scopes": out_scopes,
        "coverage": coverage,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run(config_path=None, log: _MdLog | None = None) -> dict:
    cfg = load_config(config_path)
    own_log = log is None
    if own_log:
        log = _MdLog(echo_file=resolve(cfg, "log"))

    log.h("Packsize Module - ingest")
    prod = load_production(cfg, log)
    err = load_errors(cfg, log)

    log.h("Metrics")
    scopes = build_scopes(cfg)
    scope_daily = {}
    for sc in scopes:
        dm = daily_metrics(prod, err, cfg, log, sc)
        scope_daily[sc["key"]] = dm
        if dm is None or dm.empty:
            log.warn(f"{sc['label']}: no production rows")
            continue
        met = int(dm["met_standard"].sum())
        log.ok(f"{sc['label']:<10} {len(dm):3d} days  "
               f"{dm['cartons'].mean():6.0f} cartons/day  "
               f"target {sc['target_day']:.0f}  "
               f"{dm['capacity_pct'].mean():5.1f}% of target  "
               f"({met} day(s) at 100%)")

    payload = build_payload(prod, err, cfg, scope_daily)

    out_json = resolve(cfg, "data_json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    # Direct write + verify. OneDrive's sync agent breaks tmp -> rename.
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    size = out_json.stat().st_size
    if size < 500:
        log.err(f"data.json wrote only {size} bytes - suspect a failed write")
    else:
        log.ok(f"wrote {out_json.name} ({size:,} bytes)")

    if own_log:
        log.close()
    return {"cfg": cfg, "prod": prod, "err": err,
            "daily": scope_daily.get("combined"), "scope_daily": scope_daily,
            "payload": payload}


if __name__ == "__main__":
    cfg_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(cfg_arg)
