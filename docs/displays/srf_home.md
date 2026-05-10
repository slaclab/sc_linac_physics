# SRF Home

`displays/srfhome/` is the top-level operator dashboard for the SC Linac. It serves as the central hub for launching applications, monitoring watcher services, and accessing external resources.

## Layout

```
SRFHome (PyDM Display)
├── Mini Status Panel — key PV readbacks (linac summary, fault counts, cryogenic state)
├── Links & Bookmarks Panel — buttons for Confluence, E-Log, EDM screens
└── Watcher Groupboxes (one per configured watcher)
    ├── Start / Stop buttons
    ├── Status indicator (running / stopped / failed)
    ├── Log tail (last N lines from service log file)
    └── Heartbeat PV value
```

## Watcher management

"Watchers" are long-running background services (e.g., `quench_resetter`, `tune_status_poll`) that run in tmux sessions and are monitored via EPICS heartbeat PVs.

Watchers are defined in `cli/watcher_commands.py` (`WATCHER_CONFIGS` dict). SRF Home reads this config at startup and creates groupboxes dynamically — adding a new watcher requires only a `WATCHER_CONFIGS` entry, no display code change.

Each watcher increments a heartbeat PV every loop cycle. SRF Home polls this PV; a static value (no increment for N seconds) signals a stalled process and is highlighted in the UI.

`make_watcher_groupbox()` in `utils.py` is the factory function that builds each watcher control panel from a config entry.

## Heartbeat detection logic

The heartbeat PV is the primary health indicator for watcher services. External alerting (e.g., automated email or alarm PV) can also watch for a stale heartbeat. The SRF Home UI provides the first line of visibility.

## Entry point

```bash
sc-srf-home
```
