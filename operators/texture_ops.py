"""
Batch Render Pro — Texture Operators

Operators for scanning materials to find Image Texture nodes,
and managing the list of swappable texture slots.
"""

import bpy
from bpy.types import Operator

from ..utils.texture_swap import find_all_image_texture_nodes_in_scene


class BRP_OT_ScanMaterials(Operator):
    """Scan all scene materials and populate the texture slot list with Image Texture nodes"""
    bl_idname = "batch_render_pro.scan_materials"
    bl_label = "Scan Materials"
    bl_description = "Find all Image Texture nodes in the scene's materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.batch_render_pro
        slots = props.texture_slots

        # Clear existing slots
        slots.clear()
        props.active_texture_slot_index = 0

        # Scan scene for Image Texture nodes
        results = find_all_image_texture_nodes_in_scene(context.scene)

        if not results:
            self.report({'WARNING'}, "No Image Texture nodes found in scene materials.")
            return {'FINISHED'}

        for entry in results:
            slot = slots.add()
            slot.material_name = entry['material'].name
            slot.node_name = entry['node'].name
            slot.object_name = entry['object'].name
            slot.display_label = entry['label']
            slot.enabled = True

        self.report({'INFO'}, f"Found {len(results)} Image Texture node(s).")
        return {'FINISHED'}


class BRP_OT_RemoveTextureSlot(Operator):
    """Remove the selected texture slot from the list"""
    bl_idname = "batch_render_pro.remove_texture_slot"
    bl_label = "Remove Texture Slot"
    bl_description = "Remove the selected texture slot"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.batch_render_pro
        return len(props.texture_slots) > 0

    def execute(self, context):
        props = context.scene.batch_render_pro
        idx = props.active_texture_slot_index
        props.texture_slots.remove(idx)
        # Clamp the active index so it doesn't go out of bounds
        props.active_texture_slot_index = min(idx, len(props.texture_slots) - 1)
        return {'FINISHED'}


class BRP_OT_ToggleTextureSlot(Operator):
    """Toggle a texture slot on or off"""
    bl_idname = "batch_render_pro.toggle_texture_slot"
    bl_label = "Toggle Texture Slot"
    bl_description = "Enable or disable the selected texture slot"

    index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.batch_render_pro
        if 0 <= self.index < len(props.texture_slots):
            slot = props.texture_slots[self.index]
            slot.enabled = not slot.enabled
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = (
    BRP_OT_ScanMaterials,
    BRP_OT_RemoveTextureSlot,
    BRP_OT_ToggleTextureSlot,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
