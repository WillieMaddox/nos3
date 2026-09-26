#!/usr/bin/env python3
"""Positive control for the CFE_TBL LOAD/ACTIVATE mechanism (companion to EX-0012.04).

Why this exists
---------------
EX-0012.04 sends CFE_TBL LOAD against `/cf/attacker_rts.tbl`, a file that is never
staged, so the load is *rejected* — the footprint is the CommandErrorCounter bump,
not an actual table change. That proves the command path but leaves an obvious
question open: can this mechanism actually LOAD and MODIFY a live table?

This tool answers it directly and safely, with no hand-crafted binary:

  1. DUMP the target table's ACTIVE image to /cf (cFS writes a valid .tbl file).
  2. Read it back on the host (/cf is the bind-mounted fsw/build/exe/cpu1/cf), flip
     exactly ONE payload byte, write a modified copy.
  3. LOAD the modified copy (into the inactive buffer), VALIDATE it, ACTIVATE it.
  4. DUMP the now-active image and DIFF against the original — the one flipped byte
     is the proof the load took effect in the running FSW.
  5. RESTORE: LOAD+ACTIVATE the original dump, re-DUMP, confirm byte-identical.

Safety
------
* Default target is CS.DefMemoryTbl — the Checksum app is a MONITOR, not an
  actuator, so a transient one-byte change cannot move the vehicle or command a
  device. Do NOT point this at SC.RTS_TBL* / LC actionpoints / any ADCS table.
* The flipped byte is chosen in a non-zero constant that repeats at a fixed
  stride — structural padding / filler (e.g. CS.DefMemoryTbl's Filler16), which no
  validator inspects — so it perturbs nothing the app acts on and passes VALIDATE.
  (Zero-fill is deliberately avoided: it is often a real field of an EMPTY entry
  whose non-zero value the validator rejects.)
* ACTIVATE only happens if VALIDATE passes; otherwise the run stops before any
  change is applied and reports the rejection.
* The original image is restored at the end (unless --no-restore), and every table
  reloads from disk on the next stack restart regardless.

This is a verification artifact. It writes no manifest and its output must NOT be
banked into the training corpus.

Usage
-----
    python3 verify_table_load.py --fsw-host <ip>          # full round trip
    python3 verify_table_load.py --fsw-host <ip> --inspect   # dump + show only
    python3 verify_table_load.py --auto-discover
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import subprocess
import sys
import time

CFE_TBL_CMD_MID = 0x1804
FC_NOOP, FC_RESET, FC_LOAD, FC_DUMP, FC_VALIDATE, FC_ACTIVATE = 0, 1, 2, 3, 4, 5
BUFFER_ACTIVE, BUFFER_INACTIVE = 1, 0

PATH_LEN = 64          # CFE_MISSION_MAX_PATH_LEN
NAME_LEN = 40          # CFE_MISSION_TBL_MAX_FULL_NAME_LEN
FS_HDR = 64            # sizeof(CFE_FS_Header_t)
TBL_HDR = 12 + NAME_LEN  # Reserved(4)+Offset(4)+NumBytes(4)+TableName[40], big-endian
PAYLOAD_OFF = FS_HDR + TBL_HDR   # 116

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CF = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                          "fsw", "build", "exe", "cpu1", "cf"))


def ccsds_cmd(fc: int, payload: bytes = b"") -> bytes:
    data = struct.pack("BB", fc, 0) + payload
    return struct.pack(">HHH", CFE_TBL_CMD_MID, 0xC000, len(data) - 1) + data


def _fixed(s: str, n: int) -> bytes:
    b = s.encode("ascii", "ignore")[:n]
    return b + b"\x00" * (n - len(b))


def dump_cmd(table: str, cf_path: str, active: bool = True) -> bytes:
    return ccsds_cmd(FC_DUMP,
                     struct.pack("<H", BUFFER_ACTIVE if active else BUFFER_INACTIVE)
                     + _fixed(table, NAME_LEN) + _fixed(cf_path, PATH_LEN))


def load_cmd(cf_path: str) -> bytes:
    return ccsds_cmd(FC_LOAD, _fixed(cf_path, PATH_LEN))


def validate_cmd(table: str, active: bool) -> bytes:
    return ccsds_cmd(FC_VALIDATE,
                     struct.pack("<H", BUFFER_ACTIVE if active else BUFFER_INACTIVE)
                     + _fixed(table, NAME_LEN))


def activate_cmd(table: str) -> bytes:
    return ccsds_cmd(FC_ACTIVATE, _fixed(table, NAME_LEN))


class Tbl:
    def __init__(self, host: str, port: int, cf_host_dir: str, dry: bool = False):
        self.host, self.port, self.cf_host_dir, self.dry = host, port, cf_host_dir, dry
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ⚠ CFE_TBL VALIDATE and ACTIVATE are ASYNCHRONOUS: the command only queues a
    # request that the owning app services on its next CFE_TBL_Manage() cycle
    # (~1-2 s for CS). Measured 2026-09-24: validation completed ~2 s AFTER the
    # command, so a 1.5 s settle sent ACTIVATE before the buffer was validated and
    # dumped the "after" image before the swap propagated — the load/validate both
    # succeeded but the change looked absent. 4 s per step clears the handshake.
    def send(self, desc: str, pkt: bytes, settle: float = 4.0) -> None:
        print(f"  -> {desc}")
        if not self.dry:
            self.sock.sendto(pkt, (self.host, self.port))
            time.sleep(settle)

    def dump(self, table: str, stem: str, active: bool = True) -> str:
        """DUMP `table` to /cf/<stem>.tbl and return the HOST path once it lands."""
        cf_path = f"/cf/{stem}.tbl"
        host_path = os.path.join(self.cf_host_dir, f"{stem}.tbl")
        if os.path.exists(host_path):
            os.remove(host_path)
        self.send(f"DUMP {'ACTIVE' if active else 'INACTIVE'} {table} -> {cf_path}",
                  dump_cmd(table, cf_path, active))
        for _ in range(20):
            if os.path.exists(host_path) and os.path.getsize(host_path) > PAYLOAD_OFF:
                return host_path
            time.sleep(0.5)
        raise SystemExit(f"DUMP did not produce {host_path} — is the stack up and "
                         f"is {self.cf_host_dir} the FSW's /cf?")


def parse_dump(path: str) -> tuple[int, bytes]:
    """Return (payload_numbytes, whole_file_bytes); sanity-check the cFE headers."""
    raw = open(path, "rb").read()
    if raw[0:4] != b"cFE1":
        raise SystemExit(f"{path}: not a cFE file image (ContentType={raw[0:4]!r})")
    # TBL header is big-endian: Reserved, Offset, NumBytes
    _, offset, numbytes = struct.unpack(">III", raw[FS_HDR:FS_HDR + 12])
    if offset != 0 or PAYLOAD_OFF + numbytes != len(raw):
        raise SystemExit(f"{path}: unexpected geometry offset={offset} "
                         f"numbytes={numbytes} filesize={len(raw)}")
    return numbytes, raw


def pick_safe_byte(payload: bytes) -> int:
    """Offset (within payload) of a byte that is safe to flip.

    ⚠ A zero-fill run is NOT safe: for many tables the zero regions are real
    fields of EMPTY entries (e.g. CS.DefMemoryTbl's StartAddress), and the app's
    validator REJECTS an EMPTY entry whose address/size is non-zero — so flipping
    there changes nothing (measured 2026-09-24). The reliable target is a
    NON-ZERO byte that repeats at a fixed stride: that pattern is almost always
    structural padding / a filler constant, which no validator inspects (e.g.
    CS_Def_EepromMemory_Table_Entry_t.Filler16 = 0x1234 every 16 bytes). Prefer
    the first such byte; fall back to the last non-zero byte, then the last byte.
    """
    n = len(payload)
    for stride in (16, 8, 4, 12, 32):          # common entry sizes
        for base in range(min(stride, n)):
            vals = payload[base::stride]
            if len(vals) >= 3 and vals[0] != 0 and len(set(vals)) == 1:
                return base                      # a non-zero constant column
    nz = [i for i, b in enumerate(payload) if b != 0]
    return nz[-1] if nz else n - 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fsw-host", default=None)
    p.add_argument("--auto-discover", action="store_true",
                   help="Look up sc01-nos-fsw IP via docker inspect.")
    p.add_argument("--fsw-cmd-port", type=int, default=5012)
    p.add_argument("--table", default="CS.DefMemoryTbl",
                   help="Full registered table name (APP.TableName). Default: a "
                        "Checksum monitor table (non-actuating). Do NOT use "
                        "SC.RTS_TBL* or any actuator table.")
    p.add_argument("--cf-dir", default=DEFAULT_CF,
                   help="Host path that backs the FSW's /cf (bind mount).")
    p.add_argument("--offset", type=int, default=None,
                   help="Payload byte offset to flip. Default: auto (zero run).")
    p.add_argument("--inspect", action="store_true",
                   help="Only DUMP the table and show its geometry; change nothing.")
    p.add_argument("--no-restore", action="store_true",
                   help="Leave the modified image active (it still reloads on "
                        "the next stack restart). Default restores immediately.")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    host = a.fsw_host
    if a.auto_discover and not host:
        host = subprocess.check_output(
            ["docker", "inspect", "-f",
             "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
             "sc01-nos-fsw"], text=True).strip()
    if not host:
        raise SystemExit("need --fsw-host or --auto-discover")
    print(f"FSW {host}:{a.fsw_cmd_port} | table {a.table} | /cf -> {a.cf_dir}\n")

    t = Tbl(host, a.fsw_cmd_port, a.cf_dir, dry=a.dry_run)
    # ⚠ OSAL silently drops any write whose basename is >= OS_MAX_FILE_NAME (20
    # chars incl. nul) — see reference_fsw_file_dump_and_appid. Keep every /cf
    # filename short and INDEPENDENT of the (long) table name.
    S_ORIG, S_MOD, S_AFTER, S_REST = "tbl_o", "tbl_m", "tbl_a", "tbl_r"

    orig_path = t.dump(a.table, S_ORIG, active=True)
    numbytes, orig = parse_dump(orig_path)
    payload = bytearray(orig[PAYLOAD_OFF:PAYLOAD_OFF + numbytes])
    print(f"  dumped {orig_path}: payload {numbytes} bytes")

    off = a.offset if a.offset is not None else pick_safe_byte(payload)
    if not (0 <= off < numbytes):
        raise SystemExit(f"offset {off} outside payload [0,{numbytes})")
    old = payload[off]
    print(f"  target payload byte: offset {off} (file byte {PAYLOAD_OFF + off}), "
          f"current value 0x{old:02X}")

    if a.inspect:
        print("\n--inspect: no change made.")
        return 0

    # Modify one byte and write the load file.
    payload[off] = old ^ 0x01
    new = payload[off]
    mod = bytearray(orig)
    mod[PAYLOAD_OFF + off] = new
    mod_path = os.path.join(a.cf_dir, f"{S_MOD}.tbl")
    open(mod_path, "wb").write(mod)
    print(f"  wrote {mod_path}: byte {off} 0x{old:02X} -> 0x{new:02X}\n")

    if not a.dry_run:
        t.send(f"LOAD /cf/{S_MOD}.tbl", load_cmd(f"/cf/{S_MOD}.tbl"))
        t.send(f"VALIDATE INACTIVE {a.table}", validate_cmd(a.table, active=False))
        t.send(f"ACTIVATE {a.table}", activate_cmd(a.table))

    after_path = t.dump(a.table, S_AFTER, active=True)
    _, after = parse_dump(after_path)
    ap = after[PAYLOAD_OFF:PAYLOAD_OFF + numbytes]

    diffs = [i for i in range(numbytes) if ap[i] != orig[PAYLOAD_OFF + i]]
    ok = diffs == [off] and ap[off] == new
    print("\n" + "=" * 60)
    if ok:
        print(f"PASS: active image changed at exactly payload byte {off} "
              f"(0x{old:02X} -> 0x{ap[off]:02X}). LOAD+ACTIVATE modified the "
              f"live table.")
    elif not diffs:
        print("NO CHANGE: active image is unchanged. The modified image was most "
              "likely rejected by the table's VALIDATE function — try --offset in "
              "a different (data) field, or a different --table.")
    else:
        print(f"UNEXPECTED: active image differs at offsets {diffs[:8]}"
              f"{'...' if len(diffs) > 8 else ''} (expected only [{off}]).")
    print("=" * 60)

    if ok and not a.no_restore and not a.dry_run:
        print("\nRestoring original image...")
        t.send(f"LOAD /cf/{S_ORIG}.tbl", load_cmd(f"/cf/{S_ORIG}.tbl"))
        t.send(f"VALIDATE INACTIVE {a.table}", validate_cmd(a.table, active=False))
        t.send(f"ACTIVATE {a.table}", activate_cmd(a.table))
        rpath = t.dump(a.table, S_REST, active=True)
        _, restored = parse_dump(rpath)
        same = restored[PAYLOAD_OFF:PAYLOAD_OFF + numbytes] == orig[PAYLOAD_OFF:PAYLOAD_OFF + numbytes]
        print("Restore verified: active image byte-identical to original."
              if same else "⚠ Restore MISMATCH — inspect manually.")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
