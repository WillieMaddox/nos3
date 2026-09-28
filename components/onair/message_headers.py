from ctypes import *
import sbn_python_client as sbn

# =============================================================================
# message_headers.py
#
# ctypes telemetry struct definitions for NOS3 security / anomaly-detection
# logging.  Used by sbn_adapter.py (import message_headers as msg_hdr) and
# indexed by nos3_security_tlm.json.
#
# Sources
#   cfg/nos3_defs/cpu1_msgids.h
#   components/*/fsw/cfs/platform_inc/*_msgids.h
#   components/*/fsw/cfs/src/*_msg.h
#   components/*/fsw/shared/*_device.h
#   fsw/cfe/modules/*/config/default_cfe_*_msgstruct.h
#   fsw/apps/sc/fsw/inc/sc_msg.h
#   fsw/apps/sch/fsw/src/sch_msg.h
#   fsw/apps/sbn/fsw/platform_inc/sbn_msgids.h
#
# cFE mission constants  (must match cfg/nos3_defs/cfe_mission_cfg.h)
_MAX_API_LEN   = 20     # CFE_MISSION_MAX_API_LEN
_EVS_MSG_LEN   = 122    # CFE_MISSION_EVS_MAX_MESSAGE_LENGTH
_MAX_APPS      = 16     # CFE_MISSION_ES_MAX_APPLICATIONS
_TBL_NAME_LEN  = 40     # CFE_MISSION_TBL_MAX_FULL_NAME_LEN
_MAX_PATH_LEN  = 64     # CFE_MISSION_MAX_PATH_LEN
_SC_NUM_ATS    = 2      # SC_NUMBER_OF_ATS
_SC_RTS_WORDS  = 4      # ceil(64 RTS / 16 per uint16)
# =============================================================================

# ---------------------------------------------------------------------------
# Original sample structs (preserved for backward compatibility)
# ---------------------------------------------------------------------------

class SAMPLE_Device_HK_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("DeviceCounter", c_uint32),
        ("DeviceConfig",  c_uint32),
        ("DeviceStatus",  c_uint32),
    ]

class SAMPLE_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",        sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
        ("DeviceHK",          SAMPLE_Device_HK_tlm_t),
    ]

# ===========================================================================
# 1.  CFE Event Services — Long Event Message          MID 0x0808
# ===========================================================================

class CFE_EVS_PacketID_t(Structure):
    """Identifies the originating app and event for every EVS message."""
    _pack_ = 1
    _fields_ = [
        ("AppName",      c_char    * _MAX_API_LEN),
        ("EventID",      c_uint16),
        ("EventType",    c_uint16),   # 1=DEBUG 2=INFO 3=ERROR 4=CRITICAL
        ("SpacecraftID", c_uint32),
        ("ProcessorID",  c_uint32),
    ]

class CFE_EVS_LongEventTlm_t(Structure):
    """CFE_EVS_LONG_EVENT_MSG_MID 0x0808
    Primary cross-system security log.  Every cFS app emits events here
    including CryptoLib failures, app crashes, and state transitions.
    Attack signals: ERROR/CRITICAL from unexpected AppName; events from
    apps not in the scheduled startup list.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("PacketID",  CFE_EVS_PacketID_t),
        ("Message",   c_char * _EVS_MSG_LEN),
        ("Spare1",    c_uint8),
        ("Spare2",    c_uint8),
    ]

# ===========================================================================
# 2.  CFE Software Bus — Housekeeping                  MID 0x0803
# ===========================================================================

class CFE_SB_HousekeepingTlm_t(Structure):
    """CFE_SB_HK_TLM_MID 0x0803
    SB routing health.
    Attack signals: NoSubscribersCounter spike (message-injection probe);
    MsgLimitErrorCounter spike (pipe-flooding DoS attack).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",                     sbn.CFE_SB_Msg_t),
        ("CommandCounter",                c_uint8),
        ("CommandErrorCounter",           c_uint8),
        ("NoSubscribersCounter",          c_uint8),
        ("MsgSendErrorCounter",           c_uint8),
        ("MsgReceiveErrorCounter",        c_uint8),
        ("InternalErrorCounter",          c_uint8),
        ("CreatePipeErrorCounter",        c_uint8),
        ("SubscribeErrorCounter",         c_uint8),
        ("PipeOptsErrorCounter",          c_uint8),
        ("DuplicateSubscriptionsCounter", c_uint8),
        ("GetPipeIdByNameErrorCounter",   c_uint8),
        ("Spare2Align",                   c_uint8),
        ("PipeOverflowErrorCounter",      c_uint16),
        ("MsgLimitErrorCounter",          c_uint16),
        ("MemPoolHandle",                 c_uint32),
        ("MemInUse",                      c_uint32),
        ("UnmarkedMem",                   c_uint32),
    ]

# ===========================================================================
# 3.  CFE Software Bus — All Subscriptions             MID 0x080D
# ===========================================================================

class CFE_SB_SubEntries_t(Structure):
    """Single subscription entry (MsgId + routing info)."""
    _pack_ = 1
    _fields_ = [
        ("MsgId",  c_uint32),
        ("Qos",    c_uint8 * 2),
        ("PipeId", c_uint8),
        ("Spare",  c_uint8),
    ]

# ⚠ UNSUBSCRIBED 2026-08-25 (AINOS3-108). MID 0x080D is command-produced
# (CFE_SB_SEND_PREV_SUBS_CC) with 0 scheduler entries, so it never transmits and read
# [0] for the life of the subscription. Scheduling it is possible but belongs with the
# other command-produced diagnostic packets, not here.
class CFE_SB_AllSubscriptionsTlm_t(Structure):
    """CFE_SB_ALLSUBS_TLM_MID 0x080D
    Full subscription snapshot — baseline at startup, delta-detect eavesdropping.
    CFE_SB_SUB_ENTRIES_PER_PKT default = 20; segmented across TotalSegments packets.
    Attack signal: new MsgId in Entry[] after initialization.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",     sbn.CFE_SB_Msg_t),
        ("PktSegment",    c_uint32),
        ("TotalSegments", c_uint32),
        ("Entries",       c_uint32),
        ("Entry",         CFE_SB_SubEntries_t * 20),
    ]

# ===========================================================================
# 4.  SBN — Module Status                              MID 0x08DC
# ===========================================================================

# ⚠ UNSUBSCRIBED 2026-08-25 (AINOS3-108). MID 0x08DC is command-produced with 0
# scheduler entries. ⚠⚠ DO NOT simply schedule it to "fix" the silence: that one MID
# carries FIVE different payload structs chosen by which command was sent —
# SBN_HK_LEN, SBN_HKNET_LEN, SBN_HKPEER_LEN, SBN_HKMYSUBS_LEN, SBN_HKPEERSUBS_LEN
# (fsw/apps/sbn/fsw/src/sbn_cmds.c:257-491). This struct models only the first, so four
# of the five variants would be silently mis-parsed — an intermittent byte
# misalignment, far harder to spot than a fixed one. Model the variants first.
class SBN_ModuleStatusTlm_t(Structure):
    """SBN_TLM_MID 0x08DC
    SBN peer connection status (response to SBN_HK_CC commands).
    Attack signal: unexpected peer count or new peer appearing mid-mission.
    SBN_MOD_STATUS_MSG_SZ default = 64 bytes of protocol-specific peer state.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",    sbn.CFE_SB_Msg_t),
        ("ProtocolIdx",  c_uint16),
        ("ModuleStatus", c_uint8 * 64),
    ]

