# Niivue, sform/qform, and MITK Interoperability Insights

## NIfTI Affine Matrix Selection

### Niivue's Behavior
- **Niivue uses `sform` when `sform_code >= qform_code`** (standard NIfTI behavior).
- Source: `niivue_/packages/niivue/src/nvimage/AffineProcessor.ts` line 58.
- If codes are equal, sform is preferred.
- the niivue standard phantom seems to have contradicting sfrom and qfrom...

### MITK's Behavior
- **MITK prefers `qform` when `qform_code > 0`**.
- This causes misalignment if qform and sform don't match.
- **Solution**: Set both qform and sform to identical transformations.

---

## Niivue Affine Formats: hdr.affine vs vol.matRAS

### Update (2026-02)
Previous documentation stated that `vol.matRAS` is missing translation. **Empirical testing shows both `hdr.affine` and `vol.matRAS` contain identical translations** for tested phantoms:
```
hdr.affine t: -75.8, -110.8, -71.8
matRAS t:    -75.76, -110.76, -71.76
```
The earlier confusion likely stemmed from a different bug (see "Nested Array Parsing" below).

### Format Difference
- **`hdr.affine`**: Stored as a **nested 4x4 array** (`[[r00,r01,r02,tx],[r10,...],...]`), length = 4.
- **`vol.matRAS`**: Stored as a **flat row-major 16-element array**, length = 16.

### Critical Bug: Nested Array Parsing Failure
`voxelToWorldFactory(affine)` checks `affine.length >= 16` and only handles flat arrays. When `hdr.affine` (nested, length=4) is passed, it **falls through to identity** `(x,y,z) => [x,y,z]`, silently discarding all rotation, scaling, and translation.

This caused the FOV mesh to be built in "voxel = world" space instead of proper NIfTI world coordinates. For phantoms where the NIfTI translation happened to be small, the error was not noticeable.

### The Fix (Implemented)
Flatten nested arrays in `getVolumeInfo()` before passing to the transform pipeline:
```javascript
if (Array.isArray(affine) && affine.length < 16 && Array.isArray(affine[0])) {
  affine = [
    affine[0][0], affine[0][1], affine[0][2], affine[0][3],
    affine[1][0], affine[1][1], affine[1][2], affine[1][3],
    affine[2][0], affine[2][1], affine[2][2], affine[2][3],
    affine[3][0], affine[3][1], affine[3][2], affine[3][3]
  ];
}
```

### Export Recommendation
For NIfTI export, use `hdr.affine` as the primary source (after flattening). Fall back to `vol.matRAS` only if `hdr.affine` is unavailable. Both contain the same data; `hdr.affine` is the canonical NIfTI source.

---

## Voxel Spacing Estimation

Always estimate voxel spacing by calculating the distance between adjacent voxels in world space using the current affine matrix (`vol.matRAS`):
1. Compute world coordinates for $(0,0,0)$ and $(1,0,0)$.
2. Distance $= \text{dist}(P_{000}, P_{100})$.
3. **Why**: Relying on `hdr.pixDims` can lead to 0.75x or 1.33x scaling errors if the header is inconsistent with the affine matrix or if the volume was reoriented.

---

## FOV Mask NIfTI Export (Rotated Affine)

To perfectly match the oriented FOV box (especially when tilted), the exported FOV mask NIfTI uses a **rotated affine matrix** instead of an axis-aligned one. This ensures the NIfTI volume grid is internally aligned with the FOV box axes, preventing "over-coverage" in world Z-direction.

### Mathematical Derivation

1. **Rotation Matrix ($R$):**
   Derived from FOV rotation $(\theta_x, \theta_y, \theta_z)$ using $Z-Y-X$ Euler sequence:
   $$R = R_z(\theta_z) \cdot R_y(\theta_y) \cdot R_x(\theta_x)$$

2. **Voxel Spacing ($S$):**
   Calculated from local FOV size $(L_x, L_y, L_z)$ and requested matrix dimensions $(D_x, D_y, D_z)$:
   $$sp_x = L_x / D_x, \quad sp_y = L_y / D_y, \quad sp_z = L_z / D_z$$

3. **World Origin ($P_{world,0}$):**
   The world coordinate of voxel $(0,0,0)$ center, using true FOV center $C_{world}$:
   $$P_{local,0} = \left[ -L_x/2 + sp_x/2, \quad -L_y/2 + sp_y/2, \quad -L_z/2 + sp_z/2 \right]$$
   $$P_{world,0} = R \cdot P_{local,0} + C_{world}$$

