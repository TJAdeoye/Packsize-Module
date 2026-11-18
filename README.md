# Packsize Module

Daily production reporting for the Packsize on-demand packaging line at HK1.
Reads the two manual PackNet drops, scores every day against a derived standard,
and writes a single self-contained dashboard with daily, monthly, quarterly and
yearly views.

---

## Views

The dashboard has two axes of navigation, giving twelve views in total.

**Scope** (top tabs) — each carries its own target:

| Scope | Machines | Associates | Target |
|---|---|---|---|
| Combined | 705164 + 706614 | 2 | **2,800/day** |
| MG1 | 705164 | 1 | **1,400/day** |
| MG2 | 706614 | 1 | **1,400/day** |

**Period** (second row) — Daily, Monthly, Quarterly, Yearly. Every scope has a full
history in each period, so MG1's yearly trend is as available as the combined one.

Tile targets follow the scope: the machine tabs are scored against one machine's
1,400/day, the overview against both machines' 2,800/day. Per-labour-hour is the
exception — the spec of 175 per associate is flat, so it reads the same on every tab.

Machine tab names come from `machine.aliases` in config.yaml; rename them there.

### Clicking into a tile

Every tile on both the daily and period views opens a history panel for that metric,
scoped to the machine tab you are on. The panel has its own Daily / Monthly / Quarterly /
Yearly switch, the target drawn as a dashed line, bars coloured against it, and a summary
row: latest, average, best, worst, days met and hit rate. Opening from a period tile lands
on that granularity; opening from a daily tile lands on daily.

The Cartons panel also carries the box-SKU split for the latest day beneath the chart.

### Associate toggle

The 1 / 2 associate switch on the per-labour-hour tile appears only on the **Combined**
tab. One machine is run by one associate, so the machine tabs have nothing to toggle and
are fixed at 1. On Combined the switch exists to read a short-staffed day honestly, since
the pipeline otherwise assumes two associates every day.

## Folder layout

```
Packsize Module\
├── Carton Production File\        <- MANUAL DAILY DROP: PackNet carton production export
├── Error Excel File\              <- MANUAL DAILY DROP: PackNet error / availability export
├── Packsize_Dashboard.html        <- the output. Open this.
└── Configuration\
    ├── config.yaml                <- paths, standard, shift, business rules
    ├── packsize_etl.py            <- ingest + metrics
    ├── build_dashboard.py         <- renders the HTML
    ├── run.py                     <- orchestrator
    ├── run_packsize.bat           <- double-click launcher
    ├── Packsize_Daily.ipynb       <- notebook: same pipeline, plus ad-hoc analysis
    ├── packsize_data.json         <- generated payload (audit trail)
    ├── packsize_run.log           <- appended every run
    └── archive\                   <- dated dashboard snapshots
```

Both drop folders are read **in full** every run and de-duplicated. Dropping a single
day or a complete re-export both work. Nothing is deleted, moved, or renamed — your
source files are never touched.

---

## First-time setup

```bat
py -3 -m pip install --upgrade pandas pyyaml openpyxl jupyter
```

Then confirm the wiring:

```bat
cd "…\Packsize Module\Configuration"
py -3 run.py --check
```

That validates the config, both drop folders, and write access — and ingests nothing.

---

## Daily use

1. Drop today's two exports into their folders.
2. Double-click `run_packsize.bat`.
3. `Packsize_Dashboard.html` opens on the **Daily** view — that's the 7:30 call screen.

From the command line:

| Command | What it does |
|---|---|
| `py -3 run.py` | Rebuild the dashboard |
| `py -3 run.py --open` | Rebuild and open it |
| `py -3 run.py --check` | Validate setup, ingest nothing |
| `py -3 run.py --recalibrate` | Re-derive the standard and print it |

**To schedule it:** Task Scheduler → daily at 06:45 → action `run_packsize.bat`,
"Start in" set to the Configuration folder. Drop the files the evening before, or
first thing, and the dashboard is waiting.

