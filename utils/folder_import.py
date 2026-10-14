"""
Batch Render Pro — Folder Import Utility

Scans a folder for supported image files and returns them as a flat list,
used to populate the batch queue (one image per queue entry).
"""

import os
import re


# Image file extensions we accept (WebP, PNG, JPEG only)
SUPPORTED_IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.webp',
}


def is_image_file(filepath):
    """Check if a file has a supported image extension.

    Hidden files are skipped: macOS writes '._name.png' metadata files next
    to images on external drives, and those can't be loaded as images.
    """
    name = os.path.basename(filepath)
    if name.startswith('.'):
        return False
    _, ext = os.path.splitext(name)
    return ext.lower() in SUPPORTED_IMAGE_EXTENSIONS


def natural_key(name):
    """Sort key so 'img2' comes before 'img10' (case-insensitive)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def import_from_folder(folder_path):
    """
    Import all image files from a folder as a flat list.
    Returns a list of absolute file paths in natural order (img2 before img10).

    One image per queue entry, mapped to the first (or only) swappable slot.

    Args:
        folder_path (str): Absolute path to the folder.

    Returns:
        list[str]: Naturally sorted list of absolute image file paths.
    """
    if not os.path.isdir(folder_path):
        print(f"[BatchRenderPro] ERROR: Folder not found: {folder_path}")
        return []

    images = []
    for filename in sorted(os.listdir(folder_path), key=natural_key):
        filepath = os.path.join(folder_path, filename)
        if os.path.isfile(filepath) and is_image_file(filepath):
            images.append(filepath)

    return images
