#!/usr/bin/env python3
"""AINOS3-48 — EVS AppData slot -> app-name crosswalk.

`CFE_EVS_HK.AppData` is an array of 16 CFE_EVS_AppTlmData_t records whose field 0
is an opaque cFE resource AppID (e.g. 1114113 = 0x110001), NOT a name. SHAP
attribution (AINOS3-38) shows AppData dominating most attack attributions, so we
need to resolve each AppID to the app it represents to make that signal
actionable (and to unblock the AINOS3-39 counter-reliance audit).

The AppID->name binding is deterministic for a fixed cFS image, so this is a
build-static crosswalk pinned against ONE live `CFE_ES_QUERY_ALL` dump — we do
NOT subscribe an ES-App-Info MID at runtime.

Usage:
    # Dump live app info from the FSW and (re)write the committed crosswalk:
    python appid_crosswalk.py --write

    # Diff-guard: re-dump and fail if the running build no longer matches the
    # committed crosswalk (ties into the schema-fingerprint discipline):
    python appid_crosswalk.py --check

    # Parse an existing dump file instead of commanding the FSW:
    python appid_crosswalk.py --write --from-file <appinfo_dump>

The dump is the binary CFE_ES QueryAll file: a 64-byte CFE_FS_Header_t followed
by fixed-size CFE_ES_AppInfo_t records (ResourceId u32 @0, Type u32 @4,
Name[20] @8). Record stride verified = 184 bytes for this build.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CROSSWALK_PATH = os.path.join(HERE, "..", "cfe_appid_crosswalk.json")
# The FSW writes QueryAll into /cf (OSAL virtual mount), which is the physical
# build cf dir under the shared repo mount. NOTE: the basename must stay under
# OSAL's OS_MAX_FILE_NAME (20 chars incl. nul) or cFS silently rejects the write
# — "appids.dump" (11) is safe; "appid_crosswalk.dump" (20) is NOT.
FSW_DUMP_PATH = "/cf/appids.dump"
HOST_DUMP_PATH = os.path.join(REPO, "fsw/build/exe/cpu1/cf/appids.dump")

CFE_ES_CMD_MID = 0x1806
CFE_ES_QUERY_ALL_CC = 9
FS_HEADER_LEN = 64
RECORD_STRIDE = 184
TYPE_NAMES = {1: "CORE_APP", 2: "EXTERNAL_APP", 3: "LIBRARY"}


def fsw_ip() -> str:
    """The nos-fsw command port (UDP 5012) is only reachable by container IP."""
    import subprocess
    out = subprocess.check_output(
        ["docker", "inspect", "sc01-nos-fsw", "--format",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"]).decode()
    return out.split()[0]


def send_query_all(dump_path: str = FSW_DUMP_PATH) -> None:
    """Send CFE_ES_QUERY_ALL so the FSW writes its app-info dump to dump_path."""
    fname = dump_path.encode("ascii").ljust(64, b"\x00")
    sec = struct.pack("BB", CFE_ES_QUERY_ALL_CC, 0)  # FC + unused checksum
    data = sec + fname
    pkt = struct.pack(">HHH", CFE_ES_CMD_MID, 0xC000, len(data) - 1) + data
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(pkt, (fsw_ip(), 5012))
    time.sleep(2)  # let ES write the file


def parse_dump(path: str) -> dict:
    """Parse the binary CFE_ES QueryAll file -> {appid_hex: {name, type, type_name}}."""
    data = open(path, "rb").read()
    body = data[FS_HEADER_LEN:]
    out = {}
    for i in range(len(body) // RECORD_STRIDE):
        b = body[i * RECORD_STRIDE:(i + 1) * RECORD_STRIDE]
        rid = struct.unpack_from("<I", b, 0)[0]
        typ = struct.unpack_from("<I", b, 4)[0]
        name = b[8:28].split(b"\x00")[0].decode("ascii", "replace")
        out[f"0x{rid:08X}"] = {
            "appid": rid, "name": name, "type": typ,
            "type_name": TYPE_NAMES.get(typ, str(typ)),
        }
    return out


def load_committed() -> dict:
    if not os.path.exists(CROSSWALK_PATH):
        return {}
    return json.load(open(CROSSWALK_PATH)).get("apps", {})


def build(from_file: str | None) -> dict:
    if from_file is None:
        send_query_all()
        from_file = HOST_DUMP_PATH
    if not os.path.exists(from_file):
        sys.exit(f"dump not found: {from_file} (is the stack up? did /cf get written?)")
    return parse_dump(from_file)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="(re)write the committed crosswalk")
    ap.add_argument("--check", action="store_true",
                    help="re-dump and fail (exit 1) if it no longer matches the committed crosswalk")
    ap.add_argument("--from-file", default=None, help="parse this dump instead of commanding the FSW")
    args = ap.parse_args()

    apps = build(args.from_file)
    if not apps:
        return 2
    print(f"parsed {len(apps)} resources from dump")

    if args.check:
        committed = load_committed()
        if committed == apps:
            print("OK: running build matches committed crosswalk")
            return 0
        added = set(apps) - set(committed)
        removed = set(committed) - set(apps)
        changed = {k for k in set(apps) & set(committed)
                   if apps[k]["name"] != committed[k]["name"]}
        print("MISMATCH vs committed crosswalk:")
        for k in sorted(added):   print(f"  + {k} {apps[k]['name']}")
        for k in sorted(removed): print(f"  - {k} {committed[k]['name']}")
        for k in sorted(changed): print(f"  ~ {k} {committed[k]['name']} -> {apps[k]['name']}")
        return 1

    if args.write:
        # AppData slot i (0-based, 0..15) holds the (i+1)-th registered app, i.e.
        # AppID CFE_ES_APPID_BASE(0x110000)+1+i — validated live against
        # CFE_EVS_HK.AppData[i].AppID (1114113=0x110001=CFE_EVS ... slot 5=SCH).
        # Emitting the slot->name array explicitly lets SHAP attribution render
        # AppData[<name>].<field> without re-deriving the offset.
        appdata_slots = []
        for i in range(16):
            entry = apps.get(f"0x{0x110001 + i:08X}")
            appdata_slots.append(entry["name"] if entry else None)
        doc = {
            "_comment": ("AINOS3-48 EVS AppData AppID->name crosswalk. Pinned against one "
                         "live CFE_ES_QUERY_ALL dump. AppData holds the first 16 "
                         "EVS-registered apps (AppIDs 0x110001-0x110010). `appdata_slots` "
                         "is the slot-index->name array for attribution rendering. "
                         "Regenerate with `appid_crosswalk.py --write`; guard with `--check`."),
            "record_stride": RECORD_STRIDE,
            "appdata_slots": appdata_slots,
            "apps": apps,
        }
        with open(CROSSWALK_PATH, "w") as f:
            json.dump(doc, f, indent=2)
        print(f"wrote {CROSSWALK_PATH}")
        return 0

    # default: just print
    for k, v in apps.items():
        print(f"  {k}  {v['type_name']:12} {v['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
