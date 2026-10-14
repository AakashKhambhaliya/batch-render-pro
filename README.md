# Batch Render Pro

A **Blender addon** for automated batch rendering with dynamic texture swapping and multi-camera support. Set up a queue once and render every product/material/camera combination unattended.

- **Blender:** 3.6+
- **Location:** `View3D → Sidebar (N) → Batch Render`
- **Category:** Render

## Features

- 🔁 **Dynamic texture swapping** — render the same scene with different textures/materials
- 📁 **Folder import** — import a folder of images to build the queue automatically
- 🎥 **Multi-camera support** — render from multiple cameras in one batch
- 📋 **Render queue** — build, reorder and run a list of render jobs
- 🧩 **Multi-material products** — swap a different image on each material of the same product in one render
- 🏷️ **Flexible output naming**

## Multi-material products

When a product has more than one material to swap (e.g. a body and a door panel), every queue entry can carry one image per material. Materials an entry doesn't set keep their original texture.

**From folders (fastest):** e.g. a *Body* folder and a *Door* folder with 10 images each.
1. Click **Scan Materials**. Under **Image Folder per Material**, pick a folder for each material (Body → Body folder, Door → Door folder).
2. Choose how to pair them and click **Build Queue from Folders**:
   - **1st with 1st, 2nd with 2nd** (default) — render 1 uses the 1st image of every folder, render 2 the 2nd, … Files are taken in name order (`img2` before `img10`), so number them to control the pairing. A folder with fewer images repeats; a folder with a single logo applies it to every render.
   - **Match by File Name** — files with the same name render together (`Body/red.png` + `Door/red.jpg`). A material with no matching file keeps its original texture.
   - **All Combinations** — every image of each material with every image of the others (10 × 10 = 100 renders).

**By hand:** select a queue entry; the *Materials in …* box lists every enabled material. Click a material's button to choose its image, or **X** to keep its original. Use **+** to add an empty entry.

**Import Folder** now asks whether each image goes to the *Selected Material* or to *All Enabled Materials* (same image on every material).

Use the `{textures}` naming token to put all of an entry's image names in the output filename.

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
utils/                 texture_swap, folder_import, naming helpers
```

## License

See addon header. Provided as-is.