# ===========================================================================
# 5.  NovAtel OEM615 — GNSS Device Telemetry          MID 0x0871
# ===========================================================================

class NOVATEL_OEM615_Device_Data_tlm_t(Structure):
    """Raw GNSS navigation solution from the NovAtel OEM615 receiver."""
    _pack_ = 1
    _fields_ = [
        ("Weeks",           c_uint16),
        ("SecondsIntoWeek", c_uint32),
        ("Fractions",       c_double),
        ("ECEFX",           c_double),
        ("ECEFY",           c_double),
        ("ECEFZ",           c_double),
        ("VelX",            c_double),
        ("VelY",            c_double),
        ("VelZ",            c_double),
        ("lat",             c_double),
        ("lon",             c_double),
        ("alt",             c_double),
    ]

class NOVATEL_OEM615_Device_tlm_t(Structure):
    """NOVATEL_OEM615_DEVICE_TLM_MID 0x0871
    GPS navigation solution — primary GPS-spoofing detection source.
    Attack signals: instantaneous position/velocity discontinuity;
    lat/lon/alt jump inconsistent with orbital dynamics.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",      sbn.CFE_SB_Msg_t),
        ("Novatel_oem615", NOVATEL_OEM615_Device_Data_tlm_t),
    ]

# ===========================================================================
# 6.  NovAtel OEM615 — Housekeeping                   MID 0x0870
# ===========================================================================

class NOVATEL_OEM615_Hk_tlm_t(Structure):
    """NOVATEL_OEM615_HK_TLM_MID 0x0870
    GNSS receiver command health.
    Attack signal: DeviceEnabled toggling without a ground command;
    CommandErrorCount spike (probe of invalid receiver commands).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
    ]

# ===========================================================================
# 7.  Generic ADCS — GNC Telemetry                    MID 0x0943
# ===========================================================================

class Generic_ADCS_GNC_Hmgmt_t(Structure):
    """ADCS momentum-management sub-structure embedded in GNC telemetry."""
    _pack_ = 1
    _fields_ = [
        ("Kb",        c_double),
        ("b_range",   c_double),
        ("loFrac",    c_double),
        ("hiFrac",    c_double),
        ("mm_active", c_uint8  * 3),
        ("Mcmd",      c_double * 3),
    ]

class Generic_ADCS_GNC_Tlm_t(Structure):
    """GENERIC_ADCS_GNC_MID 0x0943
    Guidance, Navigation, and Control state — richest ADCS security packet.
    Attack signals: Mode change without prior ground command;
    Tcmd[3] non-zero with no scheduled maneuver;
    qErr[4] growing unchecked (ADCS destabilization).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("DT",        c_double),
        ("MaxMcmd",   c_double),
        ("Mode",      c_uint8),
        ("HmgmtOn",   c_uint8),
        ("Hmgmt",     Generic_ADCS_GNC_Hmgmt_t),
        ("bvb",       c_double * 3),
        ("svb",       c_double * 3),
        ("SunValid",  c_uint8),
        ("wbn",       c_double * 3),
        ("HwhlMaxB",  c_double * 3),
        ("HwhlB",     c_double * 3),
        ("Mcmd",      c_double * 3),
        ("Tcmd",      c_double * 3),
        ("qValid",    c_uint8),
        ("qbn",       c_double * 4),
        ("qErr",      c_double * 4),
    ]

# ===========================================================================
# 8.  Generic ADCS — Housekeeping                     MID 0x0940
# ===========================================================================

class Generic_ADCS_Hk_tlm_t(Structure):
    """GENERIC_ADCS_HK_TLM_MID 0x0940
    ADCS command health.
    Attack signal: CommandErrorCount/CommandCount ratio spike indicates
    unauthorized or malformed ADCS command injection.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
    ]

# ===========================================================================
# 9.  Generic ADCS — Device Output                    MID 0x0945
# ===========================================================================

class Generic_ADCS_DO_Trq_TlmPayload_t(Structure):
    """Magnetic torquer actuator command output."""
    _pack_ = 1
    _fields_ = [
        ("qba",  c_double * 4),
        ("Mcmd", c_double * 3),
    ]

class Generic_ADCS_DO_Rw_TlmPayload_t(Structure):
    """Reaction-wheel actuator command output."""
    _pack_ = 1
    _fields_ = [
        ("axis", (c_double * 3) * 3),
        ("Tcmd", c_double * 3),
    ]

class Generic_ADCS_DO_Tlm_t(Structure):
    """GENERIC_ADCS_DO_MID 0x0945
    Actuator command outputs — cross-reference with GNC to detect direct injection.
    Attack signal: Trq.Mcmd or Rw.Tcmd non-zero with no corresponding GNC Tcmd
    (actuator bypass — commands inserted below the control loop).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Trq",       Generic_ADCS_DO_Trq_TlmPayload_t),
        ("Rw",        Generic_ADCS_DO_Rw_TlmPayload_t),
    ]

# ===========================================================================
# 10. Generic Reaction Wheel — Housekeeping            MID 0x0993
# ===========================================================================

class GENERIC_RW_Data_t(Structure):
    """Reaction-wheel momentum vector [N·m·s]."""
    _pack_ = 1
    _fields_ = [
        ("momentum", c_double * 3),
    ]

class GENERIC_RW_HkTlm_t(Structure):
    """GENERIC_RW_APP_HK_TLM_MID 0x0993
    Reaction-wheel status.
    Attack signal: momentum change with no preceding ADCS_DO Rw.Tcmd
    (direct hardware-level command injection bypassing the control loop).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",            sbn.CFE_SB_Msg_t),
        ("CommandErrorCounter",  c_uint8),
        ("CommandCounter",       c_uint8),
        ("DeviceErrorCount_RW0", c_uint8),
        ("DeviceErrorCount_RW1", c_uint8),
        ("DeviceErrorCount_RW2", c_uint8),
        ("DeviceCount_RW0",      c_uint8),
        ("DeviceCount_RW1",      c_uint8),
        ("DeviceCount_RW2",      c_uint8),
        ("DeviceEnabled_RW0",    c_uint8),
        ("DeviceEnabled_RW1",    c_uint8),
        ("DeviceEnabled_RW2",    c_uint8),
        ("data",                 GENERIC_RW_Data_t),
    ]

# ===========================================================================
# 11. Generic EPS — Housekeeping                       MID 0x091A
# ===========================================================================

class GENERIC_EPS_Switch_tlm_t(Structure):
    """Per-switch power telemetry (Voltage, Current, Status)."""
    _pack_ = 1
    _fields_ = [
        ("Voltage", c_uint16),
        ("Current", c_uint16),
        ("Status",  c_uint16),
    ]

class GENERIC_EPS_Device_HK_tlm_t(Structure):
    """EPS device housekeeping — bus voltages, temperatures, 8 switch states."""
    _pack_ = 1
    _fields_ = [
        ("BatteryVoltage",        c_uint16),
        ("BatteryTemperature",    c_uint16),
        ("Bus3p3Voltage",         c_uint16),
        ("Bus5p0Voltage",         c_uint16),
        ("Bus12Voltage",          c_uint16),
        ("EPSTemperature",        c_uint16),
        ("SolarArrayVoltage",     c_uint16),
        ("SolarArrayTemperature", c_uint16),
        ("Switch",                GENERIC_EPS_Switch_tlm_t * 8),
    ]