4. **Final Affine Matrix ($A_{mask}$):**
   Sets both **sform** (matrix) and **qform** (quaternions):
   $$A_{mask} = \begin{bmatrix} R_{00} \cdot sp_x & R_{01} \cdot sp_y & R_{02} \cdot sp_z & P_{world,0,x} \\ R_{10} \cdot sp_x & R_{11} \cdot sp_y & R_{12} \cdot sp_z & P_{world,0,y} \\ R_{20} \cdot sp_x & R_{21} \cdot sp_y & R_{22} \cdot sp_z & P_{world,0,z} \\ 0 & 0 & 0 & 1 \end{bmatrix}$$

### Benefits
- **Zero Interpolation Error**: Every voxel in the mask is "inside" the FOV.
- **Perfect Tilted Display**: Viewers (MITK, Niivue) use the affine to display the volume at the correct physical tilt.
- **Correct Z-Coverage**: A single-slice mask (e.g., $128 \times 128 \times 1$) appears as a single tilted plane in world space.

---

## STL Export: RAS vs LPS

Different viewers expect different coordinate systems:
- **RAS (Right-Anterior-Superior)**: Niivue, NIfTI standard.
- **LPS (Left-Posterior-Superior)**: MITK, DICOM standard.
- **Conversion**: LPS = RAS with X and Y axes flipped ($x \to -x, y \to -y$).

We export both `fov-box-ras.stl` and `fov-box-lps.stl` to ensure compatibility.

---

## Interactive FOV Rotation (Best Practices)

To ensure a natural and consistent "feeling" during mouse-based FOV rotation, several coordinate-system and display issues must be addressed:

### 1. Robust Rotation Pivot
Always use the visual crosshair position in the **current tile** as the rotation pivot. 
- **Method**: Use `nv.frac2canvasPosWithTile(frac, tileIndex)` instead of global `frac2canvasPos`.
- **Why**: In multi-planar layouts (e.g., 2x2), calculating rotation relative to a pivot in a different tile creates a massive "lever arm," making rotation feel sluggish or inconsistent.

### 2. Device Pixel Ratio (DPR) Calibration
Mouse events (`clientX/Y`) are in CSS pixels, while Niivue's internal positions are often in backing-store pixels.
- **Solution**: Normalize the pivot point by the DPR: `pivotX = rect.left + (canvasPos[0] / dpr)`.
- **Why**: Failure to divide by DPR causes the rotation center to "drift" on high-DPI screens (e.g., 4K monitors or Retina displays).

### 3. Plane-Specific Rotation Directions
Medical views often require different rotation signs to feel "natural" because screen space is Y-down, while volume space is Z-up (Superior):
- **Axial**: Standard clockwise.
- **Coronal**: Inverted (clockwise mouse movement should move Superior part to the Right).
- **Sagittal**: User-preference/standard-dependent (typically non-inverted).
- **Radiological Convention**: If active, the X-axis is flipped (Left is Right), so rotation directions in **Axial** and **Coronal** planes must be inverted to remain consistent with the visual feedback.

---

## Recovering Box from STL (PCA Method)

When converting an oriented STL box back to a NIfTI mask, use **Principal Component Analysis (PCA)** on the STL vertices to determine the box parameters:

1. **Center**: The mean of all unique vertices.
2. **Axes**: The principal components (eigenvectors) of the vertex coordinates define the local X, Y, and Z axes of the box.
3. **Dimensions**: The range (max - min) of the vertices projected onto each principal axis.

This method is robust against any initial rotation or translation of the STL and allows for the automatic construction of a perfectly matching **rotated NIfTI affine**.

---

## Best Practices for Export

1. **Set both qform and sform** to identical transformations.
2. **Set codes to 2** (SCANNER_ANAT) for maximum compatibility.
3. **Extract spacing from affine**, never trust `pixDims` alone.
4. **Use rotated affines** for oriented masks to avoid interpolation and "bounding box" over-coverage.
5. **Calibrate UI interactions for DPR** to ensure precise dragging and rotation.

---

## Python/Nibabel Resampling: Critical qform/sform Pitfall

### The Problem
When resampling a NIfTI and copying the source header:
```python
new_header = source_img.header.copy()
resampled_img = nib.Nifti1Image(resampled_data, reference_affine, header=new_header)
```

**Nibabel only sets `sform` from the affine parameter!** The `qform` retains the old values from the copied source header.

### Symptoms
- **Niivue**: Displays correctly (uses sform)
- **MITK**: Misaligned (prefers qform when `qform_code > 0`)

### The Fix
Explicitly synchronize both forms after creating the image:
```python
resampled_img.set_sform(reference_affine, code=2)
resampled_img.set_qform(reference_affine, code=2)
```

---

## Niivue Export: Affine Source Selection

### Background
Niivue provides two affine sources that (as of tested versions) contain **identical data** in different formats:
- `hdr.affine`: Nested 4x4 array from the NIfTI header (canonical source)
- `vol.matRAS`: Flat 16-element row-major array (Niivue internal)

