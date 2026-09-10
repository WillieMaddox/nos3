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
import os
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

# AINOS3-86: INERTIAL pointing takes a commanded target attitude. Until now NO
# scenario tooling ever sent it, so every INERTIAL soak we have run held the
# mode with whatever `qbn_cmd` the app booted with — a candidate cause of the
# 33.6% nominal false-alarm rate (sustained control effort toward a default
# attitude is dynamics that legitimately look anomalous).
ADCS_FC_INERTIAL_QUATERNION = 9

# Body-to-inertial identity: body frame aligned with the inertial frame. A
# well-defined target the controller can actually converge to, and the same
# value the COSMOS lib uses (generic_adcs_lib.rb:96).
ADCS_QUAT_IDENTITY = (0.0, 0.0, 0.0, 1.0)

# ── AINOS3-86: why identity is the WRONG target, and what the right one is ────
#
# Commanding the star tracker on is not enough to close the INERTIAL loop, and
# neither is commanding *some* target attitude. `AC_inertial()` is gated on
# `qValid`, which traces to 42's `ST->Valid`, which 42 clears whenever the ST
# boresight falls inside an exclusion cone (`42sensors.c:304-342`):
#
#     Sun   : blinded within 30 deg of the sun vector
#     Earth : blinded within (limb half-angle + 10 deg) of NADIR
#     Moon  : blinded within 10 deg of the moon vector
#
# NOS3 flies at ~392 km, so the limb half-angle is 70.4 deg and the Earth cone is
# **80.4 deg wide about nadir** (`SC_NOS3.txt:248-257` gives 1 ST, +Z boresight,
# 8x8 deg FOV). That cone is the whole problem: at any FIXED inertial attitude
# the nadir direction sweeps a full circle in the body frame once per ~92 min
# orbit, so the boresight drops inside the cone for a large part of every orbit.
# Measured against 42's own truth telemetry for the attitude we actually held:
# blinded for ~40 % of the orbit, in one unbroken ~35-minute stretch.
#
# That is why a 300 s `single_mode_hold_INERTIAL` looked like it had "no closed
# loop" on 2026-09-10 (0/723 frames valid — it landed inside the blind stretch)
# and like it had an intermittent one on 2026-08-25 (56/80 — it caught an edge).
# Neither was a detector or a controller problem. Identity is simply an arbitrary
# attitude with no relationship to the orbit, so it inherits that duty cycle.
#
# THE FIX: point the boresight along the ORBIT NORMAL. The nadir vector is
# perpendicular to the orbit normal by construction and stays that way for the
# whole orbit, so boresight-to-nadir is pinned at 90 deg -- a permanent 9.6 deg
# margin outside the 80.4 deg Earth cone, every orbit, forever. The sun margin
# comes free from the beta angle (90 - |beta|); NOS3's orbit gives 116.6 deg
# against a 30 deg cone.
#
# ⚠ The target is ORBIT-DEPENDENT, so it is DERIVED at runtime from the live
# state vector rather than hardcoded -- a TLE change would silently invalidate a
# baked-in constant, which is exactly the class of stale-config bug that made
# this ticket expensive in the first place.