class GENERIC_EPS_Hk_tlm_t(Structure):
    """GENERIC_EPS_HK_TLM_MID 0x091A
    Power-system health.
    Attack signals: Switch.Status change without operator command (subsystem kill);
    BatteryVoltage / Bus[x]Voltage anomaly (unauthorized load or drain).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceHK",          GENERIC_EPS_Device_HK_tlm_t),
    ]

# ===========================================================================
# 12. Generic Radio — Housekeeping                     MID 0x0930
# ===========================================================================

class GENERIC_RADIO_Device_HK_tlm_t(Structure):
    """Radio device sub-housekeeping (counter, config, proximity signal)."""
    _pack_ = 1
    _fields_ = [
        ("DeviceCounter", c_uint32),
        ("DeviceConfig",  c_uint32),
        ("ProxSignal",    c_uint32),
    ]

class GENERIC_RADIO_Hk_tlm_t(Structure):
    """GENERIC_RADIO_HK_TLM_MID 0x0930
    Radio command health and proximity-link statistics.
    Attack signals: ForwardCount activity without authorized cross-link ops;
    DeviceHK.DeviceConfig change (frequency / power reconfiguration).
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("ForwardErrorCount", c_uint8),
        ("ForwardCount",      c_uint8),
        ("DeviceHK",          GENERIC_RADIO_Device_HK_tlm_t),
    ]

# ===========================================================================
# 13. Generic Radio — Device Telemetry                 MID 0x0931
# ===========================================================================

# ⚠ UNSUBSCRIBED 2026-08-25 (AINOS3-108). Kept for reference; do not re-add without
# reading this. MID 0x0931 is fully REDUNDANT — GENERIC_RADIO_Device_HK_tlm_t, embedded
# in RADIO_HK 0x0930 as `DeviceHK`, carries the identical three fields, and that one
# arrives. 0x0931 itself has 0 scheduler entries and 0 TO routes: the radio app only
# publishes it opportunistically from its proxy task (generic_radio_app.c:537), so it
# was measured silent across 21,269 frames.
class GENERIC_RADIO_Device_tlm_t(Structure):
    """GENERIC_RADIO_DEVICE_TLM_MID 0x0931
    RF-layer device telemetry.
    Attack signals: ProxSignal anomaly inconsistent with orbital geometry
    (jamming / spoofed proximity link); unexpected DeviceConfig value.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",     sbn.CFE_SB_Msg_t),
        ("DeviceCounter", c_uint32),
        ("DeviceConfig",  c_uint32),
        ("ProxSignal",    c_uint32),
    ]

# ===========================================================================
# 14. CFE Executive Services — Housekeeping            MID 0x0800
# ===========================================================================

class CFE_ES_HousekeepingTlm_t(Structure):
    """CFE_ES_HK_TLM_MID 0x0800
    Application lifecycle and system health.
    Attack signals: ProcessorResets incrementing (crash exploitation);
    RegisteredExternalApps changing mid-mission (unauthorized app load);
    HeapBytesFree draining (memory-exhaustion attack).
    PerfFilterMask/TriggerMask: 128 IDs / 32 bits = 4 uint32 words each.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",              sbn.CFE_SB_Msg_t),
        ("CommandCounter",         c_uint8),
        ("CommandErrorCounter",    c_uint8),
        ("CFECoreChecksum",        c_uint16),
        ("CFEMajorVersion",        c_uint8),
        ("CFEMinorVersion",        c_uint8),
        ("CFERevision",            c_uint8),
        ("CFEMissionRevision",     c_uint8),
        ("OSALMajorVersion",       c_uint8),
        ("OSALMinorVersion",       c_uint8),
        ("OSALRevision",           c_uint8),
        ("OSALMissionRevision",    c_uint8),
        ("PSPMajorVersion",        c_uint8),
        ("PSPMinorVersion",        c_uint8),
        ("PSPRevision",            c_uint8),
        ("PSPMissionRevision",     c_uint8),
        ("SysLogBytesUsed",        c_uint32),
        ("SysLogSize",             c_uint32),
        ("SysLogEntries",          c_uint32),
        ("SysLogMode",             c_uint32),
        ("ERLogIndex",             c_uint32),
        ("ERLogEntries",           c_uint32),
        ("RegisteredCoreApps",     c_uint32),
        ("RegisteredExternalApps", c_uint32),
        ("RegisteredTasks",        c_uint32),
        ("RegisteredLibs",         c_uint32),
        ("ResetType",              c_uint32),
        ("ResetSubtype",           c_uint32),
        ("ProcessorResets",        c_uint32),
        ("MaxProcessorResets",     c_uint32),
        ("BootSource",             c_uint32),
        ("PerfState",              c_uint32),
        ("PerfMode",               c_uint32),
        ("PerfTriggerCount",       c_uint32),
        ("PerfFilterMask",         c_uint32 * 4),
        ("PerfTriggerMask",        c_uint32 * 4),
        ("PerfDataStart",          c_uint32),
        ("PerfDataEnd",            c_uint32),
        ("PerfDataCount",          c_uint32),
        ("PerfDataToWrite",        c_uint32),
        ("HeapBytesFree",          c_uint32),
        ("HeapBlocksFree",         c_uint32),
        ("HeapMaxBlockSize",       c_uint32),
    ]

# ===========================================================================
# 15. CFE Table Services — Housekeeping                MID 0x0804
# ===========================================================================

class CFE_TBL_HousekeepingTlm_t(Structure):
    """CFE_TBL_HK_TLM_MID 0x0804
    Table load and validation activity.
    Attack signal: NumLoadPending / ValidationCounter outside maintenance windows
    (table modification = persistent attack payload);
    LastValTableName identifies which table was targeted.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",             sbn.CFE_SB_Msg_t),
        ("CommandCounter",        c_uint8),
        ("CommandErrorCounter",   c_uint8),
        ("NumTables",             c_uint16),
        ("NumLoadPending",        c_uint16),
        ("ValidationCounter",     c_uint16),
        ("LastValCrc",            c_uint32),
        ("LastValStatus",         c_int32),
        ("ActiveBuffer",          c_uint8),
        ("LastValTableName",      c_char * _TBL_NAME_LEN),
        ("SuccessValCounter",     c_uint8),
        ("FailedValCounter",      c_uint8),
        ("NumValRequests",        c_uint8),
        ("NumFreeSharedBufs",     c_uint8),
        ("ByteAlignPad1",         c_uint8),
        ("MemPoolHandle",         c_uint32),
        ("LastUpdateTimeSeconds", c_uint32),
        ("LastUpdateTimeSubsecs", c_uint32),
        ("LastUpdatedTable",      c_char * _TBL_NAME_LEN),
        ("LastFileLoaded",        c_char * _MAX_PATH_LEN),
        ("LastFileDumped",        c_char * _MAX_PATH_LEN),
        ("LastTableLoaded",       c_char * _TBL_NAME_LEN),
    ]

# ===========================================================================
# 16. CFE Time Services — Housekeeping                 MID 0x0805
# ===========================================================================

class CFE_TIME_HousekeepingTlm_t(Structure):
    """CFE_TIME_HK_TLM_MID 0x0805
    Time reference health.
    Attack signal: ClockStateFlags switching source from GPS-derived to internal
    (enables replay-attack windows, breaks crypto epoch validation);
    SecondsMET discontinuity.
    Note: conditional Seconds1HzAdj / SecondsDelay fields omitted; add them
    if CFE_PLATFORM_TIME_CFG_SERVER or CFE_PLATFORM_TIME_CFG_CLIENT is true.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",           sbn.CFE_SB_Msg_t),
        ("CommandCounter",      c_uint8),
        ("CommandErrorCounter", c_uint8),
        ("ClockStateFlags",     c_uint16),
        ("ClockStateAPI",       c_uint16),
        ("LeapSeconds",         c_int16),
        ("SecondsMET",          c_uint32),
        ("SubsecsMET",          c_uint32),
        ("SecondsSTCF",         c_uint32),
        ("SubsecsSTCF",         c_uint32),
    ]

