#!/usr/bin/env python3
"""Add loose / CommonMark-safe blank-line spacing to markdown.

Inserts a blank line between every list item, before a list starts, after a list
ends, and around section headings — the spacing some strict markdown readers need
to parse lists and sections correctly (see feedback_markdown_blank_line_spacing).

ADD-ONLY: this only ever INSERTS blank lines; it never changes, reorders, or removes
content. Code blocks (``` / ~~~ fences) and table rows are left untouched. Always
verify with `diff` that only blank lines were added.

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
        is_list = bool(LIST.match(body))
        is_head = bool(HEADING.match(body))
        indented = (not blank) and body[:1] in (" ", "\t")
        prev_blank = (not out) or _blank(out[-1])

        if not blank and not prev_blank:
            if is_list or is_head:
                out.append("\n")                      # blank before a list item / heading
            elif last_listish and not indented:
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
            added = len(new) - len(lines)
            if not check:
                with open(path, "w") as f:
                    f.writelines(new)
                print(f"{path}: +{added} blank lines")
            else:
                print(f"{path}: would add {added} blank lines")
    if not changed:
        print("all files already spaced correctly")
    sys.exit(1 if (check and changed) else 0)


if __name__ == "__main__":
    main()
