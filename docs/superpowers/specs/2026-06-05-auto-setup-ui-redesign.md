# Auto Setup UI Redesign

**Date:** 2026-06-05
**Status:** Approved for implementation

## Context

The existing auto setup GUI (`applications/auto_setup/`) was built quickly with no attention to design. Key pain points:

- CM tabs overflow at the linac level (L3B has 20 CMs, L4B has 23 — a tab row doesn't fit)
- No color-coded status — impossible to see at a glance which cavities are running, errored, or ready
- No way to mark a cavity or CM as "do not touch" during maintenance
- Buttons do not reflect state (Set Up stays enabled while already running)
- Progress bar shows percentage but not which step is currently running
- Industrial/harsh aesthetic; operators requested something less stark

## Usage Patterns

Three primary workflows, all must be supported:

1. **Individual cavity** — one cavity acting up; operator wants to set up just that one
2. **Whole machine** — machine was turned off; set up all cavities across all linacs
3. **Cryomodule-by-cryomodule** — setting up most but not all CMs, skipping those under maintenance

## Navigation: Three-Level Tile Hierarchy

One scrollable page with no tab rows. Everything uses the same tile visual language at each level.

### Level 1 — Machine overview

A grid of **linac tiles** (L0B, L1B, L2B, L3B, L4B). L1B and L1BHL are merged into a single L1B tile. Each linac tile contains its CMs as named colored chips (same color semantics as status dots). This lets operators see all CM statuses for the entire machine at a glance without any navigation.

Linac tile chip counts: L0B (1), L1B (4), L2B (12), L3B (20), L4B (23). Chips wrap within the tile.

### Level 2 — Linac detail panel

Clicking a linac tile opens a panel below it showing **CM tiles**. Each CM tile shows the CM name, overall status, and 8 cavity status dots in a 4×2 grid. CM tiles wrap naturally — no overflow. A linac-level control bar appears at the top of the panel.

### Level 3 — CM detail panel

Clicking a CM tile opens a panel below showing **8 cavity cards** in a 4×2 grid with full controls. A CM-level control bar appears at the top of the panel.

Only one linac panel and one CM panel are open at a time. Clicking a different linac tile closes the current linac panel (and any open CM panel within it) before opening the new one. Clicking the same linac tile again closes the panel (toggle behavior).

## Color Palette

**Midnight navy + blush** — `B` from the design review.

| Role | Background | Border | Text |
|------|-----------|--------|------|
| Page background | `#0f1825` | — | — |
| Card/panel background | `#182030` | `#2a3a55` | `#a0b0c8` |
| Ready (green) | `#182a20` | `#2a5535` | `#80c8a0` |
| Running (gold) | `#2a2015` | `#5a4520` | `#e0b070` |
| Error (blush) | `#2a1520` | `#5a2840` | `#e08090` |
| Locked (muted) | `#1a1a28` | `#303050` | `#7080a0` |
| Offline (dim) | `#141820` | `#202530` | `#404858` |
| Accent / selected | — | `#6688cc` | `#a8c8f0` |

Progress bar fills use a subtle gradient within the running/ready color range.

## Status Semantics

| State | Code | Color | Icon |
|-------|------|-------|------|
| Ready | 0 | Green | `●` |
| Running | 1 | Gold | `⟳` |
| Error | 2 | Blush/pink | `✗` |
| Locked | — | Muted purple | `🔒` |
| Offline | — | Dim grey | `—` |

## Setup Step Checkboxes

The four global checkboxes — **SSA Calibration**, **Auto Tune**, **Cavity Characterization**, **RF Ramp** — remain at the top of the page near the machine controls. They apply to all Set Up operations at every level. Their current EPICS PV-backed behavior is unchanged.

## Controls at Each Level

### Machine level (sticky top bar)
- Set Up Machine *(confirmation dialog)*
- Shut Down Machine *(confirmation dialog)*
- Abort Machine *(confirmation dialog)*
- Summary counts: `● N ready  ⟳ N  ✗ N  🔒 N`

### Linac panel header
- Set Up [Linac] *(confirmation dialog)*
- Shut Down [Linac] *(confirmation dialog)*
- Abort [Linac] *(confirmation dialog)*
- Capture all ACON
- Lock [Linac]

### CM panel header
- Set Up All
- Shut Down All
- Abort All
- Lock CM

### Cavity card
- Set Up *(disabled while running or locked)*
- Turn Off *(disabled while locked)*
- Abort *(always enabled, even when locked)*
- Lock toggle `🔒`
- Expert screen link (`PyDMEDMDisplayButton`, links to `$EDM/llrf/rf_srf_cavity_main.edl`)

## Cavity Card Layout

```
┌─────────────────────────────────────────┐
│ ⟳ CAV 1                          🔒  ↗ │  ← status + lock + expert screen
│ ACON [16.6] MV · AACT 8.2 MV           │  ← ACON editable spinbox, AACT readback
│ ████████░░░░░░░  SSA Cal · 55%          │  ← progress bar + current step label
│ Waiting for SSA to reach setpoint…      │  ← status message (alarm-sensitive)
│ note: checked last shift                │  ← note field (smaller, muted)
│                                         │
│  [Set Up]  [Turn Off]  [Abort]          │  ← action buttons
└─────────────────────────────────────────┘
```

ACON is displayed as an editable `PyDMLineEdit` (or `PyDMSpinbox`) wired to the `{prefix}ACON` PV, so operators can set the target amplitude directly from the cavity card. AACT remains a read-only `PyDMLabel`. Because ACON is directly editable on each card, the per-CM "Push ADES → ACON" button is removed.

The step label next to the progress bar maps progress ranges to step names:
- 0–25%: SSA Cal
- 25–50%: Auto Tune
- 50–70%: Cavity Char
- 70–100%: RF Ramp

## Lock Feature

Lock is available at cavity, CM, and linac level.

- **Locking**: immediate — dims the card, disables Set Up and Turn Off, keeps Abort enabled
- **Unlocking**: requires a confirmation dialog to prevent accidentally re-enabling something under active maintenance
- **Cascade**: locking a CM locks all 8 of its cavities; locking a linac locks all its CMs. Unlocking a CM/linac does not automatically unlock individual cavities that were already locked before the cascade.
- **Broad operations skip locked items**: Set Up, Shut Down, and Abort at machine, linac, and CM level all skip locked cavities. This applies whether a cavity was locked individually or via cascade.
- Lock state is **local UI state only** — it does not write to EPICS PVs and does not persist between sessions. Its purpose is to prevent accidental clicks during a session.

## Confirmation Dialogs

Required for the following operations:

| Operation | Dialog text |
|-----------|-------------|
| Set Up Machine | "Set up all unlocked cavities across the entire machine?" |
| Shut Down Machine | "Shut down all unlocked cavities across the entire machine?" |
| Abort Machine | "Abort all running setup operations?" |
| Set Up [Linac] | "Set up all unlocked cavities in [Linac]?" |
| Shut Down [Linac] | "Shut down all unlocked cavities in [Linac]?" |
| Abort [Linac] | "Abort all running setup operations in [Linac]?" |
| Unlock cavity/CM/linac | "Unlock [name]? Make sure no one is working on it." |

## Implementation Scope

This is a **frontend-only redesign**. No changes to:
- Backend classes (`SetupCavity`, `SetupCryomodule`, `SetupLinac`, `SetupMachine`)
- EPICS PV definitions or naming
- CLI launchers
- The `Settings` dataclass (checkbox state sharing)

Files to rewrite:
- `frontend/gui_cavity.py` — `GUICavity`
- `frontend/gui_cryomodule.py` — `GUICryomodule`
- `frontend/gui_linac.py` — `GUILinac`
- `setup_gui.py` — `SetupGUI` top-level layout

New stylesheet constants should live in a new `frontend/style.py` file.
