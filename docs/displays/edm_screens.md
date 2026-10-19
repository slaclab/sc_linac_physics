# EDM Screens (`sc-edm`)

Opens an SRF EDM screen from the terminal, without going through SRF Home.

```bash
sc-edm --help
sc-edm cavity 02 3 --tab 4
sc-edm ssa H1 2
sc-edm freqscan 02 A
sc-edm cryo 02
sc-edm cavity 02 3 --print
```

Cryomodules are written `02` or `H1`, not `CM02`. Cavities are `1`-`8` and racks are `A` or `B`.
`sc-edm <screen> --help` shows the arguments a screen takes and its `.edl` path.

| Screen | Needs | File |
|--------|-------|------|
| `cavity` | CM, cavity, optional `--tab` | `llrf/rf_srf_cavity_main.edl` |
| `ssa` | CM, cavity | `llrf/rf_srf_ssa_cm.edl` or `_hl.edl` |
| `intlk` | CM, cavity | `llrf/rf_srf_intlk_cryo.edl` |
| `prl` | CM, cavity | `llrf/rf_srf_prl_cm.edl` |
| `waveform` | CM, cavity | `llrf/rf_srf_wf_acq_cm.edl` |
| `fault-waveform` | CM, cavity | `llrf/rf_srf_wf_fault_overview.edl` |
| `prl-rack` | CM, rack | `llrf/rf_srf_wf_prl_rack.edl` |
| `freqscan` | CM, rack | `llrf/rf_srf_freq_scan_rack{A,B}.edl` |
| `cryo` | CM | `cryo/cryo_cryomodule.edl` |
| `cryo-all` | nothing | `cryo/cryo_system_all.edl` |
| `unit-tests` | nothing | `llrf/rf_srf_cavity_unit_all.edl` |

All paths are relative to `$EDM`. The command runs `edm -x -eolc -m <macros> <file>`, and the
`edm` process exits when you close the screen. `--print` shows that command and starts nothing.
It works without `$EDM` set or EDM installed.

Cavity and rack screens get the same macros as the fault buttons, from `Cavity.edm_macro_string`.
Rack screens use the first cavity in the rack, the same as the tuning GUI's rack button.

## Adding a screen

Add an `EdmScreen` to `SCREENS` in `utils/edm_screens.py`. The subcommand, its arguments and the
help text come from that entry. To name cavity-screen tabs, add them to `CAVITY_TABS`.

## Files

- `src/sc_linac_physics/utils/edm_screens.py`: the screen catalog and the `edm` command builder
- `src/sc_linac_physics/cli/edm_commands.py`: the `sc-edm` command
