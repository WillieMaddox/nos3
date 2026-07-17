# NOS3 Security Telemetry Log Reference

This document describes the CSV log files produced by the OnAIR anomaly-detection
pipeline running against NOS3 (NASA Operational Simulator for Small Satellites).
It covers the attack surface categories monitored, why each matters, which CSV
columns carry the relevant signals, how values are encoded, and how missing data
is represented.

---

## Table of Contents

1. [Logging Pipeline Overview](#1-logging-pipeline-overview)

2. [CSV Structure and Column Ordering](#2-csv-structure-and-column-ordering)

3. [Value Types and Encoding](#3-value-types-and-encoding)

4. [Missing and Stale Data](#4-missing-and-stale-data)

5. [Attack Surface Categories and Threats](#5-attack-surface-categories-and-threats)

   - [5.1 Unauthorized Software Execution](#51-unauthorized-software-execution--cdh)

   - [5.2 Event Suppression and Flooding](#52-event-suppression-and-flooding--cdh)

   - [5.3 Software Bus Attacks](#53-software-bus-attacks--cdh)

   - [5.4 Table Injection](#54-table-injection--cdh)

   - [5.5 Time Manipulation](#55-time-manipulation--cdh)

   - [5.6 Stored Command Injection](#56-stored-command-injection--cdh)

   - [5.7 Schedule Disruption](#57-schedule-disruption--cdh)

   - [5.8 GPS Spoofing](#58-gps-spoofing--gnc)

   - [5.9 ADCS Hijack and Actuator Bypass](#59-adcs-hijack-and-actuator-bypass--gnc)

   - [5.10 Sensor Spoofing](#510-sensor-spoofing--gnc)

   - [5.11 Orbit Modification](#511-orbit-modification--gnc)

   - [5.12 Power System Attack](#512-power-system-attack--power)

   - [5.13 Communications Attack](#513-communications-attack--comm)

6. [Full Column Reference by Subsystem](#6-full-column-reference-by-subsystem)

---

## 1. Logging Pipeline Overview

```
cFS Software Bus (SBN TCP peer)
        │
        │  Telemetry MIDs 0x08xx subscribed at startup
        ▼
  sbn_client.so  ←── C shared library
        │
        │  recv_msg() blocking call
        ▼
  sbn_adapter.py / message_listener_thread()
        │
        │  ctypes struct overlay → field extraction
        ▼
  get_current_data()   (double-buffered)
        │
        │  OnAIR sim loop calls get_next() each frame
        ▼
  KnowledgeRepPluginDict  →  CSV writer
        │
        ▼
  csv_out_<HH>_<MM>_<SS>.csv
```

Key implementation details:

- **Double buffer**: two copies of `currentData` alternate as "write" and "read"
  buffers. `get_next()` swaps them. Data persists in the read buffer until a new
  packet arrives for that MID.

- **Blocking recv**: the listener thread blocks on `sbn.recv_msg()`. Each received
  packet updates only the fields belonging to that packet's MID; all other columns
  retain their previous value.

- **Frame rate**: OnAIR's sim loop drives the CSV write rate. Each row is one frame.
  Multiple SBN packets may arrive between frames, but only the most recent value per
  MID is written per row.

---

## 2. CSV Structure and Column Ordering

Each CSV row is one OnAIR frame. The first row is the header row containing column
names exactly as listed in the `"order"` array of `nos3_security_tlm.json`.

Column names follow the pattern: `<APP_NAME>.<field>.<subfield>...`

The column order is determined by the `"order"` array in `nos3_security_tlm.json`
and matches the `channels` dict insertion order. The subsystem groupings used for
anomaly-detection training (`CDH`, `GNC`, `POWER`, `COMM`) are declared in the
`"subsystems"` section but do **not** change column order.

Subsystem groups in the log (in order of appearance):

| Group  | Columns (approx.) | Coverage |
|--------|-------------------|----------|
| CDH    | 1–155             | cFS core services, SC, SCH |
| GNC    | 156–260           | GPS, ADCS, RW, THRUSTER |
| POWER  | 261–282           | EPS bus voltages, switches |
| COMM   | 283–295           | Radio, SBN peer state |

---

## 3. Value Types and Encoding

### 3.1 Scalar Fields

Scalar fields (`uint8`, `uint16`, `uint32`, `int16`, `int32`, `float`, `double`)
are stored as their Python string representation.

| C type      | Python type  | Example CSV cell |
|-------------|--------------|------------------|
| `c_uint8`   | `str(int)`   | `3`              |
| `c_uint16`  | `str(int)`   | `1024`           |
| `c_uint32`  | `str(int)`   | `2097152`        |
| `c_int16`   | `str(int)`   | `-37`            |
| `c_float`   | `str(float)` | `51.423`         |
| `c_double`  | `str(float)` | `6.378137e+06`   |

Byte-string fields (`c_char * N`) are stored as their Python bytes repr:
`b'CFE_EVS\x00...'`. Trailing null bytes are present up to the declared length.

### 3.2 One-Dimensional Arrays

A 1D ctypes array (`c_double * 3`, `c_uint16 * 4`, etc.) is serialised as a flat
Python list. The cell value is the `repr()` of that list.

```
c_double * 3  →  [x, y, z]
```

**Example — `ADCS_GNC.wbn` (body angular rate, rad/s):**
```
[0.0012, -0.0003, 0.0007]
```

**Example — `SC.RtsExecutingStatus` (64-RTS bitmap as 4 × uint16):**
```
[0, 0, 0, 0]
```
Each element is a 16-bit word. Bit N of word W is set if RTS `W*16 + N` is
currently executing.

**Example — `CFE_ES.PerfFilterMask` (4 × uint32, covers 128 perf IDs):**
```
[4294967295, 4294967295, 4294967295, 4294967295]
```

### 3.3 Two-Dimensional Arrays (Array of Arrays)

A 2D ctypes array (`(c_double * 3) * 3`) is serialised as a list of lists.

```
(c_double * 3) * 3  →  [[r0c0, r0c1, r0c2],
                         [r1c0, r1c1, r1c2],
                         [r2c0, r2c1, r2c2]]
```

**Fields in this category:**

| Column | Shape | Meaning |
|--------|-------|---------|
| `ADCS_DO.Rw.axis` | 3 × 3 | Reaction-wheel spin-axis unit vectors (one row per wheel) |
| `ADCS_DI.Payload.Rw.whl_axis` | 3 × 3 | Same, from the data-input layer |

**Example — identity-matrix (wheels aligned with body axes):**
```
[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
```

### 3.4 Arrays of Structs

An array of structs is serialised as a list of lists, where each inner list
contains the struct's field values in declaration order.

**`CFE_EVS_HK.AppData`** — array of 16 × `CFE_EVS_AppTlmData_t`:
```
[[AppID, AppMessageSentCounter, AppEnableStatus, AppMessageSquelchedCounter],
 [...],
 ... × 16]
```
Concrete example (app 0 enabled, 42 messages sent, 0 squelched):
```
[[0, 42, 1, 0], [1, 7, 1, 0], [2, 0, 1, 0], ...]
```

**`EPS.DeviceHK.Switch`** — array of 8 × `GENERIC_EPS_Switch_tlm_t`:
```
[[Voltage0, Current0, Status0],
 [Voltage1, Current1, Status1],
 ... × 8]
```
All values are raw ADC counts (`uint16`). `Status` is `1` = on, `0` = off.

**`ADCS_DI.Payload.Css.Sensor`** — array of 6 × `Generic_ADCS_DI_Css_Sensor_Payload_t`:
```
[[ax, ay, az, scale, percenton],   ← sensor 0
 ...                               ← sensors 1–5]
```
Each inner list: `axis` (3 floats), `scale` (float), `percenton` (float in 0–100).

**`CFE_SB_SUBS.Entry`** — array of 20 × `CFE_SB_SubEntries_t`:
```
[[MsgId0, [Qos0a, Qos0b], PipeId0, Spare0],
 ... × 20]
```

### 3.5 Quaternions

Quaternions are stored as 1D arrays of 4 doubles: `[q1, q2, q3, q4]`.
The convention used by Generic ADCS is `[x, y, z, w]` (scalar last).
A unit quaternion representing no rotation is `[0.0, 0.0, 0.0, 1.0]`.

**Fields using quaternions:**

| Column | Represents |
|--------|------------|
| `ADCS_GNC.qbn` | Body-to-inertial attitude estimate |
| `ADCS_GNC.qErr` | Attitude error quaternion |
| `ADCS_DO.Trq.qba` | Torquer actuator output quaternion |
| `ADCS_DI.Payload.*.qbs` | Body-to-sensor mounting quaternion |
| `ADCS_DI.Payload.St.q` | Star tracker inertial attitude |

### 3.6 Bitmask Fields

Several fields are bitmasks encoded as integers.

| Column | Bit meaning |
|--------|-------------|
| `CFE_TIME.ClockStateFlags` | Bit 0: time-set; bit 1: flywheel; bit 2: clock-set |
| `CFE_EVS_HK.OutputPort` | Bits 0–3: output ports enabled (UART, SysLog, etc.) |
| `SC.RtsExecutingStatus` | 4 × uint16; bit N of word W → RTS W×16+N is running |
| `SC.RtsDisabledStatus` | Same layout; bit set → that RTS is disabled |

---

## 4. Missing and Stale Data

### 4.1 Pre-receive (never received)

All data cells are initialised to `[0]` before any packet arrives. If a MID has
not been received since startup, every column for that MID shows `[0]`.

### 4.2 Stale data

The double-buffer does **not** clear old values when swapped. If telemetry for a
given MID stops arriving (e.g., that app crashed or the SBN link dropped), the CSV
continues to show the **last received value** indefinitely.

A sustained freeze across multiple rows while other MIDs continue updating is
itself an anomaly signal (app death, link loss, or rate-change attack).

### 4.3 Byte-string fields when empty

`c_char * N` fields initialised to zero appear as `b'\x00\x00...'` (all null
bytes). A non-null value indicates the field has been populated. Trailing nulls
after meaningful content are normal.

---

## 5. Attack Surface Categories and Threats

### 5.1 Unauthorized Software Execution — CDH

**Why it matters:** cFS allows apps to be loaded and started at runtime via ground
command. An attacker who can inject commands can install a persistent malicious app
that survives processor resets. A firmware-level attacker can modify the cFE core
binary itself.

**Source packets:** `CFE_ES` (0x0800)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `CFE_ES.RegisteredExternalApps` | Constant after init | Any change mid-mission |
| `CFE_ES.RegisteredTasks` | Constant after init | Unexpected increase |
| `CFE_ES.ProcessorResets` | 0 or low / monotonically non-decreasing | Sudden increment = crash/exploit |
| `CFE_ES.CFECoreChecksum` | Fixed after boot | Any change = firmware tamper |
| `CFE_ES.HeapBytesFree` | Stable oscillation | Monotonic drain = memory-exhaustion attack |
| `CFE_ES.ERLogEntries` | 0 or stable | Spike = exceptions being thrown |

---

### 5.2 Event Suppression and Flooding — CDH

**Why it matters:** The cFS Event Services (EVS) system is the primary runtime
diagnostic log. An attacker who can disable event output for a targeted app can
perform other attack steps in silence. Conversely, an attacker can flood the event
log to exhaust it (filling the fixed-size ring buffer) before executing the main
attack, ensuring the attack activity is never logged.

**Source packets:** `CFE_EVS` (0x0808) — per-event, `CFE_EVS_HK` (0x0801) — aggregate

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `CFE_EVS.PacketID.EventType` | 1 (DEBUG) or 2 (INFO) in steady state | Value 3 (ERROR) or 4 (CRITICAL) |
| `CFE_EVS.PacketID.AppName` | Known set from startup | New/unexpected app name |
| `CFE_EVS.Message` | Routine status strings | Security-relevant text (e.g., "crypto failure", "invalid cmd") |
| `CFE_EVS_HK.AppData[n][2]` | `1` (enabled) for all known apps | `0` during an anomaly = event suppression |
| `CFE_EVS_HK.MessageTruncCounter` | 0 or very low | Spike = event flooding in progress |
| `CFE_EVS_HK.UnregisteredAppCounter` | 0 | Nonzero = events from unlicensed code |
| `CFE_EVS_HK.LogFullFlag` | 0 | `1` = log exhausted |
| `CFE_EVS_HK.LogOverflowCounter` | 0 | Nonzero = messages lost |

**`CFE_EVS_HK.AppData` array layout:** 16 entries, one per registered app.
Each entry: `[AppID, AppMessageSentCounter, AppEnableStatus, AppMessageSquelchedCounter]`.
`AppEnableStatus = 0` means that app's events are suppressed.

---

### 5.3 Software Bus Attacks — CDH

**Why it matters:** The cFS Software Bus (SB) is the internal pub/sub message
router. An attacker with access to the SBN TCP link can inject messages into any
subscribed MID. Flooding a pipe causes message drops. Probing with unsubscribed MIDs
reveals the topology. Subscribing to MIDs from unauthorized code enables
eavesdropping.

**Source packets:** `CFE_SB` (0x0803), `CFE_SB_SUBS` (0x080D)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `CFE_SB.NoSubscribersCounter` | 0 or low | Spike = MID injection probe |
| `CFE_SB.PipeOverflowErrorCounter` | 0 | Nonzero = pipe-flooding DoS |
| `CFE_SB.MsgLimitErrorCounter` | 0 | Nonzero = pipe-flooding DoS |
| `CFE_SB.DuplicateSubscriptionsCounter` | 0 | Nonzero = unauthorized eavesdrop subscription |
| `CFE_SB.MsgSendErrorCounter` | 0 | Nonzero = routing failure |
| `CFE_SB_SUBS.Entry[n][0]` (MsgId) | Stable set after init | New MsgId appearing = eavesdropping setup |

**`CFE_SB_SUBS.Entry` array layout:** Up to 20 subscription entries per packet,
segmented across `TotalSegments` packets. Each entry:
`[MsgId (uint32), [Qos0, Qos1], PipeId (uint8), Spare (uint8)]`.

---

### 5.4 Table Injection — CDH

**Why it matters:** cFS tables (CFE_TBL) are the primary mechanism for uploading
persistent configuration to the spacecraft. An attacker who can inject a table load
can modify any app's operating parameters — attitude control gains, stored command
sequences, scheduler entries — with effects that persist across processor resets.

**Source packets:** `CFE_TBL` (0x0804)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `CFE_TBL.NumLoadPending` | 0 outside maintenance window | Nonzero = table load in progress |
| `CFE_TBL.ValidationCounter` | Stable | Spike outside window = validation of injected table |
| `CFE_TBL.FailedValCounter` | 0 | Nonzero = corrupted table rejected (attack probe) |
| `CFE_TBL.LastValTableName` | Known table names | Unexpected table name |
| `CFE_TBL.LastFileLoaded` | Known file paths | Unknown file path |
| `CFE_TBL.LastUpdateTimeSeconds` | Only changes during maintenance | Change outside window |

---

### 5.5 Time Manipulation — CDH

**Why it matters:** Mission Elapsed Time (MET) is the reference for all scheduled
operations, crypto key epochs, and log timestamps. Injecting a time adjustment
(via the TIME service `Set Time` command) can break crypto validity windows, cause
command sequences to execute at wrong times, or create replay-attack opportunities.

**Source packets:** `CFE_TIME` (0x0805)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `CFE_TIME.SecondsMET` | Monotonically increasing | Discontinuity (jump forward or backward) |
| `CFE_TIME.ClockStateFlags` | GPS-locked (bit 0 set) | Source switches to internal flywheel (bit 1 set, bit 0 clear) |
| `CFE_TIME.SecondsSTCF` | Constant unless corrected | Unexpected change |
| `CFE_TIME.LeapSeconds` | Constant | Any change |

**`ClockStateFlags` bit map:**

- Bit 0 (`0x0001`): time has been set

- Bit 1 (`0x0002`): flywheel mode (no external sync)

- Bit 2 (`0x0004`): clock has been set at least once

---

### 5.6 Stored Command Injection — CDH

**Why it matters:** The Stored Commands (SC) app manages Absolute Time Sequences
(ATS) and Relative Time Sequences (RTS) — pre-loaded scripts that execute commands
autonomously. An attacker who injects a malicious ATS can execute any command at a
chosen time, including enabling thrusters, disabling safety limits, or wiping
storage. RTS sequences can be armed and left dormant until triggered.

**Source packets:** `SC` (0x08AA)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `SC.RtsExecutingStatus` | `[0,0,0,0]` or known-active RTS IDs | Change without operator initiation |
| `SC.AtsCmdErrCtr` | 0 | Spike after ATS upload = malformed injected sequence probing |
| `SC.AtsCmdCtr` | Increments only during planned maneuvers | Increment outside window |
| `SC.NumRtsActive` | 0 or known count | Unexpected increase |
| `SC.AtpState` | Known states (IDLE=0, EXECUTING=1) | Unexpected state change |
| `SC.AppendLoadCount` | Stable | Increment = ATS append upload |

**`SC.RtsExecutingStatus` encoding:** 4 × `uint16` = 64 bits. Bit N of word W is
set if RTS number `W × 16 + N` is currently executing. `[1, 0, 0, 0]` means only
RTS 0 is running; `[3, 0, 0, 0]` means RTS 0 and RTS 1 are both running.

**`SC.AtpFreeBytes` encoding:** 2 × `uint32`, one per ATS buffer. A sudden drop
to near zero after an ATS upload indicates the buffer was almost fully overwritten.

---

### 5.7 Schedule Disruption — CDH

**Why it matters:** The Scheduler (SCH) app sends wake-up messages to all cFS apps
on a precise 1 Hz major-frame / minor-slot timing grid. Disrupting the schedule
can starve safety-critical apps of CPU time, cause sensor data to go stale, and
prevent telemetry from being downlinked.

**Source packets:** `SCH` (0x0897)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `SCH.SkippedSlotsCount` | 0 | Spike = timing starvation / CPU DoS |
| `SCH.MissedMajorFrameCount` | 0 | Spike = 1 Hz tone lost (timing source attack) |
| `SCH.BadTableDataCount` | 0 | Nonzero = corrupted schedule table injected |
| `SCH.TableVerifyFailureCount` | 0 | Nonzero = table corruption rejected |
| `SCH.ScheduleActivityFailureCount` | 0 | Nonzero = apps not responding to schedule |
| `SCH.MajorFrameSource` | Known source (0=internal, 1=external) | Unexpected change |

---

### 5.8 GPS Spoofing — GNC

**Why it matters:** The NovAtel OEM615 GNSS receiver provides the only absolute
position/velocity reference onboard. A GPS spoofing attack injects false satellite
signals to make the spacecraft believe it is at a different position. This can cause
autonomous maneuvers to target the wrong orbit, break ground-station link windows,
and deceive orbit determination.

**Source packets:** `NOVATEL` (0x0871) device telemetry, `NOVATEL_HK` (0x0870) health

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `NOVATEL.Novatel_oem615.ECEFX/Y/Z` | Smooth orbital trajectory (±7000 km range) | Instantaneous discontinuity |
| `NOVATEL.Novatel_oem615.VelX/Y/Z` | ~7.5 km/s magnitude, consistent with orbit | Jump inconsistent with orbital dynamics |
| `NOVATEL.Novatel_oem615.lat/lon/alt` | Smoothly varying; alt ~400–600 km for LEO | Jump to implausible lat/lon or altitude |
| `NOVATEL.Novatel_oem615.Weeks` | Monotonically increasing GPS week | Any backward jump |
| `NOVATEL_HK.DeviceEnabled` | `1` | `0` = GPS disabled without command |

**Units:** ECEF X/Y/Z in metres (double precision). Velocity in m/s (double). lat/lon
in degrees (float32). alt in metres (float32).

---

### 5.9 ADCS Hijack and Actuator Bypass — GNC

**Why it matters:** The Attitude Determination and Control System (ADCS) controls
spacecraft orientation. An attacker who compromises the GNC control mode can command
arbitrary attitude maneuvers — pointing the antenna away from the ground station,
rotating solar panels out of sun, or desaturating wheels in a harmful direction.
A more subtle attack bypasses the control loop entirely and injects torque commands
directly to actuator hardware, leaving GNC telemetry clean while physically moving
the spacecraft.

**Source packets:** `ADCS_GNC` (0x0943), `ADCS_DO` (0x0945), `ADCS_HK` (0x0940)

#### GNC Control Mode Attack

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `ADCS_GNC.Mode` | Constant for mission phase (uint8) | Change without ground command |
| `ADCS_GNC.Tcmd` | `[0.0, 0.0, 0.0]` except during maneuvers | Nonzero outside scheduled maneuver window |
| `ADCS_GNC.Mcmd` | Near-zero except during desaturation | Nonzero without B-dot scenario |
| `ADCS_GNC.qErr` | Small magnitude, stable | Growing magnitude = destabilization |
| `ADCS_HK.CommandErrorCount` | 0 | Spike = unauthorized command injection to ADCS |

#### Actuator Bypass Attack

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `ADCS_DO.Rw.Tcmd` | Matches `ADCS_GNC.Tcmd` | Nonzero when `ADCS_GNC.Tcmd` is zero |
| `ADCS_DO.Trq.Mcmd` | Matches `ADCS_GNC.Mcmd` | Nonzero when `ADCS_GNC.Mcmd` is zero |
| `RW.data.momentum` | Smoothly varying | Jump inconsistent with `ADCS_DO.Rw.Tcmd` |

**`ADCS_DO.Rw.axis` and `ADCS_DI.Payload.Rw.whl_axis`** are 3 × 3 matrices of
double-precision floats. Each row is the unit vector of one reaction wheel's spin
axis in body frame. Normally constant (physical mounting). Any change is anomalous.

**`ADCS_GNC.qbn` and related quaternions** are 4-element lists `[qx, qy, qz, qw]`.
Unit quaternion `[0, 0, 0, 1]` = identity (no rotation). Growing `qErr` magnitude
(sum of squares of first three elements) indicates attitude error.

---

### 5.10 Sensor Spoofing — GNC

**Why it matters:** The ADCS_DI (Data Input) packet captures raw sensor measurements
before the attitude-determination filter. An attacker who can corrupt sensor outputs
(via hardware fault injection, EMI, or firmware modification) can feed false attitude
data to the control loop without triggering the GNC-level anomaly detectors.
Cross-referencing DI sensors against each other and against GNC outputs detects
inconsistencies that indicate spoofing.

**Source packets:** `ADCS_DI` (0x0941)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `ADCS_DI.Payload.St.valid` | `1` when out of eclipse and not slewing | `0` outside eclipse = star tracker blinded/spoofed |
| `ADCS_DI.Payload.Imu.wbn` | Consistent with `ADCS_GNC.wbn` | Large discrepancy = IMU spoofing |
| `ADCS_DI.Payload.Mag.bvb` | Follows orbital magnetic model | Deviation = magnetometer spoofing |
| `ADCS_DI.Payload.Fss.valid` | `1` in sunlight | `0` in sunlight = FSS blocked/spoofed |
| `ADCS_DI.Payload.Css.Sensor[n][4]` (percenton) | Matches sun-angle geometry | All zeros in sunlight = CSS disabled |

**`ADCS_DI.Payload.Css.Sensor` array layout:** 6 sensors × 5 values each:
`[axis_x, axis_y, axis_z, scale, percenton]`.
`percenton` is 0–100. The CSS sun vector `ADCS_DI.Payload.Css.svb` is derived from
these readings; if sensors disagree with the derived vector, spoofing is indicated.

---

### 5.11 Orbit Modification — GNC

**Why it matters:** The reaction-wheel system stores angular momentum; the thruster
provides delta-V for orbit changes. Unauthorized activation of either constitutes
an orbit-modification attack: wheels can desaturate into an unintended attitude;
a thruster firing changes the orbital period, altitude, or inclination. These are
the highest-consequence physical attacks on the spacecraft.

**Source packets:** `RW` (0x0993), `THRUSTER` (0x08EA)

#### Reaction Wheel Orbit Attack (desaturation attack)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `RW.DeviceEnabled_RW0/1/2` | `1` | `0` = wheel unexpectedly disabled |
| `RW.data.momentum` | Smooth variation within operating bounds | Spike without corresponding `ADCS_DO.Rw.Tcmd` |
| `RW.DeviceErrorCount_RW*` | 0 | Nonzero = hardware command rejected |

#### Thruster Orbit Attack

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `THRUSTER.DeviceEnabled` | `0` between burns, `1` during burn | `1` with no planned maneuver |
| `THRUSTER.CommandCount` | Increments only during planned burns | Increment outside burn window |
| `THRUSTER.DeviceCount` | Matches planned actuations | Unexpected increment |
| `THRUSTER.CommandErrorCount` | 0 | Nonzero = rejected command (probe attempt) |

---

### 5.12 Power System Attack — POWER

**Why it matters:** The Electrical Power System (EPS) controls the power bus
switches that supply individual subsystems. An attacker who can toggle a switch can
kill any subsystem (GPS receiver, radio, reaction wheels) without leaving obvious
software traces. Power drain via unauthorized high-current loads can deplete the
battery and cause a power-on reset.

**Source packets:** `EPS` (0x091A)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `EPS.DeviceHK.Switch[n][2]` (Status) | `1` or `0` per mission profile | Change without corresponding command |
| `EPS.DeviceHK.BatteryVoltage` | Stable oscillation (ADC counts) | Sudden drop = unauthorized load |
| `EPS.DeviceHK.Bus3p3Voltage` | Stable | Drop = processor rail stress |
| `EPS.DeviceHK.Bus5p0Voltage` | Stable | Drop = sensor rail stress |
| `EPS.DeviceHK.Bus12Voltage` | Stable | Drop = actuator rail stress |
| `EPS.DeviceHK.SolarArrayVoltage` | Varies with orbital phase | Drop in sunlight = panel damage or orientation attack |

**`EPS.DeviceHK.Switch` array layout:** 8 switches × 3 values each:
`[Voltage (uint16, ADC), Current (uint16, ADC), Status (uint16)]`.
All values are raw 12-bit ADC counts (0–4095); physical conversion requires the
EPS calibration table. `Status = 1` = switch on, `Status = 0` = switch off.

---

### 5.13 Communications Attack — COMM

**Why it matters:** The radio provides the only ground uplink/downlink and the
inter-satellite proximity link. An attacker who reconfigures the radio (frequency,
power, modulation) can sever the ground link (DoS) or redirect uplink commands to
a rogue ground station. Unexpected proximity-link activity may indicate an
unauthorized rendezvous or eavesdropping by a nearby asset.

**Source packets:** `RADIO_HK` (0x0930), `RADIO_DEV` (0x0931), `SBN` (0x08DC)

| Key Field | Normal Value | Anomaly Signal |
|-----------|-------------|----------------|
| `RADIO_HK.DeviceHK.DeviceConfig` | Fixed config word | Any change = frequency/power reconfiguration |
| `RADIO_HK.ForwardCount` | 0 outside authorized cross-links | Nonzero = unauthorized proximity-link activity |
| `RADIO_DEV.ProxSignal` | Expected signal strength per orbital geometry | Anomalous level = jamming or spoofed proximity link |
| `SBN.ModuleStatus` | Fixed after peer negotiation | Change = peer dropped or new peer connected |
| `RADIO_HK.CommandErrorCount` | 0 | Nonzero = invalid radio command injection |
| `RADIO_HK.DeviceErrorCount` | 0 | Nonzero = hardware-level fault or attack |

**`SBN.ModuleStatus`** is an opaque 64-byte blob (`[uint8 × 64]`). Its internal
layout is protocol-specific (TCP module). A sudden change mid-mission indicates
peer connection state has changed, which may mean the original peer (ground system)
dropped and a different system connected.

---

## 6. Full Column Reference by Subsystem

### CDH — Command and Data Handling

| Column | Source MID | C Type | Description / Anomaly |
|--------|-----------|--------|----------------------|
| `CFE_EVS.PacketID.AppName` | 0x0808 | `char[20]` | App that generated the event |
| `CFE_EVS.PacketID.EventID` | 0x0808 | `uint16` | Numeric event code |
| `CFE_EVS.PacketID.EventType` | 0x0808 | `uint16` | 1=DEBUG 2=INFO **3=ERROR 4=CRITICAL** |
| `CFE_EVS.PacketID.SpacecraftID` | 0x0808 | `uint32` | Spacecraft identifier |
| `CFE_EVS.PacketID.ProcessorID` | 0x0808 | `uint32` | Processor identifier |
| `CFE_EVS.Message` | 0x0808 | `char[122]` | Event text; ERROR/CRITICAL from unknown app = attack |
| `CFE_EVS_HK.CommandCounter` | 0x0801 | `uint8` | EVS valid command count |
| `CFE_EVS_HK.CommandErrorCounter` | 0x0801 | `uint8` | EVS command errors |
| `CFE_EVS_HK.MessageTruncCounter` | 0x0801 | `uint8` | Truncated events; spike = flooding attack |
| `CFE_EVS_HK.UnregisteredAppCounter` | 0x0801 | `uint8` | Events from unknown apps |
| `CFE_EVS_HK.LogFullFlag` | 0x0801 | `uint8` | 1 = log exhausted |
| `CFE_EVS_HK.LogMode` | 0x0801 | `uint8` | 0=overwrite 1=discard |
| `CFE_EVS_HK.LogOverflowCounter` | 0x0801 | `uint16` | Log overflow count |
| `CFE_EVS_HK.AppData` | 0x0801 | `list[16][4]` | Per-app: AppID, SentCtr, **EnableStatus**, SquelchedCtr |
| `CFE_ES.CommandCounter` | 0x0800 | `uint8` | ES valid commands |
| `CFE_ES.CFECoreChecksum` | 0x0800 | `uint16` | cFE core CRC; change = firmware tamper |
| `CFE_ES.RegisteredExternalApps` | 0x0800 | `uint32` | External apps; change = unauthorized app load |
| `CFE_ES.ProcessorResets` | 0x0800 | `uint32` | Processor reset count; increment = crash |
| `CFE_ES.HeapBytesFree` | 0x0800 | `uint32` | Free heap; drain = memory exhaustion attack |
| `CFE_ES.PerfFilterMask` | 0x0800 | `list[4]` (uint32) | Perf monitor filter (128 IDs) |
| `CFE_ES.PerfTriggerMask` | 0x0800 | `list[4]` (uint32) | Perf monitor trigger (128 IDs) |
| `CFE_SB.NoSubscribersCounter` | 0x0803 | `uint8` | No-subscriber msgs; spike = injection probe |
| `CFE_SB.PipeOverflowErrorCounter` | 0x0803 | `uint16` | Pipe overflow; spike = DoS |
| `CFE_SB.MsgLimitErrorCounter` | 0x0803 | `uint16` | Msg limit errors; spike = DoS |
| `CFE_SB.DuplicateSubscriptionsCounter` | 0x0803 | `uint8` | Duplicate subs; nonzero = eavesdrop |
| `CFE_SB_SUBS.Entry` | 0x080D | `list[20][4]` | Subscription table; new MsgId = eavesdrop |
| `CFE_TBL.NumLoadPending` | 0x0804 | `uint16` | Pending loads; nonzero outside window = table injection |
| `CFE_TBL.FailedValCounter` | 0x0804 | `uint8` | Failed validations; nonzero = corrupt injection |
| `CFE_TBL.LastValTableName` | 0x0804 | `char[40]` | Last validated table name |
| `CFE_TIME.ClockStateFlags` | 0x0805 | `uint16` | Clock source bitmask |
| `CFE_TIME.SecondsMET` | 0x0805 | `uint32` | MET seconds; discontinuity = time attack |
| `SC.RtsExecutingStatus` | 0x08AA | `list[4]` (uint16) | Executing RTS bitmap (64 RTS) |
| `SC.AtsCmdErrCtr` | 0x08AA | `uint16` | ATS errors; spike after upload = injection probe |
| `SCH.SkippedSlotsCount` | 0x0897 | `uint16` | Skipped slots; spike = timing DoS |
| `SCH.BadTableDataCount` | 0x0897 | `uint16` | Bad table data; nonzero = schedule injection |
| `SCH.MissedMajorFrameCount` | 0x0897 | `uint32` | Missed 1 Hz tones; spike = timing DoS |

### GNC — Guidance, Navigation, and Control

| Column | Source MID | C Type | Description / Anomaly |
|--------|-----------|--------|----------------------|
| `NOVATEL.Novatel_oem615.ECEFX/Y/Z` | 0x0871 | `double` (m) | ECEF position; discontinuity = GPS spoof |
| `NOVATEL.Novatel_oem615.VelX/Y/Z` | 0x0871 | `double` (m/s) | ECEF velocity; jump = GPS spoof |
| `NOVATEL.Novatel_oem615.lat/lon` | 0x0871 | `float` (deg) | Geodetic position |
| `NOVATEL.Novatel_oem615.alt` | 0x0871 | `float` (m) | Altitude; ~400–600 km for LEO |
| `NOVATEL_HK.DeviceEnabled` | 0x0870 | `uint8` | GPS on/off; `0` without command = sabotage |
| `ADCS_GNC.Mode` | 0x0943 | `uint8` | GNC mode; change without command = hijack |
| `ADCS_GNC.Tcmd` | 0x0943 | `list[3]` (double, N·m) | RW torque command; nonzero outside maneuver = attack |
| `ADCS_GNC.qbn` | 0x0943 | `list[4]` (double) | Body-to-inertial quaternion `[x,y,z,w]` |
| `ADCS_GNC.qErr` | 0x0943 | `list[4]` (double) | Attitude error quaternion; growth = destabilization |
| `ADCS_GNC.wbn` | 0x0943 | `list[3]` (double, rad/s) | Body angular rate |
| `ADCS_DO.Rw.axis` | 0x0945 | `list[3][3]` (double) | RW spin-axis matrix; should be constant |
| `ADCS_DO.Rw.Tcmd` | 0x0945 | `list[3]` (double, N·m) | RW torque output; should match GNC.Tcmd |
| `ADCS_DI.Payload.St.valid` | 0x0941 | `uint8` | Star tracker valid; `0` in sunlight = spoof |
| `ADCS_DI.Payload.Imu.wbn` | 0x0941 | `list[3]` (double, rad/s) | IMU rate; should match GNC.wbn |
| `ADCS_DI.Payload.Css.Sensor` | 0x0941 | `list[6][5]` (double) | CSS: [axis×3, scale, percenton] per sensor |
| `ADCS_DI.Payload.Rw.whl_axis` | 0x0941 | `list[3][3]` (double) | RW axis matrix from DI layer |
| `RW.data.momentum` | 0x0993 | `list[3]` (double, N·m·s) | Wheel momentum; change without Tcmd = injection |
| `RW.DeviceEnabled_RW0/1/2` | 0x0993 | `uint8` | Wheel enable flags |
| `THRUSTER.DeviceEnabled` | 0x08EA | `uint8` | `1` during burn only; unauthorized `1` = orbit attack |
| `THRUSTER.CommandCount` | 0x08EA | `uint8` | Thruster commands; outside burn window = attack |

### POWER — Electrical Power System

| Column | Source MID | C Type | Description / Anomaly |
|--------|-----------|--------|----------------------|
| `EPS.DeviceHK.BatteryVoltage` | 0x091A | `uint16` (ADC) | Battery bus; drop = unauthorized load |
| `EPS.DeviceHK.Bus3p3Voltage` | 0x091A | `uint16` (ADC) | 3.3 V rail |
| `EPS.DeviceHK.Bus5p0Voltage` | 0x091A | `uint16` (ADC) | 5.0 V rail |
| `EPS.DeviceHK.Bus12Voltage` | 0x091A | `uint16` (ADC) | 12 V rail |
| `EPS.DeviceHK.SolarArrayVoltage` | 0x091A | `uint16` (ADC) | Solar array; drop in sunlight = attack |
| `EPS.DeviceHK.Switch` | 0x091A | `list[8][3]` (uint16) | 8 switches: [Voltage, Current, **Status**] |

**EPS voltage fields** are raw 12-bit ADC counts. No conversion factor is applied
in the log. Relative changes are meaningful even without calibration.

### COMM — Communications

| Column | Source MID | C Type | Description / Anomaly |
|--------|-----------|--------|----------------------|
| `RADIO_HK.DeviceHK.DeviceConfig` | 0x0930 | `uint32` | Radio config word; change = reconfiguration attack |
| `RADIO_HK.ForwardCount` | 0x0930 | `uint8` | Prox-link forward count; nonzero = unauthorized activity |
| `RADIO_DEV.ProxSignal` | 0x0931 | `uint32` | RF signal strength; anomaly = jamming/spoof |
| `SBN.ModuleStatus` | 0x08DC | `list[64]` (uint8) | SBN peer state blob; change = peer switch |
