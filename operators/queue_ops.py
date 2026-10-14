"""
Batch Render Pro — Queue Operators

Operators for importing images from folders, adding/removing queue entries,
and managing the batch queue.
"""

import bpy
import os
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator

from ..utils.folder_import import import_from_folder, is_image_file
from ..utils.naming import get_texture_basename
from ..utils.multi_material import (
    set_mapping,
    remove_mapping,
    refresh_primary_image,
    pair_slot_folders,
)


def _target_slots(props, apply_to):
    """(index, slot) pairs an imported image should be mapped to."""
    slots = props.texture_slots
    if len(slots) == 0:
        return []
    if apply_to == 'ALL':
        return [(i, s) for i, s in enumerate(slots) if s.enabled]
    idx = props.active_texture_slot_index
    if 0 <= idx < len(slots) and slots[idx].enabled:
        return [(idx, slots[idx])]
    for i, s in enumerate(slots):
        if s.enabled:
            return [(i, s)]
    return []


class BRP_OT_ImportFolder(Operator):
    """Import all images from a selected folder into the batch queue"""
    bl_idname = "batch_render_pro.import_folder"
    bl_label = "Import Image Folder"
    bl_description = "Select a folder and import all supported images from it"
    bl_options = {'REGISTER', 'UNDO'}

    # Blender's native folder-picker property
    directory: StringProperty(
        name="Directory",
        description="Folder containing images to import",
        subtype='DIR_PATH',
    )
    # File browser filter settings
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})
    filter_image: BoolProperty(default=True, options={'HIDDEN'})

    apply_to: bpy.props.EnumProperty(
        name="Apply To",
        description="Which material slot(s) each imported image is applied to",
        items=[
            ('ACTIVE', "Selected Material",
             "Apply each image to the material slot selected in 'Texture Slots to Swap'"),
            ('ALL', "All Enabled Materials",
             "Apply the same image to every enabled material slot"),
        ],
        default='ACTIVE',
    )

    def invoke(self, context, event):
        # Open the file browser in folder-select mode
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        props = context.scene.batch_render_pro
        folder_path = self.directory

        if not folder_path or not os.path.isdir(folder_path):
            self.report({'ERROR'}, "Invalid folder path.")
            return {'CANCELLED'}

        image_paths = import_from_folder(folder_path)

        if not image_paths:
            self.report({'WARNING'}, f"No supported images found in: {folder_path}")
            return {'CANCELLED'}

        targets = _target_slots(props, self.apply_to)

        for path in image_paths:
            entry = props.queue_entries.add()
            entry.name = get_texture_basename(path)
            entry.image_path = path

            # Map the image to the chosen material slot(s). With no slots
            # scanned yet, image_path alone drives the first enabled slot.
            for slot_idx, slot in targets:
                set_mapping(entry, slot, slot_idx, path)

        props.active_queue_entry_index = len(props.queue_entries) - 1
        self.report({'INFO'}, f"Imported {len(image_paths)} images from folder.")
        return {'FINISHED'}


