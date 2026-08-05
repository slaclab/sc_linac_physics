# RF Commissioning Visual Redesign

**Date:** 2026-08-05
**Status:** Approved, ready for implementation

## Goal

Make the RF commissioning app feel less "masculine"/techy — replace the neon green/cyan dark theme with a softer muted dark palette, use system fonts for labels, and replace the terminal-style log with an activity feed.

## Design Decisions

### 1. Color Palette — Cool Muted Dark

Backgrounds shift from neutral gray to blue-gray tinted. All neon/electric accent colors replaced with muted equivalents.

| Token | Old | New | Role |
|---|---|---|---|
| `BG_DEEP` | `#1e1e1e` | `#1c1f26` | Deepest background (window, plot areas) |
| `BG_PANEL` | `#2a2a2a` | `#242830` | Panel/card backgrounds |
| `BG_INTERACTIVE` | `#2b2b2b` | `#2d3344` | Dropdowns, input fields, chips |
| `BG_INSET` | — | `#1c2030` | PV value inset backgrounds |
| `BORDER` | `#4a4a4a` | `#353a45` | Default borders |
| `BORDER_EMPHASIS` | `#555` | `#454c5e` | Focused/active borders |
| `TEXT_PRIMARY` | `#dddddd` | `#c9cdd6` | Main readable text |
| `TEXT_SECONDARY` | `#aaaaaa` | `#8b96a8` | Labels, captions |
| `TEXT_MUTED` | `#888888` | `#5a6278` | Hints, timestamps, disabled |
| `COLOR_SUCCESS` | `#4CAF50` | `#4ab782` | Completed phases, pass, synced |
| `COLOR_PRIMARY` | `#2563eb` / `#2196F3` | `#7b8cde` | Primary buttons, current phase indicator |
| `COLOR_WARNING` | `#FF9800` | `#d4956a` | Out-of-sync, warnings |
| `COLOR_ERROR` | `#dc2626` / `#ef5350` | `#c0544a` | Abort, errors, failed phases |
| `COLOR_DISABLED` | `#475569` | `#353a45` | Disabled button backgrounds |
| `TEXT_DISABLED` | `#94a3b8` | `#5a6278` | Disabled button text |
| `ACCENT_PV` | `#4a9eff` (cyan) | `#8b96c4` | Left-border accent on PV labels |
| `ACCENT_LOCAL` | `#ff9a4a` (bright orange) | `#c4956b` | Left-border accent on local value labels |
| `BG_PV` | `#1a2a3a` | `#1c2030` | PV label background |
| `BG_LOCAL` | `#2a2a1a` | `#211d18` | Local label background (warm tint) |

### 2. Typography

- **Labels, descriptions, headings:** `system-ui, -apple-system, sans-serif` — no more monospace for non-data text
- **Hardware values, IDs, measurements:** `'SF Mono', 'Menlo', 'Consolas', monospace` — monospace only where it adds meaning (actual numbers from hardware)
- Section header labels: 9–10px, `font-weight: 600`, `letter-spacing: 0.05–0.08em`, `text-transform: uppercase`, `color: TEXT_MUTED`

### 3. Spacing & Shape

- Border radius: **8px** for cards/panels, **6px** for buttons/badges, **5px** for input fields and chips
- Panel padding: **12px** interior, **16px** for header/toolbar areas
- Gap between panels: **12px**
- More breathing room between label and its value field (6px margin)

### 4. Activity Feed (replaces terminal log)

The `Phase History` terminal-style log is replaced with a feed:

```
● Results saved (ID: 2)         ← dot in COLOR_SUCCESS
  3:41 PM

● Frequency tuning completed    ← dot in COLOR_SUCCESS
  3:41 PM

● Executing step: record_results  ← dot in COLOR_PRIMARY
  3:41 PM

● Stage 4 complete: ...          ← dot in TEXT_MUTED
  3:41 PM
```

- Bullet dot color encodes status: success=`COLOR_SUCCESS`, in-progress=`COLOR_PRIMARY`, info=`TEXT_MUTED`
- Timestamp on its own line below each entry, in `TEXT_MUTED`
- `system-ui` font, 11px body, 10px timestamp
- Container: `BG_PANEL` background, `BORDER` border, `8px` radius

### 5. Button Styles

| Button | Before | After |
|---|---|---|
| Primary (Start/Run) | Solid `#2563eb` | Solid `COLOR_PRIMARY` (`#7b8cde`) |
| Pause | Solid `#f59e0b` amber | Ghost: transparent bg, `BORDER_EMPHASIS` border |
| Abort | Solid `#dc2626` | Ghost: transparent bg, `COLOR_ERROR` border + text |
| Complete badge | Green solid | Subtle: `COLOR_SUCCESS` bg at 12% opacity, border at 25% |

## Implementation Approach

**Option B — Centralized theme module.** Extend the existing `ui/builders/styles.py` into a `ui/builders/theme.py` with all color and font tokens as named constants. All `setStyleSheet()` calls across the frontend import from `theme.py` rather than hardcoding hex values.

### Files to create/modify

1. **Create** `ui/builders/theme.py` — all color tokens, font stacks, border-radius constants
2. **Modify** `ui/builders/styles.py` — replace hardcoded values with references to `theme.py` constants; keep the same public names (`PV_LABEL_STYLE`, `PV_CAP_STYLE`, etc.) since they're imported in `builders/__init__.py`, `base.py`, and `phase_builders.py`
3. **Modify** `ui/builders/base.py` — update button/toolbar styles
4. **Modify** `ui/container/header.py` — header background, borders, combo styles
5. **Modify** `ui/container/sync.py` — synced/out-of-sync colors
6. **Modify** `ui/container/progress_panel.py` — phase node colors
7. **Modify** `ui/container/notes.py` — notes panel colors, quick-add button
8. **Modify** `ui/magnet_status_badge.py` — QPalette colors
9. **Modify** `ui/displays/` and `ui/controllers/` — any inline styles

### Activity feed changes

The `Phase History` widget (`history_text`, a `QTextEdit` with `color: #00ff00` on `background-color: #1a1a1a`) is in `ui/builders/base.py:302`. Entries are appended via `self.history_text.append(f"[{timestamp}] {message}")` in `ui/phase_display_base.py:105`.

Replace the `QTextEdit` with a custom `ActivityFeedWidget` (`QScrollArea` containing a `QVBoxLayout` of rows):
- Each row: colored `QLabel` dot + `QLabel` message + `QLabel` timestamp
- Dot color determined by entry type: success=`COLOR_SUCCESS`, progress=`COLOR_PRIMARY`, info=`TEXT_MUTED`
- Expose an `append(message, entry_type="info")` method so `phase_display_base.py:105` only needs a minor signature update
- `base_placeholder.py:216` calls `self.history_text.clear()` — implement `clear()` on the new widget

## Out of Scope

- Layout structure (panel positions, splitters) — unchanged
- Plot/chart styling (matplotlib/pyqtgraph widgets) — unchanged
- `.ui` file changes — none exist in this app
- Dark/light mode toggle — not added
