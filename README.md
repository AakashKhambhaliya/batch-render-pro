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

**From the ZIP (recommended):**
1. Download [`batch_render_pro.zip`](batch_render_pro.zip).
2. Blender → **Edit → Preferences → Add-ons → Install…** and select the ZIP.
3. Enable **Render: Batch Render Pro**.
4. Open the **N** sidebar in the 3D viewport and switch to the **Batch Render** tab.

**From source:** copy the [`batch_render_pro/`](batch_render_pro) folder into your Blender `addons/` directory, then enable it in Preferences.

## Project structure

```
batch_render_pro/
  __init__.py            Addon registration + hot-reload
  properties.py          Scene properties / settings
  operators/             Texture, queue, camera and render operators
  panels/main_panel.py   Sidebar UI
  utils/                 texture_swap, csv_import, naming helpers
```

## License

See addon header. Provided as-is.
