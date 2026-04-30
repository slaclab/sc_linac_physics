# Tuning

`applications/tuning/` manages cavity frequency control during operation. Cavities must stay near resonance (within ~20 Hz for normal operation) or be parked/landed to a cold reference frequency when not in use.

## Cavity tuning states

Each cavity has a `tune_config` PV with four possible states:

| Value | Constant | Meaning |
|-------|----------|---------|
| 0 | `TUNE_CONFIG_RESONANCE_VALUE` | On resonance, ready for beam |
| 1 | `TUNE_CONFIG_COLD_VALUE` | Landed at cold/parked frequency |
| 2 | `TUNE_CONFIG_PARKED_VALUE` | Stepper parked at a defined reference |
| 3 | `TUNE_CONFIG_OTHER_VALUE` | Transitioning or unknown |

## `TuningGUI` (`tuning_gui.py`)

PyDM Display showing a grid of `CavitySection` widgets — one per cavity across all cryomodules. Each `CavitySection` shows:
- Tune state selector (enum combobox → writes `tune_config` PV)
- Stepper offset spinbox (manual nudge)
- Frequency detune readback (Hz)
- Tuning mode indicator

The GUI reads current state from EPICS and allows operators to manually command state transitions and issue stepper moves.

## `state/` subpackage — background polling and persistence

The `state/` subpackage runs as a background watcher service (`sc-watcher start tune_status_poll`). Its purpose is to persist a historical record of tuning state for trend analysis and offline replay.

### `tune_status_poll.py`

Each iteration (~every N seconds):
1. Batch-reads all 296 cavity `tune_config` and `df_cold` PVs via `PVBatch.get_values()`
2. Upserts current values into SQLite `cavity_state` table
3. Appends a versioned snapshot to `df_cold_version` table (append-only, never updated)
4. Writes a JSON summary to `{json_dir}/tune_status.json` for low-latency GUI consumption

The dual-persistence approach (SQLite for historical queries + JSON file for live reads) avoids database overhead on every GUI refresh.

### `tune_status_query.py`

Query tool for retrieving historical snapshots. Used by operators investigating drift or step changes in cavity frequency.

### `common.py`

Shared DB connection setup, table definitions, and batch PV name construction.

## Non-obvious design choices

- **`PVBatch.get_values()` for bulk reads** — avoids creating 592 PV objects (296 cavities × 2 PVs) just for polling. PV objects have connection overhead; `caget_many()` is faster for one-shot reads.
- **Versioned `df_cold` table** — every sample is a new row with a timestamp. Enables reconstruction of the full frequency drift history for each cavity without scanning archived PVs.
- **JSON for GUI reads** — the tuning display reads the JSON file rather than querying SQLite directly, eliminating database lock contention during high-frequency UI refresh.

## Entry points

```bash
sc-tune                               # GUI
sc-watcher start tune_status_poll     # background polling service
sc-cold-tune -cm 01 -cav 3           # manual cold-landing command
```
