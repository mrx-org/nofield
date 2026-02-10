# SPEC: Scan Module

The Scan Module is a core component of the No-field Scanner lab. It manages the execution of simulations (scans) and provides a queue-based interface for tracking and viewing results.

## Overview
The module bridges the gap between **Planning** (Sequence Explorer/Niivue) and **Results** (NIfTI images). It implements a "File-Pair" logic where every scan produces both a Pulseq sequence file (`.seq`) and a corresponding reconstructed volume (`.nii.gz`).

## Architecture
- **Location**: `scan_zero/`
- **Class**: `ScanModule` (defined in `scan_module.js`)
- **Styles**: `scan_module.css`
- **Dependencies**: 
    - `event_hub.js` for inter-module communication.
    - `NiivueModule` (global instance `window.nvModule`) for image data and resampling logic.
    - `Pyodide` for running the simulation engine (Python).

## Key State
- `queue`: An array of `Job` objects representing past and current scans.
- `scanCounter`: A session-based integer that provides unique prefixes (1., 2., etc.) for scans.
- `currentSequence`: The sequence currently selected in the Sequence Explorer.
- `currentFov`: The FOV geometry (size, offset, rotation) received from Niivue.

## The "Fake Scan" Engine
Since a real MRzero simulation is not yet fully integrated, the current implementation uses a **Resampling Simulation**:
1. **Trigger**: User clicks the "SCAN" button.
2. **Execution**: The module automatically triggers `SequenceExplorer.executeFunction(silent=true, scanCounter)`. This creates a protocol snapshot under User Protocols (e.g. `1_prot_gre.py`) and ensures the pulse sequence is generated in memory without switching to Sequence Mode or showing a plot. As part of this silent execution, the Sequence Explorer reads `seq.definitions['FOV'/'fov']` (if present) from the last sequence object and emits `sequence_fov_dims` so that Niivue’s FOV size X/Y/Z are synchronized to the actual sequence FOV used for the scan.
3. **Data Capture**:
    - The module retrieves the current base volume from Niivue.
    - It retrieves the current FOV box coordinates.
4. **Python Execution**: 
    - Uses `nibabel` and `scipy.ndimage.map_coordinates` in Pyodide.
    - Resamples the base volume into the exact grid defined by the FOV box.
    - **Sequence Export**: A real `.seq` file is written to the Pyodide VFS at `/outputs/scan_[N]_[TS]_[Name].seq`.
        - **Normal sequences** (e.g. `seq_gre`): The in-memory sequence object is saved via `seq.write(vfs_path)` (from `SourceManager._last_sequence` / `__main__.seq`).
        - **seq_pulseq_interpreter**: The **original** user-specified `.seq` file (path from the `seq_file` param input) is **copied** to the output path with `shutil.copy2`. This avoids relying on `seq.write()` for sequences loaded via `.read()` and ensures VIEW SEQ and Download work.
5. **Results**:
    - Generates a Blob URL for the new NIfTI file.
    - Automatically triggers **VIEW SCAN** upon completion.

## Interface & Workflow
- **SCAN Button**: Green button at the top; triggers the simulation.
- **Queue Item**: Shows the sequence number (e.g., `1.`), sequence name, and 24h timestamp.
- **Visual Feedback**: Uses a color-coded left border (Green: Done, Yellow: Scanning, Red: Error).
- **Actions**:
    - **VIEW SCAN**: Loads the NIfTI into Niivue, hides other scans, and switches to **Planning Mode**.
    - **VIEW SEQ**: Switches the app to **Sequence Mode**, reads the `.seq` file from VFS (`/outputs/...`), and plots it. For interpreter scans the file is the copy made at scan time.
    - **Download (↓)**: Exports the `.seq` file to the local machine.
    - **Remove (×)**: Deletes the job from the session queue.

## Integration Points (eventHub)
- `sequenceSelected`: Updates the "Ready" sequence name.
- `fov_changed`: Syncs internal FOV geometry for the next scan.
- `loadJob`: Interacts with `window.viewManager` to ensure the correct mode is active.

## Layout Configuration
In the `no-field_index.html` Lab Shell, the module is integrated into the 3-column footer:
```css
/* Layout in no-field_index.html */
grid-template-columns: 1fr 0.8fr 1.5fr; /* Tree | Scan | Params */
```
