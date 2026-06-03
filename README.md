# Batch Render Pro

A **Blender addon** for automated batch rendering with dynamic texture swapping, CSV-driven variations and multi-camera support. Set up a queue once and render every product/material/camera combination unattended.

- **Blender:** 3.6+
- **Location:** `View3D → Sidebar (N) → Batch Render`
- **Category:** Render

## Features

- 🔁 **Dynamic texture swapping** — render the same scene with different textures/materials
- 📄 **CSV-driven variations** — import a CSV to define each render's parameters and output name
- 🎥 **Multi-camera support** — render from multiple cameras in one batch
- 📋 **Render queue** — build, reorder and run a list of render jobs
- 🏷️ **Flexible output naming**

## Installation

1. On this page click the green **`< > Code`** button → **Download ZIP**.
2. In Blender open **Edit → Preferences → Add-ons**, click **Install…** (Blender 4.2+: **Install from Disk…**), and select the ZIP you just downloaded — no need to unzip it.
3. Tick the checkbox to enable **Batch Render Pro**.
4. Open the **N** sidebar in the 3D viewport and switch to the **Batch Render** tab.

> The addon lives at the repository root, so the ZIP that GitHub generates installs directly in Blender as-is.

## Project structure

```
__init__.py            Addon registration + hot-reload
properties.py          Scene properties / settings
operators/             Texture, queue, camera and render operators
panels/main_panel.py   Sidebar UI
utils/                 texture_swap, csv_import, naming helpers
```

## License

See addon header. Provided as-is.