def quat_boresight_to(vec_eci, ref=(1.0, 0.0, 0.0)):
    """Build `qbn` placing the ST boresight (body +Z) along `vec_eci`.

    Returns (q1, q2, q3, q4) with q4 real -- the wire order that
    `adcs_set_inertial_quaternion` expects and that 42 writes.

    The rotation about the boresight is a free parameter; we fix it by putting
    body +X along the component of `ref` perpendicular to the boresight, so the
    result is deterministic and reproducible rather than arbitrary.

    Convention, verified rather than assumed (AINOS3-86, 2026-09-10): 42 builds
    its body-from-inertial DCM as `Q2C(S->B[0].qn, S->B[0].CN)`
    (`42dynamics.c:190`, `dcmkit.c:70`), so `CN` maps N -> B and the body axes
    are the ROWS of `CN` expressed in N. Reconstructing 42's own published `svb`
    through this convention reproduces it to **0.05 deg**; the opposite
    convention is off by 40 deg. That check is what makes the geometry below
    trustworthy -- do not "simplify" it away.
    """
    import math

    def _norm(v):
        n = math.sqrt(sum(c * c for c in v))
        if n == 0.0:
            raise ValueError("cannot build an attitude from a zero vector")
        return tuple(c / n for c in v)

    def _dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def _cross(a, b):
        return (a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    zb = _norm(vec_eci)
    if abs(_dot(ref, zb)) > 0.95:            # ref nearly parallel: pick another
        ref = (0.0, 1.0, 0.0)
    xb = _norm(tuple(ref[i] - _dot(ref, zb) * zb[i] for i in range(3)))
    yb = _cross(zb, xb)

    CN = [list(xb), list(yb), list(zb)]      # rows = body axes in N
    tr = CN[0][0] + CN[1][1] + CN[2][2]
    if tr > 0.0:
        sc = math.sqrt(tr + 1.0) * 2.0
        q4 = 0.25 * sc
        q1 = (CN[1][2] - CN[2][1]) / sc
        q2 = (CN[2][0] - CN[0][2]) / sc
        q3 = (CN[0][1] - CN[1][0]) / sc
    else:
        i = max(range(3), key=lambda k: CN[k][k])
        j, k = (i + 1) % 3, (i + 2) % 3
        sc = math.sqrt(1.0 + CN[i][i] - CN[j][j] - CN[k][k]) * 2.0
        qv = [0.0, 0.0, 0.0]
        qv[i] = 0.25 * sc
        qv[j] = (CN[j][i] + CN[i][j]) / sc
        qv[k] = (CN[k][i] + CN[i][k]) / sc
        q4 = (CN[j][k] - CN[k][j]) / sc
        q1, q2, q3 = qv
    n = math.sqrt(q1 * q1 + q2 * q2 + q3 * q3 + q4 * q4)
    return (q1 / n, q2 / n, q3 / n, q4 / n)


NOS3_42_INOUT = os.path.expanduser("~/.nos3/42/NOS3InOut")


def orbit_normal_from_config(inout_dir=NOS3_42_INOUT):
    """The ECI orbit normal, read from 42's mission configuration.

    Returns a unit 3-tuple in the same inertial frame the FSW's `qbn` uses.

    ⚠ Why config and not telemetry. The obvious route is the NOVATEL state
    vector, but that is ECEF and converting it to ECI needs absolute UTC, which
    the recorded telemetry cannot supply: `NOVATEL.Novatel_oem615.Weeks` is a
    **rollover-truncated** GPS week (the sim carries the rollover count in a
    separate field taken from 42's `SC[0].GPS[0].Rollover`, which we do not
    subscribe). Reading 341 as an absolute week places the epoch in 1986 instead
    of 2025 and rotates the derived normal by ~90 deg -- measured, not feared, on
    2026-09-10. Guessing the rollover would be a silent-failure mode of exactly
    the kind this ticket exists to remove.

    The orbit plane, meanwhile, is a **mission parameter**, not a measurement:
    42 propagates from the Keplerian elements in `Orb_LEO.txt`. Inclination and
    RAAN give the normal in closed form, exactly, with no time conversion:

        h = ( sin(i) sin(RAAN), -sin(i) cos(RAAN), cos(i) )

    Cross-checked against 42's own truth stream (r x v from the published ECI
    state vector): agreement to **0.03 deg**.

    ⚠ RAAN precesses ~5 deg/day at this altitude, which moves the normal by the
    same amount. Irrelevant over a collection run against a 9.6 deg margin, but
    re-derive rather than cache if a run ever spans days.
    """
    import math

    orb_file = None
    sim_inp = os.path.join(inout_dir, "Inp_Sim.txt")
    with open(sim_inp) as f:
        for line in f:
            if "Input file name for Orb 0" in line:
                orb_file = line.split("!")[0].split()[-1].strip()
                break
    if not orb_file:
        raise RuntimeError(f"could not find the Orb 0 input file name in {sim_inp}")

    inc = raan = None
    with open(os.path.join(inout_dir, orb_file)) as f:
        for line in f:
            if "!" not in line:
                continue
            value, _, comment = line.partition("!")
            c = comment.lower()
            if "inclination" in c:
                inc = float(value.split()[0])
            elif "right ascension of ascending node" in c:
                raan = float(value.split()[0])
    if inc is None or raan is None:
        raise RuntimeError(f"could not parse inclination/RAAN from {orb_file}")

    i, o = math.radians(inc), math.radians(raan)
    return (math.sin(i) * math.sin(o), -math.sin(i) * math.cos(o), math.cos(i))


def quat_inertial_hold_target(inout_dir=NOS3_42_INOUT):
    """The INERTIAL target attitude that keeps the star tracker usable.

    Boresight (+Z body) on the orbit normal -> nadir stays 90 deg away for the
    whole orbit, so 42 never trips the Earth exclusion. See the block comment
    above `quat_boresight_to` for why any other fixed attitude is blinded for a
    large part of every orbit.
    """
    return quat_boresight_to(orbit_normal_from_config(inout_dir))


def quat_orbit_normal(pos_eci, vel_eci):
    """The INERTIAL target that keeps the star tracker permanently unblinded.

    `pos_eci`/`vel_eci` in metres and m/s. The orbit normal is r x v.
    """
    h = (pos_eci[1] * vel_eci[2] - pos_eci[2] * vel_eci[1],
         pos_eci[2] * vel_eci[0] - pos_eci[0] * vel_eci[2],
         pos_eci[0] * vel_eci[1] - pos_eci[1] * vel_eci[0])
    return quat_boresight_to(h)

THR_FC_ENABLE = 2
THR_FC_DISABLE = 3
THR_FC_PERCENTAGE = 4

EPS_FC_SWITCH = 2
EPS_STATE_OFF = 0x00
EPS_STATE_ON = 0xAA

RADIO_FC_CONFIG = 2

# AINOS3-86: the star tracker boots DISABLED and nothing ever enabled it, so it
# never published device telemetry. That matters far beyond a missing field:
# `AC_inertial()` is gated on `GNC->qValid` (generic_adcs_adac.c:338), which
# traces to the ST valid flag — so INERTIAL mode performed NO closed-loop
# pointing in any data collected before 2026-08-23. Enable it before any
# INERTIAL work. Also the root cause of AINOS3-91's corpus-wide inert ST_DEV
# fields.
ST_FC_ENABLE = 2
ST_FC_DISABLE = 3


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

    def st_enable(self, enable: bool = True) -> None:
        """Enable (or disable) the star tracker device.

        Required for INERTIAL: with the ST disabled the ADCS app sees
        `St.valid == 0`, so `qValid == 0` and the inertial control law never
        executes — the torque command freezes at whatever the previous mode left
        and the vehicle drifts uncontrolled while still reporting Mode 3.
        """
        fc = ST_FC_ENABLE if enable else ST_FC_DISABLE
        self.send(f"ST {'ENABLE' if enable else 'DISABLE'}", ST_CMD_MID, fc)

    def adcs_set_inertial_quaternion(self, q=ADCS_QUAT_IDENTITY) -> None:
        """Command the INERTIAL-mode target attitude (`GENERIC_ADCS_INERTIAL_QUATERNION_CC`).

        Wire format from `Generic_ADCS_Quat_cmd_t` (generic_adcs_msg.h:53) — a
        packed struct of the 8-byte command header plus `double qbn[4]`, so the
        payload is four LITTLE-endian float64s, 32 bytes, total packet 40. The
        CCSDS primary header stays big-endian as everywhere else; only the
        doubles are little (matching GENERIC_ADCS_CMD.txt, which tags each
        quaternion parameter LITTLE_ENDIAN inside a BIG_ENDIAN command).

        `q` is (q1, q2, q3, q4) with q4 the real part.
        """
        if len(q) != 4:
            raise ValueError(f"quaternion needs 4 components, got {len(q)}")
        norm = sum(c * c for c in q) ** 0.5
        if abs(norm - 1.0) > 1e-6:
            raise ValueError(f"quaternion {q} is not unit-norm (|q|={norm:.6f}); "
                             "the controller expects a normalised attitude")
        payload = struct.pack("<4d", *(float(c) for c in q))
        self.send(f"ADCS INERTIAL_QUATERNION {q}", ADCS_CMD_MID,
                  ADCS_FC_INERTIAL_QUATERNION, payload)

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
