# Microphonics

`applications/microphonics/` captures and analyzes mechanical vibration noise that couples into cavity frequency. Microphonics appear as RF amplitude/phase jitter and must be understood and mitigated to maintain beam quality.

## What it measures

Mechanical vibrations (from cryo pumps, building HVAC, acoustic noise) couple through the cryomodule structure into cavity frequency. The microphonics application reads the cavity detuning PV (`DFBEST` or equivalent) at high sample rates and computes:

- **RMS detuning** — overall noise level
- **Peak detuning** — worst-case excursion
- **FFT spectrum** — identifies dominant vibration frequencies
- **Spectrogram** — time-frequency map showing transient or periodic sources
- **Histogram** — detuning distribution (Gaussian = random noise, non-Gaussian = deterministic source)

## GUI structure

```
MicrophonicsGUI (PyDM Display)
├── Left panel (40%)
│   ├── ConfigPanel — cavity selection, duration, sample rate, file output options
│   └── StatusPanel — live RMS, peak, mean, variance
└── Right panel (60%)
    └── PlotPanel
        ├── TimeSeries plot
        ├── FFTPlot
        ├── SpectrogramPlot
        └── HistogramPlot (pyqtgraph)
```

## Key classes

### `AsyncDataManager` (`gui/async_data_manager.py`)

Worker thread pool managing data acquisition jobs. Emits:
- `acquisitionProgress(int)` — 0–100 during acquisition
- `acquisitionError(str)` — error message
- `jobComplete(np.ndarray)` — measured detuning array when done

### `ConfigPanel` (`gui/config_panel.py`)

User inputs: cavity selector, measurement duration (seconds), sample rate (Hz), optional file output path. Produces a `MeasurementConfig` dataclass passed to the worker.

### `DataLoader` (`gui/data_loader.py`)

Reads previously saved measurements from `.npy` or HDF5 files and replays them through the same plot pipeline. Useful for offline analysis.

### Plot classes (`plots/`)

| Class | Notes |
|-------|-------|
| `TimeSeries` | Scrolling time-domain detuning |
| `FFTPlot` | Single-sided amplitude spectrum |
| `SpectrogramPlot` | Incremental sliding-window update (not full recalculation per frame) |
| `HistogramPlot` | Distribution with Gaussian overlay |

## Non-obvious design

- **Incremental spectrogram**: The spectrogram appends new frequency bins as time advances rather than recomputing the full matrix each update. This keeps the GUI responsive for long (>60 s) acquisitions.
- **PV batch fetch**: `format_pv_base()` converts cavity identifiers to standardized PV names; acquisition batches the channel-access requests to minimize round-trip latency.
- **Worker isolation**: Errors in the acquisition worker are caught and re-emitted as signals — they never crash the GUI event loop.

## Entry point

```bash
sc-microphonics   # (if registered) or launched from SRF Home
```
