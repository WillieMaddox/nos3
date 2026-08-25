#!/usr/bin/env python3
"""Enforce the ticket/sprint separation of concerns.

The problem this exists to prevent: a ticket that carries across sprints used to
get its body duplicated into each sprint plan, so its definition forked. AINOS3-96
ended up with 4 acceptance criteria in SPRINT_27_PLAN.md and 2 more in
SPRINT_28_PLAN.md, with nothing declaring that the union was the real list. Ten
tickets were in that state.

The rule:

    Ticket files own WHAT and WHETHER-IT'S-DONE.
    Sprint plans own WHEN and WHY-NOW.

so definitional content (acceptance criteria, results) may appear in exactly one
place — `tickets/<KEY>.md` — while sprint-scoped reasoning (why this ticket is in
this sprint, sequencing, what changed) stays in the sprint plan where it belongs.

Checks:
  1. every ticket file's key matches its filename and exists in JIRA_CROSSWALK.md
  2. every ticket file has Summary, Acceptance criteria and Log sections
  3. THE ANTI-FORK RULE, universal: if `tickets/<KEY>.md` exists, no sprint plan
     may carry DEFINITIONAL content for that key — `**Summary:**`,
     `**Description:**`, acceptance criteria or a `**Result:**` block. A `###
     <KEY>` heading is still fine and expected: sprint plans keep sprint-scoped
     narrative (why this ticket now, sequencing, de-scope position) under it.
     A closed ticket that was never migrated keeps its body in the sprint that
     did the work, which is its single home and is fine.
  4. no MIGRATED sprint plan contains an `Acceptance Criteria` heading, a
     `**Result:**` block, or a "Body as scoped in <other plan>" pointer

Rule 3 applies everywhere. Rule 4 applies only to plans carrying the marker line
`<!-- tickets-migrated -->`, so partially-migrated and historical sprints are not
falsely flagged — back-fill a ticket file later and rule 3 tells you at once to
remove the stale plan body.

Run:  python3 components/onair/training/check_ticket_docs.py [--tickets-dir ...]
Exit 0 = clean, 1 = violations.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

KEY_RE = re.compile(r"^AINOS3-\d+$")
BODY_RE = re.compile(r"^### (AINOS3-\d+)\b", re.M)
MIGRATED = "<!-- tickets-migrated -->"
REQUIRED = ("## Acceptance criteria", "## Log")


def emit_pending(pending_dir: str) -> int:
    """Print the Jira-creation queue: everything in tickets/pending/, formatted as
    Summary + Type + Description so it can be pasted straight into Jira.

    This is the SSH workflow — `ls tickets/pending/` is the queue, and this dumps
    the fields Jira needs without opening each file. Every sprint item needs
    Summary + Description + Type, so all three are printed.
    """
    paths = sorted(glob.glob(os.path.join(pending_dir, "*.md")))
    if not paths:
        print(f"{pending_dir}: empty — nothing awaiting a Jira key")
        return 0
    print(f"{len(paths)} slug(s) awaiting a Jira key\n")
    for path in paths:
        text = open(path).read()
        slug = os.path.splitext(os.path.basename(path))[0]
        def field(name, default="?"):
            m = re.search(rf"^{name}:\s*(.+)$", text, re.M)
            return m.group(1).strip() if m else default
        summ = re.search(r"^\*\*Summary:\*\*\s*(.+?)(?:\n\n|\Z)", text, re.M | re.S)
        desc = re.search(r"^## Description\s*\n(.+?)(?=^## )", text, re.M | re.S)
        n_ac = len(re.findall(r"^- \[[ x]\] ", text, re.M))
        print("=" * 78)
        print(f"slug:  {slug}")
        print(f"type:  {field('type')}")
        print(f"epic:  {field('epic', '—')}")
        print(f"ACs:   {n_ac}")
        print(f"file:  {path}")
        print("\nSUMMARY\n" + " ".join((summ.group(1) if summ else "MISSING").split()))
        print("\nDESCRIPTION\n" + (desc.group(1).strip() if desc else "MISSING"))
        print(f"\nafter creating it:  git mv {path} "
              f"{os.path.dirname(pending_dir)}/AINOS3-<N>.md  "
              f"&& sed -i 's/^key: .*/key: AINOS3-<N>/' <newfile>")
        print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tickets-dir", default="components/onair/tickets")
    p.add_argument("--pending", action="store_true",
                   help="print the Jira-creation queue (tickets/pending/) with "
                        "Summary + Type + Description, then exit")
    p.add_argument("--plans-glob", default="components/onair/SPRINT_*_PLAN.md")
    p.add_argument("--crosswalk", default="components/onair/JIRA_CROSSWALK.md")
    args = p.parse_args()

    if args.pending:
        return emit_pending(os.path.join(args.tickets_dir, "pending"))

    problems: list[str] = []
    crosswalk = ""
    if os.path.exists(args.crosswalk):
        crosswalk = open(args.crosswalk).read()
    else:
        problems.append(f"crosswalk not found: {args.crosswalk}")

    tickets: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(args.tickets_dir, "*.md"))):
        key = os.path.splitext(os.path.basename(path))[0]
        text = open(path).read()
        tickets[key] = text
        if not KEY_RE.match(key):
            problems.append(f"{path}: filename is not a bare Jira key")
            continue
        m = re.search(r"^key:\s*(\S+)", text, re.M)
        if not m:
            problems.append(f"{path}: no `key:` in frontmatter")
        elif m.group(1) != key:
            problems.append(f"{path}: frontmatter key {m.group(1)} != filename {key}")
        if crosswalk and key not in crosswalk:
            problems.append(f"{path}: {key} is not in JIRA_CROSSWALK.md")
        for sec in REQUIRED:
            if sec not in text:
                problems.append(f"{path}: missing section `{sec}`")
        if "**Summary:**" not in text:
            problems.append(f"{path}: missing `**Summary:**`")

    n_migrated = 0
    for path in sorted(glob.glob(args.plans_glob)):
        text = open(path).read()
        base = os.path.basename(path)
        # Rule 3 — universal anti-fork check, marker or not. A heading is fine;
        # definitional content under it is not, once a ticket file owns it.
        for m in re.finditer(r"^### (AINOS3-\d+)\b.*?(?=^### |^## |\Z)",
                             text, re.M | re.S):
            key, section = m.group(1), m.group(0)
            if key not in tickets:
                continue
            leaks = [lbl for lbl, pat in (
                ("**Summary:**", r"\*\*Summary:\*\*"),
                ("**Description:**", r"\*\*Description:\*\*"),
                ("Acceptance Criteria", r"Acceptance Criteria"),
                ("**Result:**", r"\*\*Result:?\*\*"),
            ) if re.search(pat, section)]
            if leaks:
                problems.append(
                    f"{base}: `### {key}` carries definitional content "
                    f"({', '.join(leaks)}) but {args.tickets_dir}/{key}.md owns it")
        if MIGRATED not in text:
            continue                      # rule 4 is for migrated plans only
        n_migrated += 1
        if re.search(r"Acceptance Criteria", text, re.I):
            problems.append(f"{base}: contains an Acceptance Criteria heading — "
                            f"ACs belong in tickets/<KEY>.md")
        if "**Result:**" in text:
            problems.append(f"{base}: contains a **Result:** block — results "
                            f"belong in the ticket file's Log")
        if "Body as scoped in" in text:
            problems.append(f"{base}: contains a cross-plan 'Body as scoped in' "
                            f"pointer — link to tickets/<KEY>.md instead")

    print(f"{len(tickets)} ticket file(s); "
          f"{len(glob.glob(args.plans_glob))} plan(s) anti-fork checked, "
          f"{n_migrated} marked migrated")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p_ in problems:
            print(f"  - {p_}")
        return 1
    print("clean — no definitional content outside tickets/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
