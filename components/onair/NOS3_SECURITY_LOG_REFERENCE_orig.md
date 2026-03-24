  ---                                                                                                                   
  Top 20 Telemetry/Command Logs for Attack & Anomaly Detection in NOS3                                                  
                                                                                                                        
  Based on the actual message structures in this codebase, the following are ranked by security relevance. The MIDs are
  taken directly from cpu1_msgids.h and the component *_msgids.h files.

  ---
  Attack Surface Categories

  Before the list, the attack vectors you need to cover are:

  ┌────────────────────────────────────┬────────────────────────────────────────────────┐
  │              Category              │                     Threat                     │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Command injection / replay         │ Unauthorized uplink commands via CI_LAB or SBN │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ GPS/GNSS spoofing                  │ False position injected into NovAtel OEM615    │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Attitude hijacking                 │ Unauthorized ADCS mode or actuator commands    │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Power sabotage                     │ Unauthorized EPS switch states                 │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Software bus flooding              │ Message DoS via SBN peer                       │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Persistence via table modification │ CFE_TBL or DS filter table overwrite           │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Stored command injection           │ SC (Stored Commands) RTS/ATS manipulation      │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Crypto/auth bypass                 │ CryptoLib failures surfaced via EVS            │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Eavesdropping                      │ New unexpected SBN peer or SB subscription     │
  ├────────────────────────────────────┼────────────────────────────────────────────────┤
  │ Time manipulation                  │ CFE_TIME drift to break crypto windows         │
  └────────────────────────────────────┴────────────────────────────────────────────────┘

  ---
  The Top 20

  Tier 1 - Cross-cutting Security Visibility (Must Have)

  1. CFE_EVS_LONG_EVENT_MSG_MID — 0x0808
  - Why: The single most important log. All apps emit events here, including auth failures, CryptoLib errors, app
  crashes, and unexpected state transitions. No other log gives you cross-system visibility in a single channel.
  - Key fields: AppName, EventType (DEBUG/INFO/ERROR/CRITICAL), EventID, Message
  - Threat signals: Repeated ERROR/CRITICAL events from CryptoLib, CI_LAB, or unknown app names; events from apps not in
   the scheduled startup list.

  2. CFE_SB_HK_TLM_MID — 0x0803
  - Why: Software Bus health directly exposes injection and flooding attacks.
  - Key fields: MsgSendErrorCounter, MsgReceiveErrorCounter, NoSubscribersCounter, MsgLimitErrorCounter
  - Threat signals: Spike in NoSubscribersCounter = message being sent that nobody expects (injection probe);
  MsgLimitErrorCounter spike = SB pipe flooding (DoS).

  3. CFE_SB_ALLSUBS_TLM_MID — 0x080D
  - Why: Captures every active SB subscription across all pipes. Baseline this at startup and flag any delta.
  - Key fields: Full subscription table dump (MsgID → PipeID mappings)
  - Threat signals: New subscription appearing after initialization = unauthorized process subscribing (eavesdrop or
  injection).

  4. SBN_TLM_MID — 0x08DC (from sbn_msgids.h)
  - Why: SBN is the primary external entry point. Peer connection changes indicate unauthorized external processes.
  - Key fields: PeerCount, per-peer RecvCnt, SendCnt, State
  - Threat signals: New peer appearing; RecvCnt spike from a known peer without corresponding ground station activity.

  Tier 2 - Navigation/Positioning Integrity

  5. NOVATEL_OEM615_DEVICE_TLM_MID — 0x0933
  - Why: GPS spoofing is a primary attack vector for orbital maneuver deception. The device telemetry (not just HK)
  contains the actual nav solution.
  - Key fields: Position (lat/lon/alt), velocity, SolStatus, satellite count, PDOP
  - Threat signals: Instantaneous position/velocity discontinuity; SolStatus degradation without corresponding orbital
  event; satellite count drop-then-recover (jamming pattern).

  6. NOVATEL_OEM615_HK_TLM_MID — 0x0932
  - Why: Tracks command authorization — DeviceEnabled toggling without an authorized operator command is a red flag.
  - Key fields: CommandErrorCount, CommandCount, DeviceErrorCount, DeviceEnabled
  - Threat signals: DeviceEnabled toggling; CommandErrorCount spike (attacker probing invalid commands).

  Tier 3 - Attitude Control & Actuation

  7. GENERIC_ADCS_GNC_MID — 0x0943
  - Why: The GNC telemetry contains the full commanded state (mode, torque commands, attitude error). This is the most
  information-dense ADCS packet for detecting unauthorized maneuvers. Defined in generic_adcs_msg.h as
  Generic_ADCS_GNC_Tlm_Payload_t.
  - Key fields: Mode, qbn[4] (body quaternion), qErr[4] (attitude error), Tcmd[3] (commanded torque), Mcmd[3] (momentum
  mgmt command), SunValid
  - Threat signals: Mode change without prior ground command; Tcmd non-zero with no scheduled maneuver; qErr growing
  unchecked (ADCS destabilization).

  8. GENERIC_ADCS_HK_TLM_MID — 0x0940
  - Why: CommandErrorCount vs CommandCount ratio reveals unauthorized or malformed ADCS commands.
  - Key fields: CommandErrorCount, CommandCount
  - Threat signals: High error ratio = command injection with wrong parameters.

  9. GENERIC_ADCS_DO_MID — 0x0945
  - Why: Device outputs are what actually fire actuators. Cross-referencing with GNC commands detects spoofed actuator
  signals that bypass the control loop.
  - Key fields: Trq.Mcmd[3] (torquer commands), Rw.Tcmd[3] (reaction wheel torques)
  - Threat signals: Actuator commands with no corresponding GNC command = direct actuator injection.

  10. GENERIC_REACTION_WHEEL_HK_TLM_MID — 0x0928
  - Why: Wheel speed changes without corresponding ADCS torque commands indicate direct hardware-level injection.
  - Key fields: CommandErrorCount, CommandCount, wheel speed per axis
  - Threat signals: Speed change with no preceding Rw.Tcmd in ADCS DO telemetry.

  Tier 4 - Power System

  11. GENERIC_EPS_HK_TLM_MID — 0x091A
  - Why: EPS switch manipulation (killing power to subsystems) is a high-impact sabotage vector. The
  GENERIC_EPS_Switch_cmd_t has SwitchNumber and State fields.
  - Key fields: CommandErrorCount, CommandCount, DeviceErrorCount, switch states, voltage/current from DeviceHK
  - Threat signals: Switch state changes without corresponding operator command; voltage anomalies indicating power
  drain or load injection.

  Tier 5 - Communication

  12. GENERIC_RADIO_HK_TLM_MID — 0x0930
  - Why: Tracks command and forward error counts. ForwardCount and ForwardErrorCount expose unauthorized proximity link
  usage (GENERIC_RADIO_PROXIMITY_CC).
  - Key fields: CommandErrorCount, CommandCount, ForwardErrorCount, ForwardCount, DeviceHK
  - Threat signals: ForwardCount activity without authorized cross-link operations; error spike after a CONFIG_CC
  command.

  13. GENERIC_RADIO_DEVICE_TLM_MID — 0x0931
  - Why: RF-layer anomalies (signal jamming, spoofed uplink) are visible here before any app-level impact.
  - Key fields: receive signal strength, Doppler shift, link state, frequency config
  - Threat signals: Signal strength anomalies inconsistent with orbital geometry; frequency deviating from mission plan.

  Tier 6 - Flight Software Infrastructure

  14. CFE_ES_HK_TLM_MID — 0x0800
  - Why: Executive Services tracks app lifecycle. Unexpected app restarts suggest crash exploitation.
  - Key fields: SysLogBytesUsed, ResetType, ResetSubtype, ProcessorResets, TaskCount, AppCount, RegisteredExternalLibs
  - Threat signals: ProcessorResets incrementing; AppCount changing mid-mission; ResetType not matching expected
  power-on sequence.

  15. CFE_TBL_HK_TLM_MID — 0x0804
  - Why: Table modification is the primary persistence mechanism in cFS. An attacker who can modify DS filter tables or
  LC action tables has mission-level control.
  - Key fields: NumTables, NumLoadPending, ValidationRequestCtr, ValidationResultCtr, LastUpdateTime
  - Threat signals: ValidationRequestCtr incrementing outside maintenance windows; NumLoadPending non-zero with no
  ground upload activity.

  16. CFE_TIME_HK_TLM_MID — 0x0805
  - Why: Time manipulation enables replay attack windows and breaks crypto epoch validation.
  - Key fields: ClockSource (internal/external), APIState, ReferenceTime, MET
  - Threat signals: ClockSource switching from external (GPS-derived) to internal; MET discontinuity.

  Tier 7 - Stored/Scheduled Commands

  17. SC_HK_TLM_MID (SC app - Stored Commands, currently modified per git status)
  - Why: The SC app executes pre-loaded command sequences (RTS/ATS). Unauthorized RTS enables or ATS loads create
  persistent attack payloads.
  - Key fields: RTSActiveCount, RTSExecutingCount, AtsErrCounter, LastAtsErrCmd, RTSCommandCtr, enabled RTS bitmap
  - Threat signals: RTS enabling with no operator initiation; AtsErrCounter after upload = malformed injected sequence.

  18. SCH_HK_TLM_MID (Scheduler)
  - Why: The scheduler drives when all other apps execute. Modifying the schedule table changes mission timing globally.
  - Key fields: ValidMajorFrameCount, MissedMajorFrameCount, SkippedSlotsCount, SyncAttemptsLeft
  - Threat signals: MissedMajorFrameCount spike = timing attack or resource starvation; table validation outside
  maintenance windows.

  Tier 8 - Sensor Cross-Reference

  19. GENERIC_ADCS_DI_MID — 0x0941
  - Why: Raw sensor data (IMU, magnetometer, star tracker, CSS) before the attitude determination filter.
  Cross-referencing DI (data input) with AD (attitude determination) detects sensor spoofing where injected sensor
  values differ from physical truth.
  - Key fields: Imu.wbn[3] (angular rate), Imu.acc[3] (acceleration), Mag.bvb[3] (B-field), St.q[4] (star tracker
  quaternion), St.valid, Css.valid
  - Threat signals: St.valid=0 without expected eclipse/maneuver; IMU rate inconsistent with commanded ADCS torques.

  20. CFE_EVS_HK_TLM_MID — 0x0801
  - Why: EVS housekeeping tracks per-app event counts and filter states. An attacker suppressing event output (via
  EVS_DISABLE_APP_EVENTS_CC) would show here.
  - Key fields: MessageFormatMode, OutputPort, per-registered-app filtered count, MessageTruncCounter
  - Threat signals: Event suppression for specific apps during anomaly windows; MessageTruncCounter spike = event
  flooding used to hide an attack.

  ---
  Implementation via SBN / SBN_client

  The sbn_python_client.py provides the exact interface you need. The
  components/onair/fsw/onair/data_handling/sbn_adapter.py is the reference pattern — it already does subscribe → receive
   → parse. For CSV logging, the approach is:

  SBN_Client (Python) → subscribe(MID) for all 20 → recv_msg() loop → ctypes struct parse → csv.writer row

  The JSON config file format (from cfs_sample_tlm.json) maps MID → [app_name, struct_type]. You would create one JSON
  config covering all 20 MIDs, with corresponding ctypes structs in message_headers.py.

  MID summary table for the config:

  ┌─────┬────────────┬─────────────────────────────┐
  │  #  │    MID     │         Description         │
  ├─────┼────────────┼─────────────────────────────┤
  │ 1   │ 0x0808     │ CFE EVS Long Event Messages │
  ├─────┼────────────┼─────────────────────────────┤
  │ 2   │ 0x0803     │ CFE SB Housekeeping         │
  ├─────┼────────────┼─────────────────────────────┤
  │ 3   │ 0x080D     │ CFE SB All Subscriptions    │
  ├─────┼────────────┼─────────────────────────────┤
  │ 4   │ 0x08DC     │ SBN Housekeeping            │
  ├─────┼────────────┼─────────────────────────────┤
  │ 5   │ 0x0933     │ NovAtel OEM615 Device (GPS) │
  ├─────┼────────────┼─────────────────────────────┤
  │ 6   │ 0x0932     │ NovAtel OEM615 HK           │
  ├─────┼────────────┼─────────────────────────────┤
  │ 7   │ 0x0943     │ ADCS GNC Telemetry          │
  ├─────┼────────────┼─────────────────────────────┤
  │ 8   │ 0x0940     │ ADCS Housekeeping           │
  ├─────┼────────────┼─────────────────────────────┤
  │ 9   │ 0x0945     │ ADCS Device Output          │
  ├─────┼────────────┼─────────────────────────────┤
  │ 10  │ 0x0928     │ Reaction Wheel HK           │
  ├─────┼────────────┼─────────────────────────────┤
  │ 11  │ 0x091A     │ EPS Housekeeping            │
  ├─────┼────────────┼─────────────────────────────┤
  │ 12  │ 0x0930     │ Radio Housekeeping          │
  ├─────┼────────────┼─────────────────────────────┤
  │ 13  │ 0x0931     │ Radio Device Telemetry      │
  ├─────┼────────────┼─────────────────────────────┤
  │ 14  │ 0x0800     │ CFE ES Housekeeping         │
  ├─────┼────────────┼─────────────────────────────┤
  │ 15  │ 0x0804     │ CFE Table Services HK       │
  ├─────┼────────────┼─────────────────────────────┤
  │ 16  │ 0x0805     │ CFE Time Services HK        │
  ├─────┼────────────┼─────────────────────────────┤
  │ 17  │ SC HK MID  │ Stored Commands HK          │
  ├─────┼────────────┼─────────────────────────────┤
  │ 18  │ SCH HK MID │ Scheduler HK                │
  ├─────┼────────────┼─────────────────────────────┤
  │ 19  │ 0x0941     │ ADCS Data Input (sensors)   │
  ├─────┼────────────┼─────────────────────────────┤
  │ 20  │ 0x0801     │ CFE EVS Housekeeping        │
  └─────┴────────────┴─────────────────────────────┘

  ---
  One Critical Note on CCSDS Sequence Counters

  Every CCSDS packet has a Sequence counter in the primary header (bits 0x3FFF). For replay attack detection, log this
  field for every packet. A replayed packet will have a sequence number that is out-of-order or duplicated for that MID.
   This is available on every message through Primary_Header_t.Sequence in sbn_python_client.py — it costs nothing extra
   to log.

  ---
  What to Build

  1. Create a message_headers.py with ctypes structs for all 20 message types (following the existing SAMPLE_Hk_tlm_t
  pattern in sbn_adapter.py)
  2. Create a nos3_security_tlm.json config mapping all 20 MIDs
  3. Extend sbn_adapter.py to write rows to CSV on each get_current_data() call, including CCSDS_Sequence,
  CCSDS_Seconds, CCSDS_Subseconds, and MID as leading columns for OnAir's temporal analysis

  The SC app showing as modified in git (m fsw/apps/sc) is worth reviewing before logging — any in-progress changes to
  stored command sequences would directly affect SC HK telemetry baselines.