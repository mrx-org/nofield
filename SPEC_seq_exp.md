# Sequence Explorer Specification

## Intent
In-browser Python environment for executing PyPulseq scripts and visualizing MRI sequence waveforms.

## Core Functionality
- **Execution**: Pyodide-powered Python runtime for local sequence generation.
- **Silent Execution**: Support for background sequence generation (without mode switching or plotting) for simulation workflows.
- **Dynamic UI**: Automatic generation of input controls from Python function signatures.
- **Plotting**: Optimized Matplotlib visualization of RF, Gradients (X, Y, Z), and ADC events with downsampling.
- **Integration**: Synchronizes internal sequence parameters with scanner FOV events and emits `sequenceSelected` for other modules.
- **Editor**: Built-in CodeMirror instance for live sequence logic modification.

## Modular API
- **Class**: `SequenceExplorer`
- **Parts**:
  - `renderTree(target)`: Sequence database / file tree.
  - `renderParams(target)`: Dynamic protocol parameter inputs.
  - `renderPlot(target)`: Matplotlib waveform output pane.
- **Key Methods**:
  - `executeFunction(silent)`: Executes the current sequence with optional UI suppression.

---

## Cases

### 1. Web Scraping and sources_config

This is what the sources_config.py does. We scrape:
- pypulseq examples from GitHub folder
- mrseq sequences from the mrseq module
- MRzero sequences from the playground (GitHub folder)
- specific .py files from GitHub or a remote website
- sequences from a local folder (built-in), e.g. served from localhost

All of them are loaded in the seq explorer and mirrored into the local Pyodide structure so they can be remixed. For remixing and playback, each file carries a **mini TOML** header (see below). Config sources use `type` ("file" | "folder" | "module"), `path` (or `url`), optional `name` (tree label), **`seq_func`** (entry-point function; legacy: `base_sequence`), and `dependencies`.

### 2. Mini TOML in each file

Each sequence or protocol file has a header that describes dependencies and metadata. With this header, the app can install deps, resolve imports, and run the file.

**TOML schema (single source of truth):**
- **`[dependencies]`**: package specs (e.g. `pypulseq = "*"`).
- **`[metadata]`**:
  - **`kind`**: `"sequence"` | `"protocol"` — whether this file is a sequence or a protocol wrapper.
  - **`seq_func_file`**: path/module of the **sequence we use** (call target). For a sequence file = this file; for a protocol = the file we import from and call.
  - **`seq_func`**: name of the **function we call** (call target). For a sequence = this file’s function; for a protocol = the base sequence (e.g. `seq_gre`, `main`). Protocol files do **not** store their own name in TOML.
  - **`type`**: `"file"` | `"module"` (loader type).

**Example — sequence file:**
```python
# Source configuration (TOML format)
_source_config_toml = """
[dependencies]
    pypulseq = "*"

[metadata]
kind = "sequence"
seq_func_file = "built_in_seq/mr0_rare_2d_seq.py"
seq_func = "seq_RARE_2D"
type = "file"
"""
```

**Example — protocol file (wraps a sequence; TOML only describes the call target):**
```python
# Source configuration (TOML format)
_source_config_toml = """
[dependencies]
    pypulseq = "*"

[metadata]
kind = "protocol"
seq_func_file = "built_in_seq/gre_seq.py"
seq_func = "seq_gre"
type = "file"
"""
# ... import and def prot_gre(...): return seq_gre(**kwargs)
```

Protocols always call the base sequence (`seq_*` or `main`). Saving a protocol from an existing protocol still generates code that calls the original base, not a `prot_*` function.

### 3. Tree organization

- **User Refined**: user-edited **sequences** (saved under `user/seq/`).
- **User Protocols**: user-saved **protocols** (saved under `user/prot/`).
- Other groups by source `name` (e.g. Built-in, mrseq.scripts).

### 4. Virtual filesystem layout (Pyodide)

All in-memory paths used for loading and saving:

- **`user/seq/`** — User-edited sequences only. Save As (from the editor) shows and overwrites only files here.
- **`user/prot/`** — User-saved protocols only.
- **`remote/`** — Single files fetched from a URL (GitHub raw, MRzero notebook, etc.). One file per URL; not mixed with user content.
- **`folder/<sourceKey>/`** — Files from a folder source (e.g. pypulseq examples, MRzero playground). `<sourceKey>` is derived from the source name so different folders don’t collide.

Built-in sequences are mirrored under **`/built_in_seq/`** (filesystem root) for imports. The Save As dialog lists only `user/seq/` so loaded pypulseq/MRzero files do not appear there.

### 5. Protocol generation

Protocol files are generated with:
- TOML header with `kind = "protocol"`, `seq_func_file` and `seq_func` set to the **call target** (the base sequence), plus dependencies.
- An import for the base sequence and a `def prot_*(...): return seq_func(**kwargs)` that forwards parameters. No protocol file path or `prot_*` name is written into the TOML.

---

*Parse and use when needed:*
```python
# import tomli
# config = tomli.loads(_source_config_toml)
# deps = list(config['dependencies'].keys())
```
