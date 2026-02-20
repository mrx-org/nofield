# Niivue Component Specification

## Intent
Modular medical imaging component for 3D/orthographic NIfTI visualization and interactive scanner Field of View (FOV) planning.

## Core Functionality
- **Visualization**: WebGL-accelerated volume rendering with crosshair-synchronized slices.
- **FOV Planning**: Interactive 3D box manipulation to define physical scanner coordinates (size, offset, rotation).
- **Coordinate Math**: Logic for voxel-to-world (mm) mapping using NIfTI Q-form/S-form headers.
- **Shared State**: Emits real-time `fov_changed` events via a central hub.
- **Volume Management**: Session-aware volume list with reverse chronological ordering, unique numbering, and Title+Meta styling.
- **Visual Feedback**: Green pulse highlight on the viewer and volume list when new data is added.
- **Interactions**: 
  - Standardized mouse gestures: Ctrl+Left (Move FOV), Ctrl+Right (Rotate FOV), Ctrl+Scroll (Resize FOV), Ctrl+Middle Drag (Zoom).
  - Automatic mode switching to "Planning" on any viewer interaction.

## Modular API
- **Class**: `NiivueModule`
- **Parts**: 
  - `renderViewer(target)`: The WebGL canvas and status overlay.
  - `renderControls(target)`: Compact tabbed UI (VIEWER, OPTIONS, FOV).
- **Key Methods**:
  - `loadUrl(url, name, isAdding)`: Robust additive or destructive volume loading with initialization queuing.
  - `triggerHighlight()`: Triggers the green visual feedback animation.
  - `updateVolumeList()`: Rebuilds the synchronized management UI.

## Phantom JSON Execution (viewer)
- **JSON tab** (only when using `viewer.html`): Lists JSON phantom config filenames from the current session; selecting one shows its content in a CodeMirror editor. Buttons: **Save** / **Save As** / **Revert** (in VFS), **Execute** (runs phantom and loads result into the viewer).
- **Add Folder**: User selects a folder; all NIfTIs and JSONs are uploaded to Pyodide’s VFS under `/phantom`. No raw NIfTIs are loaded into Niivue; the user picks one JSON (from a dialog or the JSON tab), then **Execute** runs.
- **Execute**: Calls the same logic as the standalone `data/execute_json.py` inside Pyodide: `write_executed=False`, `write_averaged=True`, output to `/phantom/averaged`. Produces 3D density-weighted averaged maps (density, T1, T2, T2′, ADC, dB0, B1+, B1−) with NaN where total density ≤ threshold (default 0.01). Resulting NIfTIs are read from VFS and loaded into Niivue as one volume group (label `*_averaged`).
- **Single source of truth**: Phantom execution logic lives in `data/execute_json.py`; the viewer fetches and runs that script in Pyodide, so CLI and browser stay in sync.

