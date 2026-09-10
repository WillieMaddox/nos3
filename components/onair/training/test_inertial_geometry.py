#!/usr/bin/env python3
"""Tests for the AINOS3-86 INERTIAL pointing geometry.

These guard the two things that were actually wrong, not the arithmetic:

  1. **The quaternion convention.** 42 builds `CN` (inertial -> body) via
     `Q2C(qn, CN)`. Getting that backwards flips the boresight-to-nadir angle
     from 63 deg (blinded) to 88 deg (clear) — i.e. it inverts the verdict while
     still looking plausible. The convention is pinned here against 42's own
     published `svb`.
  2. **The target being the ORBIT NORMAL.** Any fixed attitude that is not
     perpendicular to nadir is Earth-blinded for part of every orbit; the whole
     fix is that the orbit normal never is.
"""
import math
import os
import sys

import pytest

# ⚠ scenarios/cmd.py SHADOWS the stdlib `cmd` module. Under pytest the stdlib one
# is often already in sys.modules, so a plain `from cmd import ...` silently
# resolves to /usr/lib/python3.x/cmd.py. Load it by path, under its own name.
import importlib.util  # noqa: E402

_CMD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios", "cmd.py")
_spec = importlib.util.spec_from_file_location("nos3_scenario_cmd", _CMD_PATH)
_cmd = importlib.util.module_from_spec(_spec)
sys.modules["nos3_scenario_cmd"] = _cmd
_spec.loader.exec_module(_cmd)

orbit_normal_from_config = _cmd.orbit_normal_from_config
quat_boresight_to = _cmd.quat_boresight_to
quat_inertial_hold_target = _cmd.quat_inertial_hold_target

R_E = 6378137.0

# 42 truth telemetry captured 2026-09-10 — position/attitude and, crucially,
# 42's OWN sun-vector-in-body, which is what pins the convention.
TRUTH_POS = (-3774662.0, -3460386.0, 4429093.0)
TRUTH_VEL = (6378.0, -2631.0, 3368.0)
TRUTH_QN = (-0.116, 0.930, -0.301, 0.179)
TRUTH_SVB = (0.991, -0.131, 0.002)


def dcm_from_q(q):
    """Must match 42's Q2C (dcmkit.c:70): maps inertial -> body."""
    q1, q2, q3, q4 = q
    return [
        [q1*q1 - q2*q2 - q3*q3 + q4*q4, 2*(q1*q2 + q3*q4), 2*(q1*q3 - q2*q4)],
        [2*(q1*q2 - q3*q4), -q1*q1 + q2*q2 - q3*q3 + q4*q4, 2*(q2*q3 + q1*q4)],
        [2*(q1*q3 + q2*q4), 2*(q2*q3 - q1*q4), -q1*q1 - q2*q2 + q3*q3 + q4*q4],
    ]


def mxv(M, v):
    return tuple(sum(M[i][j] * v[j] for j in range(3)) for i in range(3))


def unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])


def angle_deg(a, b):
    d = sum(x * y for x, y in zip(unit(a), unit(b)))
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


def sun_eci(y, mo, d, hh, mi, s):
    """Low-precision solar direction, ~0.01 deg — ample against a 30 deg cone."""
    yy, mm = (y - 1, mo + 12) if mo <= 2 else (y, mo)
    A = yy // 100
    B = 2 - A + A // 4
    jd = (int(365.25 * (yy + 4716)) + int(30.6001 * (mm + 1)) + d + B - 1524.5
          + (hh + mi / 60 + s / 3600) / 24)
    n = jd - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439)
    return (math.cos(lam), math.cos(eps) * math.sin(lam), math.sin(eps) * math.sin(lam))


# ── 1. the convention ────────────────────────────────────────────────────────

def test_quaternion_convention_reproduces_42_published_svb():
    """The anchor: our DCM must turn 42's qn + the true sun direction into 42's svb.

    If this drifts, every angle downstream is silently wrong.
    """
    CN = dcm_from_q(TRUTH_QN)
    computed = unit(mxv(CN, sun_eci(2025, 10, 20, 17, 57, 46)))
    assert angle_deg(computed, TRUTH_SVB) < 0.5


