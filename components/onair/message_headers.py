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
        ("lat",             c_float),
        ("lon",             c_float),
        ("alt",             c_float),
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