---

## The standard — engineered (Packsize)

Confirmed by Tim Williams at Packsize, 11 Sep 2026: **175 cartons/hour**, and the spec is
**one associate to one machine**. The rate is already derated — it factors in the EM7's
mechanical limits, box style and design, tiling frequency, **85% OEE**, and **25% PF&D**
(personal, fatigue and delay). It is not a lab maximum.

```
175 cartons/hr  x  2 associates (1 machine each)  x  8 hours  =  2,800 cartons/day
per labour-hour standard = 175, flat - it does not move with headcount
implied raw mechanical rate = 175 / (0.85 x 0.75) = ~275 cartons/hr
```

| Metric | Standard | Basis |
|---|---|---|
| **Cartons per day** | **2,800** | **175/hr x 2 associates x 8 hrs** |
| Per labour-hour | 175 | per associate, per machine, flat |
| Capacity used | 100% | the engineered rate is the target |
| Availability | ≥ 95% | diagnostic, from our own history |
| Utilization | ≥ 42% | diagnostic, p90 of window days |
| Fault events | ≤ 2/day | guardrail, p25 |
| Trim waste | ≤ 12.4% | guardrail, trailing window |
| Produced optimally | ≥ 81% | guardrail, trailing window |

Current attainment averages **27%**. No day in the record reached 2,800; the best, 1,540
on 23 Jul, is 55% of spec.

### The staffing gap is half the shortfall

`config.yaml` deliberately carries two different machine counts:

```yaml
machine:
  concurrent: 1              # ACTUAL - the crew runs one machine at a time
  associates_per_machine: 1  # SPEC   - Packsize rates 1 associate = 1 machine
```

Machines that *should* run = associates ÷ associates_per_machine = **2**.
Machines that *do* run = **1**.

Two associates sharing one machine caps output at 1,400/day — 50% of spec — before the
shift even starts. `concurrent` drives the physical machine-hour denominators
(availability, utilization); the spec count drives the target. Splitting the two
associates onto the two machines is the single largest available gain, and it needs no
extra headcount, no second shift, and no capital.

**Because 175/hr already embeds an 85% OEE allowance, do not subtract availability or
utilization losses again on top of the 2,800 target** — that double-counts the same
downtime. Those metrics are diagnostics that explain a missed day, not separate goals.

`run.py --recalibrate` will not overwrite the throughput figures while
`standard.basis` is `engineered`; it refreshes the diagnostics only.

### Machine design rating and concurrency

The Packsize design team rates one machine at **175 boxes/hour** (`machine.rated_boxes_per_hour`).

Two machines are installed but **the crew runs one at a time** (`machine.concurrent: 1`), so every
scheduled-hours denominator uses the concurrent count, not the installed count. This is verified in
the data: on days when both machines log cycles, median concurrent running time is only ~16% of the
smaller machine's active minutes — they alternate rather than run in parallel.

That makes the design ceiling **175 × 1 × 8 = 1,400 cartons/day**. The **Capacity used** tile scores
each day against it. Days where both machines ran **at the same time** are detected from the cycle timestamps —
not inferred from day totals — and flagged `2M` in the recent-days table. 23 of 133 days
qualify (15+ concurrent minutes). Most days show both machines logging but near-zero
concurrent minutes, which is the alternating pattern.

Getting this wrong matters: treating both machines as concurrent halves utilization and doubles the
ceiling, which would make a line running near its limit look like it had 50% headroom.

One caveat worth knowing: the export's `Cycle Time In Seconds` field implies about 377 boxes per
*running* machine-hour, which is more than double the 175 rating. That field does not capture full
machine occupancy, so it cannot be compared with the rating directly. Capacity attainment is
therefore measured against **scheduled** hours, not running hours.

---

### Where utilization comes from — and its known weakness

```
utilization % = sum(Cycle Time In Seconds) / 3600 / (concurrent x paid_hours) x 100
```

