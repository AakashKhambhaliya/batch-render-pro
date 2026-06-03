"""
Batch Render Pro — CSV/JSON Import Utility

Parses CSV and JSON files to build batch queue entries.
Supports multi-slot mappings where each row defines which image goes into which slot.

Expected CSV format:
    slot_a,slot_b
    /path/to/design_red.png,/path/to/logo_v1.png
    /path/to/design_blue.png,/path/to/logo_v2.png

Expected JSON format:
    [
        {"slot_a": "/path/to/design_red.png", "slot_b": "/path/to/logo_v1.png"},
        {"slot_a": "/path/to/design_blue.png", "slot_b": "/path/to/logo_v2.png"}
    ]
"""

import csv
import json
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

    This is the simple mode — one image per queue entry, mapped to the
    first (or only) swappable slot.

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


def import_from_csv(csv_path):
    """
    Import batch queue entries from a CSV file.

    The CSV header row defines slot names. Each subsequent row maps
    image file paths to those slots.

    Args:
        csv_path (str): Absolute path to the CSV file.

    Returns:
        tuple: (slot_names: list[str], entries: list[dict])
            Each entry dict maps slot_name -> image_filepath.
            Returns ([], []) on error.
    """
    if not os.path.isfile(csv_path):
        print(f"[BatchRenderPro] ERROR: CSV file not found: {csv_path}")
        return [], []

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            slot_names = reader.fieldnames or []

            if not slot_names:
                print("[BatchRenderPro] ERROR: CSV file has no header row.")
                return [], []

            entries = []
            for row_num, row in enumerate(reader, start=2):
                entry = {}
                valid = True
                for slot in slot_names:
                    filepath = row.get(slot, '').strip()
                    if filepath:
                        # Resolve relative paths relative to the CSV file location
                        if not os.path.isabs(filepath):
                            csv_dir = os.path.dirname(csv_path)
                            filepath = os.path.abspath(os.path.join(csv_dir, filepath))
                        entry[slot] = filepath
                    else:
                        entry[slot] = ''

                if entry:
                    entries.append(entry)

            return slot_names, entries

    except Exception as e:
        print(f"[BatchRenderPro] ERROR: Failed to parse CSV '{csv_path}': {e}")
        return [], []


def import_from_json(json_path):
    """
    Import batch queue entries from a JSON file.

    Expected format: a list of objects, where each object maps
    slot names to image file paths.

    Args:
        json_path (str): Absolute path to the JSON file.

    Returns:
        tuple: (slot_names: list[str], entries: list[dict])
            Returns ([], []) on error.
    """
    if not os.path.isfile(json_path):
        print(f"[BatchRenderPro] ERROR: JSON file not found: {json_path}")
        return [], []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list) or len(data) == 0:
            print("[BatchRenderPro] ERROR: JSON root must be a non-empty array of objects.")
            return [], []

        # Collect all unique slot names from all entries
        slot_names = []
        seen = set()
        for entry in data:
            if not isinstance(entry, dict):
                continue
            for key in entry.keys():
                if key not in seen:
                    seen.add(key)
                    slot_names.append(key)

        entries = []
        for entry in data:
            if not isinstance(entry, dict):
                continue

            resolved_entry = {}
            for slot in slot_names:
                filepath = entry.get(slot, '').strip() if isinstance(entry.get(slot), str) else ''
                if filepath and not os.path.isabs(filepath):
                    json_dir = os.path.dirname(json_path)
                    filepath = os.path.abspath(os.path.join(json_dir, filepath))
                resolved_entry[slot] = filepath

            entries.append(resolved_entry)

        return slot_names, entries

    except json.JSONDecodeError as e:
        print(f"[BatchRenderPro] ERROR: Invalid JSON in '{json_path}': {e}")
        return [], []
    except Exception as e:
        print(f"[BatchRenderPro] ERROR: Failed to parse JSON '{json_path}': {e}")
        return [], []
