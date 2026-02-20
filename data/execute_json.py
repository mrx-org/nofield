#!/usr/bin/env python3
"""
Execute a NIfTI phantom JSON configuration into actual NIfTI volumes.

Usage:
    python execute_json.py

Workflow:
1. You select a folder that contains:
   - One or more NIfTI files (e.g. *.nii or *.nii.gz)
   - One or more JSON phantom configuration files (nifti_phantom_v1)
2. You choose which JSON config to execute (if there are multiple).
3. The script generates:
   - "executed": 4D NIfTI files (one 4th-dim slice per tissue) for each property.
   - "averaged": 3D NIfTI files with density-weighted average over tissues, e.g.
     T1_avg = (T1_gm*density_gm + T1_wm*density_wm + ...) / (density_gm + density_wm + ...).

The logic mirrors the in-browser Pyodide implementation used by the Niivue viewer.
"""

import os
import sys
import json
import gzip as _gzip
import io
import numpy as np
import nibabel as nib

# tkinter only for standalone CLI (not available in Pyodide/browser)
def select_folder(title: str) -> str:
    """Open a folder selection dialog and return the selected path."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes("-topmost", True)  # Bring dialog to front

    folder = filedialog.askdirectory(title=title)

    root.destroy()
    return folder


def _parse_file_ref(ref_str):
    """Parse 'fname.nii.gz[0]' -> (fname, index)."""
    s = str(ref_str).strip()
    bracket = s.rfind("[")
    if bracket < 0 or not s.endswith("]"):
        raise ValueError(f"Invalid file_ref: {ref_str!r} (repr: {s!r})")
    fname = s[:bracket]
    idx_str = s[bracket + 1 : -1]
    if not idx_str.isdigit():
        raise ValueError(f"Invalid file_ref index: {ref_str!r}")
    return fname, int(idx_str)


def execute_phantom(
    json_name,
    phantom_dir,
    out_dir=None,
    averaged_dir=None,
    write_executed=False,
    write_averaged=True,
    density_nan_threshold=0.01,
):
    """
    Execute a phantom JSON configuration into NIfTI property maps.

    Parameters
    ----------
    json_name : str
        Filename of the JSON config (basename, not full path).
    phantom_dir : str
        Directory containing the JSON and all referenced NIfTI files.
    out_dir : str, optional
        Directory where executed (4D per-tissue) NIfTI maps will be written.
        Required if write_executed is True.
    averaged_dir : str, optional
        Directory for density-weighted 3D averages. Required if write_averaged is True.
    write_executed : bool, default True
        If True, write 4D per-tissue maps to out_dir.
    write_averaged : bool, default True
        If True, write 3D density-weighted averages to averaged_dir.
    density_nan_threshold : float, default 0.01
        Voxels with total_density <= this value get NaN in averaged maps.

    Returns
    -------
    out_paths : list of str
        Paths to the generated NIfTI files in out_dir (empty if not writing executed).
    """
    if write_executed and out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)
    if write_averaged and averaged_dir is not None:
        os.makedirs(averaged_dir, exist_ok=True)
    json_path = os.path.join(phantom_dir, json_name)
    with open(json_path, "r", encoding="utf-8") as _f:
        config = json.load(_f)

    if config.get("file_type") != "nifti_phantom_v1":
        raise ValueError(f"Unsupported file_type: {config.get('file_type')}")

    _img_cache = {}

    def _load_nii(fname):
        """Load NIfTI from disk, with explicit gzip handling."""
        if fname not in _img_cache:
            full_path = os.path.join(phantom_dir, fname)
            if not os.path.isfile(full_path):
                raise FileNotFoundError(f"Referenced NIfTI not found: {full_path}")

            with open(full_path, "rb") as _fbin:
                _raw = _fbin.read()
            if fname.endswith(".gz"):
                _raw = _gzip.decompress(_raw)
            _fh = nib.FileHolder(fileobj=io.BytesIO(_raw))
            _img_cache[fname] = nib.Nifti1Image.from_file_map(
                {"header": _fh, "image": _fh}
            )
        return _img_cache[fname]

    def _get_vol(ref_str):
        fname, idx = _parse_file_ref(ref_str)
        img = _load_nii(fname)
        data = img.get_fdata(dtype=np.float32)
        vol = data[..., idx] if data.ndim == 4 else data
        return vol, img.affine, img

    def _resolve(prop_val, shape):
        # Constant scalar
        if isinstance(prop_val, (int, float)):
            return np.full(shape, float(prop_val), dtype=np.float32)
        # Direct file reference string "fname.nii.gz[idx]"
        elif isinstance(prop_val, str):
            v, _, _ = _get_vol(prop_val)
            return v.astype(np.float32)
        # Mapping dict {"file": "ref", "func": "x * 0.5"}
        elif isinstance(prop_val, dict):
            v, _, _ = _get_vol(prop_val["file"])
            v = v.astype(np.float32)
            x = v
            x_min = float(v.min())
            x_max = float(v.max())
            x_mean = float(v.mean())
            x_std = float(v.std())
            result = eval(
                prop_val["func"],
                {"__builtins__": {}},
                {
                    "x": x,
                    "x_min": x_min,
                    "x_max": x_max,
                    "x_mean": x_mean,
                    "x_std": x_std,
                },
            )
            return np.asarray(result, dtype=np.float32)
        else:
            raise ValueError(f"Unknown property type: {type(prop_val)}")

    # Determine shape + affine from first tissue density
    tissues = config.get("tissues") or {}
    if not tissues:
        raise ValueError("Config has no 'tissues' entries.")

    first_tissue = next(iter(tissues.values()))
    if "density" not in first_tissue:
        raise KeyError(
            f"First tissue has no 'density' key. Available keys: {list(first_tissue.keys())}"
        )

    _ref_fname, _ref_idx = _parse_file_ref(first_tissue["density"])
    ref_img = _load_nii(_ref_fname)
    ref_vol, ref_affine, _ = _get_vol(first_tissue["density"])
    shape = ref_vol.shape[:3]

    SCALAR_PROPS = ["density", "T1", "T2", "T2'", "ADC", "dB0"]
    SCALAR_DEFAULTS = {
        "density": 1.0,
        "T1": float("inf"),
        "T2": float("inf"),
        "T2'": float("inf"),
        "ADC": 0.0,
        "dB0": 0.0,
    }
    INF_PROPS = {"T1", "T2", "T2'"}

    # One list-of-3D-volumes per property; one entry per tissue
    per_tissue = {p: [] for p in SCALAR_PROPS}
    b1p_tissues = []  # list of lists: [tissue][channel] -> 3D array
    b1m_tissues = []

    for tissue_name, tissue_cfg in tissues.items():
        if "density" not in tissue_cfg:
            raise KeyError(
                f"Tissue '{tissue_name}' has no 'density' key. "
                f"Available keys: {list(tissue_cfg.keys())}"
            )
        density = _resolve(tissue_cfg["density"], shape)
        per_tissue["density"].append(density)

        for prop in SCALAR_PROPS:
            if prop == "density":
                continue
            raw = tissue_cfg.get(prop, SCALAR_DEFAULTS[prop])
            val = _resolve(raw, shape)
            # Store property value only where tissue is present; 0 elsewhere
            if prop in INF_PROPS:
                vol = np.where(density > 0, val, 0.0).astype(np.float32)
            else:
                vol = (val * (density > 0)).astype(np.float32)
            per_tissue[prop].append(vol)

        # B1+ channels for this tissue
        b1p_list = tissue_cfg.get("B1+", [1.0])
        if not isinstance(b1p_list, list):
            b1p_list = [b1p_list]
        b1p_tissues.append(
            [
                (np.where(density > 0, _resolve(ch, shape), 0.0)).astype(np.float32)
                for ch in b1p_list
            ]
        )

        # B1- channels for this tissue
        b1m_list = tissue_cfg.get("B1-", [1.0])
        if not isinstance(b1m_list, list):
            b1m_list = [b1m_list]
        b1m_tissues.append(
            [
                (np.where(density > 0, _resolve(ch, shape), 0.0)).astype(np.float32)
                for ch in b1m_list
            ]
        )

    base_name = os.path.splitext(os.path.splitext(json_name)[0])[0]
    out_paths = []

    def _save_4d(vols, suffix):
        """Stack list of 3D arrays into a 4D NIfTI and save."""
        if not vols:
            return
        data4d = np.stack(vols, axis=-1)
        data4d = np.nan_to_num(data4d, nan=0.0, posinf=0.0, neginf=0.0)
        # Copy source header so spatial zooms and orientation are preserved
        hdr = ref_img.header.copy()
        hdr.set_data_shape(data4d.shape)
        hdr.set_data_dtype(np.float32)
        # Ensure pixdim[4] is 1.0 so viewers expose the 4D frame slider
        zooms = list(hdr.get_zooms())
        while len(zooms) < 4:
            zooms.append(1.0)
        zooms[3] = 1.0
        hdr.set_zooms(zooms)

        fname = f"{base_name}_{suffix}.nii"
        out_path = os.path.join(out_dir, fname)
        nib.save(nib.Nifti1Image(data4d, ref_affine, header=hdr), out_path)
        out_paths.append(out_path)

    b1p_flat = [ch for tissue_chs in b1p_tissues for ch in tissue_chs]
    b1m_flat = [ch for tissue_chs in b1m_tissues for ch in tissue_chs]

    # Save 4D scalar properties and B1+/B1- (only if write_executed and out_dir set)
    if write_executed and out_dir is not None:
        for prop, vols in per_tissue.items():
            if vols:
                _save_4d(vols, prop)
        if b1p_flat:
            _save_4d(b1p_flat, "B1+")
        if b1m_flat:
            _save_4d(b1m_flat, "B1-")

    # --- Density-weighted averaged 3D maps (only if write_averaged and averaged_dir set) ---
    averaged_paths = []
    if write_averaged and averaged_dir is not None:
        density_vols = per_tissue["density"]
        total_density = np.sum(density_vols, axis=0).astype(np.float32)
        # Avoid division by zero
        denom = np.where(total_density > 0, total_density, 1.0)

        def _save_3d(data3d, suffix, allow_nan=True):
            # NIfTI float32 supports NaN (IEEE 754); viewers treat it as no-data
            if allow_nan:
                data3d = np.nan_to_num(
                    data3d, nan=np.nan, posinf=np.nan, neginf=np.nan
                )
            else:
                data3d = np.nan_to_num(data3d, nan=0.0, posinf=0.0, neginf=0.0)
            data3d = np.asarray(data3d, dtype=np.float32)
            hdr = ref_img.header.copy()
            hdr.set_data_shape(data3d.shape)
            hdr.set_data_dtype(np.float32)
            zooms = list(hdr.get_zooms())[:3]
            hdr.set_zooms(zooms)
            fname = f"{base_name}_{suffix}.nii"
            out_path = os.path.join(averaged_dir, fname)
            nib.save(nib.Nifti1Image(data3d, ref_affine, header=hdr), out_path)
            averaged_paths.append(out_path)

        # density: total over tissues (0 = no tissue; keep as 0, not nan)
        _save_3d(total_density, "density", allow_nan=False)

        # T1, T2, T2', ADC, dB0: weighted average (prop_t * d_t) / total_density
        for prop in ["T1", "T2", "T2'", "ADC", "dB0"]:
            vols = per_tissue.get(prop, [])
            if not vols:
                continue
            weighted = np.sum(
                np.stack(vols, axis=0) * np.stack(density_vols, axis=0), axis=0
            )
            avg = np.where(
                total_density > density_nan_threshold, weighted / denom, np.nan
            ).astype(np.float32)
            _save_3d(avg, prop)

        # B1+ / B1-: same formula, weight each 4th-dim slice by its tissue density
        density_for_b1p = [
            density_vols[i]
            for i, tissue_chs in enumerate(b1p_tissues)
            for _ in tissue_chs
        ]
        if b1p_flat and density_for_b1p:
            weighted_b1p = np.sum(
                np.stack(b1p_flat, axis=0) * np.stack(density_for_b1p, axis=0), axis=0
            )
            b1p_avg = np.where(
                total_density > density_nan_threshold, weighted_b1p / denom, np.nan
            ).astype(np.float32)
            _save_3d(b1p_avg, "B1+")

        density_for_b1m = [
            density_vols[i]
            for i, tissue_chs in enumerate(b1m_tissues)
            for _ in tissue_chs
        ]
        if b1m_flat and density_for_b1m:
            weighted_b1m = np.sum(
                np.stack(b1m_flat, axis=0) * np.stack(density_for_b1m, axis=0), axis=0
            )
            b1m_avg = np.where(
                total_density > density_nan_threshold, weighted_b1m / denom, np.nan
            ).astype(np.float32)
            _save_3d(b1m_avg, "B1-")

    return out_paths + averaged_paths


def main():
    print("=" * 60)
    print("NIfTI Phantom JSON Executor")
    print("=" * 60)
    print()

    # Step 1: Select folder containing JSON + NIfTI files
    print("Step 1: Select folder containing phantom JSON + NIfTI files...")
    folder = select_folder("Select phantom folder (JSON + NIfTI files)")
    if not folder:
        print("No folder selected. Exiting.")
        sys.exit(1)

    folder = os.path.abspath(folder)
    print(f"Selected folder: {folder}")
    print()

    # Step 2: Find JSON configs
    json_names = sorted(
        f for f in os.listdir(folder) if f.lower().endswith(".json")
    )
    if not json_names:
        print("No .json files found in the selected folder. Exiting.")
        sys.exit(1)

    if len(json_names) == 1:
        json_name = json_names[0]
        print(f"Found a single JSON config: {json_name}")
    else:
        print("Available JSON configs:")
        for i, name in enumerate(json_names, start=1):
            print(f"  [{i}] {name}")
        print()
        while True:
            choice = input(
                f"Select JSON to execute [1-{len(json_names)}] (default 1): "
            ).strip()
            if not choice:
                idx = 0
                break
            if choice.isdigit():
                idx_int = int(choice) - 1
                if 0 <= idx_int < len(json_names):
                    idx = idx_int
                    break
            print("Invalid choice, please try again.")
        json_name = json_names[idx]

    print()
    print(f"Executing phantom for JSON: {json_name}")

    # Step 3: Output choice and density threshold
    print("Output: [1] both, [2] executed only, [3] averaged only (default 1): ", end="")
    out_choice = input().strip() or "1"
    if out_choice == "2":
        write_executed, write_averaged = True, False
    elif out_choice == "3":
        write_executed, write_averaged = False, True
    else:
        write_executed, write_averaged = True, True

    print("Density threshold for NaN in averaged maps (default 0.01): ", end="")
    thresh_str = input().strip()
    density_nan_threshold = float(thresh_str) if thresh_str else 0.01

    out_dir = os.path.join(folder, "executed") if write_executed else None
    averaged_dir = os.path.join(folder, "averaged") if write_averaged else None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        print(f"4D per-tissue maps → {out_dir}")
    if averaged_dir:
        os.makedirs(averaged_dir, exist_ok=True)
        print(f"Density-weighted 3D averages → {averaged_dir} (threshold={density_nan_threshold})")
    print()

    try:
        out_paths = execute_phantom(
            json_name,
            phantom_dir=folder,
            out_dir=out_dir,
            averaged_dir=averaged_dir,
            write_executed=write_executed,
            write_averaged=write_averaged,
            density_nan_threshold=density_nan_threshold,
        )
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    if out_paths:
        print("Generated 4D maps (executed):")
        for p in out_paths:
            print(f"  - {os.path.basename(p)}")
    if averaged_dir and os.path.isdir(averaged_dir):
        print("Generated 3D averaged maps (averaged):")
        for f in sorted(os.listdir(averaged_dir)):
            if f.endswith(".nii") or f.endswith(".nii.gz"):
                print(f"  - {f}")

    print()
    print("=" * 60)
    print("Done.")


if __name__ == "__main__" and "pyodide" not in sys.modules:
    main()

