---
key: AINOS3-126
slug: sbn-adapter-blended-output
type: Story
epic: AINOS3-63 (detector-gates)
status: Backlog
priority: High
estimate: E 5 / T 1.5
opened: 2026-09-19
origin: AINOS3-125 (blended-log-format)
---

# AINOS3-126 — Emit one coherent frame from the SBN double buffer

**Summary:** As a detector owner, I want the live OnAIR frame to carry one coherent set of telemetry values instead of alternating buffer snapshots, so every detector sees each update on the frame it arrives rather than on every other frame, and so the gates can stop compensating for an artifact.

## Description

`AINOS3-125` fixed the recorded corpus offline. This fixes the **live frame**, which
is where every deployed detector actually reads.

The transform is the one already validated offline: keep a reference dict per buffer, write a
field to the output frame only when it changed against **its own buffer's** previous frame,
carry everything else forward. ⚠ A naive single "latest value" dict is WRONG — buffer B's
copy of a field is usually stale, and letting it overwrite A's fresh update reproduces the
flicker exactly.

⚠ **This is a schema-SEMANTICS change and forces an IF retrain.** By the `AINOS3-108` rule
the deployed detector pins the recorded schema; here the column set is unchanged but the
*values* on a given frame change, which is the same hazard by a different route. The
deployed IF and classifier were fitted on interleaved deltas and must be refitted on blended
ones before this can go live.

⚠ **It also invalidates the live-behaviour baselines**, which are currently true records of a
system that really does see interleaved frames: `AINOS3-86`'s 0.00 % controlled-INERTIAL FP,
`AINOS3-90`'s 55.8 incidents/hour, and the Section-A rule-gate validations all describe
pre-change behaviour and need re-measuring after it.

⚠ **The defect originates upstream** (NASA OnAIR, `sbn_adapter` only — `redis_adapter`
blanks its write buffer each message and `csv_parser` has none), so record our divergence
when the patch lands or a future rebase will silently drop it.

## Acceptance criteria

