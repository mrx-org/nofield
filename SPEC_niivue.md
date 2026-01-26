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
