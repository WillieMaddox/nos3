#!/usr/bin/env python3
"""
Apply OpenC3 5 compatibility transformations to NOS3 component .rb files.

Run from the build targets directory (openc3-cosmos-nos3/targets/) after all
component source files have been copied in. Only transforms files that originated
from component submodules; gsw/cosmos/config/targets/ files are already correct.

Transformations applied to each TARGET/lib/*.rb and TARGET/procedures/**/*.rb:
  1. Remove `require 'cosmos'` and `require 'cosmos/script'`
  2. Replace `require 'X.rb'`  →  `require_utility('TARGET/lib/X')`
  3. Replace `cmd("TARGET ...")` etc  →  `cmd("TARGET_DEBUG ...")`
  4. Replace `start("tests/X.rb")` →  `start("TARGET/procedures/tests/X.rb")`

Usage: python3 openc3_rb_transform.py <targets_dir> <component_targets_file>
  targets_dir: path to the targets/ directory in the build
  component_targets: newline-separated list of target names that came from components/
                     (as opposed to gsw/cosmos/config/targets/)
"""

import os
import re
import sys

# Targets that have no _DEBUG variant (special/sim targets, see gsw_build.sh logic)
NO_DEBUG_TARGETS = {'SIM_42_TRUTH', 'SYSTEM', 'TO_DEBUG', 'SIM_CMDBUS_BRIDGE',
                    'PDU', 'CMD_UTIL', 'CI_DEBUG', 'SYN', 'CFDP_TEST', 'CFDP',
                    'MISSION', 'ARDUCAM', 'SAMPLE'}


def build_lib_map(targets_dir):
    """Return {filename.rb: TARGET} from all targets/TARGET/lib/ directories."""
    lib_map = {}
    for target in os.listdir(targets_dir):
        lib_dir = os.path.join(targets_dir, target, 'lib')
        if os.path.isdir(lib_dir):
            for fname in os.listdir(lib_dir):
                if fname.endswith('.rb') and fname not in lib_map:
                    lib_map[fname] = target
    return lib_map


def transform(content, target_name, lib_map):
    lines = content.splitlines(keepends=True)
    out = []
    for line in lines:
        # 1. Remove COSMOS 4 auto-loaded requires
        if re.match(r"\s*require\s+['\"]cosmos['\"]\s*$", line):
            continue
        if re.match(r"\s*require\s+['\"]cosmos/script['\"]\s*$", line):
            continue

        # 2. Replace bare require 'X.rb' or require "X.rb"
        m = re.match(r"^(\s*)require\s+['\"]([^'\"]+)\.rb['\"]\s*$", line)
        if m:
            indent, base = m.group(1), m.group(2)
            fname = base + '.rb'
            if fname in lib_map:
                t = lib_map[fname]
                line = f"{indent}require_utility('{t}/lib/{base}')\n"
            # else leave unchanged (unrecognised lib — warn but don't break)

        out.append(line)

    content = ''.join(out)

    # 3. Add _DEBUG suffix to all cmd/tlm calls for debug-capable targets.
    #    Match the target name as a whole word followed by a space inside a string.
    #    e.g.  cmd("GENERIC_TORQUER PACKET")  →  cmd("GENERIC_TORQUER_DEBUG PACKET")
    #    Also handles:  wait_check_packet("TARGET", ...)  →  wait_check_packet("TARGET_DEBUG", ...)
    for t in lib_map.values():
        if t in NO_DEBUG_TARGETS:
            continue
        # "TARGET STUFF"  →  "TARGET_DEBUG STUFF"
        content = re.sub(
            r'(?<=["\'])' + re.escape(t) + r'(?= )',
            t + '_DEBUG',
            content
        )
        # "TARGET"  (standalone, e.g. as second arg to wait_check_packet)
        content = re.sub(
            r'(?<=["\'])' + re.escape(t) + r'(?=["\'])',
            t + '_DEBUG',
            content
        )

    # 4. Fix start("tests/X.rb") → start("TARGET/procedures/tests/X.rb")
    #    and start("X.rb")       → start("TARGET/procedures/X.rb")
    def fix_start(m):
        quote = m.group(1)
        path = m.group(2)
        if path.startswith(target_name + '/'):
            return m.group(0)   # already absolute — leave it
        return f'start({quote}{target_name}/procedures/{path}{quote})'

    content = re.sub(r'start\(([\'"])([^\'"]+\.rb)\1\)', fix_start, content)

    return content


def process_dir(targets_dir, component_targets, lib_map):
    count = 0
    for target in sorted(os.listdir(targets_dir)):
        if target not in component_targets:
            continue
        target_dir = os.path.join(targets_dir, target)
        for root, _, files in os.walk(target_dir):
            for fname in files:
                if not fname.endswith('.rb'):
                    continue
                # Skip radio-specific files — they reference TARGET_RADIO intentionally
                if 'radio' in fname.lower():
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    original = f.read()
                transformed = transform(original, target, lib_map)
                if transformed != original:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(transformed)
                    count += 1
    return count


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <targets_dir> <component_targets_list_file>', file=sys.stderr)
        sys.exit(1)

    targets_dir = sys.argv[1]
    component_targets_file = sys.argv[2]

    with open(component_targets_file) as f:
        component_targets = {line.strip() for line in f if line.strip()}

    lib_map = build_lib_map(targets_dir)
    count = process_dir(targets_dir, component_targets, lib_map)
    print(f'openc3_rb_transform: updated {count} files')
