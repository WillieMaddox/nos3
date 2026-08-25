---
key: AINOS3-85
slug: actuator-saturation-fidelity
type: Spike
epic: —
status: Open
priority: Backlog
opened: 2026-08-11
sprints: [27]
---

# AINOS3-85 — Reach actuator saturation for the recovery-boundary test

**Summary:** As a security researcher, I want an injection that drives the ADCS into genuine actuator saturation, so the "within-mode recovery vs no autonomous FDIR" boundary is tested empirically instead of inferred.

## Description

The Sprint-26 recovery experiment showed the FSW self-recovers a *mild*
perturbation within a mode (BDOT drove `|Mcmd|` 0→30 to null the rate) but has no autonomous
safing (no HS app). The extreme branch — a disturbance exceeding actuator authority, where the
controller CAN'T recover and, lacking FDIR, wouldn't safe itself — remained inference: the
EX-0005.02 `RW SET_TORQUE +3000` path never built real body momentum (`|Hwhl|` stayed pinned
at 0.0016; the sim didn't integrate a tumble). Find an injection that reaches saturation
(sustained/large RW torque, a body-rate initial condition, or a different actuator path),
observe whether the within-mode controller diverges, and confirm no autonomous mode-change
fires.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` An injection reproducibly drives `|wbn|` / wheel momentum past the controller's recovery
      authority (a real tumble / RW saturation), verified via `csv.DictReader`.
- [ ] `AC2` Recorded: does the within-mode controller diverge, and does `ADCS_GNC.Mode` stay put (no
      autonomous safing)? — resolving the extreme-case claim from inference to fact.
- [ ] `AC3` Any new observable it surfaces (e.g. a saturation flag) noted as a possible detector input.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