# ===========================================================================
# 17. Stored Commands (SC) — Housekeeping              MID 0x08AA
# ===========================================================================

class SC_HkTlm_t(Structure):
    """SC_HK_TLM_MID 0x08AA
    Stored command sequence state.
    Attack signals: RtsExecutingStatus bitmap changes without operator initiation
    (unauthorized RTS enable = persistent attack payload);
    AtsCmdErrCtr after upload (malformed injected sequence probe).
    SC_NUMBER_OF_ATS=2 → AtpFreeBytes[2]; SC_NUMBER_OF_RTS=64 → 4 uint16 words.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",                sbn.CFE_SB_Msg_t),
        ("AtsNumber",                c_uint8),
        ("AtpState",                 c_uint8),
        ("ContinueAtsOnFailureFlag", c_uint8),
        ("CmdErrCtr",                c_uint8),
        ("CmdCtr",                   c_uint8),
        ("Padding8",                 c_uint8),
        ("SwitchPendFlag",           c_uint16),
        ("NumRtsActive",             c_uint16),
        ("RtsNumber",                c_uint16),
        ("RtsActiveCtr",             c_uint16),
        ("RtsActiveErrCtr",          c_uint16),
        ("AtsCmdCtr",                c_uint16),
        ("AtsCmdErrCtr",             c_uint16),
        ("RtsCmdCtr",                c_uint16),
        ("RtsCmdErrCtr",             c_uint16),
        ("LastAtsErrSeq",            c_uint16),
        ("LastAtsErrCmd",            c_uint16),
        ("LastRtsErrSeq",            c_uint16),
        ("LastRtsErrCmd",            c_uint16),
        ("AppendCmdArg",             c_uint16),
        ("AppendEntryCount",         c_uint16),
        ("AppendByteCount",          c_uint16),
        ("AppendLoadCount",          c_uint16),
        ("AtpCmdNumber",             c_uint32),
        ("AtpFreeBytes",             c_uint32 * _SC_NUM_ATS),
        ("NextRtsTime",              c_uint32),
        ("NextAtsTime",              c_uint32),
        ("RtsExecutingStatus",       c_uint16 * _SC_RTS_WORDS),
        ("RtsDisabledStatus",        c_uint16 * _SC_RTS_WORDS),
    ]

# ===========================================================================
# 18. Scheduler (SCH) — Housekeeping                   MID 0x0897
# ===========================================================================

class SCH_HkPacket_t(Structure):
    """SCH_HK_TLM_MID 0x0897
    Mission schedule health.
    Attack signals: MissedMajorFrameCount spike (timing starvation / DoS);
    TableVerifyFailureCount (table corruption attempt);
    BadTableDataCount (corrupted schedule injection).
    """
    _pack_ = 1
    _fields_ = [
        ("TelemetryHeader",              sbn.CFE_SB_Msg_t),
        ("CmdCounter",                   c_uint8),
        ("ErrCounter",                   c_uint8),
        ("SyncToMET",                    c_uint8),
        ("MajorFrameSource",             c_uint8),
        ("ScheduleActivitySuccessCount", c_uint32),
        ("ScheduleActivityFailureCount", c_uint32),
        ("SlotsProcessedCount",          c_uint32),
        ("SkippedSlotsCount",            c_uint16),
        ("MultipleSlotsCount",           c_uint16),
        ("SameSlotCount",                c_uint16),
        ("BadTableDataCount",            c_uint16),
        ("TableVerifySuccessCount",      c_uint16),
        ("TableVerifyFailureCount",      c_uint16),
        ("TablePassCount",               c_uint32),
        ("ValidMajorFrameCount",         c_uint32),
        ("MissedMajorFrameCount",        c_uint32),
        ("UnexpectedMajorFrameCount",    c_uint32),
        ("MinorFramesSinceTone",         c_uint16),
        ("NextSlotNumber",               c_uint16),
        ("LastSyncMETSlot",              c_uint16),
        ("IgnoreMajorFrame",             c_uint8),
        ("UnexpectedMajorFrame",         c_uint8),
    ]

# ===========================================================================
# 19. Generic ADCS — Data Input (raw sensor fusion)    MID 0x0941
# ===========================================================================

class Generic_ADCS_DI_Mag_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("qbs", c_double * 4),
        ("bvb", c_double * 3),
    ]

class Generic_ADCS_DI_Fss_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("qbs",   c_double * 4),
        ("valid", c_uint8),
        ("svb",   c_double * 3),
    ]

class Generic_ADCS_DI_Css_Sensor_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("axis",      c_double * 3),
        ("scale",     c_double),
        ("percenton", c_double),
    ]

class Generic_ADCS_DI_Css_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("Sensor", Generic_ADCS_DI_Css_Sensor_Payload_t * 6),
        ("valid",  c_uint8),
        ("svb",    c_double * 3),
    ]

class Generic_ADCS_DI_Imu_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("qbs",   c_double * 4),
        ("pos",   c_double * 3),
        ("valid", c_uint8),
        ("wbn",   c_double * 3),
        ("acc",   c_double * 3),
    ]

class Generic_ADCS_DI_Rw_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("whl_axis", (c_double * 3) * 3),
        ("H_maxB",   c_double * 3),
        ("HwhlB",    c_double * 3),
    ]

class Generic_ADCS_DI_St_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("qbs",   c_double * 4),
        ("q",     c_double * 4),
        ("valid", c_uint8),
    ]

class Generic_ADCS_DI_Tlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("Mag", Generic_ADCS_DI_Mag_Tlm_Payload_t),
        ("Fss", Generic_ADCS_DI_Fss_Tlm_Payload_t),
        ("Css", Generic_ADCS_DI_Css_Tlm_Payload_t),
        ("Imu", Generic_ADCS_DI_Imu_Tlm_Payload_t),
        ("Rw",  Generic_ADCS_DI_Rw_Tlm_Payload_t),
        ("St",  Generic_ADCS_DI_St_Tlm_Payload_t),
    ]

class Generic_ADCS_DI_Tlm_t(Structure):
    """GENERIC_ADCS_DI_MID 0x0941
    Raw sensor inputs before attitude-determination filter.
    Cross-reference with AD output to detect sensor spoofing.
    Attack signals: St.valid=0 outside eclipse/maneuver;
    Imu.wbn inconsistent with ADCS_DO Rw.Tcmd in same window;
    Mag.bvb deviating from orbital magnetic model.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Payload",   Generic_ADCS_DI_Tlm_Payload_t),
    ]

# ===========================================================================
# 20. Generic Thruster — Housekeeping                  MID 0x08EA
# ===========================================================================