def test_opposite_convention_is_badly_wrong():
    """Guards against 'simplifying' the transpose away — it is a 40 deg error."""
    CN = dcm_from_q(TRUTH_QN)
    CNT = [[CN[j][i] for j in range(3)] for i in range(3)]
    computed = unit(mxv(CNT, sun_eci(2025, 10, 20, 17, 57, 46)))
    assert angle_deg(computed, TRUTH_SVB) > 10.0


# ── 2. the diagnosis ─────────────────────────────────────────────────────────

def test_the_attitude_we_actually_held_was_earth_occulted():
    """Reproduces the root cause: 63 deg from nadir, inside the 80.4 deg cone."""
    orbrad = math.sqrt(sum(c * c for c in TRUTH_POS))
    limb = math.degrees(math.asin(R_E / orbrad))
    nadir_n = tuple(-c / orbrad for c in TRUTH_POS)
    a = angle_deg((0, 0, 1), mxv(dcm_from_q(TRUTH_QN), nadir_n))
    assert a == pytest.approx(63.0, abs=1.0)
    assert a < limb + 10.0        # 42 clears ST->Valid


# ── 3. the fix ───────────────────────────────────────────────────────────────

def test_orbit_normal_matches_the_truth_state_vector():
    """Config-derived normal must agree with r x v from 42's own ECI telemetry."""
    from_config = orbit_normal_from_config()
    from_truth = unit(cross(TRUTH_POS, TRUTH_VEL))
    assert angle_deg(from_config, from_truth) < 0.1


def test_target_attitude_puts_the_boresight_on_the_orbit_normal():
    q = quat_inertial_hold_target()
    CN = dcm_from_q(q)
    boresight_eci = (CN[2][0], CN[2][1], CN[2][2])   # +Z body, as a row of CN
    assert angle_deg(boresight_eci, orbit_normal_from_config()) < 0.01


def test_orbit_normal_target_is_never_earth_blinded_over_a_full_orbit():
    """The property the fix rests on: 90 deg from nadir at EVERY point in the orbit."""
    q = quat_inertial_hold_target()
    CN = dcm_from_q(q)
    orbrad = math.sqrt(sum(c * c for c in TRUTH_POS))
    limb = math.degrees(math.asin(R_E / orbrad))
    u = unit(TRUTH_POS)
    w = unit(cross(cross(TRUTH_POS, TRUTH_VEL), TRUTH_POS))
    worst = 180.0
    for k in range(0, 360, 5):
        th = math.radians(k)
        r_t = tuple(orbrad * (math.cos(th) * u[i] + math.sin(th) * w[i]) for i in range(3))
        a = angle_deg((0, 0, 1), mxv(CN, tuple(-c / orbrad for c in r_t)))
        worst = min(worst, a)
    assert worst == pytest.approx(90.0, abs=1.0)
    assert worst > limb + 10.0


def test_identity_target_IS_blinded_for_part_of_the_orbit():
    """The contrast that justifies the change — identity is not a safe target."""
    CN = dcm_from_q((0.0, 0.0, 0.0, 1.0))
    orbrad = math.sqrt(sum(c * c for c in TRUTH_POS))
    limb = math.degrees(math.asin(R_E / orbrad))
    u = unit(TRUTH_POS)
    w = unit(cross(cross(TRUTH_POS, TRUTH_VEL), TRUTH_POS))
    blinded = 0
    for k in range(0, 360, 5):
        th = math.radians(k)
        r_t = tuple(orbrad * (math.cos(th) * u[i] + math.sin(th) * w[i]) for i in range(3))
        if angle_deg((0, 0, 1), mxv(CN, tuple(-c / orbrad for c in r_t))) < limb + 10.0:
            blinded += 1
    assert blinded > 0


def test_boresight_helper_handles_a_reference_parallel_to_the_target():
    """Degenerate case: ref along the boresight must not produce a NaN attitude."""
    q = quat_boresight_to((1.0, 0.0, 0.0), ref=(1.0, 0.0, 0.0))
    assert all(math.isfinite(c) for c in q)
    assert math.sqrt(sum(c * c for c in q)) == pytest.approx(1.0, abs=1e-9)
    CN = dcm_from_q(q)
    assert angle_deg((CN[2][0], CN[2][1], CN[2][2]), (1.0, 0.0, 0.0)) < 0.01
