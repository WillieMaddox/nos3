#!/usr/bin/env python3
"""Normalize CommonMark-safe blank-line spacing around markdown lists and headings.

Ensures a blank line BEFORE a list starts, AFTER a list ends, and AROUND section
headings — the spacing some strict markdown readers need to parse lists and sections
correctly (see feedback_markdown_blank_line_spacing). Lists are kept TIGHT: there are
NO blank lines BETWEEN list items, only before the first item and after the last.

This INSERTS the surrounding blank lines and REMOVES any blank line that sits between
two list items (a leftover from the earlier loose-list convention). It never changes,
reorders, or removes non-blank content. Code blocks (``` / ~~~ fences) and table rows
are left untouched. Always verify with `diff` that only blank lines moved.

Usage:
    md_space.py FILE...            # edit in place
    md_space.py --check FILE...    # exit 1 if any file would change (no write)
"""
import re
import sys

LIST = re.compile(r"^(\s*)([-*+]|\d+\.)\s")
HEADING = re.compile(r"^#{1,6}\s")
FENCE = re.compile(r"^\s*(```|~~~)")


def _blank(s):
    return s.strip() == ""


def _next_nonblank(lines, start):
    """The next non-blank line body at/after `start`, or None."""
    for j in range(start, len(lines)):
        body = lines[j].rstrip("\n")
        if not _blank(body):
            return body
    return None


def reformat(lines):
    out = []
    in_code = False
    last_listish = False  # last non-blank emitted line was a list item or its continuation
    n = len(lines)
    for idx, line in enumerate(lines):
        body = line.rstrip("\n")
        if FENCE.match(body):
            in_code = not in_code
            out.append(line)
            last_listish = False
            continue
        if in_code:
            out.append(line)
            continue

        blank = _blank(body)

        # Drop a blank line that sits BETWEEN two list elements: the previous emitted
        # content was a list item / continuation and the next content line is a list
        # marker. Lists must be tight — blanks only wrap the list, never split items.
        if blank and last_listish:
            nxt = _next_nonblank(lines, idx + 1)
            if nxt is not None and LIST.match(nxt):
                continue  # remove this blank; do not emit

        is_list = bool(LIST.match(body))
        is_head = bool(HEADING.match(body))
        indented = (not blank) and body[:1] in (" ", "\t")
        prev_blank = (not out) or _blank(out[-1])

        if not blank and not prev_blank:
            if is_head:
                out.append("\n")                      # blank before a heading
            elif is_list and not last_listish:
                out.append("\n")                      # blank before the FIRST item of a list
            elif last_listish and not indented and not is_list:
                out.append("\n")                      # blank after a list, before a paragraph

        out.append(line)

        # blank after a heading, before following content
        if is_head and idx + 1 < n and not _blank(lines[idx + 1]):
            out.append("\n")

        if not blank:
            last_listish = is_list or (indented and last_listish)
    return out


def main():
    args = sys.argv[1:]
    check = "--check" in args
    files = [a for a in args if a != "--check"]
    changed = []
    for path in files:
        with open(path) as f:
            lines = f.readlines()
        new = reformat(lines)
        if new != lines:
            changed.append(path)
            delta = len(new) - len(lines)
            if not check:
                with open(path, "w") as f:
                    f.writelines(new)
                print(f"{path}: reflowed ({delta:+d} lines)")
            else:
                print(f"{path}: would reflow ({delta:+d} lines)")
    if not changed:
        print("all files already spaced correctly")
    sys.exit(1 if (check and changed) else 0)


if __name__ == "__main__":
    main()
