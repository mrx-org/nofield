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

### 6. Parameter inspection and protocol arguments

**Intent:** The UI builds dynamic parameter controls from the **base sequence**’s function signature. When executing or when saving a protocol, we need to turn UI values into Python argument expressions that the base sequence accepts.

**Inspection (Python, `seq_source_manager.py`) — inspect only:**
- Parameters are extracted via **inspect only**: get the function (by importing the module or executing the code), then `inspect.signature(func)` and each parameter's default. No AST path; one code path, real runtime types and defaults.
- **Resolving the function:** For module sources, `importlib.import_module(module_path)` then `getattr(module, function_name)`. For file-based sources, `exec(code, exec_globals)` then get the function from the namespace (or `__main__`).
- **Type normalization:** All extracted types are normalized before sending to the frontend:
  - `tuple` and `list` → stored as **type `'list'`**, value converted to a list (so the sequence’s `fov: tuple = (256e-3, 256e-3, 3e-3)` becomes type `'list'` and default `[0.256, 0.256, 0.003]`).
  - `np.ndarray` → **type `'ndarray'`**, value as list (`.tolist()`).
  - Other types → type is `type(default).__name__` (e.g. `'int'`, `'float'`, `'bool'`, `'str'`), or `'None'` if no default.
- Runs when the user selects a sequence in the UI (once per selection). Cost is dominated by import/exec; `inspect.signature()` is negligible. Signature types (e.g. tuple) are normalized to list/ndarray in the UI.

**Protocol argument generation (JS, `seq_explorer.js`):**
- When building the protocol file or the execute script, UI values are turned into Python expression strings:
  - `bool` → `'True'` / `'False'`.
  - `int` / `float` → value as-is (literal).
  - `list` or `ndarray` → **`np.array(${inputValue})`**, where `inputValue` is the text field content (e.g. `[0.256, 0.256, 0.003]` or `256e-3, 256e-3, 3e-3`). So the **protocol** always passes an array for these, even if the sequence signature was `tuple`.
  - `str` → value in double quotes.
  - Other / unknown → value as raw expression.
- Result: in “edit sequence” the user sees `fov: tuple = (256e-3, 256e-3, 3e-3)`; in the generated protocol they see `fov= np.array([...])`. The base sequence typically accepts both tuple and array, but the representation is inconsistent.

**Possible improvements (for a later revision):**
- Preserve **tuple** as a distinct type in extraction and in the UI (e.g. type `'tuple'`), and in the protocol generate `tuple(...)` or `(a, b, c)` instead of `np.array(...)` when the sequence parameter is typed as tuple.
- Or document that we intentionally normalize to list/ndarray and always pass `np.array(...)` so the base sequence receives a numpy array regardless of signature style.
- Optionally use **annotation** from the source (e.g. `fov: tuple`) when AST/inspect can provide it, so the UI and protocol generator can match the sequence’s declared type.

### 7. seq_pulseq_interpreter

**Intent:** Allow loading a Pulseq `.seq` file (from upload or from a path/URL) and using it as the current sequence for plot and scan, without a separate “interpreter” code path. Integrates with the existing inspect → params → execute flow.

**Approach:** A built-in sequence `seq_pulseq_interpreter(filename=...)` that reads the given path with `pypulseq.Sequence().read(filename)` and returns the sequence. Standard parameter inspection then exposes a single `filename` parameter. A **special parameter type** (`'file'` or `'url'`) is used so the UI can render an upload control in addition to a text field.

**Python (built-in sequence):**
- Add a built-in file (e.g. `built_in_seq/seq_pulseq_interpreter.py`) with a TOML header and:
  - `def seq_pulseq_interpreter(filename: Annotated[str, "file"] = "fn.seq"):` (or type alias `SeqFile = Annotated[str, "file"]`).
  - Implementation: `seq = pp.Sequence(); seq.read(filename); return seq`.
- Add this file to `sources_config.py` like other built-in sequences.

**Type detection (Python, `seq_source_manager.py`):**
- In `extract_function_parameters`, after deriving `type_name` from the default value, **optionally** inspect the parameter’s annotation.
- If the annotation is `typing.Annotated[...]` (use `get_origin` and `get_args`), and the metadata (second element of `get_args`) is the string `"file"` or `"url"`, set `type_name = 'file'` or `'url'` instead of `'str'`.
- No other inspect logic changes; only this override for annotated params.

**Param UI (JS, `seq_explorer.js`):**
- In `renderParameterControls`, for `param.type === 'file'` or `param.type === 'url'`: render a **text input** (path/URL) plus an **upload button** (for `'file'`). On file selection: write the file to the Pyodide VFS (e.g. `/uploads/`), ensure the directory exists, and set the text input’s value to that VFS path. The value passed to execute is always a string (path or URL).
- In all places that build Python argument expressions from params (executeFunction, protocol save, TOML/save): treat `'file'` and `'url'` like `'str'` (quoted string).

**VFS and protocols:**
- Uploaded files live in session-scoped VFS (e.g. `/uploads/`). Temporary VFS is acceptable; no persistence required.
- Protocols that wrap `seq_pulseq_interpreter` store the `filename` argument as a string (the path or URL). The protocol thus “links” to the seq file via that string. Same session: path still valid; new session: user can re-upload or use a server URL if supported.

**Scan integration:** No change in the scan module. Execution runs `seq_pulseq_interpreter(filename=...)`; the returned sequence is stored in `__main__.seq` and `SourceManager._last_sequence` as for any other sequence, and the existing scan flow uses it.

---

*Parse and use when needed:*
```python
# import tomli
# config = tomli.loads(_source_config_toml)
# deps = list(config['dependencies'].keys())
```
