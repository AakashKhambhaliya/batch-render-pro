"""
Batch Render Pro — Queue Operators

Operators for importing images from folders, adding/removing queue entries,
and managing the batch queue.
"""

import bpy
import os
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator

from ..utils.folder_import import import_from_folder
from ..utils.naming import get_texture_basename


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

        for path in image_paths:
            entry = props.queue_entries.add()
            entry.name = get_texture_basename(path)
            entry.image_path = path

            # Auto-map to the first enabled slot if any exist
            if len(props.texture_slots) > 0:
                mapping = entry.mappings.add()
                mapping.slot_index = 0
                mapping.image_path = path

        self.report({'INFO'}, f"Imported {len(image_paths)} images from folder.")
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
