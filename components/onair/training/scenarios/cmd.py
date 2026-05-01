"""Minimal UDP CCSDS commander for nominal scenarios.

Extracted from the kill-chain pattern in `gsw/attack_scripts/sparta/execution/
demo_gnc_kill_chain.py` so scenario scripts can issue commands without pulling
in attack-specific code.

NOS3 has zero command authentication: any well-formed CCSDS packet sent to
nos-fsw:5012 is accepted (this is also the premise the anomaly detector is
trying to compensate for). So a vanilla `socket.sendto` is the entire
transport.
"""

from __future__ import annotations

import socket
import struct
import time

# ── Subsystem command MIDs (verified from COSMOS target definitions) ──
ADCS_CMD_MID = 0x1940
ADCS_HK_REQ_MID = 0x1941
RW_CMD_MID = 0x1992
TORQUER_CMD_MID = 0x193A
TORQUER_HK_REQ_MID = 0x193B
THRUSTER_CMD_MID = 0x18EA
THRUSTER_HK_REQ_MID = 0x18EB
CSS_CMD_MID = 0x1910
CSS_HK_REQ_MID = 0x1911
FSS_CMD_MID = 0x1920
FSS_HK_REQ_MID = 0x1921
IMU_CMD_MID = 0x1925
IMU_HK_REQ_MID = 0x1926
MAG_CMD_MID = 0x192A
MAG_HK_REQ_MID = 0x192B
ST_CMD_MID = 0x1935
ST_HK_REQ_MID = 0x1936
GPS_CMD_MID = 0x1870
GPS_HK_REQ_MID = 0x1871
EPS_CMD_MID = 0x191A
EPS_HK_REQ_MID = 0x191B
RADIO_CMD_MID = 0x1930
RADIO_HK_REQ_MID = 0x1931

# ── Generic function codes (every component has these) ──
FC_NOOP = 0
FC_RST_COUNTERS = 1
FC_REQ_HK = 0  # for *_HK_REQ_MID packets

# ── Subsystem-specific function codes ──
ADCS_FC_SET_MODE = 2
ADCS_MODE_PASSIVE = 0
ADCS_MODE_BDOT = 1
ADCS_MODE_SUNSAFE = 2
ADCS_MODE_INERTIAL = 3

THR_FC_ENABLE = 2
THR_FC_DISABLE = 3
THR_FC_PERCENTAGE = 4

EPS_FC_SWITCH = 2
EPS_STATE_OFF = 0x00
EPS_STATE_ON = 0xAA

RADIO_FC_CONFIG = 2


def build_ccsds_cmd(mid: int, fc: int, payload: bytes = b"") -> bytes:
    """Build a CCSDS-1.0 command packet: 6-byte primary header + 2-byte secondary + payload."""
    sec_hdr = struct.pack("BB", fc, 0)  # FC + checksum (unused, zero)
    data = sec_hdr + payload
    primary = struct.pack(">HHH", mid, 0xC000, len(data) - 1)
    return primary + data


class Commander:
    """Sends CCSDS commands over UDP to nos-fsw and logs each one for the manifest."""

    def __init__(self, fsw_host: str, fsw_cmd_port: int = 5012, dry_run: bool = False):
        self.fsw_host = fsw_host
        self.fsw_cmd_port = fsw_cmd_port
        self.dry_run = dry_run
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log: list[dict] = []

    def send(self, description: str, mid: int, fc: int, payload: bytes = b"",
             post_delay: float = 0.2) -> None:
        pkt = build_ccsds_cmd(mid, fc, payload)
        entry = {
            "description": description,
            "mid_hex": f"0x{mid:04X}",
            "fc": fc,
            "pkt_len": len(pkt),
        }
        if not self.dry_run:
            try:
                self.sock.sendto(pkt, (self.fsw_host, self.fsw_cmd_port))
            except OSError as e:
                entry["error"] = str(e)
        else:
            entry["dry_run"] = True
        self.log.append(entry)
        if post_delay:
            time.sleep(post_delay)

    def noop(self, mid: int, name: str) -> None:
        self.send(f"NOOP {name}", mid, FC_NOOP)

    def req_hk(self, hk_mid: int, name: str) -> None:
        self.send(f"REQ_HK {name}", hk_mid, FC_REQ_HK)

    def adcs_set_mode(self, mode: int) -> None:
        names = {0: "PASSIVE", 1: "BDOT", 2: "SUNSAFE", 3: "INERTIAL"}
        payload = struct.pack("B", mode)
        self.send(f"ADCS SET_MODE {names.get(mode, mode)}", ADCS_CMD_MID, ADCS_FC_SET_MODE, payload)

    def thruster_pct(self, pct: int) -> None:
        """Fire thruster at given duty cycle (0-100). Note: long-form payload depends on
        thruster sim ICD; here we send a 1-byte percent which matches the basic THR_FC_PERCENTAGE.
        """
        payload = struct.pack("B", max(0, min(100, pct)))
        self.send(f"THRUSTER PERCENTAGE {pct}", THRUSTER_CMD_MID, THR_FC_PERCENTAGE, payload)

    def thruster_enable(self, enable: bool) -> None:
        fc = THR_FC_ENABLE if enable else THR_FC_DISABLE
        self.send(f"THRUSTER {'ENABLE' if enable else 'DISABLE'}", THRUSTER_CMD_MID, fc)

    def eps_switch(self, switch_num: int, on: bool) -> None:
        state = EPS_STATE_ON if on else EPS_STATE_OFF
        payload = struct.pack("BB", switch_num, state)
        self.send(f"EPS SWITCH {switch_num} {'ON' if on else 'OFF'}",
                  EPS_CMD_MID, EPS_FC_SWITCH, payload)

    def radio_config(self, cfg: int) -> None:
        payload = struct.pack(">I", cfg)
        self.send(f"RADIO CONFIG 0x{cfg:08X}", RADIO_CMD_MID, RADIO_FC_CONFIG, payload)
