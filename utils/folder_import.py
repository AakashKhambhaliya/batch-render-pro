"""
Batch Render Pro — Folder Import Utility

Scans a folder for supported image files and returns them as a flat list,
used to populate the batch queue (one image per queue entry).
"""

import os


# Image file extensions we accept (WebP, PNG, JPEG only)
SUPPORTED_IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.webp',
}


def is_image_file(filepath):
    """Check if a file has a supported image extension."""
    _, ext = os.path.splitext(filepath)
    return ext.lower() in SUPPORTED_IMAGE_EXTENSIONS


def import_from_folder(folder_path):
    """
    Import all image files from a folder as a flat list.
    Returns a list of absolute file paths, sorted alphabetically.

    One image per queue entry, mapped to the first (or only) swappable slot.

    Args:
        folder_path (str): Absolute path to the folder.

    Returns:
        list[str]: Sorted list of absolute image file paths.
    """
    if not os.path.isdir(folder_path):
        print(f"[BatchRenderPro] ERROR: Folder not found: {folder_path}")
        return []

    images = []
    for filename in sorted(os.listdir(folder_path)):
        filepath = os.path.join(folder_path, filename)
        if os.path.isfile(filepath) and is_image_file(filepath):
            images.append(filepath)

    return images
