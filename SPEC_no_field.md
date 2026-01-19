# No-field Scanner Specification

## Intent
Unified MRI laboratory dashboard that synchronizes spatial FOV planning with pulse sequence timing and verification.

## Core Functionality
- **Dual-Mode Shell**:
  - **Planning**: Prioritizes 3D anatomical orientation and FOV box positioning.
  - **Sequence**: Prioritizes pulse sequence waveform visualization and parameter tuning.
- **Live Link**: Automatic injection of Niivue FOV coordinates into pulse sequence parameters via `EventHub`.
- **Slot System**: CSS Grid "Slot" architecture for dynamic component swapping between sidebar, main, and footer areas.
- **View Management**: `ViewManager` state machine for orchestrating module placement.

## Architecture
- **Entry**: `no-field_index.html`
- **Communication**: Pub/Sub `EventHub` for decoupled module interaction.
## UI Layout (CSS Grid Architecture)
The dashboard uses a "Slot" system to dynamically swap components between `Planning` and `Sequence` modes.

```
+-------------------------------------------------------------+
|                        Header                               |
| [No-field Scanner]                          [Other actions] |
+-------------------------------------------------------------+
|                   |                                         |
|   slot-sidebar    |               slot-main                 |
|                   |                                         |
| [NiivueModule     |   +-------------------------------+     |
|  Controls (Tabs)] |   |      NiivueModule Viewer      |     |
|                   |   |              OR               |     |
|                   |   |     SequenceExplorer Plot     |     |
|                   |   +-------------------------------+     |
|                   |                                         |
+-------------------------------------------------------------+
|                slot-footer (Full Width)                     |
| +-----------------------+ +-------------------------------+ |
| | col-tree              | | col-params                    | |
| | [SequenceExplorer     | | [SequenceExplorer             | |
| |  Sequences]           | |  Protocol]                    | |
| +-----------------------+ +-------------------------------+ |
+-------------------------------------------------------------+
```
