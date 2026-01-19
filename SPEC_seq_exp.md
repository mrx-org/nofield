# Sequence Explorer Specification

## Intent
In-browser Python environment for executing PyPulseq scripts and visualizing MRI sequence waveforms.

## Core Functionality
- **Execution**: Pyodide-powered Python runtime for local sequence generation (logic freeze).
- **Dynamic UI**: Automatic generation of input controls from Python function signatures.
- **Plotting**: Optimized Matplotlib visualization of RF, Gradients (X, Y, Z), and ADC events with downsampling.
- **Integration**: Synchronizes internal sequence parameters with scanner FOV events.
- **Editor**: Built-in CodeMirror instance for live sequence logic modification.

## Modular API
- **Class**: `SequenceExplorer`
- **Parts**:
  - `renderTree(target)`: Sequence database / file tree.
  - `renderParams(target)`: Dynamic protocol parameter inputs.
  - `renderPlot(target)`: Matplotlib waveform output pane.