### The Rule
Use `hdr.affine` as the **primary source** (after flattening to row-major 16), fall back to `vol.matRAS` only if unavailable. Always flatten nested arrays before use:
```javascript
if (hdr?.affine) {
    currentAffineRow = parseAffine(hdr.affine); // handles nested → flat
}
if (!currentAffineRow && vol.matRAS) {
    currentAffineRow = [...vol.matRAS]; // already flat-16
}
```

---

## Voxel Center vs. Corner (+0.5 Correction)

When aligning a discrete NIfTI mask with a continuous STL mesh, there is often an ambiguity regarding whether coordinates refer to **voxel centers** or **voxel corners**.

### The Logic
- **NIfTI Standard**: In world space, the coordinate $[x, y, z]$ typically points to the **center** of a voxel.
- **Mesh Alignment**: If the first voxel's center is at $[0, 0, 0]$, its physical boundaries (corners) actually extend to $[-0.5 \cdot sp, -0.5 \cdot sp, -0.5 \cdot sp]$.

### Implementation in this App
The rotated affine matrix calculation for the FOV mask **implicitly handles the +0.5 voxel shift**. 

When calculating the `rasOrigin` (the center of voxel $[0,0,0]$), we use:
$$P_{local,0} = \left[ -L_x/2 + sp_x/2, \quad -L_y/2 + sp_y/2, \quad -L_z/2 + sp_z/2 \right]$$

Adding half the voxel spacing ($sp/2$) effectively shifts the grid so that the **entire voxel volume** stays contained within the theoretical FOV box. Without this correction, the mask would appear shifted by half a voxel in all directions relative to the STL mesh.

Because this logic is mathematically robust and hardcoded into the export, the manual "Shift Voxel" toggle is unnecessary and has been removed from the UI.

---

## Interactive FOV Positioning via Mouse Click

### Offset Convention
The FOV offset values (`fovOffX/Y/Z`) represent **displacement in mm from the NIfTI grid center voxel**:
$$\text{cx} = \frac{d_x - 1}{2} + \frac{\text{offX}}{s_x}$$
When offset = 0, the FOV is centered at the center voxel of the NIfTI volume. The center voxel's world position depends on the NIfTI affine.

### Click-to-Offset Pipeline

1. **Screen → RAS world mm**: Use Niivue's slice geometry (`screenSlices[tileIndex]`) to compute the clicked world position from mouse coordinates. This is more reliable than using affine transforms directly.

2. **RAS world mm → Voxel**: Invert the same vox→mm transform used by `getFovGeometry()`. To guarantee self-consistency, **probe** the transform at 4 points and invert the recovered 3x3 matrix, rather than relying on any stored affine or Niivue API (`convertMM2Frac` may use a different internal transform).

3. **Voxel → Offset**: `offX = (vx - centerVox_x) * spacing_x`

### Key Insight: Transform Self-Consistency
The FOV pipeline has **three** vox↔mm transforms that must be consistent:
- `voxToMmFactory(vol, affine)` — used in `getFovGeometry()` to place mesh vertices
- `worldMmToFovOffset()` — inverts the above to convert click position to offset
- Niivue's slice renderer — determines where the volume appears on screen

If the forward and inverse transforms don't match exactly (e.g., one uses `hdr.affine` while the other uses `vol.vox2mm`), the FOV appears shifted. The **probe-and-invert** approach guarantees the inverse matches the forward path regardless of which internal Niivue path is active:

```javascript
const vox2mm = this.voxToMmFactory(vol, affine);
const o  = vox2mm(0, 0, 0);
const ex = vox2mm(1, 0, 0);
const ey = vox2mm(0, 1, 0);
const ez = vox2mm(0, 0, 1);
// Recover 3x3 matrix columns, then invert via cofactors
```

### Phantom Load Reset Flow
Loading a new phantom (demo, folder, or file-with-JSON) must fully reset the viewer state. Without this, `getVolumeInfo()` may return stale data from the previous phantom. The reset sequence:
1. **Confirmation dialog** — warns the user that all volumes/scans/masks will be removed.
2. **`resetViewer()`** — removes FOV mesh, clears all volumes, resets FOV state variables.
3. **Load new data** — via `loadUrl` or `loadMultiPhantomFromFiles`.
4. **`refreshFovForNewVolume()`** — re-reads volume info, recalculates spacing and fullFovMm, resets offset sliders to 0,0,0 (centered), enables the FOV checkbox, and triggers a mesh rebuild.

This replaces the previous approach where `loadMultiPhantomFromFiles` and `loadUrl` each had their own inline FOV-setup code, which was duplicated and prone to stale-volume bugs.

### Fallback
Store `lastLocationMm` from Niivue's `onLocationChange` callback for use when slice geometry is unavailable.