class BRP_OT_BuildFromSlotFolders(Operator):
    """Create multi-material queue entries from each material slot's image folder"""
    bl_idname = "batch_render_pro.build_from_slot_folders"
    bl_label = "Build Queue from Folders"
    bl_description = (
        "Create one queue entry per image set, using the image folder of each "
        "enabled material slot. Slots without a folder keep their original texture"
    )
    bl_options = {'REGISTER', 'UNDO'}

    replace_queue: BoolProperty(
        name="Replace Queue",
        description="Clear the current queue before adding the new entries",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        props = context.scene.batch_render_pro
        return any(s.enabled and s.source_folder for s in props.texture_slots)

    def execute(self, context):
        props = context.scene.batch_render_pro
        slots = props.texture_slots

        participating = []   # (slot_index, slot)
        slot_files = []
        for idx, slot in enumerate(slots):
            if not slot.enabled:
                continue
            folder = bpy.path.abspath(slot.source_folder) if slot.source_folder else ""
            if folder and not os.path.isdir(folder):
                self.report({'ERROR'}, f"Folder not found for '{slot.display_label}': {folder}")
                return {'CANCELLED'}
            files = import_from_folder(folder) if folder else None
            if folder and not files:
                self.report({'ERROR'}, f"No images in folder for '{slot.display_label}': {folder}")
                return {'CANCELLED'}
            participating.append((idx, slot))
            slot_files.append(files)

        rows = pair_slot_folders(slot_files, props.multi_import_mode)
        if not rows:
            self.report({'WARNING'}, "No images found in the material folders.")
            return {'CANCELLED'}

        if self.replace_queue:
            props.queue_entries.clear()

        for name, row in rows:
            entry = props.queue_entries.add()
            entry.name = name
            for (slot_idx, slot), path in zip(participating, row):
                if path:
                    set_mapping(entry, slot, slot_idx, path)
            refresh_primary_image(entry, slots)

        props.active_queue_entry_index = len(props.queue_entries) - len(rows)

        notes = []
        if props.multi_import_mode == 'BY_ORDER':
            counts = {len(f) for f in slot_files if f}
            if len(counts) > 1:
                detail = ", ".join(f"{slot.display_label}: {len(f)}"
                                   for (_, slot), f in zip(participating, slot_files) if f)
                notes.append(f"Folders have different image counts ({detail}); "
                             f"shorter folders repeat from the start.")

        partial = sum(1 for _, row in rows
                      for (_, slot), p in zip(participating, row)
                      if p is None and slot.source_folder)
        msg = f"Created {len(rows)} multi-material entr{'y' if len(rows) == 1 else 'ies'}."
        if partial:
            msg += f" {partial} slot(s) had no matching image and keep their original texture."
        for note in notes:
            msg += " " + note
        self.report({'WARNING'} if notes else {'INFO'}, msg)
        return {'FINISHED'}


class BRP_OT_SetSlotImage(Operator):
    """Choose the image this material slot uses for the selected queue entry"""
    bl_idname = "batch_render_pro.set_slot_image"
    bl_label = "Choose Image"
    bl_description = "Choose the image this material uses for the selected queue entry"
    bl_options = {'REGISTER', 'UNDO'}

    slot_index: bpy.props.IntProperty()
    filepath: StringProperty(subtype='FILE_PATH')
    filter_image: BoolProperty(default=True, options={'HIDDEN'})
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        props = context.scene.batch_render_pro
        return 0 <= props.active_queue_entry_index < len(props.queue_entries)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        props = context.scene.batch_render_pro
        if not (0 <= self.slot_index < len(props.texture_slots)):
            self.report({'ERROR'}, "Invalid material slot.")
            return {'CANCELLED'}
        path = bpy.path.abspath(self.filepath)
        if not os.path.isfile(path) or not is_image_file(path):
            self.report({'ERROR'}, "Please choose a PNG, JPEG or WebP image.")
            return {'CANCELLED'}
        entry = props.queue_entries[props.active_queue_entry_index]
        slot = props.texture_slots[self.slot_index]
        set_mapping(entry, slot, self.slot_index, path)
        refresh_primary_image(entry, props.texture_slots)
        return {'FINISHED'}


class BRP_OT_ClearSlotImage(Operator):
    """Keep this material's original texture for the selected queue entry"""
    bl_idname = "batch_render_pro.clear_slot_image"
    bl_label = "Keep Original"
    bl_description = "Remove this material's image from the selected entry (it keeps its original texture)"
    bl_options = {'REGISTER', 'UNDO'}

    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.batch_render_pro
        if not (0 <= props.active_queue_entry_index < len(props.queue_entries)):
            return {'CANCELLED'}
        if not (0 <= self.slot_index < len(props.texture_slots)):
            return {'CANCELLED'}
        entry = props.queue_entries[props.active_queue_entry_index]
        slot = props.texture_slots[self.slot_index]
        remove_mapping(entry, slot, self.slot_index)
        refresh_primary_image(entry, props.texture_slots)
        return {'FINISHED'}


class BRP_OT_AddQueueEntry(Operator):
    """Add a new empty entry to the batch queue"""
    bl_idname = "batch_render_pro.add_queue_entry"
    bl_label = "Add Entry"
    bl_description = "Add a manual entry to the batch queue"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.batch_render_pro
        entry = props.queue_entries.add()
        entry.name = f"Entry {len(props.queue_entries)}"
        props.active_queue_entry_index = len(props.queue_entries) - 1
        return {'FINISHED'}


class BRP_OT_RemoveQueueEntry(Operator):
    """Remove the selected entry from the batch queue"""
    bl_idname = "batch_render_pro.remove_queue_entry"
    bl_label = "Remove Entry"
    bl_description = "Remove the selected queue entry"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.batch_render_pro
        return len(props.queue_entries) > 0

    def execute(self, context):
        props = context.scene.batch_render_pro
        idx = props.active_queue_entry_index
        props.queue_entries.remove(idx)
        props.active_queue_entry_index = max(0, min(idx, len(props.queue_entries) - 1))
        return {'FINISHED'}


class BRP_OT_ClearQueue(Operator):
    """Clear all entries from the batch queue"""
    bl_idname = "batch_render_pro.clear_queue"
    bl_label = "Clear Queue"
    bl_description = "Remove all items from the batch queue"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.batch_render_pro
        return len(props.queue_entries) > 0

    def execute(self, context):
        props = context.scene.batch_render_pro
        props.queue_entries.clear()
        props.active_queue_entry_index = 0
        self.report({'INFO'}, "Queue cleared.")
        return {'FINISHED'}


class BRP_OT_MoveQueueEntry(Operator):
    """Move the selected queue entry up or down"""
    bl_idname = "batch_render_pro.move_queue_entry"
    bl_label = "Move Entry"
    bl_description = "Reorder the selected queue entry"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[
            ('UP', "Up", "Move entry up"),
            ('DOWN', "Down", "Move entry down"),
        ]
    )

    @classmethod
    def poll(cls, context):
        props = context.scene.batch_render_pro
        return len(props.queue_entries) > 1

    def execute(self, context):
        props = context.scene.batch_render_pro
        idx = props.active_queue_entry_index
        count = len(props.queue_entries)

        if self.direction == 'UP' and idx > 0:
            props.queue_entries.move(idx, idx - 1)
            props.active_queue_entry_index -= 1
        elif self.direction == 'DOWN' and idx < count - 1:
            props.queue_entries.move(idx, idx + 1)
            props.active_queue_entry_index += 1

        return {'FINISHED'}


class BRP_OT_InsertNamingToken(Operator):
    """Insert this token into the naming pattern"""
    bl_idname = "batch_render_pro.insert_naming_token"
    bl_label = "Insert Token"
    bl_options = {'REGISTER', 'UNDO'}

    token: bpy.props.StringProperty()

    def execute(self, context):
        props = context.scene.batch_render_pro
        current = props.naming_pattern
        
        # Don't add a leading underscore if string is empty or already ends with underscore
        if not current or current.endswith("_"):
            props.naming_pattern = current + self.token
        else:
            props.naming_pattern = current + "_" + self.token
            
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = (
    BRP_OT_ImportFolder,
    BRP_OT_BuildFromSlotFolders,
    BRP_OT_SetSlotImage,
    BRP_OT_ClearSlotImage,
    BRP_OT_AddQueueEntry,
    BRP_OT_RemoveQueueEntry,
    BRP_OT_ClearQueue,
    BRP_OT_MoveQueueEntry,
    BRP_OT_InsertNamingToken,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