class GENERIC_THRUSTER_Hk_tlm_t(Structure):
    """GENERIC_THRUSTER_HK_TLM_MID 0x08EA
    Thruster command health.
    Attack signals: DeviceEnabled toggling without operator command
    (unauthorized thruster activation = orbit-modification attack);
    CommandCount incrementing outside planned maneuver window.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
    ]

# ===========================================================================
# 21. CFE Event Services — Housekeeping                MID 0x0801
# ===========================================================================

class CFE_EVS_AppTlmData_t(Structure):
    """Per-application event statistics embedded in EVS HK packet."""
    _pack_ = 1
    _fields_ = [
        ("AppID",                      c_uint32),
        ("AppMessageSentCounter",      c_uint16),
        ("AppEnableStatus",            c_uint8),
        ("AppMessageSquelchedCounter", c_uint8),
    ]

class CFE_EVS_HousekeepingTlm_t(Structure):
    """CFE_EVS_HK_TLM_MID 0x0801
    Event-service health — per-app enable state.
    Attack signal: AppEnableStatus=0 for a specific app during an anomaly window
    (event suppression used to hide attack activity);
    MessageTruncCounter spike (event flooding to obscure a concurrent attack).
    AppData: CFE_MISSION_ES_MAX_APPLICATIONS = 16 apps.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",              sbn.CFE_SB_Msg_t),
        ("CommandCounter",         c_uint8),
        ("CommandErrorCounter",    c_uint8),
        ("MessageFormatMode",      c_uint8),
        ("MessageTruncCounter",    c_uint8),
        ("UnregisteredAppCounter", c_uint8),
        ("OutputPort",             c_uint8),
        ("LogFullFlag",            c_uint8),
        ("LogMode",                c_uint8),
        ("MessageSendCounter",     c_uint16),
        ("LogOverflowCounter",     c_uint16),
        ("LogEnabled",             c_uint8),
        ("Spare1",                 c_uint8),
        ("Spare2",                 c_uint8),
        ("Spare3",                 c_uint8),
        ("AppData",                CFE_EVS_AppTlmData_t * _MAX_APPS),
    ]


# ===========================================================================
# Extra sensor / actuator / core-app telemetry — 16 MIDs added 2026-07-16 for
# the SPARTA coverage validation campaign (RECORDING only; not yet model
# features). Structs translated byte-exact from the component C headers; each
# begins with the 16-byte CFE telemetry header (sbn.CFE_SB_Msg_t) + packed=1.
# ===========================================================================

_GENERIC_CSS_NUM_CHANNELS = 6   # GENERIC_CSS_NUM_CHANNELS
_LC_HKWR_NUM_BYTES = 44         # ((LC_MAX_WATCHPOINTS 176 + 15)/16)*4
_LC_HKAR_NUM_BYTES = 88         # ((LC_MAX_ACTIONPOINTS 176 + 7)/8)*4

# --- Coarse Sun Sensor (CSS) --- 0x0910 HK / 0x0911 DEVICE
class GENERIC_CSS_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
    ]

class GENERIC_CSS_Device_Data_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [("Voltage", c_uint16 * _GENERIC_CSS_NUM_CHANNELS)]

class GENERIC_CSS_Device_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",   sbn.CFE_SB_Msg_t),
        ("Generic_css", GENERIC_CSS_Device_Data_tlm_t),
    ]

# --- Fine Sun Sensor (FSS) --- 0x0920 HK / 0x0921 DEVICE
class GENERIC_FSS_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
    ]

class GENERIC_FSS_Device_Data_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("Alpha",     c_float),
        ("Beta",      c_float),
        ("ErrorCode", c_uint8),
    ]

class GENERIC_FSS_Device_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",   sbn.CFE_SB_Msg_t),
        ("Generic_fss", GENERIC_FSS_Device_Data_tlm_t),
    ]

# --- Inertial Measurement Unit (IMU) --- 0x0925 HK / 0x0926 DEVICE
class GENERIC_IMU_Device_HK_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("DeviceCounter", c_uint32),
        ("DeviceStatus",  c_uint32),
    ]

class GENERIC_IMU_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
        ("DeviceHK",          GENERIC_IMU_Device_HK_tlm_t),
    ]

class GENERIC_IMU_Device_Axis_Data_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("LinearAcc",  c_float),
        ("AngularAcc", c_float),
    ]

class GENERIC_IMU_Device_Data_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("X_Data", GENERIC_IMU_Device_Axis_Data_t),
        ("Y_Data", GENERIC_IMU_Device_Axis_Data_t),
        ("Z_Data", GENERIC_IMU_Device_Axis_Data_t),
    ]

class GENERIC_IMU_Device_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",   sbn.CFE_SB_Msg_t),
        ("Generic_imu", GENERIC_IMU_Device_Data_tlm_t),
    ]

# --- Magnetometer (MAG) --- 0x092A HK / 0x092B DEVICE
class GENERIC_MAG_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
    ]

class GENERIC_MAG_Device_Data_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("MagneticIntensityX", c_int32),
        ("MagneticIntensityY", c_int32),
        ("MagneticIntensityZ", c_int32),
    ]

class GENERIC_MAG_Device_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",   sbn.CFE_SB_Msg_t),
        ("Generic_mag", GENERIC_MAG_Device_Data_tlm_t),
    ]

# --- Star Tracker (ST) --- 0x0935 HK / 0x0936 DEVICE
class GENERIC_STAR_TRACKER_Device_HK_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [("DeviceCounter", c_uint32)]

class GENERIC_STAR_TRACKER_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
        ("DeviceHK",          GENERIC_STAR_TRACKER_Device_HK_tlm_t),
    ]

class GENERIC_STAR_TRACKER_Device_Data_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("Q0",      c_double),
        ("Q1",      c_double),
        ("Q2",      c_double),
        ("Q3",      c_double),
        ("IsValid", c_uint8),
    ]

class GENERIC_STAR_TRACKER_Device_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",            sbn.CFE_SB_Msg_t),
        ("Generic_star_tracker", GENERIC_STAR_TRACKER_Device_Data_tlm_t),
    ]

# --- Magnetic Torquer (actuator) --- 0x093A HK
class GENERIC_TORQUER_Device_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("Direction", c_uint8),
        ("PercentOn", c_uint8),
    ]

class GENERIC_TORQUER_Hk_tlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",         sbn.CFE_SB_Msg_t),
        ("CommandErrorCount", c_uint8),
        ("CommandCount",      c_uint8),
        ("DeviceErrorCount",  c_uint8),
        ("DeviceCount",       c_uint8),
        ("DeviceEnabled",     c_uint8),
        ("TorquerPeriod",     c_uint32),
        ("TrqInfo",           GENERIC_TORQUER_Device_tlm_t * 3),
    ]

# --- Telemetry Output (TO_LAB) --- 0x08E8 HK
class TO_LAB_HkTlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("CommandCounter",      c_uint8),
        ("CommandErrorCounter", c_uint8),
        ("spareToAlign",        c_uint8 * 2),
    ]

class TO_LAB_HkTlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Payload",   TO_LAB_HkTlm_Payload_t),
    ]

# --- Command Ingest (CI_LAB) --- 0x08E0 HK
class CI_LAB_HkTlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("CommandErrorCounter", c_uint8),
        ("CommandCounter",      c_uint8),
        ("EnableChecksums",     c_uint8),
        ("SocketConnected",     c_uint8),
        ("Spare1",              c_uint8 * 8),
        ("IngestPackets",       c_uint32),
        ("IngestErrors",        c_uint32),
        ("Spare2",              c_uint32),
    ]

class CI_LAB_HkTlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Payload",   CI_LAB_HkTlm_Payload_t),
    ]

# --- Telemetry Output (full 'to' app, Odyssey/OSR) --- 0x0880 HK
# The full TO app (not to_lab) is the one COSMOS reads and that owns the real
# downlink routing. Its HK is richer: 8 uint16 fields including usConfigRoutes /
# usEnabledRoutes (the route/destination masks) — the genuine downlink-exfil signal
# to_lab's bare command-counter HK (0x08E8) lacks. Fields sit directly under the
# struct (no Payload sub-struct), so they name as TO.usCmdCnt, TO.usEnabledRoutes, …
class TO_HkTlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",       sbn.CFE_SB_Msg_t),
        ("usCmdCnt",        c_uint16),
        ("usCmdErrCnt",     c_uint16),
        ("usMsgSubCnt",     c_uint16),
        ("usMsgSubErrCnt",  c_uint16),
        ("usTblUpdateCnt",  c_uint16),
        ("usTblErrCnt",     c_uint16),
        ("usConfigRoutes",  c_uint16),
        ("usEnabledRoutes", c_uint16),
    ]

