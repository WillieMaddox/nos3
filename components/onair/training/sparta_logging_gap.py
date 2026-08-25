#!/usr/bin/env python3
"""Cross-reference SPARTA's logging best practices against what we record (AINOS3-95).

Consumes `extract_logging_workbook.py`'s JSON and answers, per recommendation:
do we record it, and if not, what would carry it. The mapping itself is a
JUDGEMENT and lives in `RECS` below — the same "encoded source of truth"
pattern `app/gen_nos3_coverage.py` uses — but three things are MACHINE-CHECKED
so the judgement cannot silently rot:

1. **Coverage.** Every distinct indicator-of-compromise string in the workbook's
   13 subsystem sheets is claimed by exactly one `RECS` entry. A new workbook
   revision that adds a row fails the run instead of being quietly dropped.
2. **Field existence.** Every schema column named in a `ours=` list must exist in
   `nos3_security_tlm.json`. A column pruned by a future schema change fails here.
3. **Verdict consistency.** `YES` needs at least one recorded field; `NO` must
   name none; every non-`YES` needs a bucket.

`AC4` — techniques we call out-of-scope / UNSUBSCRIBED that the workbook says
*are* loggable — is derived by reading `app/gen_nos3_coverage.py`'s own dicts, so
it tracks that file rather than restating it.

Run:
    python3 components/onair/training/sparta_logging_gap.py \\
        [--json data/sparta/logging_workbook.json] [--markdown out.md]
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCHEMA = os.path.join(ROOT, "components/onair/nos3_security_tlm.json")
COVERAGE_GEN = os.path.join(ROOT, "app/gen_nos3_coverage.py")
DEFAULT_JSON = os.path.join(ROOT, "data/sparta/logging_workbook.json")

# Measured on the deployed stack 2026-08-25 by `measure_frame_rate.py` and a
# header diff against a live CSV. Both are ways a column can be *subscribed* and
# still never reach the recorded corpus, and both are easy to mistake for a
# field that is present but uninformative:
#
#   SILENT_MIDS  - subscribed, but zero traffic in a 90 s window. Dead
#                  subscriptions. `ST_DEV` is the cautionary one: AINOS3-91 was
#                  opened against "5 constant star-tracker fields", and the cause
#                  is that the packet never arrives at all.
#   PRUNED_COLS  - parsed into the frame (so a live plugin CAN read them) but
#                  dropped from the CSV by the format-v2 column prune, which
#                  removes non-numeric and static-version fields. Nothing trained
#                  on the corpus can ever use these.
SILENT_MIDS = {"CFE_SB_SUBS", "SBN", "RADIO_DEV", "ST_DEV"}
PRUNED_COLS = {
    "CFE_ES.CFECoreChecksum", "CFE_TBL.LastValTableName", "CFE_TBL.LastUpdatedTable",
    "CFE_TBL.LastFileLoaded", "CFE_TBL.LastFileDumped", "CFE_TBL.LastTableLoaded",
    "CFE_EVS.PacketID.AppName", "CFE_EVS.Message",
}

# verdict: YES (recorded) | PARTIAL (inconsistently — a proxy, not the recommended
#          content) | NO (not recorded)
# bucket:  SUBSCRIBABLE_NOW (a MID already on this build's bus carries it)
#          NEEDS_FSW        (an app/field this build does not provide)
#          NOT_MODELLED     (NOS3 models no such hardware or layer)
# `key` is a unique prefix of the workbook's indicator-of-compromise text.
# `key` is a unique PREFIX of the workbook's text, so for the families that repeat
# once per subsystem sheet it is deliberately short ("Access to "). `label` gives
# those rows a readable name in the emitted table; it defaults to the key.
REC = collections.namedtuple(
    "REC", "rid key verdict bucket ours carrier note label")


def R(rid, key, verdict, bucket="", ours=(), carrier="", note="", label=""):
    return REC(rid, key, verdict, bucket, list(ours), carrier, note, label or key.strip())


RECS = [
    # ── Cross-subsystem themes (repeated on most of the 13 subsystem sheets) ──
    R("GEN-CFG", "Modification of hardware configuration key-value pairs",
      "PARTIAL", "NEEDS_FSW",
      ["CFE_TBL.CommandCounter", "CFE_TBL.TableUpdateCount", "CFE_TBL.TableUpdateChanged",
       "EPS.CommandCount", "ADCS_HK.CommandCount", "RW.CommandCounter"],
      "MM (Memory Manager) / MD (Memory Dwell) — in the startup script, NOT in the build",
      "We see THAT a config-touching command landed (the R6-R14 counter family); we never "
      "see the register or the new value the workbook asks for. The 12 sheets that repeat "
      "this row make it the single most-recommended log source in the workbook."),
    R("GEN-ACCESS-IN", "Access to ", "NO", "NEEDS_FSW", [],
      "no cFS analogue — the Software Bus is anonymous publish/subscribe",
      "Recurs once per subsystem sheet and asks for `source subsystem`. cFS HK packets "
      "carry no sender identity, so this whole family is structurally unanswerable here — "
      "the same wall AINOS3-72 hit. Counts once per sheet in the workbook, once here.", label="Access to a subsystem acquired from another subsystem"),
    R("GEN-ACCESS-OUT", "Access from ", "NO", "NEEDS_FSW", [],
      "no cFS analogue — see GEN-ACCESS-IN", "Mirror of GEN-ACCESS-IN (`target subsystem`).", label="Access from a subsystem out to another subsystem"),
    R("GEN-COMM", "Communication to ", "NO", "NEEDS_FSW",
      [], "CFE_SB_ONESUB_TLM 0x080E (subscription changes) — routed by TO, no SCH entry",
      "Asks for messages ADDRESSED to a subsystem, excluding broadcast — a distinction cFS "
      "pub/sub does not make. `CFE_SB_SUBS` is subscribed but reads [0] (known-unobservable).", label="Messages addressed to a subsystem (not broadcast)"),
    R("GEN-SIGANOM", "Critical ", "YES", "",
      ["CSS.DeviceEnabled", "FSS.DeviceEnabled", "IMU.DeviceEnabled", "MAG.DeviceEnabled",
       "ST.DeviceEnabled", "THRUSTER.DeviceEnabled", "TORQUER.DeviceEnabled",
       "NOVATEL_HK.DeviceEnabled", "RW.DeviceEnabled_RW0",
       "CSS.DeviceErrorCount", "IMU.DeviceHK.DeviceStatus"],
      "", "The one recommendation family our stack was built for: rule-gate R1 "
      "(DeviceEnabled drop) plus the per-mode dynamics IF. Covers the 'critical <subsystem> "
      "signal anomalies' row on every sheet that has one.", label="Critical subcomponent signal anomalies"),
    R("GEN-TEMPLIM", "Change in temperature set limits", "NO", "NEEDS_FSW",
      [], "CFE_TBL_REG_TLM 0x080C (per-table CRC) — routed by TO, no SCH entry",
      "11 sheets ask for it. We record three EPS temperature VALUES; no subsystem exposes "
      "its LIMITS. LC watchpoint thresholds live in a table we see only as a counter."),
    R("GEN-CTRLLOGIC", "Change in control logic", "YES", "",
      ["ADCS_GNC.Hmgmt.Kb", "ADCS_GNC.Hmgmt.b_range", "ADCS_GNC.MaxMcmd", "ADCS_GNC.DT",
       "ADCS_AC.Bdot.Kb", "ADCS_AC.Bdot.b_range", "ADCS_AC.Sunsafe.Kp", "ADCS_AC.Sunsafe.Kr",
       "ADCS_AC.Sunsafe.vmax", "ADCS_AC.Inertial.Kp", "ADCS_AC.Inertial.Kr",
       "ADCS_AC.Inertial.Ki", "ADCS_AC.Inertial.phiErr_max", "CFE_TBL.CommandCounter"],
      "", "10 sheets ask for it, rated High on the ADCS/GN&C sheets. ✅ CLOSED 2026-08-25 by "
      "subscribing GENERIC_ADCS_AC_MID 0x0944 (AINOS3-95 stage 2a): every controller's gain "
      "set is now recorded, and a gain is constant in nominal so a change is the signal. "
      "⚠ Recorded but NOT yet ruled on — no detector watches these fields "
      "(ticket `detect-adcs-gain-change`).", label="Change in control logic/algorithms (gains, constants)"),
    R("GEN-DETLOGIC", "Change in determination logic", "PARTIAL", "NEEDS_FSW",
      ["ADCS_GNC.qValid", "ADCS_GNC.SunValid", "ADCS_DI.Payload.St.valid",
       "ADCS_AD.Sol.FssValid", "ADCS_AD.ST.Valid", "ADCS_AD.Imu.alpha",
       "ADCS_AD.Imu.wbn_prev"],
      "the determination ALGORITHM parameters — only its outputs and validity flags exist",
      "Improved 2026-08-25 by subscribing GENERIC_ADCS_AD_MID 0x0942 (stage 2a): per-sensor "
      "determination outputs and the IMU filter coefficient are now recorded. The stage's "
      "own parameters still are not.", label="Change in determination logic/algorithms"),
    R("EPS-LOADSHED", "Load shedding", "PARTIAL", "NEEDS_FSW",
      ["EPS.DeviceHK.Switch", "EPS.CommandCount", "ADCS_GNC.Mode"],
      "no per-switch load/current telemetry in the EPS sim",
      "The switch bitfield and the spacecraft mode are recorded; the 'affected "
      "subsystems/components and command trigger' are not. Directly relevant to AINOS3-87."),
    R("EPS-RESET", "Power reset", "PARTIAL", "NEEDS_FSW",
      ["CFE_ES.ProcessorResets", "CFE_ES.ResetType", "CFE_ES.ResetSubtype",
       "CFE_ES.MaxProcessorResets"],
      "no per-device power-reset counter", "Processor-level resets are recorded; "
      "device-level power cycling is not."),
    R("EPS-PWRON", "Power-on commands", "PARTIAL", "NEEDS_FSW",
      ["EPS.CommandCount", "EPS.CommandErrorCount"],
      "no command-argument telemetry",
      "The counter ticks; which component was powered on does not appear."),
    R("EPS-PWRDRAW", "Change in power consumption characteristics", "NO", "NEEDS_FSW",
      [], "no current/power field anywhere in GENERIC_EPS_Hk_tlm_t",
      "⚠ AINOS3-87's most useful single row. The workbook's named EPS detection signal is "
      "CHANGE IN POWER CONSUMPTION with BOL/EOL baselining and upper/lower limits. We "
      "record five VOLTAGES and zero currents, so a switch toggle cannot move a "
      "consumption feature — there is none. Explains the measured -0.4 IF lift structurally, "
      "rather than leaving it as 'we could not find an observable'."),
    # ── ADCS / GN&C (feed AINOS3-86, AINOS3-91) ──────────────────────────────
    R("ADCS-INTRA-ACCESS", "Unusual access from one ADCS subcomponent", "NO", "NEEDS_FSW",
      [], "no sender identity — see GEN-ACCESS-IN", "IA-0011. Same anonymity wall."),
    R("ADCS-INTRA-COMM", "Abnormal communication among ADCS subcomponents", "NO", "NEEDS_FSW",
      [], "no sender identity — see GEN-ACCESS-IN", "IA-0011."),
    R("ADCS-SENSORS", "Critical ADCS sensors signal anomalies", "YES", "",
      ["ADCS_DI.Payload.Mag.bvb", "ADCS_DI.Payload.Fss.svb", "ADCS_DI.Payload.Css.svb",
       "ADCS_DI.Payload.Imu.wbn", "ADCS_DI.Payload.St.q", "MAG_DEV.Generic_mag.MagneticIntensityX",
       "FSS_DEV.Generic_fss.Alpha", "CSS_DEV.Generic_css.Voltage"],
      "", "Sensor-level values plus their validity flags — well covered."),
    R("ADCS-ACTUATORS", "Critical ADCS actuators signal anomalies", "YES", "",
      ["ADCS_DO.Rw.Tcmd", "ADCS_DO.Trq.Mcmd", "RW.data.momentum", "TORQUER.TrqInfo",
       "TORQUER.TorquerPeriod", "THRUSTER.DeviceEnabled"],
      "", "Actuator commands and momentum are recorded (rule-gate R1 + dynamics IF)."),
    R("ADCS-STARMAP", "Change to star maps/catalogs", "NO", "NOT_MODELLED",
      [], "the NOS3 star-tracker sim publishes a quaternion; there is no catalog to modify",
      "Related to AINOS3-91 (star-tracker inert fields): the modelled ST surface is small "
      "enough that this High-impact recommendation has no target."),
    R("GNC-BURN", "Change to burn plan", "PARTIAL", "NOT_MODELLED",
      ["SC.AtsNumber", "SC.RtsNumber", "SC.AppendLoadCount", "SC.AtsCmdCtr"],
      "no burn planner in NOS3",
      "The closest analogue is the stored-command engine, which IS well recorded."),
    R("GNC-EPHEM", "Change to ephemerides", "YES", "",
      ["NOVATEL.Novatel_oem615.ECEFX", "NOVATEL.Novatel_oem615.ECEFY",
       "NOVATEL.Novatel_oem615.ECEFZ", "NOVATEL.Novatel_oem615.lat",
       "NOVATEL.Novatel_oem615.lon", "NOVATEL.Novatel_oem615.alt"],
      "", "Recorded as values, so a change is directly visible — this is the DE-0003.10 "
      "detection we already publish."),
    R("GNC-GPSJAM", "GPS message jamming/spoofing", "PARTIAL", "NEEDS_FSW",
      ["NOVATEL.Novatel_oem615.Weeks", "NOVATEL.Novatel_oem615.SecondsIntoWeek",
       "NOVATEL.Novatel_oem615.Fractions", "CFE_TIME.SecondsMET", "CFE_TIME.SecondsSTCF",
       "RADIO_HK.DeviceHK.ProxSignal"],
      "no signal-power / centre-frequency / bandwidth field on the GPS receiver",
      "⚠ Best free lead in the workbook. It asks for BOTH signal power (we have none) AND "
      "'time interval discrepancy' — and we already record GPS time and FSW time in the "
      "same frame without ever comparing them. A GPS-vs-MET divergence feature costs no "
      "new subscription and targets EX-0014.01/.04 and EX-0016."),
    # ── C&DH: the largest sheet, and the one NOS3 actually models ────────────
    R("CDH-MEMPOKE", "Memory pokes/loads", "PARTIAL", "NEEDS_FSW",
      ["CFE_TBL.CommandCounter", "CFE_TBL.FileLoadCount", "CFE_TBL.TableLoadCount",
       "CFE_TBL.FileLoadChanged", "CFE_TBL.TableLoadChanged"],
      "MM app — requested by the scheduler, absent from the build",
      "⚠ Downgraded 2026-08-25. Table loads are recorded as COUNTS only: the three "
      "name fields the workbook actually asks for (`LastFileLoaded`, `LastTableLoaded`, "
      "`LastUpdatedTable`) are parsed into the frame but PRUNED from the CSV, so a live "
      "rule can read them and no trained model ever can. What survives in the corpus is "
      "the AINOS3-30 derived change-flags — which that ticket measured as constant 0. "
      "Raw memory pokes have no carrier at all.", label="Memory pokes/loads and related commands"),
    R("CDH-MEMPEEK", "Memory peeks/dumps that reveal any C&DH", "NO", "NEEDS_FSW",
      [], "MM/MD apps — absent from the build",
      "⚠ Downgraded PARTIAL → NO 2026-08-25. `CFE_TBL.LastFileDumped` is parsed but "
      "PRUNED from the CSV, so nothing about a dump reaches the corpus. Memory dwells "
      "have no carrier at all.", label="Memory peeks/dumps revealing C&DH configuration"),
    R("CDH-WDT", "Suspension or changes to watchdog services", "NO", "NEEDS_FSW",
      [], "HS (Health & Safety) app — requested by the scheduler (HS_SEND_HK_MID), absent from the build",
      "⚠ AC4. EX-0012.11 / DE-0003.11 are published OUT-OF-SCOPE on 'no HS app'. That is "
      "true of the BUILD, not of the design: `cfe_es_startup.scr` loads `hs`, and the SCH "
      "table already requests its housekeeping — there is simply no `hs.so`. The workbook "
      "rates this Medium and names exactly what to log."),
    R("CDH-CODEFLAW", "Exploiting code flaws or backdoors", "PARTIAL", "SUBSCRIBABLE_NOW",
      ["ADCS_GNC.Mode", "CFE_ES.HeapBytesFree", "CFE_ES.HeapBlocksFree",
       "CFE_ES.HeapMaxBlockSize", "CFE_ES.SysLogEntries", "CFE_EVS_HK.MessageSendCounter"],
      "CFE_ES_APP_TLM 0x080B / CFE_ES_MEMSTATS 0x0810 — routed by TO, no SCH entry",
      "Four of the five named signals are recorded (mode change, unusual commands, "
      "telemetry-rate change via the staleness gate, memory). CPU utilisation is the miss.", label="Exploiting code flaws or backdoors (off-nominal behaviour)"),
    R("CDH-GOLDEN", "Changes to or corruption of default (golden)", "NO", "NEEDS_FSW",
      [],
      "CS (Checksum) app — requested by the scheduler (CS_SEND_HK_MID), absent from the build",
      "⚠ Downgraded PARTIAL → NO 2026-08-25, and this is the sharpest correction in the "
      "table. `CFE_ES.CFECoreChecksum` is subscribed but PRUNED from the CSV, so the "
      "recorded corpus contains **no integrity data of any kind** — not one checksum. The "
      "workbook asks for actual-vs-expected hashes on six separate High-rated rows. This "
      "is the strongest single argument for building the CS app.", label="Corruption of golden software/firmware images"),
    R("CDH-AUTHZ", "Changes to user/application authentication", "NO", "NOT_MODELLED",
      [], "CryptoLib is a CFE_LIB with zero Software Bus telemetry",
      "DE-0004 / DE-0006 / EX-0003. Consistent with our published rationale.", label="Changes to authentication/authorization policies, whitelists"),
    R("CDH-TRUSTZONE", "Changes to trust zone boundary definitions", "PARTIAL", "SUBSCRIBABLE_NOW",
      ["CFE_SB.CommandCounter", "CFE_SB.SubscribeErrorCounter",
       "CFE_SB.DuplicateSubscriptionsCounter", "CFE_SB.NoSubscribersCounter"],
      "CFE_SB_STATS_TLM 0x080A + CFE_SB_ONESUB_TLM 0x080E — routed by TO, no SCH entry",
      "EX-0012.04. Route changes reach us today only as a counter tick (R6) or a 30-50 s "
      "staleness latch; SB stats would carry per-pipe depth directly.", label="Changes to trust-zone boundaries / pub-sub messaging services"),
    R("CDH-CERTS", "Changes to user, device, or application certificates", "NO", "NOT_MODELLED",
      [], "CryptoLib — no SB telemetry", ""),
    R("CDH-ENCSTORE", "Suspension or changes to encrypted storage", "NO", "NOT_MODELLED",
      [], "no encrypted-storage service in this build", ""),
    R("CDH-FMS", "Suspension or changes to fault management services", "YES", "",
      ["LC.CurrentLCState", "LC.WPsInUse", "LC.ActiveAPs", "LC.WPResults", "LC.APResults",
       "LC.RTSExecCount", "CFE_EVS_HK.CommandCounter", "SC.RtsDisabledStatus",
       "ADCS_GNC.Mode"],
      "", "Our strongest alignment with the workbook: every named element (limit checking, "
      "command scripts, event messages, mode definitions) has a recorded field, and rule-gate "
      "R5/R7/R14 already fire on them. High impact in the workbook, covered here."),
    R("CDH-CPU", "CPU utilization is abnormally high", "NO", "SUBSCRIBABLE_NOW",
      [], "CFE_ES_APP_TLM 0x080B (per-app ExecutionCounter) — routed by TO, no SCH entry",
      "Needs a scheduler-table row to become periodic; that is configuration, not code."),
    R("CDH-CMDCTR", "Mismatch in command counter between ground", "PARTIAL", "NEEDS_FSW",
      ["CI.usCmdCnt", "CI.usCmdErrCnt", "TO.usCmdCnt", "CFE_ES.CommandCounter",
       "CFE_SB.CommandCounter", "CFE_EVS_HK.CommandCounter", "CFE_TBL.CommandCounter",
       "CFE_TIME.CommandCounter"],
      "the GROUND-side counter — held by COSMOS, never joined to the telemetry stream",
      "⚠ AC4. EX-0001.01 is published OUT-OF-SCOPE because 'replayed commands are "
      "byte-identical to legitimate ones'. The workbook does not propose separating the "
      "bytes — it proposes RECONCILING the spacecraft counter against the ground's own "
      "count. We hold every spacecraft-side counter already; the missing half is a join, "
      "not a MID.", label="Mismatch in command counter between ground and spacecraft"),
    R("CDH-RESET", "Any type of reset", "YES", "",
      ["CFE_ES.ProcessorResets", "CFE_ES.ResetType", "CFE_ES.ResetSubtype",
       "CFE_ES.MaxProcessorResets", "CSS.DeviceCount", "IMU.DeviceHK.DeviceCounter"],
      "", ""),
    R("CDH-VIRT-ESC", "Virtualization/ containerization escapes", "NO", "NOT_MODELLED",
      [], "cFS runs as one process; no VM/container layer inside the FSW", "LM-0005.", label="Virtualization/containerization escapes"),
    R("CDH-VIRT-BUILD", "Virtualization/ containerization changes to init", "NO", "NOT_MODELLED",
      [], "see CDH-VIRT-ESC", "", label="Container changes to initialization/build files"),
    R("CDH-DENIALS", "Resource/ trust zone access denials", "PARTIAL", "NEEDS_FSW",
      ["CFE_SB.MsgSendErrorCounter", "CFE_SB.MsgReceiveErrorCounter",
       "CFE_SB.PipeOverflowErrorCounter", "CFE_SB.MsgLimitErrorCounter",
       "CFE_SB.InternalErrorCounter"],
      "no requester identity — see GEN-ACCESS-IN",
      "Denials are counted (rule-gate R3); who was denied is not recorded."),
    R("CDH-TBLSVC", "Unauthorized access or changes to table services", "YES", "",
      ["CFE_TBL.CommandCounter", "CFE_TBL.CommandErrorCounter", "CFE_TBL.NumLoadPending",
       "CFE_TBL.ValidationCounter", "CFE_TBL.LastValCrc", "CFE_TBL.TableUpdateCount"],
      "", "EX-0012.02; rule-gate R9. `LastValCrc` even satisfies the hash half."),
    R("CDH-CRITCMD", "Any critical command", "PARTIAL", "NEEDS_FSW",
      ["SC.AtsCmdCtr", "SC.RtsCmdCtr", "THRUSTER.CommandCount"],
      "no command source/identity — see GEN-ACCESS-IN",
      "Critical commands are counted; 'source of command' is not available."),
    R("CDH-FLIGHTRULES", "Changes to flight rules", "PARTIAL", "NEEDS_FSW",
      ["LC.WPsInUse", "LC.ActiveAPs", "LC.CurrentLCState"],
      "the watchpoint/actionpoint table CONTENTS — only counts are telemetered",
      "LC is the flight-rules engine, so the shape is right; the new values are not there."),
    R("CDH-SBSVC", "Unauthorized access or changes to software bus services", "YES", "",
      ["CFE_SB.CommandCounter", "CFE_SB.NoSubscribersCounter", "CFE_SB.MsgSendErrorCounter",
       "CFE_SB.PipeOverflowErrorCounter", "CFE_SB.MsgLimitErrorCounter"],
      "", "EX-0013.01/.02, EX-0014.02, LM-0002 — rule-gate R6/R10 plus the "
      "consistency-check gate. Well covered by `CFE_SB.*`. ⚠ The two `SBN.*` fields "
      "originally credited here were dropped 2026-08-25: MID 0x08DC is subscribed but "
      "delivers nothing."),
    R("CDH-CLOCK", "Unauthorized access or changes to clock services", "YES", "",
      ["CFE_TIME.CommandCounter", "CFE_TIME.ClockStateFlags", "CFE_TIME.ClockStateAPI",
       "CFE_TIME.LeapSeconds", "CFE_TIME.SecondsSTCF", "CFE_TIME.SubsecsSTCF"],
      "", "EX-0012.12. Settings, bias (STCF) and command activity are all recorded."),
    R("CDH-APPEXIT", "Any application exit", "PARTIAL", "SUBSCRIBABLE_NOW",
      ["CFE_ES.RegisteredExternalApps", "CFE_ES.RegisteredCoreApps", "CFE_ES.RegisteredTasks"],
      "CFE_ES_APP_TLM 0x080B — which app, rather than how many",
      "An exit drops a recorded count, so the event is visible; the identity is not."),
    R("CDH-LOGSVC", "Unauthorized access or changes to logging services", "YES", "",
      ["CFE_EVS_HK.LogEnabled", "CFE_EVS_HK.LogMode", "CFE_EVS_HK.LogFullFlag",
       "CFE_EVS_HK.LogOverflowCounter", "CFE_EVS_HK.MessageSendCounter",
       "CFE_EVS_HK.MessageTruncCounter", "CFE_ES.SysLogMode", "CFE_ES.SysLogBytesUsed"],
      "", "DE-0002.03 / DE-0010 — rule-gate R2/R7 plus the staleness gate. High impact in "
      "the workbook, and one of our best-covered rows."),
    R("CDH-MLSVC", "Unauthorized access or changes to machine learning services",
      "NO", "NOT_MODELLED",
      [], "no on-board ML service in the FSW — OnAIR itself is the ML service",
      "⚠ Worth naming rather than dismissing: the workbook asks for training-data DRIFT "
      "monitoring, and the thing that would be monitored is our own corpus. That makes it "
      "an AINOS3-98 (corpus-integrity) item, not an FSW subscription item."),
    R("CDH-SCHED", "Unauthorized access or changes to scheduler services", "YES", "",
      ["SCH.CmdCounter", "SCH.ErrCounter", "SCH.SlotsProcessedCount", "SCH.SkippedSlotsCount",
       "SCH.BadTableDataCount", "SCH.TableVerifyFailureCount", "SCH.MissedMajorFrameCount",
       "SCH.ScheduleActivityFailureCount"],
      "", "EX-0008. 22 recorded columns — the most complete single service."),
    R("CDH-STOREDCMD", "Unauthorized access or changes to stored command services", "YES", "",
      ["SC.CmdCtr", "SC.CmdErrCtr", "SC.AtpState", "SC.NumRtsActive",
       "SC.RtsDisabledStatus", "SC.AtsCmdErrCtr"],
      "", "EX-0008.01/.02. 29 recorded columns."),
    R("CDH-TLMSVC", "Unauthorized access or changes to telemetry services", "YES", "",
      ["TO.usCmdCnt", "TO.usEnabledRoutes", "TO.usConfigRoutes", "TO.usMsgSubCnt",
       "TO.usTblUpdateCnt"],
      "", "Rule-gate R12/R13, delivered by AINOS3-72. The route masks are exactly the "
      "'changes to settings' the workbook asks for."),
    R("CDH-DIAGSVC", "Unauthorized access or changes to diagnostic services",
      "NO", "NOT_MODELLED", [], "no built-in self-test service in this build", ""),
    R("CDH-PKGSVC", "Unauthorized access or changes to data packaging services", "YES", "",
      ["DS.Payload.AppEnableState", "DS.Payload.DestTblLoadCounter",
       "DS.Payload.FilterTblLoadCounter", "DS.Payload.FileWriteCounter",
       "DS.Payload.DisabledPktCounter", "DS.Payload.FilteredPktCounter"],
      "", "EX-0014.03. DS carries both the settings and the throughput."),
    R("CDH-SCRIPTS", "Changes to stored command scripts", "PARTIAL", "NEEDS_FSW",
      ["SC.AppendLoadCount", "SC.AppendEntryCount", "SC.AppendByteCount", "SC.AtsNumber"],
      "CS app — for the script hashes the workbook asks for",
      "Loads are counted; contents and hashes are not.", label="Changes to stored command scripts (ATS/RTS, hashes)"),
    R("CDH-BIST", "Changes to built-in self-tests", "NO", "NOT_MODELLED",
      [], "no BIST service in this build", ""),
    R("CDH-MEMPERF", "Memory performance issues", "YES", "",
      ["CFE_ES.HeapBytesFree", "CFE_ES.HeapBlocksFree", "CFE_ES.HeapMaxBlockSize",
       "CFE_ES.SysLogBytesUsed", "CFE_ES.SysLogEntries", "CFE_ES.ERLogEntries",
       "CFE_ES.ERLogIndex", "CFE_SB.MemInUse", "CFE_SB.UnmarkedMem"],
      "", "DE-0010 — rule-gate R2. Utilisation, the exception log and the syslog are all "
      "recorded."),
    R("CDH-MEMMGMT", "Unauthorized access or changes to memory management services",
      "NO", "NEEDS_FSW", [], "MM app — requested by the scheduler, absent from the build", ""),
    # ── TT&C ─────────────────────────────────────────────────────────────────
    R("TTC-MEMPEEK", "Memory peeks/dumps that reveal any TT&C", "NO", "NOT_MODELLED",
      [], "the radio sim exposes no memory interface", "", label="Memory peeks/dumps revealing TT&C configuration"),
    R("TTC-REDUNDANT", "Communication with a redundant TT&C component", "NO", "NOT_MODELLED",
      [], "NOS3 models one radio; there is no redundant transponder", "IA-0004/.02."),
    R("TTC-FW", "Changes to or corruption of stored firmware images", "NO", "NOT_MODELLED",
      [], "no firmware layer in the radio or RF-payload sims",
      "IA-0002. The identical row appears on both `TT&C` and `Payload - RF`.", label="Corruption of stored firmware images / boot mechanisms"),
    R("TTC-RFCONFIG", "Changes to signal protocol parameters", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig", "RADIO_HK.CommandCount"],
      "the individual RF parameters — one opaque config word stands in for all of them",
      "This row and its nine siblings below (hopping, carrier, modulation, EDAC, router, "
      "encoding, off-nominal modes, TX power, AGC) all collapse onto a single recorded "
      "config word: a change is visible, WHICH parameter changed is not. DE-0002, "
      "EXF-0006/.01/.02, IMP-0002.", label="Changes to signal protocol parameters / message standards"),
    R("TTC-HOPPING", "Changes to frequency hopping", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig"], "see TTC-RFCONFIG", "", label="Changes to frequency-hopping characteristics"),
    R("TTC-CARRIER", "Changes to carrier frequency/waveform", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig"], "see TTC-RFCONFIG", ""),
    R("TTC-MODULATION", "Changes to modulation/demodulation", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig"], "see TTC-RFCONFIG", ""),
    R("TTC-EDAC", "Changes to error detection and correction", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig", "RADIO_HK.ForwardErrorCount"], "see TTC-RFCONFIG", "", label="Changes to error detection/correction algorithms"),
    R("TTC-ROUTER", "Changes to router configurations", "PARTIAL", "SUBSCRIBABLE_NOW",
      ["TO.usEnabledRoutes", "TO.usConfigRoutes"],
      "already covered on the TO side by R13; the radio side has no per-route field",
      "The one RF-config row we genuinely cover, because the routing happens in TO."),
    R("TTC-ENCODING", "Changes to bit encoding", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig"], "see TTC-RFCONFIG", "", label="Changes to bit encoding/decoding schemes"),
    R("TTC-OFFNOM", "Changes to off-nominal mode configurations", "PARTIAL", "NOT_MODELLED",
      ["RADIO_HK.DeviceHK.DeviceConfig", "ADCS_GNC.Mode"], "see TTC-RFCONFIG",
      "The spacecraft mode is recorded; the radio's own off-nominal configs are not."),
    R("TTC-TXPOWER", "Changes in transmission power levels", "NO", "NOT_MODELLED",
      [], "no transmit-power field in the radio sim", ""),
    R("TTC-AGC", "Changes to automatic gain control", "NO", "NOT_MODELLED",
      [], "no AGC field in the radio sim", "", label="Changes to automatic gain control settings"),
    R("TTC-GNDAUTH", "Changes to ground authentication", "NO", "NOT_MODELLED",
      [], "CryptoLib — no SB telemetry", "", label="Changes to ground authentication/authorization policies"),
    R("TTC-UPLINKSIG", "Abnormal uplink signal characteristics", "PARTIAL", "NEEDS_FSW",
      ["RADIO_HK.DeviceHK.ProxSignal", "RADIO_HK.ForwardErrorCount", "RADIO_HK.ForwardCount"],
      "SNR / power level / centre frequency — the radio sim telemeters none of them",
      "EX-0016.01, IMP-0002. `ProxSignal` is the only proxy and it is not an SNR. Confirms "
      "our published DE-0003.04 rationale from an external source."),
    R("TTC-LOGBEHAV", "Abnormal logging behaviors", "YES", "",
      ["CFE_EVS_HK.MessageSendCounter", "CFE_EVS_HK.LogOverflowCounter",
       "CFE_EVS_HK.LogFullFlag", "CFE_ES.SysLogEntries"],
      "", "The staleness gate plus rule-gate R2 are precisely this recommendation, built "
      "before we read the workbook."),
    R("TTC-KEYMGMT", "Changes to cryptographic key management", "NO", "NOT_MODELLED",
      [], "CryptoLib SADB — no SB telemetry", "PER-0004.", label="Changes to cryptographic key management/storage"),
    R("TTC-BYPASSCMD", "Any received bypass commands", "PARTIAL", "NEEDS_FSW",
      ["CI.usCmdCnt", "CI.usCmdErrCnt", "RADIO_HK.ForwardCount", "RADIO_HK.ForwardErrorCount"],
      "no command-opcode telemetry — only aggregate counters",
      "⚠ AC4. EX-0006 is published OUT-OF-SCOPE because the encryptor's STATE is internal "
      "to CryptoLib. The workbook asks for the COMMAND, not the state — and a command "
      "arriving is exactly the static-in-nominal counter signal rules R6-R13 are built on. "
      "The verdict deserves re-opening as a rule candidate, not as a subscription."),
    R("TTC-KEYCHGCMD", "Any received key change commands", "PARTIAL", "NEEDS_FSW",
      ["CI.usCmdCnt", "CI.usCmdErrCnt"], "no command-opcode telemetry — see TTC-BYPASSCMD",
      "⚠ AC4, same shape as TTC-BYPASSCMD (PER-0004)."),
    R("TTC-DISABLEENC", "Disable encryptor", "PARTIAL", "NEEDS_FSW",
      ["CI.usCmdCnt", "RADIO_HK.ForwardErrorCount"],
      "no command-opcode telemetry — see TTC-BYPASSCMD", "⚠ AC4, same shape (EX-0006).", label="Disable encryptor command"),
    R("TTC-GIMBAL", "Changes to gimbal control constants", "NO", "NOT_MODELLED",
      [], "no antenna gimbal in NOS3", ""),
    R("TTC-TRACKALG", "Changes to signal tracking algorithms", "NO", "NOT_MODELLED",
      [], "no signal-tracking model in the radio sim", ""),
    R("TTC-RFSWITCH", "Off-nominal activation/ deactivation of RF switches", "NO", "NOT_MODELLED",
      [], "no RF switch in the radio sim", ""),
    R("TTC-PA", "Changes to configuration parameters (if software controlled)",
      "NO", "NOT_MODELLED", [], "no power amplifier in the radio sim", "", label="Power-amplifier configuration parameters"),
    # ── SMS / TCS ────────────────────────────────────────────────────────────
    R("SMS-DOCK", "Unplanned docking", "NO", "NOT_MODELLED",
      [], "no docking mechanism in NOS3", "IA-0005.01/.02/.03, IA-0011, LM-0004."),
    R("TCS-CALTBL", "Change calibration tables", "NO", "NOT_MODELLED",
      [], "no thermal app in NOS3 — the whole TCS sheet has almost no target",
      "NOS3 records three EPS temperature values and models no heater, cooler, louver, "
      "radiator, thermistor or TEC. The TCS sheet is the clearest 'not modelled' verdict "
      "outside the payload sheets."),
    R("TCS-POLARITY", "Change in polarity", "NO", "NOT_MODELLED",
      [], "no thermoelectric cooler in NOS3", ""),
    # ── Payload ×5 ───────────────────────────────────────────────────────────
    R("PL-ACCESS-IN", "Access to payload is acquired", "NO", "NEEDS_FSW",
      [], "CAM_HK 0x08C8 needs cam-sim in the HEADLESS launch; SYN needs a simulator that "
      "does not exist",
      "⚠⚠ RETRACTED 2026-08-25 after live verification. An earlier revision of this row "
      "claimed NOS3 runs two payload apps that make the payload sheets 'subscribable now'. "
      "Both were subscribed, deployed, and delivered **0 packets in 90 s**. Cause: `cam-sim` "
      "launches ONLY under the GUI `make launch` (launch.sh:124, gnome-terminal), never "
      "under headless `make launch-quiet` — the mode every soak and corpus run uses; and "
      "`syn` has NO simulator at all (absent from launch.sh and nos3-simulator.xml). Both "
      "apps load and stay inert. General lesson: scheduled + downlinked + transmitted in "
      "source does NOT mean arriving at OnAIR — the sim must exist in the launch mode you "
      "actually run.", label="Access to payload acquired from another subsystem"),
    R("PL-ACCESS-OUT", "Access from payload to another sub-system", "NO", "NEEDS_FSW",
      [], "see PL-ACCESS-IN — both payload apps are inert in the headless pipeline",
      "IA-0006, LM-0001. Retracted with PL-ACCESS-IN."),
    R("PL-COMM", "Communication to payload from another subsystem", "NO", "NEEDS_FSW",
      [], "no sender identity — see GEN-ACCESS-IN", ""),
    R("PL-REDUNDANT", "Communication with a redundant payload component", "NO", "NOT_MODELLED",
      [], "no redundant payload in NOS3", ""),
    R("PL-SIGANOM", "Critical payload subcomponent signal anomalies", "NO", "NEEDS_FSW",
      [], "CAM_EXP 0x08C9 is initialised but never transmitted; SYN_DEV 0x08FD transmit is "
      "commented out (syn_app.c:172)",
      "Both candidate carriers were proven dead by source inspection, before the "
      "launch-mode problem is even reached."),
    R("PL-COLLECTREQ", "Changes to collection", "PARTIAL", "NEEDS_FSW",
      ["SC.AtsCmdCtr", "SC.RtsCmdCtr"], "the payload-side counter — CAM is inert headless (see PL-ACCESS-IN)",
      "Collection requests ride the stored-command engine, which IS recorded; only the "
      "payload-side confirmation is missing.", label="Changes to collection/allocation requests or stored scripts"),
    R("PL-FPA-CAL", "Change calibration tables/sequences", "NO", "NOT_MODELLED",
      [], "the arducam sim models no focal-plane array", ""),
    R("PL-LIGHTLIM", "Change in light/photodiode set limits", "NO", "NOT_MODELLED",
      [], "no iris/shutter model", ""),
    R("PL-CORRLOGIC", "Change in correction logic", "NO", "NOT_MODELLED",
      [], "no FPA correction stage", ""),
    R("PL-NOISEFLOOR", "Abnormal noise floor/saturation", "NO", "NOT_MODELLED",
      [], "no image content in the sim", ""),
    R("PL-HOTPIX", "Persistent hot/dead pixels", "NO", "NOT_MODELLED", [], "no FPA", ""),
    R("PL-PIXMARK", "Pixels marked/unmarked", "NO", "NOT_MODELLED", [], "no FPA", "", label="Pixels marked/unmarked as hot/dead"),
    R("PL-EXPOSURE", "Changes in exposure settings", "NO", "NOT_MODELLED",
      [], "the arducam experiment commands select a size, not an exposure", ""),
    R("PL-RF-USERAUTH", "Changes to user authentication and authorization policies",
      "NO", "NOT_MODELLED", [], "no RF payload in NOS3", "", label="RF payload: changes to user auth/authz policies"),
    R("PL-OCT-CROSSLINK", "Unauthorized crosslink connections", "NO", "NOT_MODELLED",
      [], "no optical crosslink terminal in NOS3", "IA-0003, IA-0008/.02, LM-0003."),
    R("PL-OCT-POLARIZATION", "Changes to carrier frequency/waveform/polarization",
      "NO", "NOT_MODELLED", [], "no OCT payload in NOS3", ""),
    R("PL-SIGPROC", "Change in signal detection, classification", "NO", "NEEDS_FSW",
      [], "SYN has no simulator anywhere in the build — the app is permanently inert",
      "Previously called 'the one payload-specific algorithm row with a real target in this "
      "build'. Retracted: the target exists as an app but never runs.", label="Change in signal detection/classification/processing logic"),
]

# Every distinct workbook indicator string must be claimed by exactly one entry.
# Recommendations whose key is deliberately a broad prefix (the per-subsystem
# access/comms families) are listed last so specific keys win.
BROAD = {"GEN-ACCESS-IN", "GEN-ACCESS-OUT", "GEN-COMM", "GEN-SIGANOM", "GEN-CFG",
         "GEN-CTRLLOGIC", "TTC-RFCONFIG", "PL-COLLECTREQ", "TTC-PA"}


# Every distinct workbook indicator string must be claimed by exactly one entry;
# when several keys are prefixes of the same row, the longest (most specific) wins.
def load_iocs(doc):
    """Distinct indicator-of-compromise strings across the 13 subsystem sheets."""
    order, sheets = [], collections.defaultdict(set)
    for name, s in doc["sheets"].items():
        if s["kind"] != "subsystem":
            continue
        for r in s["records"]:
            k = re.sub(r"\s+", " ",
                       r.get("possible attack vectors/indicators of compromise", "")).strip()
            if k not in sheets:
                order.append(k) if k not in order else None
            sheets[k].add(name)
    return order, sheets


def claim(iocs):
    """ioc -> rid, preferring the most specific (longest) matching key."""
    out, unclaimed = {}, []
    for ioc in iocs:
        hits = [r for r in RECS if ioc.startswith(r.key)]
        if not hits:
            unclaimed.append(ioc)
            continue
        out[ioc] = max(hits, key=lambda r: len(r.key)).rid
    return out, unclaimed


def coverage_verdicts(path):
    """OOS / UNSUBSCRIBED technique ids, read out of gen_nos3_coverage.py itself."""
    tree = ast.parse(open(path).read())
    dicts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                dicts[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    oos, unsub = set(), set()
    for tid, v in (dicts.get("ENRICH") or {}).items():
        if v[0] == "OUT-OF-SCOPE":
            oos.add(tid)
        if v[1] == "UNSUBSCRIBED":
            unsub.add(tid)
    for tid, v in (dicts.get("REVIEW_ADD") or {}).items():
        oos.add(tid)
        if v[1] == "UNSUBSCRIBED":
            unsub.add(tid)
    return oos, unsub, set(dicts.get("REVIEW") or {})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--markdown", help="write the AC2 gap table here")
    args = ap.parse_args(argv)

    doc = json.load(open(args.json))
    schema = set(json.load(open(SCHEMA))["order"])
    problems = []

    # -- check 2: every named column exists in the deployed schema --------------
    for r in RECS:
        for col in r.ours:
            if col not in schema:
                problems.append(f"{r.rid}: column not in nos3_security_tlm.json: {col}")
    # -- check 2b: no row may lean on a silent MID or a pruned column ---------
    for r in RECS:
        for col in r.ours:
            if col.split(".")[0] in SILENT_MIDS:
                problems.append(f"{r.rid}: cites a SILENT MID (never arrives): {col}")
            if col in PRUNED_COLS:
                problems.append(f"{r.rid}: cites a column PRUNED from the CSV: {col}")

    # -- check 3: verdict/bucket consistency ----------------------------------
    for r in RECS:
        if r.verdict == "YES" and not r.ours:
            problems.append(f"{r.rid}: YES with no recorded field")
        if r.verdict == "NO" and r.ours:
            problems.append(f"{r.rid}: NO but names recorded fields")
        if r.verdict != "YES" and not r.bucket:
            problems.append(f"{r.rid}: {r.verdict} with no bucket")
        if r.verdict == "YES" and r.bucket:
            problems.append(f"{r.rid}: YES should carry no bucket")
    rids = [r.rid for r in RECS]
    for rid, n in collections.Counter(rids).items():
        if n > 1:
            problems.append(f"duplicate rid: {rid}")

    # -- check 1: every workbook indicator is claimed ---------------------------
    iocs, ioc_sheets = load_iocs(doc)
    claimed, unclaimed = claim(iocs)
    for u in unclaimed:
        problems.append(f"unclaimed workbook indicator: {u[:80]}")
    used = set(claimed.values())
    for r in RECS:
        if r.rid not in used:
            problems.append(f"{r.rid}: claims no workbook indicator (stale key?)")

    if problems:
        print("!! CONSISTENCY FAILURES\n" + "\n".join("   " + p for p in problems))

    # -- AC1: sheet inventory ---------------------------------------------------
    print(f"\nAC1 — {len(doc['sheets'])} sheets, "
          f"{sum(len(s.get('records', [])) for s in doc['sheets'].values())} data rows, "
          f"{len(iocs)} distinct recommendations")

    # -- AC3: bucket counts -----------------------------------------------------
    by_verdict = collections.Counter(r.verdict for r in RECS)
    by_bucket = collections.Counter(r.bucket for r in RECS if r.bucket)
    print(f"\nAC2/AC3 — {len(RECS)} canonical recommendations")
    for v in ("YES", "PARTIAL", "NO"):
        print(f"   {v:8s} {by_verdict[v]:3d}")
    print("   -- what would carry the missing half --")
    for b, n in by_bucket.most_common():
        print(f"   {b:18s} {n:3d}")

    # -- AC4: re-openable verdicts ---------------------------------------------
    oos, unsub, reviewed = coverage_verdicts(COVERAGE_GEN)
    mapping = {r["id"]: r for r in doc["sheets"]["SPARTA_Mapping"]["records"]}
    loggable = {tid for tid, r in mapping.items()
                if (r.get("data type") or "").strip().upper() not in ("", "N/A")}
    flagged = sorted((oos | unsub) & loggable)
    print(f"\nAC4 — {len(oos | unsub)} techniques published out-of-scope/UNSUBSCRIBED; "
          f"{len(flagged)} of them appear in SPARTA_Mapping with a named log source:")
    for tid in flagged:
        print(f"   {tid:12s} {mapping[tid]['data type']}")
    agree = sorted((oos | unsub) & (set(mapping) - loggable))
    if agree:
        print(f"   -- workbook AGREES nothing is loggable: {', '.join(agree)}")

    if args.markdown:
        with open(args.markdown, "w") as f:
            f.write("| ID | Recommended log source | Recorded? | Our fields | "
                    "What would carry the rest |\n|---|---|---|---|---|\n")
            for r in RECS:
                ours = "<br>".join(f"`{c}`" for c in r.ours) or "—"
                f.write(f"| `{r.rid}` | {r.label} | {r.verdict} | {ours} | "
                        f"{r.carrier or '—'} |\n")
        print(f"\nAC2 table -> {args.markdown}")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
