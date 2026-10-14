"""
Batch Render Pro — Properties

Defines all PropertyGroups, CollectionProperties, and scene-level data
used throughout the addon. This is the single source of truth for addon state.
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


# ─────────────────────────────────────────────
#  Texture Slot Item  (one per swappable node)
# ─────────────────────────────────────────────

class BRP_TextureSlotItem(PropertyGroup):
    """Represents a single swappable Image Texture node in a material."""

    enabled: BoolProperty(
        name="Enabled",
        description="Include this texture slot in the batch render",
        default=True,
    )
    material_name: StringProperty(
        name="Material",
        description="Name of the material containing this node",
    )
    node_name: StringProperty(
        name="Node",
        description="Name of the Image Texture node",
    )
    display_label: StringProperty(
        name="Label",
        description="Human-readable label shown in the UI",
    )
    object_name: StringProperty(
        name="Object",
        description="Name of the object this material belongs to",
    )
    source_folder: StringProperty(
        name="Image Folder",
        description=(
            "Folder of images for this material. Used by 'Build from Slot "
            "Folders' to create multi-material queue entries"
        ),
        subtype='DIR_PATH',
    )


# ─────────────────────────────────────────────
#  Image Mapping  (per-slot image path within a queue entry)
# ─────────────────────────────────────────────

class BRP_ImageMapping(PropertyGroup):
    """Maps a texture slot to a specific image file within a queue entry."""

    slot_index: IntProperty(
        name="Slot Index",
        description="Index into the texture slots collection (legacy; used when material/node are empty)",
        default=0,
    )
    # Stable identity of the target slot. Survives re-scanning materials,
    # which can reorder the slot list and invalidate slot_index.
    material_name: StringProperty(
        name="Material",
        description="Material containing the target Image Texture node",
    )
    node_name: StringProperty(
        name="Node",
        description="Name of the target Image Texture node",
    )
    image_path: StringProperty(
        name="Image Path",
        description="Absolute path to the image file",
        subtype='FILE_PATH',
    )


# ─────────────────────────────────────────────
#  Queue Entry Item  (one row in the batch queue)
# ─────────────────────────────────────────────

class BRP_QueueEntryItem(PropertyGroup):
    """One entry in the batch render queue, containing image mappings for each slot."""

    enabled: BoolProperty(
        name="Enabled",
        description="Include this entry in the batch render",
        default=True,
    )
    name: StringProperty(
        name="Name",
        description="Display name for this queue entry",
        default="Entry",
    )
    # Primary image: shown in the queue list and used for the {texture} token.
    # For multi-material entries it mirrors the first mapped slot's image.
    image_path: StringProperty(
        name="Image",
        description="Primary image file path",
        subtype='FILE_PATH',
    )
    # One mapping per material slot this entry changes. Slots without a
    # mapping keep their original texture for this entry.
    mappings: CollectionProperty(type=BRP_ImageMapping)


# ─────────────────────────────────────────────
#  Camera Item  (one per camera in the scene)
# ─────────────────────────────────────────────

class BRP_CameraItem(PropertyGroup):
    """Represents a camera in the scene with batch render settings."""

    enabled: BoolProperty(
        name="Enabled",
        description="Include this camera in the batch render",
        default=True,
    )
    camera_name: StringProperty(
        name="Camera",
        description="Name of the camera object",
    )


# ─────────────────────────────────────────────
#  Render Log Entry
# ─────────────────────────────────────────────

class BRP_RenderLogEntry(PropertyGroup):
    """A single entry in the render log."""

    message: StringProperty(name="Message")
    status: EnumProperty(
        name="Status",
        items=[
            ('SUCCESS', "Success", "Render completed successfully"),
            ('ERROR', "Error", "Render failed"),
            ('SKIPPED', "Skipped", "Render was skipped"),
        ],
        default='SUCCESS',
    )
    timestamp: StringProperty(name="Timestamp")


# ─────────────────────────────────────────────
#  Main Addon Properties  (scene-level root)
# ─────────────────────────────────────────────

class BRP_SceneProperties(PropertyGroup):
    """Root property group attached to bpy.types.Scene. Holds all addon state."""

    # ── Texture Slots ──
    texture_slots: CollectionProperty(type=BRP_TextureSlotItem)
    active_texture_slot_index: IntProperty(name="Active Texture Slot", default=0)

    # ── Image Queue ──
    queue_entries: CollectionProperty(type=BRP_QueueEntryItem)
    active_queue_entry_index: IntProperty(name="Active Queue Entry", default=0)
    multi_import_mode: EnumProperty(
        name="Pairing",
        description="How images from each material's folder are combined into queue entries",
        items=[
            ('MATCH_NAME', "Match by Name",
             "One entry per file name; files with the same name in each folder render together "
             "(e.g. Body/red.png + Door/red.png)"),
            ('BY_ORDER', "By Order",
             "Pair the 1st file of every folder, then the 2nd, ... A folder with fewer files repeats "
             "(a single-image folder applies to every entry)"),
            ('ALL_COMBINATIONS', "All Combinations",
             "Every image of each material combined with every image of the others"),
        ],
        default='MATCH_NAME',
    )

    # ── Cameras ──
    cameras: CollectionProperty(type=BRP_CameraItem)
    active_camera_index: IntProperty(name="Active Camera", default=0)

    # ── Output Settings ──
    output_dir: StringProperty(
        name="Output Directory",
        description="Base directory for rendered images",
        subtype='DIR_PATH',
        default="//batch_renders/",
    )
    naming_pattern: StringProperty(
        name="Naming Pattern",
        description="Filename pattern. Tokens: {name}, {model}, {texture}, {textures}, {camera}, {index}, {date}, {time}",
        default="{name}_{camera}_{index}",
    )
    subfolder_mode: EnumProperty(
        name="Subfolder Mode",
        description="How to organize output into subfolders",
        items=[
            ('NONE', "No Subfolders", "Save all renders in the output directory"),
            ('PER_TEXTURE', "Per Texture", "Create a subfolder for each texture"),
            ('PER_CAMERA', "Per Camera", "Create a subfolder for each camera"),
            ('PER_BOTH', "Per Texture + Camera", "Nested subfolders: texture/camera"),
        ],
        default='NONE',
    )

    # ── Render State ──
    is_timeline_baked: BoolProperty(name="Is Timeline Baked", default=False)
    # Everything needed to render and to undo a bake, stored as JSON in the
    # .blend so a baked file can be saved, reopened (or rendered from the
    # command line) and still be restored with Clear Bake.
    bake_state: StringProperty(name="Bake State", default="", options={'HIDDEN'})
    total_render_count: IntProperty(name="Total Render Count", default=0)

    # ── Render Log ──
    render_log: CollectionProperty(type=BRP_RenderLogEntry)
    active_log_index: IntProperty(name="Active Log Entry", default=0)


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = (
    BRP_TextureSlotItem,
    BRP_ImageMapping,
    BRP_QueueEntryItem,
    BRP_CameraItem,
    BRP_RenderLogEntry,
    BRP_SceneProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.batch_render_pro = PointerProperty(type=BRP_SceneProperties)


def unregister():
    del bpy.types.Scene.batch_render_pro
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