For 9 Sep: 4.15 running hours ÷ 8 scheduled = 51.9%.

**This is a lower bound, not the true figure.** Dividing cartons by those same running hours
gives ~332 boxes/hour, which is nearly double the 175/hr design rating. A machine cannot beat
its own rating, so `Cycle Time In Seconds` is not capturing everything the machine is doing —
feed, indexing, and eject appear to be excluded. Across the Jul–Sep window the gap is a
consistent **2.15x**.

So the honest reading is a range:

| Basis | 9 Sep | What it measures |
|---|---|---|
| Cycle-time utilization | 51.9% | time the machine was actively forming — lower bound |
| Rating-implied occupancy | 98.5% | time needed to make that many boxes at 175/hr — upper bound |

Treat utilization as a **trend indicator**, not an absolute. It is comparable day to day
because the same understatement applies to every day. Resolving the range needs one answer
from Packsize: does 175/hr include feed and handling, or is it raw forming speed?

---

## Two things the pipeline handles that are easy to get wrong

**The two files are in different time zones.** PackNet exports the event log in UTC
and the production file in local time. Without conversion, every fault appears five
hours after the cycle it interrupted, and fault attribution is meaningless. Handled
by `rules.error_log_is_utc`. Cell 3 of the notebook verifies it: error events should
peak at hour 5 (shift start).

**Not every EmergencyStop is a fault.** Roughly 45% land within minutes of shift
start or end — the crew uses the e-stop as a power switch. Counting them would make
normal opening procedure the largest reported failure mode. Handled by
`rules.boundary_estop`.

**Availability and utilization are different metrics** and the dashboard reports both.
Availability asks *is the machine healthy* (fault downtime only, ~90–100%). Utilization
asks *is the machine running* (~13%). Combining them into one "uptime" number hides
where the loss actually is: about 82% of idle time carries no logged fault, which is a
flow problem, not a maintenance one.

---

## Adding a second shift

Edit `config.yaml`:

```yaml
shift:
  count: 2               # was 1
  associates: 4          # total across both shifts
  paid_hours: 8.0
```

The labor-hour denominator, the header's hours-of-operation line, and every throughput
and capacity figure follow automatically. Also raise `shift.scheduled_hours_per_machine`
to 16 so availability, utilization and the daily ceiling reflect the longer day. If a second
person is added to run **both machines at once** instead, change `machine.concurrent` to 2 — that
doubles the ceiling to 2,800/day without adding a shift.
Re-derive the standard afterwards — a two-shift day is not comparable to the
one-shift days the current standard came from.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `No production files found` | Nothing in the drop folder, or only `~$` Excel lock files. Close the workbook and re-run. |
| `missing expected column(s)` | PackNet renamed an export header. Update the mapping under `columns:` in config.yaml — no code change needed. |
| Fault counts look wrong; events peak at hour 10 | Timezone conversion is off. Check `rules.error_log_is_utc`. |
| "Charts unavailable" banner | Chart.js CDN is blocked. All figures still show in the tiles and tables. To go fully offline, save `chart.umd.min.js` beside the HTML and point `dashboard.chart_js_cdn` at it. |
| Dashboard shows an old date | The run failed. Check `packsize_run.log` — it appends a timestamped block every run. |
| A day is missing | Days under 50 cartons are treated as calibration/non-production. Change `rules.min_cartons_production_day` if that's wrong. |

---

## Not yet covered

**Produced-unit-on-hand.** PackNet records what was produced, never what was consumed,
so on-hand is not derivable from these two files. It needs pack-out or shipment
confirmations from the WMS. Once that feed exists it becomes a third drop folder and
a fourth KPI tile.

**Scheduled-hours calendar.** The denominator is fixed at 8.0 hours per machine per day.
PM windows, short days, and holidays are not reflected.

**Actual staffing by day.** The labor denominator assumes two associates every day, so
days with PTO or reassignment are scored as though fully staffed.
