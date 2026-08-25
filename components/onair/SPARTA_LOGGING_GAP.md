# SPARTA Space-Vehicle Logging Best Practices vs What We Record

**Ticket:** [`AINOS3-95`](tickets/AINOS3-95.md) · Sprint 28 · spike, **no subscription is
made by this document**.

**Source:** `data/sparta/Space_Vehicle_Logging_Best_Practices-Distro_A.xlsx` (Distro A v1,
sha256 `857a8e52666d…`) and `BestPracticesSVLogging-Distro_A--v1.pdf`, from SPARTA's
[Indicators-of-Behavior page](https://sparta.aerospace.org/related-work/iob). Both are the
Aerospace Corporation's to distribute, so they are **git-ignored** — everything below is
re-derivable from a fresh download.

**Reproduce:**

```
python3 components/onair/training/extract_logging_workbook.py   # 19 sheets -> JSON
python3 components/onair/training/sparta_logging_gap.py         # JSON x our schema
```

The second script is the one that matters. The mapping from a workbook recommendation to
our telemetry is a **judgement**, and it is encoded in that file the way
`app/gen_nos3_coverage.py` encodes the coverage matrix — but three things are
machine-checked so the judgement cannot silently rot: every distinct workbook
recommendation must be claimed by exactly one entry, every schema column named must exist
in `nos3_security_tlm.json`, and every verdict must be internally consistent. A workbook
revision that adds a row, or a schema change that prunes a column, fails the run instead of
being quietly dropped.

---

## The one-paragraph answer

The workbook is an **event-audit** standard and our pipeline is a **periodic-sample**
recorder, and most of the gap is that mismatch rather than any missing MID. Its most
repeated instruction — *log the register and the new value, with a time tag, when a
configuration changes* — we answer with "a command counter incremented". That is precisely
the signal the rule-gate R6–R14 family was built to exploit, so the shape of our detector is
externally validated; what we cannot produce is the *content* of the change. Of 97 distinct
recommendations, **17 we record, 29 we record partially, 51 we do not record at all** — and
of those we miss, **42 have no target in NOS3 at all**, 27 need FSW work, and **12 are
already on this build's software bus and simply not subscribed**. Those 12 are the
deliverable.

---

## `AC1` — every sheet, and what it is for

All 19 sheets were read; 280 data rows, 122 distinct recommendation strings.

| Sheet | Rows | Purpose — skip to it when you need… |
|---|--:|---|
| `Index & Acronyms` | 50 | column definitions and the drop-down legends. Read this **first**: it defines what "FMS Redundancy" and "Response Significance" mean |
| `Content of Log Records` | 9 | NIST SP 800-53r5 AU-3: the seven fields a log record must contain (type, time, location, source, effect, identity, rule ID) |
| `Propulsion` | 7 | thruster/valve/heater logging. NOS3 models a thruster with a counter and an enable flag only |
| `ADCS` | 12 | sensor + actuator anomaly logging, intra-ADCS access, star-catalog integrity. **Feeds `AINOS3-86`** |
| `EPS` | 11 | power-consumption baselining, load shedding, switch/reset/power-on commands. **Feeds `AINOS3-87`** |
| `GN&C` | 11 | ephemeris/burn-plan integrity and GPS jam/spoof logging. **Feeds `AINOS3-86`** |
| `C&DH` | 34 | the largest sheet and the one NOS3 actually models — every cFE service gets a row. **The sheet to read if you read only one** |
| `TT&C` | 28 | SDR/encryptor/antenna configuration changes and uplink signal characteristics |
| `SMS` | 8 | structures and mechanisms; docking. No NOS3 target |
| `TCS` | 9 | thermal limits, calibration tables, TEC polarity. No NOS3 thermal app exists |
| `Payload - Imagery` | 16 | focal-plane array, calibration, exposure, hot pixels |
| `Payload - RF` | 31 | an RF payload's own SDR/encryptor/antenna chain — a near-duplicate of `TT&C` |
| `Payload - OCT` | 17 | optical crosslink terminal; crosslink authorisation |
| `Payload - Data Processing` | 10 | on-board processing/classification algorithm integrity |
| `Payload - Hosted` | 10 | hosted-payload isolation — access *from* the payload outward |
| `SPARTA_Mapping` | 76 | **the point of the artifact**: technique → subsystem → data type → attack vector. 76 techniques indexed |
| `SPARTA_Mapping_Abstract` | 1 | a title cell. Empty of content |
| `REF_Info` | 5 | source links (SPARTA, NIST 800-53r5, NASA thermal SoA) |
| `Change_Log` | 1 | one entry — this is the original public release |

### The payload sheets: the expected verdict was right after all

⚠ **This section previously said the opposite, and was wrong.** An earlier revision claimed
the ticket's "expect the 5 Payload sheets to be not modelled" prediction was wrong for two of
them, because this build loads an imagery payload (`arducam`) and a data-processing payload
(`syn`) whose MIDs are scheduled and downlinked.

Both were subscribed and **delivered 0 packets in 90 s** on the live stack, and the payload
rows were reverted to `NEEDS_FSW`. `AINOS3-102` then traced why, and **corrected this section
a second time** — the first explanation was also wrong:

- **`cam-sim` is not GUI-only.** `make launch-quiet` runs
  `scripts/fsw/launch_sat_quiet.sh` (not `launch.sh`), which *does* start `cam-sim`, in a form
  identical to the sims that work. It starts, reads `nos3-simulator.xml`, finds
  **`<active>false</active>`** for `camsim`, and exits. `DFLAGS` carries `--rm`, so the
  container is auto-removed — leaving nothing in `docker ps -a` and no logs, which is exactly
  what made it look like it was never launched.
- **`syn` has no simulator entry at all**, consistent with needing none: SYNOPSIS is an
  on-board library and `libsynopsis.so` is built and present. Its failure to initialise is
  still unexplained.
- **Neither payload packet has a publish path**, independent of any of the above. `CAM_EXP`
  `0x08C9` is filled by `CAM_read_prep` and **never transmitted** (`CAM_PUBLISH_CC` is defined
  with no handler); `SYN_DEV` `0x08FD` has its `CFE_MSG_Init` commented out (`syn_app.c:172`).

So the ticket's original prediction stands — **all five payload sheets are effectively not
modelled** — but the reason is a config flag plus missing FSW plumbing, not a launch-mode
choice. `AINOS3-102` decided **not** to subscribe `CAM_HK`: it carries two `uint8` counters
with zero scheduled camera commands, and the packet that would carry real payload signal
cannot be subscribed at any price until someone writes a publish path.

⚠ **The general lesson, which cost this document two retractions:** *scheduled, downlinked and
transmitted in the source does not mean arriving at OnAIR.* Verify live before claiming
coverage — and when a component is silent, confirm **why** before concluding what. A simulator
that refuses to run and one that was never started are indistinguishable under `--rm`.

### Which stack a coverage claim was verified on

**Assume `make launch-quiet` unless the claim says otherwise.** It is the mode every soak,
every corpus collection and every attack validation uses, so it is the surface that counts.

Any claim verified on a different stack — `make launch`, a hand-started simulator, a modified
`nos3-simulator.xml` — **must name that stack explicitly**, because the two are not guaranteed
equivalent. An unqualified claim in this document, in a ticket, or in the coverage overlay
means `launch-quiet` and may be read as such.

## `AC2` — the gap table

One row per distinct recommendation. `Recorded?` is **YES** (we record what is asked),
**PARTIAL** (we record a proxy — almost always "a counter ticked" where the workbook asked
for "the new value"), or **NO**. The last column names what would carry the missing half.

Generated by `sparta_logging_gap.py --markdown`; regenerate rather than hand-edit.

<!-- BEGIN AC2 -->
| ID | Recommended log source | Recorded? | Our fields | What would carry the rest |
|---|---|---|---|---|
| `GEN-CFG` | Modification of hardware configuration key-value pairs | PARTIAL | `CFE_TBL.CommandCounter`<br>`CFE_TBL.TableUpdateCount`<br>`CFE_TBL.TableUpdateChanged`<br>`EPS.CommandCount`<br>`ADCS_HK.CommandCount`<br>`RW.CommandCounter` | MM (Memory Manager) / MD (Memory Dwell) — in the startup script, NOT in the build |
| `GEN-ACCESS-IN` | Access to a subsystem acquired from another subsystem | NO | — | no cFS analogue — the Software Bus is anonymous publish/subscribe |
| `GEN-ACCESS-OUT` | Access from a subsystem out to another subsystem | NO | — | no cFS analogue — see GEN-ACCESS-IN |
| `GEN-COMM` | Messages addressed to a subsystem (not broadcast) | NO | — | CFE_SB_ONESUB_TLM 0x080E (subscription changes) — routed by TO, no SCH entry |
| `GEN-SIGANOM` | Critical subcomponent signal anomalies | YES | `CSS.DeviceEnabled`<br>`FSS.DeviceEnabled`<br>`IMU.DeviceEnabled`<br>`MAG.DeviceEnabled`<br>`ST.DeviceEnabled`<br>`THRUSTER.DeviceEnabled`<br>`TORQUER.DeviceEnabled`<br>`NOVATEL_HK.DeviceEnabled`<br>`RW.DeviceEnabled_RW0`<br>`CSS.DeviceErrorCount`<br>`IMU.DeviceHK.DeviceStatus` | — |
| `GEN-TEMPLIM` | Change in temperature set limits | NO | — | CFE_TBL_REG_TLM 0x080C (per-table CRC) — routed by TO, no SCH entry |
| `GEN-CTRLLOGIC` | Change in control logic/algorithms (gains, constants) | YES | `ADCS_GNC.Hmgmt.Kb`<br>`ADCS_GNC.Hmgmt.b_range`<br>`ADCS_GNC.MaxMcmd`<br>`ADCS_GNC.DT`<br>`ADCS_AC.Bdot.Kb`<br>`ADCS_AC.Bdot.b_range`<br>`ADCS_AC.Sunsafe.Kp`<br>`ADCS_AC.Sunsafe.Kr`<br>`ADCS_AC.Sunsafe.vmax`<br>`ADCS_AC.Inertial.Kp`<br>`ADCS_AC.Inertial.Kr`<br>`ADCS_AC.Inertial.Ki`<br>`ADCS_AC.Inertial.phiErr_max`<br>`CFE_TBL.CommandCounter` | — |
| `GEN-DETLOGIC` | Change in determination logic/algorithms | PARTIAL | `ADCS_GNC.qValid`<br>`ADCS_GNC.SunValid`<br>`ADCS_DI.Payload.St.valid`<br>`ADCS_AD.Sol.FssValid`<br>`ADCS_AD.ST.Valid`<br>`ADCS_AD.Imu.alpha`<br>`ADCS_AD.Imu.wbn_prev` | the determination ALGORITHM parameters — only its outputs and validity flags exist |
| `EPS-LOADSHED` | Load shedding | PARTIAL | `EPS.DeviceHK.Switch`<br>`EPS.CommandCount`<br>`ADCS_GNC.Mode` | no per-switch load/current telemetry in the EPS sim |
| `EPS-RESET` | Power reset | PARTIAL | `CFE_ES.ProcessorResets`<br>`CFE_ES.ResetType`<br>`CFE_ES.ResetSubtype`<br>`CFE_ES.MaxProcessorResets` | no per-device power-reset counter |
| `EPS-PWRON` | Power-on commands | PARTIAL | `EPS.CommandCount`<br>`EPS.CommandErrorCount` | no command-argument telemetry |
| `EPS-PWRDRAW` | Change in power consumption characteristics | NO | — | no current/power field anywhere in GENERIC_EPS_Hk_tlm_t |
| `ADCS-INTRA-ACCESS` | Unusual access from one ADCS subcomponent | NO | — | no sender identity — see GEN-ACCESS-IN |
| `ADCS-INTRA-COMM` | Abnormal communication among ADCS subcomponents | NO | — | no sender identity — see GEN-ACCESS-IN |
| `ADCS-SENSORS` | Critical ADCS sensors signal anomalies | YES | `ADCS_DI.Payload.Mag.bvb`<br>`ADCS_DI.Payload.Fss.svb`<br>`ADCS_DI.Payload.Css.svb`<br>`ADCS_DI.Payload.Imu.wbn`<br>`ADCS_DI.Payload.St.q`<br>`MAG_DEV.Generic_mag.MagneticIntensityX`<br>`FSS_DEV.Generic_fss.Alpha`<br>`CSS_DEV.Generic_css.Voltage` | — |
| `ADCS-ACTUATORS` | Critical ADCS actuators signal anomalies | YES | `ADCS_DO.Rw.Tcmd`<br>`ADCS_DO.Trq.Mcmd`<br>`RW.data.momentum`<br>`TORQUER.TrqInfo`<br>`TORQUER.TorquerPeriod`<br>`THRUSTER.DeviceEnabled` | — |
| `ADCS-STARMAP` | Change to star maps/catalogs | NO | — | the NOS3 star-tracker sim publishes a quaternion; there is no catalog to modify |
| `GNC-BURN` | Change to burn plan | PARTIAL | `SC.AtsNumber`<br>`SC.RtsNumber`<br>`SC.AppendLoadCount`<br>`SC.AtsCmdCtr` | no burn planner in NOS3 |
| `GNC-EPHEM` | Change to ephemerides | YES | `NOVATEL.Novatel_oem615.ECEFX`<br>`NOVATEL.Novatel_oem615.ECEFY`<br>`NOVATEL.Novatel_oem615.ECEFZ`<br>`NOVATEL.Novatel_oem615.lat`<br>`NOVATEL.Novatel_oem615.lon`<br>`NOVATEL.Novatel_oem615.alt` | — |
| `GNC-GPSJAM` | GPS message jamming/spoofing | PARTIAL | `NOVATEL.Novatel_oem615.Weeks`<br>`NOVATEL.Novatel_oem615.SecondsIntoWeek`<br>`NOVATEL.Novatel_oem615.Fractions`<br>`CFE_TIME.SecondsMET`<br>`CFE_TIME.SecondsSTCF`<br>`RADIO_HK.DeviceHK.ProxSignal` | no signal-power / centre-frequency / bandwidth field on the GPS receiver |
| `CDH-MEMPOKE` | Memory pokes/loads and related commands | PARTIAL | `CFE_TBL.CommandCounter`<br>`CFE_TBL.FileLoadCount`<br>`CFE_TBL.TableLoadCount`<br>`CFE_TBL.FileLoadChanged`<br>`CFE_TBL.TableLoadChanged` | MM app — requested by the scheduler, absent from the build |
| `CDH-MEMPEEK` | Memory peeks/dumps revealing C&DH configuration | NO | — | MM/MD apps — absent from the build |
| `CDH-WDT` | Suspension or changes to watchdog services | NO | — | HS (Health & Safety) app — requested by the scheduler (HS_SEND_HK_MID), absent from the build |
| `CDH-CODEFLAW` | Exploiting code flaws or backdoors (off-nominal behaviour) | PARTIAL | `ADCS_GNC.Mode`<br>`CFE_ES.HeapBytesFree`<br>`CFE_ES.HeapBlocksFree`<br>`CFE_ES.HeapMaxBlockSize`<br>`CFE_ES.SysLogEntries`<br>`CFE_EVS_HK.MessageSendCounter` | CFE_ES_APP_TLM 0x080B / CFE_ES_MEMSTATS 0x0810 — routed by TO, no SCH entry |
| `CDH-GOLDEN` | Corruption of golden software/firmware images | NO | — | CS (Checksum) app — requested by the scheduler, absent from the build AND below the startup script's `!` terminator |
| `CDH-AUTHZ` | Changes to authentication/authorization policies, whitelists | NO | — | CryptoLib is a CFE_LIB with zero Software Bus telemetry |
| `CDH-TRUSTZONE` | Changes to trust-zone boundaries / pub-sub messaging services | PARTIAL | `CFE_SB.CommandCounter`<br>`CFE_SB.SubscribeErrorCounter`<br>`CFE_SB.DuplicateSubscriptionsCounter`<br>`CFE_SB.NoSubscribersCounter` | CFE_SB_STATS_TLM 0x080A + CFE_SB_ONESUB_TLM 0x080E — routed by TO, no SCH entry |
| `CDH-CERTS` | Changes to user, device, or application certificates | NO | — | CryptoLib — no SB telemetry |
| `CDH-ENCSTORE` | Suspension or changes to encrypted storage | NO | — | no encrypted-storage service in this build |
| `CDH-FMS` | Suspension or changes to fault management services | YES | `LC.CurrentLCState`<br>`LC.WPsInUse`<br>`LC.ActiveAPs`<br>`LC.WPResults`<br>`LC.APResults`<br>`LC.RTSExecCount`<br>`CFE_EVS_HK.CommandCounter`<br>`SC.RtsDisabledStatus`<br>`ADCS_GNC.Mode` | — |
| `CDH-CPU` | CPU utilization is abnormally high | NO | — | CFE_ES_APP_TLM 0x080B (per-app ExecutionCounter) — routed by TO, no SCH entry |
| `CDH-CMDCTR` | Mismatch in command counter between ground and spacecraft | PARTIAL | `CI.usCmdCnt`<br>`CI.usCmdErrCnt`<br>`TO.usCmdCnt`<br>`CFE_ES.CommandCounter`<br>`CFE_SB.CommandCounter`<br>`CFE_EVS_HK.CommandCounter`<br>`CFE_TBL.CommandCounter`<br>`CFE_TIME.CommandCounter` | the GROUND-side counter — held by COSMOS, never joined to the telemetry stream |
| `CDH-RESET` | Any type of reset | YES | `CFE_ES.ProcessorResets`<br>`CFE_ES.ResetType`<br>`CFE_ES.ResetSubtype`<br>`CFE_ES.MaxProcessorResets`<br>`CSS.DeviceCount`<br>`IMU.DeviceHK.DeviceCounter` | — |
| `CDH-VIRT-ESC` | Virtualization/containerization escapes | NO | — | cFS runs as one process; no VM/container layer inside the FSW |
| `CDH-VIRT-BUILD` | Container changes to initialization/build files | NO | — | see CDH-VIRT-ESC |
| `CDH-DENIALS` | Resource/ trust zone access denials | PARTIAL | `CFE_SB.MsgSendErrorCounter`<br>`CFE_SB.MsgReceiveErrorCounter`<br>`CFE_SB.PipeOverflowErrorCounter`<br>`CFE_SB.MsgLimitErrorCounter`<br>`CFE_SB.InternalErrorCounter` | no requester identity — see GEN-ACCESS-IN |
| `CDH-TBLSVC` | Unauthorized access or changes to table services | YES | `CFE_TBL.CommandCounter`<br>`CFE_TBL.CommandErrorCounter`<br>`CFE_TBL.NumLoadPending`<br>`CFE_TBL.ValidationCounter`<br>`CFE_TBL.LastValCrc`<br>`CFE_TBL.TableUpdateCount` | — |
| `CDH-CRITCMD` | Any critical command | PARTIAL | `SC.AtsCmdCtr`<br>`SC.RtsCmdCtr`<br>`THRUSTER.CommandCount` | no command source/identity — see GEN-ACCESS-IN |
| `CDH-FLIGHTRULES` | Changes to flight rules | PARTIAL | `LC.WPsInUse`<br>`LC.ActiveAPs`<br>`LC.CurrentLCState` | the watchpoint/actionpoint table CONTENTS — only counts are telemetered |
| `CDH-SBSVC` | Unauthorized access or changes to software bus services | YES | `CFE_SB.CommandCounter`<br>`CFE_SB.NoSubscribersCounter`<br>`CFE_SB.MsgSendErrorCounter`<br>`CFE_SB.PipeOverflowErrorCounter`<br>`CFE_SB.MsgLimitErrorCounter` | — |
| `CDH-CLOCK` | Unauthorized access or changes to clock services | YES | `CFE_TIME.CommandCounter`<br>`CFE_TIME.ClockStateFlags`<br>`CFE_TIME.ClockStateAPI`<br>`CFE_TIME.LeapSeconds`<br>`CFE_TIME.SecondsSTCF`<br>`CFE_TIME.SubsecsSTCF` | — |
| `CDH-APPEXIT` | Any application exit | PARTIAL | `CFE_ES.RegisteredExternalApps`<br>`CFE_ES.RegisteredCoreApps`<br>`CFE_ES.RegisteredTasks` | CFE_ES_APP_TLM 0x080B — which app, rather than how many |
| `CDH-LOGSVC` | Unauthorized access or changes to logging services | YES | `CFE_EVS_HK.LogEnabled`<br>`CFE_EVS_HK.LogMode`<br>`CFE_EVS_HK.LogFullFlag`<br>`CFE_EVS_HK.LogOverflowCounter`<br>`CFE_EVS_HK.MessageSendCounter`<br>`CFE_EVS_HK.MessageTruncCounter`<br>`CFE_ES.SysLogMode`<br>`CFE_ES.SysLogBytesUsed` | — |
| `CDH-MLSVC` | Unauthorized access or changes to machine learning services | NO | — | no on-board ML service in the FSW — OnAIR itself is the ML service |
| `CDH-SCHED` | Unauthorized access or changes to scheduler services | YES | `SCH.CmdCounter`<br>`SCH.ErrCounter`<br>`SCH.SlotsProcessedCount`<br>`SCH.SkippedSlotsCount`<br>`SCH.BadTableDataCount`<br>`SCH.TableVerifyFailureCount`<br>`SCH.MissedMajorFrameCount`<br>`SCH.ScheduleActivityFailureCount` | — |
| `CDH-STOREDCMD` | Unauthorized access or changes to stored command services | YES | `SC.CmdCtr`<br>`SC.CmdErrCtr`<br>`SC.AtpState`<br>`SC.NumRtsActive`<br>`SC.RtsDisabledStatus`<br>`SC.AtsCmdErrCtr` | — |
| `CDH-TLMSVC` | Unauthorized access or changes to telemetry services | YES | `TO.usCmdCnt`<br>`TO.usEnabledRoutes`<br>`TO.usConfigRoutes`<br>`TO.usMsgSubCnt`<br>`TO.usTblUpdateCnt` | — |
| `CDH-DIAGSVC` | Unauthorized access or changes to diagnostic services | NO | — | no built-in self-test service in this build |
| `CDH-PKGSVC` | Unauthorized access or changes to data packaging services | YES | `DS.Payload.AppEnableState`<br>`DS.Payload.DestTblLoadCounter`<br>`DS.Payload.FilterTblLoadCounter`<br>`DS.Payload.FileWriteCounter`<br>`DS.Payload.DisabledPktCounter`<br>`DS.Payload.FilteredPktCounter` | — |
| `CDH-SCRIPTS` | Changes to stored command scripts (ATS/RTS, hashes) | PARTIAL | `SC.AppendLoadCount`<br>`SC.AppendEntryCount`<br>`SC.AppendByteCount`<br>`SC.AtsNumber` | CS app — for the script hashes the workbook asks for |
| `CDH-BIST` | Changes to built-in self-tests | NO | — | no BIST service in this build |
| `CDH-MEMPERF` | Memory performance issues | YES | `CFE_ES.HeapBytesFree`<br>`CFE_ES.HeapBlocksFree`<br>`CFE_ES.HeapMaxBlockSize`<br>`CFE_ES.SysLogBytesUsed`<br>`CFE_ES.SysLogEntries`<br>`CFE_ES.ERLogEntries`<br>`CFE_ES.ERLogIndex`<br>`CFE_SB.MemInUse`<br>`CFE_SB.UnmarkedMem` | — |
| `CDH-MEMMGMT` | Unauthorized access or changes to memory management services | NO | — | MM app — requested by the scheduler, absent from the build |
| `TTC-MEMPEEK` | Memory peeks/dumps revealing TT&C configuration | NO | — | the radio sim exposes no memory interface |
| `TTC-REDUNDANT` | Communication with a redundant TT&C component | NO | — | NOS3 models one radio; there is no redundant transponder |
| `TTC-FW` | Corruption of stored firmware images / boot mechanisms | NO | — | no firmware layer in the radio or RF-payload sims |
| `TTC-RFCONFIG` | Changes to signal protocol parameters / message standards | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig`<br>`RADIO_HK.CommandCount` | the individual RF parameters — one opaque config word stands in for all of them |
| `TTC-HOPPING` | Changes to frequency-hopping characteristics | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig` | see TTC-RFCONFIG |
| `TTC-CARRIER` | Changes to carrier frequency/waveform | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig` | see TTC-RFCONFIG |
| `TTC-MODULATION` | Changes to modulation/demodulation | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig` | see TTC-RFCONFIG |
| `TTC-EDAC` | Changes to error detection/correction algorithms | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig`<br>`RADIO_HK.ForwardErrorCount` | see TTC-RFCONFIG |
| `TTC-ROUTER` | Changes to router configurations | PARTIAL | `TO.usEnabledRoutes`<br>`TO.usConfigRoutes` | already covered on the TO side by R13; the radio side has no per-route field |
| `TTC-ENCODING` | Changes to bit encoding/decoding schemes | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig` | see TTC-RFCONFIG |
| `TTC-OFFNOM` | Changes to off-nominal mode configurations | PARTIAL | `RADIO_HK.DeviceHK.DeviceConfig`<br>`ADCS_GNC.Mode` | see TTC-RFCONFIG |
| `TTC-TXPOWER` | Changes in transmission power levels | NO | — | no transmit-power field in the radio sim |
| `TTC-AGC` | Changes to automatic gain control settings | NO | — | no AGC field in the radio sim |
| `TTC-GNDAUTH` | Changes to ground authentication/authorization policies | NO | — | CryptoLib — no SB telemetry |
| `TTC-UPLINKSIG` | Abnormal uplink signal characteristics | PARTIAL | `RADIO_HK.DeviceHK.ProxSignal`<br>`RADIO_HK.ForwardErrorCount`<br>`RADIO_HK.ForwardCount` | SNR / power level / centre frequency — the radio sim telemeters none of them |
| `TTC-LOGBEHAV` | Abnormal logging behaviors | YES | `CFE_EVS_HK.MessageSendCounter`<br>`CFE_EVS_HK.LogOverflowCounter`<br>`CFE_EVS_HK.LogFullFlag`<br>`CFE_ES.SysLogEntries` | — |
| `TTC-KEYMGMT` | Changes to cryptographic key management/storage | NO | — | CryptoLib SADB — no SB telemetry |
| `TTC-BYPASSCMD` | Any received bypass commands | PARTIAL | `CI.usCmdCnt`<br>`CI.usCmdErrCnt`<br>`RADIO_HK.ForwardCount`<br>`RADIO_HK.ForwardErrorCount` | no command-opcode telemetry — only aggregate counters |
| `TTC-KEYCHGCMD` | Any received key change commands | PARTIAL | `CI.usCmdCnt`<br>`CI.usCmdErrCnt` | no command-opcode telemetry — see TTC-BYPASSCMD |
| `TTC-DISABLEENC` | Disable encryptor command | PARTIAL | `CI.usCmdCnt`<br>`RADIO_HK.ForwardErrorCount` | no command-opcode telemetry — see TTC-BYPASSCMD |
| `TTC-GIMBAL` | Changes to gimbal control constants | NO | — | no antenna gimbal in NOS3 |
| `TTC-TRACKALG` | Changes to signal tracking algorithms | NO | — | no signal-tracking model in the radio sim |
| `TTC-RFSWITCH` | Off-nominal activation/ deactivation of RF switches | NO | — | no RF switch in the radio sim |
| `TTC-PA` | Power-amplifier configuration parameters | NO | — | no power amplifier in the radio sim |
| `SMS-DOCK` | Unplanned docking | NO | — | no docking mechanism in NOS3 |
| `TCS-CALTBL` | Change calibration tables | NO | — | no thermal app in NOS3 — the whole TCS sheet has almost no target |
| `TCS-POLARITY` | Change in polarity | NO | — | no thermoelectric cooler in NOS3 |
| `PL-ACCESS-IN` | Access to payload acquired from another subsystem | NO | — | CAM_HK 0x08C8 needs cam-sim in the HEADLESS launch; SYN needs a simulator that does not exist |
| `PL-ACCESS-OUT` | Access from payload to another sub-system | NO | — | see PL-ACCESS-IN — both payload apps are inert in the headless pipeline |
| `PL-COMM` | Communication to payload from another subsystem | NO | — | no sender identity — see GEN-ACCESS-IN |
| `PL-REDUNDANT` | Communication with a redundant payload component | NO | — | no redundant payload in NOS3 |
| `PL-SIGANOM` | Critical payload subcomponent signal anomalies | NO | — | CAM_EXP 0x08C9 is initialised but never transmitted; SYN_DEV 0x08FD transmit is commented out (syn_app.c:172) |
| `PL-COLLECTREQ` | Changes to collection/allocation requests or stored scripts | PARTIAL | `SC.AtsCmdCtr`<br>`SC.RtsCmdCtr` | the payload-side counter — CAM is inert headless (see PL-ACCESS-IN) |
| `PL-FPA-CAL` | Change calibration tables/sequences | NO | — | the arducam sim models no focal-plane array |
| `PL-LIGHTLIM` | Change in light/photodiode set limits | NO | — | no iris/shutter model |
| `PL-CORRLOGIC` | Change in correction logic | NO | — | no FPA correction stage |
| `PL-NOISEFLOOR` | Abnormal noise floor/saturation | NO | — | no image content in the sim |
| `PL-HOTPIX` | Persistent hot/dead pixels | NO | — | no FPA |
| `PL-PIXMARK` | Pixels marked/unmarked as hot/dead | NO | — | no FPA |
| `PL-EXPOSURE` | Changes in exposure settings | NO | — | the arducam experiment commands select a size, not an exposure |
| `PL-RF-USERAUTH` | RF payload: changes to user auth/authz policies | NO | — | no RF payload in NOS3 |
| `PL-OCT-CROSSLINK` | Unauthorized crosslink connections | NO | — | no optical crosslink terminal in NOS3 |
| `PL-OCT-POLARIZATION` | Changes to carrier frequency/waveform/polarization | NO | — | no OCT payload in NOS3 |
| `PL-SIGPROC` | Change in signal detection/classification/processing logic | NO | — | SYN has no simulator anywhere in the build — the app is permanently inert |
<!-- END AC2 -->

---

## `AC3` — what it would take, counted

| Bucket | Count | Meaning |
|---|--:|---|
| **Recorded** | 17 | the recommendation is met by fields already in the 382-column schema |
| **Partial** | 29 | a proxy is recorded; the recommended *content* is not |
| **Not recorded** | 51 | nothing stands in |
| — **subscribable now** | **5** | a MID on this build's bus carries it; nothing but a schema edit is needed |
| — **needs FSW work** | 33 | an app or a field this build does not provide |
| — **not modelled by NOS3** | 42 | there is no such hardware or layer to log |

Buckets are counted over the 80 non-`YES` rows, so they sum to 80, not 97.

### The subscribable-now leads, ranked

⚠ **Updated 2026-08-25.** This list originally held 12 leads. Three were **subscribed and
verified** (`0x0944`, `0x0942`, `0x08B0`), two were **retracted** as inert in the headless
pipeline (CAM, SYN — see the payload-sheet note above), and two more were dropped as dead in
source (`CAM_EXP`, `SYN_DEV`). **Five remain**, all of them command-produced packets needing
scheduler work (`0x080A`, `0x080B`, `0x080C`, `0x080E`) plus the TO-side row already covered
by R13. The ranking below is preserved for its reasoning; the ✅/❌ marks record what actually
happened.

Precedent for all of them is `AINOS3-70`, which took the CSV from 360 to 382 columns and
needed an `sbn_client.so` rebuild. ⚠ Each still needs a live check that SBN actually
forwards the MID — `AINOS3-70` subscribed three MIDs that came back all-zero.

| # | MID | Packet | Answers | Why it is worth the columns |
|--:|---|---|---|---|
| 1 | `0x0944` | `GENERIC_ADCS_AC_MID` | `GEN-CTRLLOGIC` | ⭐ **The best lead in the workbook.** Carries the per-mode controller state we do not record: Bdot `Kb`/`b_range`/`bdot`, Sunsafe `Kp`/`Kr`/`vmax`/`err_t`, and **Inertial `Kp`/`Kr`/`Ki`/`phiErr_max`/`qbn_cmd` plus the live error terms `therr`, `sumtherr`, `werr`, `qErr`** — ~63 scalars. The ADCS and GN&C sheets both rate "change in control logic/algorithms" **High**, and `AINOS3-86`'s 33.6 % INERTIAL false-alarm floor is an attitude-control problem the per-mode IF is currently trying to solve from `ADCS_GNC` outputs alone, without the controller's own error state |
| 2 | `0x0942` | `GENERIC_ADCS_AD_MID` | `GEN-DETLOGIC` | Per-sensor determination outputs (`Imu.wbn_prev`, `Imu.alpha`, `Sol.FssValid`, `ST.Valid`, ~24 scalars). Partially redundant with `ADCS_DI`; take it only if lead 1 pays |
| 3 | `0x080A` | `CFE_SB_STATS_TLM` | `CDH-TRUSTZONE` | Per-pipe depth and message counts. `EX-0012.02` (route severance) reaches us today only via the staleness gate's 30–50 s latch; this is the direct signal |
| 4 | `0x080B` | `CFE_ES_APP_TLM` | `CDH-CPU`, `CDH-APPEXIT`, `CDH-CODEFLAW` | Per-app execution counters — the **CPU-utilisation** row the C&DH sheet asks for, and the "*which* app exited" half we currently see only as a dropped count |
| 5 | `0x080C` | `CFE_TBL_REG_TLM` | `GEN-TEMPLIM` | Per-table CRC. The nearest available answer to the 11 sheets asking for temperature-**limit** changes, and to config-table integrity generally |
| 6 | `0x08C8`/`0x08C9` | `CAM_HK_TLM` / `CAM_EXP_TLM` | `PL-*` | The imagery payload, see above |
| 7 | `0x08FC`/`0x08FD` | `SYN_HK_TLM` / `SYN_DEVICE_TLM` | `PL-SIGPROC` | The data-processing payload |
| 8 | `0x080E` | `CFE_SB_ONESUB_TLM` | `GEN-COMM` | Subscription changes — the only partial answer to the workbook's recurring "who talked to whom" |
| 9 | `0x08B0` | `CF_HK_TLM` | — | Not named by a recommendation, but noted while inventorying: the CFDP app is loaded, scheduled and downlinked, and file-transfer throughput is adjacent to `EXF-0003.02` and `EX-0010` |

⚠ Leads 3, 4, 5 and 8 are **command-response packets**: `to_config.c` routes them but
`sch_def_msgtbl.c` does not request them periodically. Making them periodic is a scheduler
**table** row — configuration, not code — but it is not zero, and it changes bus load.

### One honest caveat, carried forward from the sprint plan

`AINOS3-88` already tested "more recorded telemetry" across a seven-arm ablation and
returned a documented **NULL**, and it concluded the binding constraint was **corpus size**,
not feature design. Nothing here overturns that. What this spike changes is the
**provenance** of the candidates: technique-indexed by an external authority instead of
chosen by us, which was the weak joint in `AINOS3-88`'s arm selection. Lead 1 is the only
one this document would argue for on its own evidence, and it should be measured, not
assumed.

### The three apps that are asked for and not built

`cfe_es_startup.scr` loads — and `sch_def_msgtbl.c` schedules housekeeping for — five
standard cFS apps whose shared objects are **absent from `fsw/build/exe/cpu1/cf/`** and
whose source is not vendored: `cs`, `hk`, `hs`, `md`, `mm`. They therefore do not run. This
is the single largest `NEEDS_FSW` cluster, and it is unusually cheap because these are stock
NASA cFS apps rather than something to invent:

- **`cs` (Checksum)** would answer the workbook's most-repeated integrity instruction —
  golden-image, table, and script hashes — which appears on six separate rows and is rated
  **High** on every one. ⚠ Corrected 2026-08-25: the recorded corpus contains **no integrity
  data at all**. `CFE_ES.CFECoreChecksum` is subscribed but pruned from the CSV, so the
  earlier "we record exactly one checksum" overstated it. This is now the strongest single
  argument in the document for building an app.
- **`hs` (Health & Safety)** would answer the watchdog rows. See `AC4` below.
- **`mm` / `md` (Memory Manager / Dwell)** would answer "log the memory register and the new
  value" — the workbook's most-repeated recommendation, on 12 of the 13 subsystem sheets.

### The structural gap no MID closes

Fifteen recommendations ask for the **source or target subsystem** of a message or access —
`Content of Log Records` makes "Source" and "Identity" two of its seven mandatory fields.
The cFS Software Bus is **anonymous publish/subscribe**: a housekeeping packet carries no
sender. This is not a subscription gap and not a NOS3 simplification; it is a property of
the architecture, and it is why `LM-0002` (bus segregation) is detectable only as a
*sweep meta-rule* (R10) rather than as an access-control violation. Worth stating plainly
to stakeholders, because it bounds what "more logging" can ever buy on this platform.

---

## `AC4` — verdicts the workbook says are re-openable

Eleven of the 28 techniques we publish as **out-of-scope** or **UNSUBSCRIBED** appear in
`SPARTA_Mapping` with a named log source. That is a flag, not a refutation — the workbook
describes what a *real* space vehicle should log, and several of our verdicts are honest
statements about *this build*. The list below separates the two, because only the first
group is genuinely re-openable.

### Genuinely re-openable — the workbook proposes a detection we did not consider

| Technique | Our published verdict | What the workbook says instead |
|---|---|---|
| **`EX-0001.01`** Replay valid commands | OUT-OF-SCOPE — "replayed commands are byte-identical to legitimate ones; no telemetry field separates them" | ⭐ It does not propose separating the bytes. `C&DH` row 13 proposes **reconciling the spacecraft command counter against the ground's own count** — a *mismatch*, not a signature. We already record every spacecraft-side counter (`CI.usCmdCnt`, `TO.usCmdCnt`, all five `CFE_*.CommandCounter`). The missing half is a **join to COSMOS's ground-side count**, not a MID. Our rationale answered a question the standard does not ask |
| **`EX-0006`** Disable/bypass encryption | OUT-OF-SCOPE — "encryption enable state is internal to CryptoLib, no SB packet carries it" | `TT&C` rows 22 and 24 ask for the **command**, not the state: *"Any received bypass commands — log and alert under all circumstances"*. A command arriving at CI is exactly the static-in-nominal counter signal rules R6–R13 are built on. Re-openable as a **rule candidate**, not as a subscription |
| **`PER-0004`** Replace cryptographic keys | OUT-OF-SCOPE — "key material is internal to CryptoLib's SADB" | `TT&C` row 23, identical shape: *"Any received key change commands"*. Same re-open |
| **`EX-0012.11`** Modify watchdog / health monitor · **`DE-0003.11`** Watchdog state for evasion | OUT-OF-SCOPE/UNSUBSCRIBED — `AINOS3-74`: "no HS app; the pc-linux PSP watchdog is a stub" | The finding was right about the **build** and is worth restating more precisely: `cfe_es_startup.scr` **does** load `hs`, and the scheduler **does** request `HS_SEND_HK_MID` — there is simply no `hs.so`. `C&DH` row 4 names exactly what to log (setting changes, reset counts, requests to change watchdog services). Re-openable **if and only if** someone builds the app; not re-openable by subscribing |
| **`EX-0012.01`** Registers | OUT-OF-SCOPE — "CPU/peripheral register writes are not exposed in any cFS HK packet" | True of this build; the `mm`/`md` apps in the same not-built cluster are the standard cFS answer. Same conditional re-open as the watchdog pair |
| **`EX-0012.13`** / **`DE-0003.12`** Poison AI/ML training data | OUT-OF-SCOPE — "corrupts an offline dataset, not a live telemetry event" | `C&DH` row 25 agrees it is largely offline **and adds** *"input data drift from the distribution of training data should also be monitored"*. ⚠ Worth naming rather than dismissing: the ML service in question is **ours**, and the thing to monitor is our own corpus. That makes this an **`AINOS3-98` (corpus-integrity)** item, not an FSW subscription item |

### Not re-openable — the workbook names a log source NOS3 has no way to produce

`DE-0004` (masquerading), `EX-0003` (modify authentication) and `EX-0009.02` (host OS) all
map to *"authentication and authorization logs"*. NOS3 has no identity layer and CryptoLib
is a `CFE_LIB` with zero Software Bus telemetry, so there is nothing to subscribe. Our
verdicts stand. `EX-0001.02` (bus-traffic replay) maps to *"data bus messages"*, which we do
record — our verdict is about the absence of an **injection path**, which the workbook does
not address. `EX-0009.01` (flight software exploitation) maps to *"telemetry data, logs"*,
which is not a detection.

### Corroboration worth recording

The workbook independently marks **`EX-0010.03` (rootkit)** and **`EX-0010.04` (bootkit)**
with data type **`N/A`** — the only two techniques in `SPARTA_Mapping` it declines to name a
log source for. Our out-of-scope verdicts on both are now backed by the standard rather than
by our own judgement alone. Likewise `TTC-UPLINKSIG` confirms our `DE-0003.04` rationale:
SNR and receiver power level are the recommended signal, and the NOS3 radio sim telemeters
neither.

---

## What to add or modify

The spike changes nothing itself. This is the edit list it produces, in the order the
dependencies allow. Every path below was checked against the tree, not assumed.

### A — schema additions · no FSW rebuild, no `sbn_client.so` rebuild

Subscription is driven entirely by the `channels` map (`sbn_adapter.py:141`), so adding a
MID is three coordinated edits plus a deploy:

1. **`components/onair/message_headers.py`** — one `ctypes.Structure` per packet, `_pack_ = 1`,
   mirroring the C struct field-for-field:

   | MID | Struct to mirror | Source |
   |---|---|---|
   | `0x0944` | `Generic_ADCS_AC_Tlm_t` + nested `Bdot` / `Sunsafe` / `Inertial` | `components/generic_adcs/fsw/cfs/src/generic_adcs_msg.h:226-283` |
   | `0x0942` | `Generic_ADCS_AD_Tlm_t` + nested `Mag` / `Sol` / `Imu` / `ST` | same file, `:141-182` |
   | `0x08C8` / `0x08C9` | `CAM_Hk_tlm_t` / `CAM_Exp_tlm_t` | `components/arducam/fsw/cfs/src/cam_msg.h` |
   | `0x08FC` / `0x08FD` | `SYN_Hk_tlm_t` / `SYN_Device_tlm_t` | `components/syn/fsw/cfs/src/syn_msg.h` |
   | `0x08B0` | `CF_HkPacket_t` | `fsw/apps/cf/fsw/inc/` |
2. **`components/onair/nos3_security_tlm.json`** — three edits that must stay in step:
   `channels` (MID → `[prefix, struct]`), `order` (the new column names, which set CSV column
   order), and `subsystems` (each new column assigned to `GNC` / `CDH` / `POWER` / `COMM`).
3. **Deploy** — sync to `fsw/build/exe/cpu1/cf/onair/`, restart OnAIR.

**Budget, checked:** `CFE_SBN_CLIENT_MAX_MSG_IDS_PER_PIPE` is **48**
(`fsw/apps/sbn_client/fsw/src/sbn_client_defs.h:24`) and we subscribe **37**. All nine
candidates fit in the 11 free slots, so unlike `AINOS3-70` this needs **no `sbn_client.so`
rebuild**. The CSV goes 382 → roughly 485 columns.

⚠ **Validate before trusting.** `AINOS3-70` subscribed 16 MIDs and three came back all-zero.
Run a nominal soak and check each new column is non-constant with
`training/audit_dead_columns.py` before any of it reaches a model.

⚠⚠ **Measured 2026-08-25 — and the earlier version of this warning had it backwards.**
This section previously claimed every subscription *raises* the frame rate. It does not.
`components/onair/training/measure_frame_rate.py` on the deployed stack:

| | |
|---|---|
| messages arriving | **20.3 /s** across 33 live MIDs |
| frames emitted | **5.5 /s** |
| ratio | **27 %** |

OnAIR is **compute-bound, not arrival-bound**: `onair/src/run_scripts/sim.py` has no rate
limiter, so 5.5 Hz is the processing ceiling of the plugin chain. Three consequences, and
the third is the one that matters:

- **Subscribing more MIDs will not raise the frame rate.** The projected arrival increase
  for `0x0942` + `0x0944` is +2.0 msg/s (+9.8 %) — they publish at **1.0 /s** each, the
  ADCS send-path rate, not the 10 Hz implied elsewhere. The fastest single MID on the bus
  is `NOVATEL` `0x0871` at 3.6 /s.
- **The risk inverts: the rate can *fall*.** Adding ~103 columns to a 359-column frame is
  ~29 % more per-frame work in the struct walk and the CSV write, and on a compute-bound
  loop that lowers frames/s directly. So the re-baseline of `AINOS3-92`'s Hz and of the
  rate-derived thresholds (rule-gate **R2**, the **staleness** gate's advance-interval
  discovery) is still mandatory — for the opposite reason to the one first given.
- **⚠ 73 % of messages never surface as their own frame.** They are overwritten in the
  write buffer before it is read. This is pre-existing, not caused by any change here, but
  it means the staleness gate's "average advance interval" is measuring **OnAIR's loop
  rate, not the FSW's publish rate**, and any threshold expressed per-frame inherits that.
  Worth a ticket of its own.

⚠⚠ **Four subscribed MIDs deliver nothing** — `CFE_SB_SUBS` `0x080D`, `SBN` `0x08DC`,
`RADIO_DEV` `0x0931`, `ST_DEV` `0x0936`. Dead subscriptions are easy to mistake for inert
fields: **`AINOS3-91` was opened against "5 constant `ST_DEV` star-tracker fields", and the
cause is that the packet never arrives at all.** That ticket can be re-scoped or closed on
this evidence.

⚠⚠ **A subscribed column is not necessarily a recorded one.** 23 of the 382 in `order`
never reach the CSV — the format-v2 prune drops non-numeric and static-version fields. They
are still in the frame, so a live rule-gate rule can read them, but nothing trained on the
corpus can. `sparta_logging_gap.py` now hard-fails on any recommendation that leans on a
silent MID or a pruned column; that check moved six rows, two of them from `PARTIAL` to
`NO`.

### B — scheduler table · needs an FSW table rebuild

Four of the original twelve leads (`0x080A` SB stats, `0x080B` ES app, `0x080C` table registry,
`0x080E` one-subscription) are **command-response** packets. `to_config.c` already routes
them; `cfg/nos3_defs/tables/sch_def_msgtbl.c` + `sch_def_schtbl.c` do not request them, so
they never appear periodically. Adding the rows is table configuration, not code.

⚠ Like stage A, it raises the frame rate — see the boxed warning above, which applies to
every subscription, not just this stage. Do it **before** a corpus rebuild or not at all.

### C — a derived feature that needs no subscription

`components/onair/training/features.py` (and the plugin's feature path): convert
`NOVATEL.Novatel_oem615.Weeks` / `SecondsIntoWeek` / `Fractions` to epoch seconds and
difference it against `CFE_TIME.SecondsMET + SecondsSTCF`. Both operands are already in
every frame. This is the `GN&C` sheet's "time interval discrepancy", and it targets
`EX-0014.01`, `EX-0014.04` and `EX-0016` at the cost of one derived column.

### D — FSW apps to build · the largest item, and not this ticket's

Vendor and build `cs`, `hs`, `mm`, `md` (and `hk`). They are stock NASA cFS apps, they are
already listed in `cfg/nos3_defs/cpu1_cfe_es_startup.scr`, and `sch_def_msgtbl.c` already
requests their housekeeping — there is simply no `.so` in `fsw/build/exe/cpu1/cf/`. `cs`
alone answers six **High**-rated integrity rows against our single recorded checksum.

### E — verdict text to modify · documentation only

Six `REVIEW` entries in **`app/gen_nos3_coverage.py`** state a rationale the workbook
contradicts or narrows: `EX-0001.01`, `EX-0006`, `PER-0004`, `EX-0012.11`, `DE-0003.11`,
`EX-0012.01`, plus the `EX-0012.13` drift half. See `AC4` for what each should say instead.

⚠ These are **re-open flags, not verdict flips**. No cell should turn green on a document —
each needs a live test first, which is what the receiving tickets are for.

### What this document argues against doing

Subscribing all twelve — and the outcome vindicated that caution: of the twelve, only three survived verification. `AINOS3-88` already returned a NULL on "more recorded telemetry",
and nothing here overturns it. **Lead 1 (`0x0944`) is the only one argued for on this
spike's own evidence**; the rest are inventory, to be spent when a measurement justifies
them.

---

## `AC5` — what this feeds

This document subscribes nothing. It hands three things onward.

- **`AINOS3-69` (observability constraint).** The finding is that the constraint is
  **sharper than "we need more telemetry"**. 42 of 81 unmet recommendations have no target in
  NOS3 at all, and 15 more ask for a sender identity the cFS bus structurally cannot provide.
  The genuinely actionable surface proved to be **3 MIDs, not 12** — and only one of them —
  `GENERIC_ADCS_AC_MID` `0x0944` — is argued for on this document's own evidence.
- **`AINOS3-87` (`EX-0012.09` EPS switch is caught by nothing).** The `EPS` sheet answers
  that ticket's negative branch. The workbook's named EPS detection signal is **change in
  power consumption**, baselined BOL/EOL with upper and lower limits. `GENERIC_EPS_Hk_tlm_t`
  carries **five voltages and zero currents**. A switch toggle therefore cannot move a
  consumption feature, because the schema has none — which turns the measured −0.4 ± 0.1 IF
  lift from "we could not find an observable" into a structural explanation, and makes
  "reclassify as UNSUBSCRIBED, naming the missing field" the well-evidenced branch.
- **`AINOS3-86` (INERTIAL 33.6 % false alarms)** gets lead 1 above: the INERTIAL
  controller's own gains and error state (`Kp`, `Kr`, `Ki`, `phiErr_max`, `therr`,
  `sumtherr`, `werr`, `qErr`) are published on `0x0944` and unsubscribed.

One further lead falls out of the `GN&C` sheet and costs **no new subscription at all**:
the sheet asks for *"time interval discrepancy"* as a GPS spoof indicator, and we already
record GPS time (`NOVATEL.Weeks`, `SecondsIntoWeek`, `Fractions`) and FSW time
(`CFE_TIME.SecondsMET`, `SecondsSTCF`) **in the same frame without ever comparing them**. A
GPS-vs-MET divergence feature is a derived column over data we already have, targeting
`EX-0014.01`, `EX-0014.04` and `EX-0016`. It is the cheapest thing this spike found.

### Consistency, the other half of the ticket

The ticket's first stated payoff was normalising our own logging against an external
standard rather than an invented one. `Content of Log Records` gives that standard in seven
fields. Measured against it, our CSV frame supplies **Time** (`CFE_TIME`) and **Effect**
(the field values) well, **Type of Event** only through a detector's own labelling, and
supplies **Location/Device**, **Source**, **Identity** and **Rule ID** not at all — except
that the rule-gate's `rule=label` output *is* a Rule ID, which is the one place our design
already matches the standard. This is not a defect to fix inside the CSV; it is the reason
the **incident** record, not the frame, is the right place to carry audit fields. Noted for
`AINOS3-98` rather than actioned here.
