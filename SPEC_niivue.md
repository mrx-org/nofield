# Niivue Component Specification

## Intent
Modular medical imaging component for 3D/orthographic NIfTI visualization and interactive scanner Field of View (FOV) planning.

## Core Functionality
- **Visualization**: WebGL-accelerated volume rendering with crosshair-synchronized slices.
- **FOV Planning**: Interactive 3D box manipulation to define physical scanner coordinates (size, offset, rotation).
- **Coordinate Math**: Logic for voxel-to-world (mm) mapping using NIfTI Q-form/S-form headers.
- **Shared State**: Emits real-time `fov_changed` events via a central hub.

## Modular API
- **Class**: `NiivueModule`
- **Parts**: 
  - `renderViewer(target)`: The WebGL canvas and status overlay.
  - `renderControls(target)`: Tabbed UI (Source, View, FOV, Export).