# --- Command Ingest (full 'ci' app, Odyssey/OSR) --- 0x0884 HK
class CI_HkTlm_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",   sbn.CFE_SB_Msg_t),
        ("usCmdCnt",    c_uint16),
        ("usCmdErrCnt", c_uint16),
    ]

# --- Limit Checker (LC) --- 0x08A7 HK
class LC_HkPacket_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",           sbn.CFE_SB_Msg_t),
        ("CmdCount",            c_uint8),
        ("CmdErrCount",         c_uint8),
        ("CurrentLCState",      c_uint8),
        ("Pad8",                c_uint8),
        ("WPResults",           c_uint8 * _LC_HKWR_NUM_BYTES),
        ("APResults",           c_uint8 * _LC_HKAR_NUM_BYTES),
        ("PassiveRTSExecCount", c_uint16),
        ("WPsInUse",            c_uint16),
        ("ActiveAPs",           c_uint16),
        ("Pad16",               c_uint16),
        ("APSampleCount",       c_uint32),
        ("MonitoredMsgCount",   c_uint32),
        ("RTSExecCount",        c_uint32),
    ]

# --- Data Storage (DS) --- 0x08B8 HK
class DS_HkTlm_Payload_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("CmdAcceptedCounter",   c_uint8),
        ("CmdRejectedCounter",   c_uint8),
        ("DestTblLoadCounter",   c_uint8),
        ("DestTblErrCounter",    c_uint8),
        ("FilterTblLoadCounter", c_uint8),
        ("FilterTblErrCounter",  c_uint8),
        ("AppEnableState",       c_uint8),
        ("Spare8",               c_uint8),
        ("FileWriteCounter",     c_uint16),
        ("FileWriteErrCounter",  c_uint16),
        ("FileUpdateCounter",    c_uint16),
        ("FileUpdateErrCounter", c_uint16),
        ("DisabledPktCounter",   c_uint32),
        ("IgnoredPktCounter",    c_uint32),
        ("FilteredPktCounter",   c_uint32),
        ("PassedPktCounter",     c_uint32),
        ("FilterTblFilename",    c_char * _MAX_PATH_LEN),
    ]

class DS_HkPacket_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Payload",   DS_HkTlm_Payload_t),
    ]

# --- File Manager (FM) --- 0x088A HK
class FM_HousekeepingPkt_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",           sbn.CFE_SB_Msg_t),
        ("CommandCounter",      c_uint8),
        ("CommandErrCounter",   c_uint8),
        ("Spare",               c_uint8),
        ("NumOpenFiles",        c_uint8),
        ("ChildCmdCounter",     c_uint8),
        ("ChildCmdErrCounter",  c_uint8),
        ("ChildCmdWarnCounter", c_uint8),
        ("ChildQueueCount",     c_uint8),
        ("ChildCurrentCC",      c_uint8),
        ("ChildPreviousCC",     c_uint8),
    ]

# ===========================================================================
# Generic ADCS — Attitude Determination (0x0942) and Attitude Control (0x0944)
# added 2026-08-25 for AINOS3-95 stage 2a.
#
# Both are siblings of DI/GNC/DO on the same ADAC send path
# (generic_adcs_app.c SEND_{DI,AD,GNC,AC,DO}_CMD_CC = 3..7, all five scheduled
# in sch_def_msgtbl.c), so they publish at the same measured 1.00 /s and were
# simply never subscribed. AC is the reason for this pair: it carries each
# controller's own gains AND live error state, which the aggregate ADCS_GNC
# packet does not expose. Translated byte-exact from
# components/generic_adcs/fsw/cfs/src/generic_adcs_msg.h.
#
# ⚠ Packing trap: Inertial.h_mgmt is `long` (8 bytes on x86-64) while
# Sunsafe.h_mgmt is `uint8`. They are NOT the same width — c_long vs c_uint8.
# ===========================================================================

class Generic_ADCS_AD_Mag_Tlm_Payload_t(Structure):
    """Magnetometer contribution to attitude determination."""
    _pack_ = 1
    _fields_ = [
        ("bvb", c_double * 3),
        ("MagValid", c_uint8),
    ]

class Generic_ADCS_AD_Sol_Tlm_Payload_t(Structure):
    """Sun-vector determination; FssValid is not exposed anywhere else."""
    _pack_ = 1
    _fields_ = [
        ("SunValid", c_uint8),
        ("FssValid", c_uint8),
        ("svb",      c_double * 3),
    ]

class Generic_ADCS_AD_Imu_Tlm_Payload_t(Structure):
    """IMU rate determination. `wbn_prev` gives the previous-cycle rate, so a
    frame carries its own delta — unavailable from ADCS_GNC."""
    _pack_ = 1
    _fields_ = [
        ("init",     c_uint8),
        ("alpha",    c_double),
        ("valid",    c_uint8),
        ("wbn_prev", c_double * 3),
        ("wbn",      c_double * 3),
        ("acc",      c_double * 3),
    ]

class Generic_ADCS_AD_ST_Tlm_Payload_t(Structure):
    """Star-tracker attitude as consumed by determination.

    ⚠ Note for AINOS3-91: this is a SECOND view of the star tracker, arriving on
    a MID that is actually delivered — unlike ST_DEV 0x0936, which stage 0
    measured as subscribed-but-silent."""
    _pack_ = 1
    _fields_ = [
        ("Valid", c_uint8),
        ("qbn",   c_double * 4),
    ]