- [x] `AC1` `sbn_adapter` emits a blended frame by per-buffer change detection; the two reference dicts and the output frame are distinct state, and a stale value never overwrites a fresh one.
- [~] `AC2` ⚠ **Per-run equivalence: `deinterleave_csv.py(raw) == native blend`.** The adapter emits BOTH streams for a collection run — the untouched interleaved frames (a pure tap on the existing read path, so the raw side stays the same *kind* of data as the pre-existing `csv/`) AND the live blend. For each run, blending the raw stream offline must reproduce the native blend exactly. This is deterministic — both consume the identical recorded frame sequence — so it is a real proof, not a replay approximation. ⚠ Verify it in **all four modes** (the buffer mechanism is mode-agnostic, but each mode exercises different fields at different rates), using the `AINOS3-100 AC7` SUNSAFE-x1 / INERTIAL / BDOT / PASSIVE runs as they are collected.
- [~] `AC2b` ⚠ The raw tap must not alter the read: an interleaved file from the dual adapter must be the same representation the old adapter produced (same double-buffer semantics), so old and new `csv/` data pool into one corpus. Implement the tap upstream of the blend and leave `get_next()`'s buffer logic untouched.
- [x] `AC3` The `[0]` sentinel contract preserved exactly as offline: written for never-received fields, never adopted over good telemetry (see `AINOS3-125 AC2` for the four tools that fail silently otherwise).
- [ ] `AC4` ⚠ IF and classifier refitted on blended data and deployed together with the adapter. Deploying the adapter alone leaves both models scoring inputs whose distribution they were never fitted to.
- [ ] `AC5` Deployment follows the `AINOS3-37` discipline: one-line ini/flag flip, one-line rollback, live-verified on a fresh `make launch-quiet`, build tree synced. **Not deploying is a valid outcome.**
- [ ] `AC6` The invalidated live baselines named above re-measured, or explicitly marked pre-change in their tickets.
- [ ] `AC7` ⚠ **The directory naming inverted at the `inline` flip, not as a separate
      migration.** Once blended is the only recorded format, `csv_blended/` is a misnomer and
      `csv/` holds the format nobody uses. Do it in the same commit as `AC4`/`AC5`:

      ```
      [CSV_OUTPUT] OutputDir  -> …/csv/            blended, because it is the only format
      data/onair/csv_interleaved/                  historical raw, frozen
      ```

      ⚠ In `inline` mode there is **no raw stream**, so no `csv_raw/` is needed for NEW data —
      only history relocates. That makes this a one-way move rather than a three-way shuffle,
      and it is why it must not be done before the deploy. Repoint every plugin's
      `SideFileOutputDir` in the same change (`AINOS3-97 AC2`'s dependency map lists them),
      and sweep docs/tickets for `csv_blended/` references.

- [ ] `AC8` ⚠ **`sbn_adapter_blended.py` KEEPS its name; do not fold it into
      `sbn_adapter.py`.** Tempting once "blended" stops being a distinction, but
      `sbn_adapter.py` is upstream NASA OnAIR code and this ticket's own Description warns the
      defect originates there — "record our divergence when the patch lands or a future rebase
      will silently drop it". The `_blended` suffix IS that record. Renaming buries our patch
      in a file a rebase overwrites. The clean exit is to upstream the fix, at which point the
      suffix disappears for the right reason; until then retire the word "blended" only from
      user-facing prose (ini comments, docs), never from the filename. Record the decision
      either way so it is not re-litigated.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.

### 2026-09-20 · Built as a DUAL-OUTPUT adapter; equivalent live, 0.6 % of a frame

#### In plain terms

The adapter now rebuilds one coherent telemetry frame from the two half-stale snapshots
OnAIR has always recorded, and writes it to a separate directory while the old interleaved
file keeps being written exactly as before. Blending the old file offline reproduces the new
file exactly — proven on the live stack, not just on replay. It costs about half a percent of
the time available per frame.

**New adapter, not a replacement:** `fsw/onair/data_handling/sbn_adapter_blended.py`
SUBCLASSES `sbn_adapter.DataSource` and **calls** the parent `get_next()` rather than
reimplementing it. The buffer flip, the lock and the wait are untouched source, which is
`AC2b` by construction rather than by inspection.

**One knob, three modes** (`[SBN_ADAPTER] BlendMode`) — the raw stream is optional:

| Mode | `get_next()` returns | Raw stream | Blended stream |
|---|---|---|---|
| `tap` (default) | RAW — parent behaviour | `csv/csv_out_*` via `csv_output` | `csv_blended/csv_out_*` via the adapter |
| `inline` | BLENDED | **not recorded at all** | written by `csv_output` |
| `off` | RAW | written | none |

`tap` is the verification mode: both files, one row each per frame, detectors completely
unaffected. `inline` is the end state, and the move between them is a one-line ini change
each way. ⚠ `inline` is gated on `AC4` — it changes what the DETECTORS read.

⚠ **The DIRECTORY marks data as blended, not the filename.** Blended files keep the
`csv_out_*` basename, because `deinterleave_csv.py` already set that convention (it preserves
the source basename into `--out-dir`) and `AINOS3-125 AC4` already put the offline-blended
corpus in `data/onair/csv_blended/`. So `loader.load`, `list_clean_csvs` and
`build_corpus_manifest` all work on either directory with no filename special case, and
native and offline output pool into one corpus. The same rule extends to the plugin
side-files: on `inline`, repoint every `SideFileOutputDir` at `csv_blended/`, so
`csv_blended/iforest_out_*` means "decisions on blended frames" and `csv/iforest_out_*`
keeps meaning "decisions on interleaved frames" — a path, not a new schema field.

#### Equivalence — proven on the LIVE stack

The blend runs over the **stringified** values, the exact domain `deinterleave_csv.py` works
in, which makes agreement structural rather than coincidental. `inline` carries the blended
OBJECTS alongside the strings and returns those, so downstream value types are unchanged.

| run | frames | result |
|---|--:|---|
| live SUNSAFE, first build | 3,094 | **0 differing cells** |
| live SUNSAFE, after the `csv_blended/` move | 2,122 | **0 differing cells** |
| whole-corpus sweep (offline + live pairs) | 149 pairs | **149/149 equivalent** |

⚠ And not a no-op: blended differs from raw on **3,093 of 3,094 rows across 334 of 470
columns**. A transform that agreed by doing nothing would pass the same check.

⚠ Buffer LABELS differ from the offline script — it calls CSV row 0 "buffer 0", while live,
row 0 comes from `double_buffer_read_index == 1`. The blend is symmetric under swapping the
two slots, so output is identical; pinned by `test_parity_label_symmetry` rather than left as
an assumption. Live we also *know* the buffer, so the parity-disagreement class of error does
not exist natively, and the sidecar records the assignment as `authoritative`.

#### Performance — not a bottleneck, by ~160x

Measured in situ over 4,200 live frames (`ProfileEvery`), which is the figure that counts:

```
blend p50 820us  p95 1416us | write p50 369us | frame interval p50 197ms
transform = 0.61 % of a frame
```

The replay bench (`training/bench_blend.py --as-objects`) gives 0.21 %; live is higher
because it stringifies real ctypes objects as `CFE_EVS_HK.AppData` fills. ⚠ `tap`
stringifies each frame twice (blend + `csv_output`); `inline` pays it once, so the end state
is cheaper than the verification mode.

#### Tooling

- `fsw/onair/data_handling/sbn_adapter_blended.py` — `BlendEngine` (pure, positional, no
  I/O), `BlendedCsvWriter`, `_Profiler`, `DataSource`.
- `training/verify_blend_equivalence.py` — the `AC2` deliverable.
- `training/bench_blend.py` — the performance evidence.
- 25 tests in `fsw/test/onair/data_handling/test_sbn_adapter_blended.py`; full suite 525 pass.
  ⚠ Two are anti-drift pins: `_stringify` and the CSV writer are deliberately DUPLICATED from
  `csv_output_plugin` (this module loads inside the OnAIR core package, before any plugin path
  resolves), so the tests assert the copies still agree byte-for-byte. A silent divergence
  there would make the blend decide what changed in a different domain than the CSV records,
  and the equivalence proof would stop meaning anything without failing.

#### ⚠ Two verifier bugs that only appear at corpus scale

Both found by running the verifier against the real corpus rather than a scratch pair, and
both would have produced false confidence during the collection:

1. **pid does NOT identify a run.** OnAIR is always pid 11 inside its container, so all 478
   corpus files share it. Pairing is now `(pid, nearest start timestamp within 2 s)` — the
   adapter and `csv_output` open their files milliseconds apart in the same process.
2. **Session CSVs are unbounded** (`LinesPerFile = 0`); a 96k-row file at 470 columns is
   several GB once parsed into dicts. `--max-rows` bounds it. The blend is a prefix-stable
   fold — row i depends only on rows 0..i — so a prefix check is a valid proof about that
   prefix.

### 2026-09-21 · A REAL per-row timestamp — `OnAIR.FrameRecvUTC`

#### In plain terms

Nothing in the log ever said when a row happened, so the training loader reconstructed it by
guessing each file's frame rate from when the *next file* started — a gap that includes the
two-minute stack restart between runs. The guess is off by a median of 57 seconds by the end
of a file. Every frame now carries its own arrival time instead.

⚠ **This is a labelling defect, not a cosmetic one**, and it is upstream of every result
`AINOS3-101` will produce. `loader._synthesize_row_times` (`training/loader.py:368`) rebuilds
row times as `file_start + row_idx / rate`, with `rate` from `_compute_step_rates`
(`training/loader.py:341`), which infers it from the gap to the NEXT FILE's start. With
`LinesPerFile = 0` each session is one file and sessions are separated by a full
`make stop` + `launch-quiet`, so the rate is systematically UNDER-estimated and the error
accumulates down the file. Measured across the 113 `rebuild_2026-09-10` runs:

| | median | worst |
|---|--:|--:|
| row-time drift at end of file | **56.7 s** | **187.5 s** |

against attack windows of a few minutes. Many runs are pinned at exactly 5.460 Hz — the
median fallback firing, not a measurement.

⚠ **The manifest and the loader disagree about the same question.**
`build_corpus_manifest.py:268` converts attack windows to frame indices using a GOOD rate
(`n / (MET_max − MET_min)`, the `AINOS3-92` fix), while `loader.load_with_labels` re-derives
row times independently using the BAD one. The `AC1` alert-eligible 97.2 % figure is on the
good path; the labels the classifier trains on are on the bad one.

#### No existing clock could fix it

Measured on 96,754 blended frames — every candidate, not just the obvious one:

| field | advances on | verdict |
|---|--:|---|
| `CFE_TIME.SecondsMET` | 4.0 % | 4.000 s tick = 24.9 frames → ±2.0 s at best |
| `SCH.SlotsProcessedCount`, `SCH.TablePassCount`, `LC.MonitoredMsgCount` | 4.0 % | same 4 s HK cadence, no tiebreak |
| `NOVATEL…SecondsIntoWeek` | 16.0 % | ~1 Hz, and steps backwards (torn reads) |

Only GPS position/velocity change on >50 % of frames, and those are not clocks. So there is
no per-row clock in the recorded schema and one had to be added.

⚠ Worth recording for `AINOS3-125 AC8`: blending REPAIRS the vehicle clock. Raw MET steps
backwards on **48.2 %** of rows with ±24 s swings; blended MET is **perfectly monotonic**,
0 backwards steps. `AINOS3-92`'s max−min span trick is a workaround for the interleaving, and
`rule_gate`'s median-over-N filter on `CFE_TIME.SecondsMET` (an `AINOS3-127` item) is another.
That is a stronger argument for blended-canonical than the +0.034 macro-F1 in `AINOS3-125`.

#### What was added

`OnAIR.FrameRecvUTC` — stamped in `get_next()` when the frame is read, as ISO-8601 UTC, the
**same form the attack manifests use** for `start_utc`/`end_utc`. Labelling becomes a direct
comparison: no rate inference, no interpolation.

One clock reading, two records of it — the raw file (via `csv_output`) and the blended file
(via the adapter's writer) carry the SAME value for the same row. It also survives the blend
correctly: it differs from its own buffer's previous frame every time, so the
change-detection rule adopts it on every row rather than carrying a stale one forward. Pinned
by `test_timestamp_is_adopted_by_the_blend_on_every_row`.

⚠ **Added in the adapter subclass, NOT in `nos3_security_tlm.json`**, and the distinction is
load-bearing. In the tlm file the recorded layout would depend on a column the STOCK
`sbn_adapter` cannot produce, so running the stock adapter against that schema would hand
`csv_output` a row one shorter than its headers and silently mis-label every column. Keeping
it in the subclass means:

```
labels          502 -> 503        recorded cols   470 -> 471
recorded_schema_sha256  ff8a9e29... -> 74da446a...   (changed — correct)
schema_sha256 (tlm json) e39d403d...                 (UNCHANGED — file untouched)
```

The RECORDED schema genuinely gained a column; the SUBSCRIBED schema did not. All four
detector plugins bind features by NAME (`_header_to_idx` → `scalar_columns`), so none of them
ever look the new column up. ⚠ `vehicle_rep.py:24` asserts `len(headers) == len(tests)`, so
every parallel binning list grows too, not just the labels.

`[SBN_ADAPTER] FrameTimestamp = false` disables it in one line.

#### Status

- `AC1` / `AC2b` / `AC3` — done.
- `AC2` — SUNSAFE proven live; BDOT / INERTIAL / PASSIVE ride the `AINOS3-100 AC7` runs.
- ⚠ The timestamp column is NOT yet confirmed on live telemetry — the stack came down first.
  The next launch covers it.
- `AC4` / `AC5` / `AC6` — unchanged, gated on the four-mode corpus.

#### Spawned AINOS3-130

`OnAIR.SimTimeUTC` made a question askable that was previously invisible: every run
this project has collected launches from the SAME epoch, so the corpus samples one
orbital phase and has no eclipse variation at all. Whether a different launch phase
would cut the INERTIAL capture wait (+10.5 min/run, ~16.6 h across the collection) is
now a measurable question rather than an assumption.

Filed as [`AINOS3-130`](AINOS3-130.md) (sim-epoch-sweep). ⚠ It is sequenced BEFORE the
corpus collection restarts — a changed epoch would invalidate anything collected under
the old one.
