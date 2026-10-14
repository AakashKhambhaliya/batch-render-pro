"""
Batch Render Pro — Multi-Material Helpers

A product often has more than one swappable material (e.g. a body and a
door panel, a box front and a box side). Each queue entry can therefore
map a different image to every texture slot. Slots without a mapping keep
their original texture for that entry.

This module holds the mapping lookups and the logic that pairs images from
per-slot folders into queue entries. It deliberately avoids importing bpy
so the pairing rules can be tested on their own.
"""

import itertools
import os


# ─────────────────────────────────────────────
#  Mapping lookups
# ─────────────────────────────────────────────

def mapping_matches_slot(mapping, slot, slot_index):
    """True if a queue-entry mapping targets the given texture slot.

    New mappings are keyed by material + node name, which stays valid when
    the slot list is re-scanned or reordered. Older mappings (saved before
    multi-material support) only carry slot_index.
    """
    if mapping.material_name or mapping.node_name:
        return (mapping.material_name == slot.material_name
                and mapping.node_name == slot.node_name)
    return mapping.slot_index == slot_index


def find_mapping(entry, slot, slot_index):
    """Return the entry's mapping for this slot, or None."""
    for mapping in entry.mappings:
        if mapping_matches_slot(mapping, slot, slot_index):
            return mapping
    return None


def set_mapping(entry, slot, slot_index, image_path):
    """Create or update the entry's mapping for a slot."""
    mapping = find_mapping(entry, slot, slot_index)
    if mapping is None:
        mapping = entry.mappings.add()
    mapping.slot_index = slot_index
    mapping.material_name = slot.material_name
    mapping.node_name = slot.node_name
    mapping.image_path = image_path
    return mapping


def remove_mapping(entry, slot, slot_index):
    """Remove the entry's mapping for a slot. Returns True if one was removed."""
    for i, mapping in enumerate(entry.mappings):
        if mapping_matches_slot(mapping, slot, slot_index):
            entry.mappings.remove(i)
            return True
    return False


def mapped_images(entry, slots):
    """Image paths this entry maps, in texture-slot order."""
    paths = []
    for idx, slot in enumerate(slots):
        mapping = find_mapping(entry, slot, idx)
        if mapping and mapping.image_path:
            paths.append(mapping.image_path)
    return paths


def refresh_primary_image(entry, slots):
    """Keep entry.image_path (list display + {texture} token) in sync with
    the first mapped slot."""
    paths = mapped_images(entry, slots)
    entry.image_path = paths[0] if paths else ""


# ─────────────────────────────────────────────
#  Folder pairing
# ─────────────────────────────────────────────

def _stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def pair_slot_folders(slot_files, mode):
    """
    Combine per-slot image lists into queue-entry rows.

    Args:
        slot_files: list with one item per slot taking part. Each item is a
            sorted list of image paths, or None when that slot has no folder
            (it keeps its original texture in every entry).
        mode: 'MATCH_NAME', 'BY_ORDER' or 'ALL_COMBINATIONS'.

    Returns:
        list of (entry_name, row) where row[i] is the image path for slot i,
        or None to keep that slot's original texture.
    """
    active = [i for i, files in enumerate(slot_files) if files]
    if not active:
        return []

    rows = []

    if mode == 'MATCH_NAME':
        # One entry per distinct file name (case-insensitive, extension ignored).
        # A slot whose folder lacks that name keeps its original texture.
        lookup = []
        keys = []
        seen = set()
        for files in slot_files:
            table = {}
            for path in files or []:
                key = _stem(path).lower()
                table.setdefault(key, path)
                if key not in seen:
                    seen.add(key)
                    keys.append((key, _stem(path)))
            lookup.append(table)
        keys.sort(key=lambda k: k[0])
        for key, display in keys:
            row = [table.get(key) for table in lookup]
            rows.append((display, row))

    elif mode == 'BY_ORDER':
        # Nth file of each folder together. Shorter folders repeat, so a
        # folder holding a single logo applies it to every entry.
        count = max(len(slot_files[i]) for i in active)
        for n in range(count):
            row = [files[n % len(files)] if files else None for files in slot_files]
            rows.append((None, row))

    elif mode == 'ALL_COMBINATIONS':
        for combo in itertools.product(*(slot_files[i] for i in active)):
            row = [None] * len(slot_files)
            for slot_pos, path in zip(active, combo):
                row[slot_pos] = path
            rows.append((None, row))

    else:
        raise ValueError(f"Unknown pairing mode: {mode}")

    named = []
    for name, row in rows:
        if name is None:
            name = "_".join(_stem(p) for p in row if p)
        named.append((name, row))
    return named
