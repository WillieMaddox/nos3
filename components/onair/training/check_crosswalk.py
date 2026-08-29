#!/usr/bin/env python3
"""Keep JIRA_CROSSWALK.md a map, not a pile.

The crosswalk's stated contract is one durable `slug -> Jira key` binding, set once
and never changed. On 2026-08-25 it held **124 rows for ~100 distinct slugs**: 24
slugs appeared two to four times, because a ticket that moved from a backlog
section into a sprint section got a NEW row instead of an updated Status cell.

None of those duplicates disagreed about the key, so nothing was broken — but that
is luck, not design. The failure this prevents is the one already recorded at the
foot of the crosswalk: `AINOS3-30` was reused for different work and went unnoticed
for ten days because the surrounding noise made it unremarkable.

The rules, and what each check enforces:

  1. ONE ROW PER SLUG, file-wide. A slug binds to one key forever, in one place.
     Sprint membership belongs in the `Status` cell (`Sprint 28 · Done`), NOT in
     which section the row was copied into.
  2. ONE ROW PER KEY. A key naming two slugs is the AINOS3-30 failure recurring.
  3. NO DISAGREEMENT. If a slug or key does appear twice, the other column must
     still agree — a conflict is an error, a plain duplicate is a warning.
  4a. EVERY KEYED ROW HAS A STATUS; a missing one defaults to `Backlog` and must be
     WRITTEN, not left blank. An UNKEYED (`—`) row leaves `Status` BLANK — a slug is
     not in the Jira backlog until it is in Jira. When the key arrives, both cells are
     filled together: paste the key, write `Backlog`.
  4b. `—` IN THE JIRA COLUMN means not yet created. Such a row must not RESTATE that
     in `Status` ("Pending key") — the dash already says it, and duplicating it means
     two cells to edit when the key arrives. A terminal status on an unkeyed row is
     fine and meaningful: `sunsafe-pivot` was resolved without ever being ticketed.
  5. EVERY TICKET FILE IS MAPPED. `tickets/AINOS3-N.md` must have a crosswalk row,
     and its `slug:` must match the row's slug.
  6. EVERY PENDING FILE IS UNMAPPED. A file in `tickets/pending/` whose slug now
     has a key should be promoted, not left behind to drift.

Deliberate exemptions live in EXEMPT below, each with a reason — the documented
`AINOS3-30` key reuse is the only one.

    python3 components/onair/training/check_crosswalk.py [--strict]

Exit 1 on an error. `--strict` also fails on duplicate-but-agreeing rows, which is
the end state to aim for once the file is deduplicated.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ONAIR = os.path.dirname(HERE)
CROSSWALK = os.path.join(ONAIR, "JIRA_CROSSWALK.md")
TICKETS = os.path.join(ONAIR, "tickets")

# Keys knowingly bound to more than one slug, with the reason. See the crosswalk's
# own "key reuse" note — this is a historical fact to preserve, not a bug to fix.
EXEMPT = {
    "AINOS3-30": "documented key reuse, split 2026-08-19 (see crosswalk foot note)",
}

ROW = re.compile(
    r"^\|\s*(?P<key>—|AINOS3-\d+)\s*\|\s*(?P<slug>[\w-]+)\s*\|\s*(?P<type>\w+)\s*\|"
    r"\s*(?P<epic>[^|]*?)\s*\|\s*(?P<title>[^|]*?)\s*\|\s*(?P<status>[^|]*?)\s*\|\s*$")


def parse(path):
    rows, section = [], "(top)"
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if line.startswith("#"):
            section = line.strip().lstrip("#").strip()
            continue
        m = ROW.match(line)
        if m and m.group("slug") != "Slug":
            rows.append(dict(m.groupdict(), line=n, section=section))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true",
                    help="fail on duplicate rows even when they agree")
    args = ap.parse_args(argv)

    rows = parse(CROSSWALK)
    errors, warnings = [], []

    by_slug = collections.defaultdict(list)
    by_key = collections.defaultdict(list)
    for r in rows:
        by_slug[r["slug"]].append(r)
        if r["key"] != "—":
            by_key[r["key"]].append(r)

    # -- rules 1 & 3: one row per slug; duplicates must at least agree ----------
    for slug, rs in sorted(by_slug.items()):
        if len(rs) == 1:
            continue
        keys = {r["key"] for r in rs}
        where = ", ".join(f"L{r['line']} ({r['section'][:34]})" for r in rs)
        if len(keys) > 1:
            errors.append(f"slug '{slug}' bound to {sorted(keys)} — {where}")
        else:
            warnings.append(f"slug '{slug}' x{len(rs)} (same key {keys.pop()}) — {where}")

    # -- rules 2 & 3: one row per key ------------------------------------------
    for key, rs in sorted(by_key.items()):
        slugs = {r["slug"] for r in rs}
        if len(slugs) > 1:
            if key in EXEMPT:
                warnings.append(f"key {key} -> {sorted(slugs)} [exempt: {EXEMPT[key]}]")
            else:
                errors.append(f"key {key} bound to {sorted(slugs)} — the AINOS3-30 failure")

    # -- rule 4: unkeyed rows must not RESTATE their unkeyed-ness --------------
    # A terminal status here is legitimate (work resolved without ever being
    # ticketed); only redundancy with the dash is an error.
    redundant = re.compile(r"pending\s*key|awaiting\s*key|not\s*(yet\s*)?created|^tbd$|^—$",
                           re.I)
    for r in rows:
        if r["key"] == "—" and redundant.search(r["status"]):
            errors.append(f"L{r['line']}: '{r['slug']}' Status='{r['status']}' restates the "
                          f"dash in the Jira column — leave it blank")

    # -- rule 5: every ticket file is mapped -----------------------------------
    mapped = {r["key"]: r["slug"] for r in rows if r["key"] != "—"}
    for fn in sorted(os.listdir(TICKETS)):
        if not re.fullmatch(r"AINOS3-\d+\.md", fn):
            continue
        key = fn[:-3]
        if key not in mapped:
            errors.append(f"tickets/{fn}: no crosswalk row")
            continue
        text = open(os.path.join(TICKETS, fn), encoding="utf-8").read()
        m = re.search(r"^slug:\s*(\S+)", text, re.M)
        if m and m.group(1) != mapped[key]:
            errors.append(f"tickets/{fn}: slug '{m.group(1)}' != crosswalk '{mapped[key]}'")

    # -- rule 6: pending files whose slug now has a key should be promoted ------
    pend = os.path.join(TICKETS, "pending")
    if os.path.isdir(pend):
        for fn in sorted(os.listdir(pend)):
            slug = fn[:-3]
            keyed = [r["key"] for r in by_slug.get(slug, []) if r["key"] != "—"]
            if keyed:
                errors.append(f"tickets/pending/{fn}: slug now keyed {keyed[0]} — promote it")

    # rule 4a: a KEYED row must carry an explicit status; blank defaults to Backlog
    # and must be written, not left implicit.
    #
    # An UNKEYED row ('—') must NOT carry 'Backlog': a slug cannot be in the Jira
    # backlog before it is in Jira at all, so that cell would assert something untrue.
    # Leave it blank until the key exists — then 'Backlog' becomes the default and
    # creating the ticket stays a one-cell edit (paste key, write Backlog).
    # A TERMINAL status on an unkeyed row stays legitimate (work resolved without ever
    # being ticketed — see rule 4b), so only 'Backlog' is rejected here.
    # Corrected 2026-08-28: the previous version demanded 'Backlog' on every row,
    # contradicting the convention documented at the head of JIRA_CROSSWALK.md.
    for r in rows:
        keyed = r["key"] != "—"
        if keyed and not r["status"]:
            errors.append(f"L{r['line']}: '{r['slug']}' is keyed {r['key']} but has a blank "
                          f"Status — write 'Backlog' (the default) explicitly")
        if not keyed and r["status"].strip().lower() == "backlog":
            errors.append(f"L{r['line']}: '{r['slug']}' has no Jira key but Status is "
                          f"'Backlog' — it cannot be in the backlog before it is in Jira; "
                          f"leave Status blank until the key exists")

    for w in warnings:
        print(f"  warn : {w}")
    for e in errors:
        print(f"  ERROR: {e}")
    uniq = len(by_slug)
    print(f"\n{len(rows)} rows · {uniq} distinct slugs · "
          f"{len(rows) - uniq} duplicate row(s) · {len(errors)} error(s)")
    if errors:
        return 1
    if warnings and args.strict:
        print("--strict: duplicate rows are errors")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