class Generic_ADCS_AD_Tlm_t(Structure):
    """GENERIC_ADCS_AD_MID 0x0942
    Per-sensor attitude-determination outputs, before fusion.
    Attack signal: a sensor's contribution diverging from the fused ADCS_GNC
    solution (spoofed sensor accepted by determination); a validity flag
    dropping while the fused solution stays confident.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Mag",       Generic_ADCS_AD_Mag_Tlm_Payload_t),
        ("Sol",       Generic_ADCS_AD_Sol_Tlm_Payload_t),
        ("Imu",       Generic_ADCS_AD_Imu_Tlm_Payload_t),
        ("ST",        Generic_ADCS_AD_ST_Tlm_Payload_t),
    ]


class Generic_ADCS_AC_Bdot_Tlm_t(Structure):
    """B-dot detumble controller: gains + the rate-of-change it acts on."""
    _pack_ = 1
    _fields_ = [
        ("b_range", c_double),
        ("Kb",      c_double),
        ("bold",    c_double * 3),
        ("bdot",    c_double * 3),
    ]

class Generic_ADCS_AC_Sunsafe_Tlm_t(Structure):
    """Sun-safe controller: gains, then its internal error state."""
    _pack_ = 1
    _fields_ = [
        ("Kp",      c_double * 3),
        ("Kr",      c_double * 3),
        ("sside",   c_double * 3),
        ("vmax",    c_double),
        ("cmd_wbn", c_double * 3),
        ("h_mgmt",  c_uint8),
        ("therr",   c_double * 3),
        ("werr",    c_double * 3),
        ("Tcmd",    c_double * 3),
        ("err_t",   c_double),
    ]

class Generic_ADCS_AC_Inertial_Tlm_t(Structure):
    """Inertial-pointing controller: gains (incl. the integral term Ki) plus
    therr / sumtherr / werr / qErr — the live error state AINOS3-86 needs and
    which no currently-subscribed packet carries.

    ⚠ h_mgmt is `long` here, not `uint8` as in the Sunsafe struct."""
    _pack_ = 1
    _fields_ = [
        ("Kp",         c_double * 3),
        ("Kr",         c_double * 3),
        ("Ki",         c_double * 3),
        ("phiErr_max", c_double),
        ("qbn_cmd",    c_double * 4),
        ("h_mgmt",     c_long),
        ("therr",      c_double * 3),
        ("sumtherr",   c_double * 3),
        ("qErr",       c_double * 4),
        ("werr",       c_double * 3),
        ("Tcmd",       c_double * 3),
    ]

class Generic_ADCS_AC_Tlm_t(Structure):
    """GENERIC_ADCS_AC_MID 0x0944
    Per-mode attitude-control gains and internal error state, for all three
    controllers simultaneously (only the active one is meaningful).
    Attack signal: a gain changing without a commanded reconfiguration
    (the ADCS/GN&C sheets rate "change in control logic/algorithms" High);
    an integrator (Inertial.sumtherr) winding up while the fused solution
    still looks nominal.
    """
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("Bdot",      Generic_ADCS_AC_Bdot_Tlm_t),
        ("Sunsafe",   Generic_ADCS_AC_Sunsafe_Tlm_t),
        ("Inertial",  Generic_ADCS_AC_Inertial_Tlm_t),
    ]

# ===========================================================================
# CFDP telemetry — CF HK (0x08B0), added 2026-08-25 for AINOS3-95 stage 2b.
# CF is pure-software CFDP (no hardware sim), scheduled + transmitted, so OnAIR
# receives it (verified live: 20 packets / 90 s).
#
# ⚠ CAM (0x08C8) and SYN (0x08FC) were subscribed and then REMOVED after live
# verification: their apps load but produce NO telemetry in the headless
# `make launch-quiet` pipeline that runs soaks/corpus —
#   * cam-sim launches ONLY via the GUI `make launch` (launch.sh:124, gnome-terminal),
#     not headless; so CAM HK never flows in the recording pipeline.
#   * syn has NO simulator at all (absent from launch.sh and nos3-simulator.xml).
# This overturns the AINOS3-95 gap-analysis claim that CAM/SYN made the payload
# sheets "subscribable now" — they are not, in the pipeline that matters.
#
# ⚠ Also EXCLUDED after source inspection (do not "helpfully" add them):
#   CAM_EXP  0x08C9 — Exp_Pkt is init'd but never TransmitMsg'd (cam_app.c)
#   SYN_DEV  0x08FD — transmit is commented out (syn_app.c:172)
#   SB_STATS 0x080A — command-produced, 0 scheduler entries (needs FSW work)
# ===========================================================================



class CF_HkCmdCounters_t(Structure):
    _pack_ = 1
    _fields_ = [("cmd", c_uint16), ("err", c_uint16)]

class CF_HkSent_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("file_data_bytes",      c_uint64),
        ("pdu",                  c_uint32),
        ("nak_segment_requests", c_uint32),
    ]

class CF_HkRecv_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("file_data_bytes",      c_uint64),
        ("pdu",                  c_uint32),
        ("error",                c_uint32),
        ("spurious",             c_uint16),
        ("dropped",              c_uint16),
        ("nak_segment_requests", c_uint32),
    ]

class CF_HkFault_t(Structure):
    """File-operation fault counters — static in nominal, so any increment is a
    file-op fault burst (relevant to EX-0010 wiper/ransomware and EXF exfil)."""
    _pack_ = 1
    _fields_ = [
        ("file_open",          c_uint16),
        ("file_read",          c_uint16),
        ("file_seek",          c_uint16),
        ("file_write",         c_uint16),
        ("file_rename",        c_uint16),
        ("directory_read",     c_uint16),
        ("crc_mismatch",       c_uint16),
        ("file_size_mismatch", c_uint16),
        ("nak_limit",          c_uint16),
        ("ack_limit",          c_uint16),
        ("inactivity_timer",   c_uint16),
        ("spare",              c_uint16),
    ]

class CF_HkCounters_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("sent",  CF_HkSent_t),
        ("recv",  CF_HkRecv_t),
        ("fault", CF_HkFault_t),
    ]

class CF_HkChannel_Data_t(Structure):
    _pack_ = 1
    _fields_ = [
        ("counters",         CF_HkCounters_t),
        ("q_size",           c_uint16 * 7),      # CF_QueueIdx_NUM
        ("poll_counter",     c_uint8),
        ("playback_counter", c_uint8),
        ("frozen",           c_uint8),
        ("spare",            c_uint8 * 7),
    ]

class CF_HkPacket_t(Structure):
    """CF_HK_TLM_MID 0x08B0 — CFDP file-transfer housekeeping.
    channel0/channel1 are modelled as explicit members rather than a [2] array
    (identical wire layout under _pack_=1) so OnAIR's field-walker emits numeric
    per-channel columns instead of one opaque array cell.
    ⚠ Expect most channel fields constant-0 in nominal ops — CF is idle unless a
    file transfer is running; the security value is the fault counters latching."""
    _pack_ = 1
    _fields_ = [
        ("TlmHeader", sbn.CFE_SB_Msg_t),
        ("counters",  CF_HkCmdCounters_t),
        ("spare",     c_uint8 * 4),
        ("channel0",  CF_HkChannel_Data_t),
        ("channel1",  CF_HkChannel_Data_t),
    ]

# ===========================================================================
#  CS — Checksum app housekeeping                       MID 0x08A4
#  Source: fsw/apps/cs/fsw/inc/cs_msg.h  (CS_HkPacket_t)
#  Added AINOS3-111: on-board integrity monitoring. CS CRCs the cFE core, OS
#  code segment, and the 23 NOS3 app code segments (cfg/nos3_defs/tables/
#  cs_apptbl.c) and telemeters per-domain miscompare counters + state. The
#  *ErrCounter fields are the attack signal: they are 0 in nominal ops and
#  latch on any code/table corruption (EX-0004 / EX-0005 class).
#  cpuaddr is 64-bit on this target -> c_uint64.
# ===========================================================================

class CS_HkPacket_t(Structure):
    """CS_HK_TLM_MID 0x08A4 — Checksum-app integrity housekeeping.
    The six *CSState fields report per-domain enable/disable; the six
    *ErrCounter fields are miscompare counts (0 in nominal, latch on
    corruption). PassCounter increments each full sweep of all tables —
    a frozen PassCounter means CS stopped checksumming (denial)."""
    _pack_ = 1
    _fields_ = [
        ("TlmHeader",                   sbn.CFE_SB_Msg_t),
        ("CmdCounter",                  c_uint8),
        ("CmdErrCounter",               c_uint8),
        ("ChecksumState",               c_uint8),
        ("EepromCSState",               c_uint8),
        ("MemoryCSState",               c_uint8),
        ("AppCSState",                  c_uint8),
        ("TablesCSState",               c_uint8),
        ("OSCSState",                   c_uint8),
        ("CfeCoreCSState",              c_uint8),
        ("RecomputeInProgress",         c_uint8),
        ("OneShotInProgress",           c_uint8),
        ("Filler8",                     c_uint8),
        ("EepromCSErrCounter",          c_uint16),
        ("MemoryCSErrCounter",          c_uint16),
        ("AppCSErrCounter",             c_uint16),
        ("TablesCSErrCounter",          c_uint16),
        ("CfeCoreCSErrCounter",         c_uint16),
        ("OSCSErrCounter",              c_uint16),
        ("CurrentCSTable",              c_uint16),
        ("CurrentEntryInTable",         c_uint16),
        ("EepromBaseline",              c_uint32),
        ("OSBaseline",                  c_uint32),
        ("CfeCoreBaseline",             c_uint32),
        ("LastOneShotAddress",          c_uint64),
        ("LastOneShotSize",             c_uint32),
        ("LastOneShotMaxBytesPerCycle", c_uint32),
        ("LastOneShotChecksum",         c_uint32),
        ("PassCounter",                 c_uint32),
    ]


# --- struct-size guard (merge=ours drift protection) ---
# message_headers.py is a merge=ours file, so upstream FSW C-struct changes are
# silently masked here. These sizes were verified byte-exact against the component
# *_msg.h structs (see the MagValid / NOVATEL lat-lon-alt fixes). A mismatch means
# the Python layout drifted from the C struct -> fail loudly at import instead of
# recording misaligned garbage. On a legitimate C-struct change, re-audit and update.
import ctypes as _ct
_EXPECTED_STRUCT_SIZES = {
    "CFE_ES_HousekeepingTlm_t": 164,
    "CFE_EVS_AppTlmData_t": 8,
    "CFE_EVS_HousekeepingTlm_t": 160,
    "CFE_EVS_LongEventTlm_t": 172,
    "CFE_EVS_PacketID_t": 32,
    "CFE_SB_AllSubscriptionsTlm_t": 188,
    "CFE_SB_HousekeepingTlm_t": 44,
    "CFE_SB_SubEntries_t": 8,
    "CFE_TBL_HousekeepingTlm_t": 298,
    "CFE_TIME_HousekeepingTlm_t": 40,
    "CF_HkChannel_Data_t": 88,
    "CF_HkCmdCounters_t": 4,
    "CF_HkCounters_t": 64,
    "CF_HkFault_t": 24,
    "CF_HkPacket_t": 200,
    "CF_HkRecv_t": 24,
    "CF_HkSent_t": 16,
    "CI_HkTlm_t": 20,
    "CI_LAB_HkTlm_Payload_t": 24,
    "CI_LAB_HkTlm_t": 40,
    "CS_HkPacket_t": 80,
    "DS_HkPacket_t": 112,
    "DS_HkTlm_Payload_t": 96,
    "FM_HousekeepingPkt_t": 26,
    "GENERIC_CSS_Device_Data_tlm_t": 12,
    "GENERIC_CSS_Device_tlm_t": 28,
    "GENERIC_CSS_Hk_tlm_t": 21,
    "GENERIC_EPS_Device_HK_tlm_t": 64,
    "GENERIC_EPS_Hk_tlm_t": 84,
    "GENERIC_EPS_Switch_tlm_t": 6,
    "GENERIC_FSS_Device_Data_tlm_t": 9,
    "GENERIC_FSS_Device_tlm_t": 25,
    "GENERIC_FSS_Hk_tlm_t": 21,
    "GENERIC_IMU_Device_Axis_Data_t": 8,
    "GENERIC_IMU_Device_Data_tlm_t": 24,
    "GENERIC_IMU_Device_HK_tlm_t": 8,
    "GENERIC_IMU_Device_tlm_t": 40,
    "GENERIC_IMU_Hk_tlm_t": 29,
    "GENERIC_MAG_Device_Data_tlm_t": 12,
    "GENERIC_MAG_Device_tlm_t": 28,
    "GENERIC_MAG_Hk_tlm_t": 21,
    "GENERIC_RADIO_Device_HK_tlm_t": 12,
    "GENERIC_RADIO_Device_tlm_t": 28,
    "GENERIC_RADIO_Hk_tlm_t": 33,
    "GENERIC_RW_Data_t": 24,
    "GENERIC_RW_HkTlm_t": 51,
    "GENERIC_STAR_TRACKER_Device_Data_tlm_t": 33,
    "GENERIC_STAR_TRACKER_Device_HK_tlm_t": 4,
    "GENERIC_STAR_TRACKER_Device_tlm_t": 49,
    "GENERIC_STAR_TRACKER_Hk_tlm_t": 25,
    "GENERIC_THRUSTER_Hk_tlm_t": 21,
    "GENERIC_TORQUER_Device_tlm_t": 2,
    "GENERIC_TORQUER_Hk_tlm_t": 31,
    "Generic_ADCS_AC_Bdot_Tlm_t": 64,
    "Generic_ADCS_AC_Inertial_Tlm_t": 248,
    "Generic_ADCS_AC_Sunsafe_Tlm_t": 185,
    "Generic_ADCS_AC_Tlm_t": 513,
    "Generic_ADCS_AD_Imu_Tlm_Payload_t": 82,
    "Generic_ADCS_AD_Mag_Tlm_Payload_t": 25,
    "Generic_ADCS_AD_ST_Tlm_Payload_t": 33,
    "Generic_ADCS_AD_Sol_Tlm_Payload_t": 26,
    "Generic_ADCS_AD_Tlm_t": 182,
    "Generic_ADCS_DI_Css_Sensor_Payload_t": 40,
    "Generic_ADCS_DI_Css_Tlm_Payload_t": 265,
    "Generic_ADCS_DI_Fss_Tlm_Payload_t": 57,
    "Generic_ADCS_DI_Imu_Tlm_Payload_t": 105,
    "Generic_ADCS_DI_Mag_Tlm_Payload_t": 56,
    "Generic_ADCS_DI_Rw_Tlm_Payload_t": 120,
    "Generic_ADCS_DI_St_Tlm_Payload_t": 65,
    "Generic_ADCS_DI_Tlm_Payload_t": 668,
    "Generic_ADCS_DI_Tlm_t": 684,
    "Generic_ADCS_DO_Rw_TlmPayload_t": 96,
    "Generic_ADCS_DO_Tlm_t": 168,
    "Generic_ADCS_DO_Trq_TlmPayload_t": 56,
    "Generic_ADCS_GNC_Hmgmt_t": 59,
    "Generic_ADCS_GNC_Tlm_t": 327,
    "Generic_ADCS_Hk_tlm_t": 18,
    "LC_HkPacket_t": 172,
    "NOVATEL_OEM615_Device_Data_tlm_t": 86,
    "NOVATEL_OEM615_Device_tlm_t": 102,
    "NOVATEL_OEM615_Hk_tlm_t": 21,
    "SAMPLE_Device_HK_tlm_t": 12,
    "SAMPLE_Hk_tlm_t": 33,
    "SBN_ModuleStatusTlm_t": 82,
    "SCH_HkPacket_t": 68,
    "SC_HkTlm_t": 92,
    "TO_HkTlm_t": 32,
    "TO_LAB_HkTlm_Payload_t": 4,
    "TO_LAB_HkTlm_t": 20,
}
_size_mismatches = [
    f"{_n}: {_ct.sizeof(globals()[_n])}B != expected {_sz}B"
    for _n, _sz in _EXPECTED_STRUCT_SIZES.items()
    if _n in globals() and _ct.sizeof(globals()[_n]) != _sz
]
assert not _size_mismatches, (
    "message_headers struct layout drifted from the FSW C structs "
    "(merge=ours drift) -> " + "; ".join(_size_mismatches) +
    " -- re-audit against the component *_msg.h and update _EXPECTED_STRUCT_SIZES."
)
