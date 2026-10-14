"""
Batch Render Pro — UI Panels

Layouts and UILists for the 3D Viewport properties panel.
"""

import os

import bpy
from bpy.types import Panel, UIList

from ..utils.multi_material import find_mapping
from ..operators.render_ops import _load_state

# ─────────────────────────────────────────────
#  UI Lists (Draw items in the property collections)
# ─────────────────────────────────────────────

class BRP_UL_TextureSlots(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.display_label, icon='TEXTURE')
        if item.source_folder:
            row.label(text="", icon='FILE_FOLDER')


class BRP_UL_QueueEntries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon='IMAGE_DATA')
        # Display primary image, plus how many other materials change
        mapped = sum(1 for m in item.mappings if m.image_path)
        if item.image_path:
            text = bpy.path.basename(item.image_path)
            if mapped > 1:
                text += f"  +{mapped - 1}"
            row.label(text=text)
        else:
            row.label(text="<No Image>", icon='ERROR')


class BRP_UL_Cameras(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.camera_name, icon='CAMERA_DATA')


# ─────────────────────────────────────────────
#  Panels
# ─────────────────────────────────────────────

class BRP_PT_MainPanel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Batch Render'
    bl_label = "Batch Render Pro"

    def draw(self, context):
        layout = self.layout
        props = context.scene.batch_render_pro

        # --- 1. Texture Slots ---
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Texture Slots to Swap:", icon='NODE_TEXTURE')
        
        row = col.row()
        row.template_list("BRP_UL_TextureSlots", "", props, "texture_slots", props, "active_texture_slot_index", rows=3)
        
        btns = col.row(align=True)
        btns.operator("batch_render_pro.scan_materials", text="Scan Materials", icon='VIEWZOOM')
        btns.operator("batch_render_pro.remove_texture_slot", text="", icon='TRASH')

        # --- Material folders: one image folder per scene material ---
        slots = props.texture_slots
        enabled = [(i, sl) for i, sl in enumerate(slots) if sl.enabled]
        if enabled:
            sub = box.box().column(align=True)
            sub.label(text="Image Folder per Material:", icon='FILE_FOLDER')
            for idx, slot in enabled:
                sub.label(text=slot.display_label, icon='MATERIAL')
                sub.prop(slot, "source_folder", text="")
                sub.separator(factor=0.5)
            row = sub.row(align=True)
            row.prop(props, "multi_import_mode", text="")
            sub.operator("batch_render_pro.build_from_slot_folders",
                         text="Build Queue from Folders", icon='ADD')


        # --- 2. Image Queue ---
        layout.separator()
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Image Queue:", icon='LINENUMBERS_ON')
        
        row = col.row()
        row.template_list("BRP_UL_QueueEntries", "", props, "queue_entries", props, "active_queue_entry_index", rows=5)
        
        btns = col.row(align=True)
        btns.operator("batch_render_pro.import_folder", text="Import Folder", icon='FILE_FOLDER')
        btns.operator("batch_render_pro.add_queue_entry", text="", icon='ADD')
        btns.operator("batch_render_pro.remove_queue_entry", text="", icon='REMOVE')
        btns.operator("batch_render_pro.clear_queue", text="", icon='X')

        # Reorder buttons
        move = col.row(align=True)
        op = move.operator("batch_render_pro.move_queue_entry", text="", icon='TRIA_UP')
        op.direction = 'UP'
        op = move.operator("batch_render_pro.move_queue_entry", text="", icon='TRIA_DOWN')
        op.direction = 'DOWN'

        # Per-material images of the selected entry
        entries = props.queue_entries
        if len(slots) > 0 and 0 <= props.active_queue_entry_index < len(entries):
            entry = entries[props.active_queue_entry_index]
            sub = box.box().column(align=True)
            sub.label(text=f"Materials in '{entry.name}':", icon='MATERIAL')
            legacy = len(entry.mappings) == 0 and entry.image_path
            first_enabled = next((i for i, sl in enumerate(slots) if sl.enabled), -1)
            for idx, slot in enumerate(slots):
                if not slot.enabled:
                    continue
                row = sub.row(align=True)
                mapping = find_mapping(entry, slot, idx)
                if mapping and mapping.image_path:
                    image_name = bpy.path.basename(mapping.image_path)
                elif legacy and idx == first_enabled:
                    image_name = bpy.path.basename(entry.image_path)
                else:
                    image_name = "(original)"
                row.label(text=slot.display_label, icon='TEXTURE')
                op = row.operator("batch_render_pro.set_slot_image", text=image_name, icon='FILEBROWSER')
                op.slot_index = idx
                if mapping and mapping.image_path:
                    op = row.operator("batch_render_pro.clear_slot_image", text="", icon='X')
                    op.slot_index = idx


        # --- 3. Cameras ---
        layout.separator()
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Cameras:", icon='OUTLINER_OB_CAMERA')
        
        row = col.row()
        row.template_list("BRP_UL_Cameras", "", props, "cameras", props, "active_camera_index", rows=3)
        
        btns = col.row(align=True)
        btns.operator("batch_render_pro.scan_cameras", text="Scan Cameras", icon='FILE_REFRESH')
        op = btns.operator("batch_render_pro.set_all_cameras", text="All")
        op.state = True
        op = btns.operator("batch_render_pro.set_all_cameras", text="None")
        op.state = False


        # --- 4. Output Settings ---
        layout.separator()
        box = layout.box()
        box.label(text="Output Settings:", icon='OUTPUT')
        col = box.column()
        
        col.prop(props, "output_dir", text="Path")
        col.prop(props, "naming_pattern", text="Name Pattern")
        
        # Token suggestion shortcut buttons
        row = col.row(align=True)
        row.scale_y = 0.8
        for token in ['{name}', '{texture}', '{textures}', '{camera}', '{index}']:
            op = row.operator("batch_render_pro.insert_naming_token", text=token)
            op.token = token
        
        row = col.row()
        row.prop(props, "subfolder_mode", text="Subfolders")


        # --- 5. Render Engine ---
        layout.separator()
        
        # Calculate totals
        enabled_entries = sum(1 for e in props.queue_entries if e.enabled)
        enabled_cameras = sum(1 for c in props.cameras if c.enabled)
        total_renders = enabled_entries * enabled_cameras
        
        col = layout.column(align=True)
        col.scale_y = 1.2
        
        if props.is_timeline_baked:
            col.operator("batch_render_pro.clear_timeline", text="Clear Bake", icon='X')
            layout.separator()
            box = layout.box()
            box.label(text=f"Baked {props.total_render_count} frames to Timeline.", icon='INFO')
            box.label(text="Press CTRL+F12 to Render Animation", icon='RENDER_ANIMATION')
            if total_renders != props.total_render_count:
                box.label(text="Queue changed since baking — Clear Bake and bake again",
                          icon='ERROR')
            state = _load_state(context.scene)
            seq_dir = state.get('sequence_dir', '') if state else ''
            if seq_dir and not os.path.isdir(seq_dir):
                box.label(text="Texture sequence files are missing — Clear Bake and bake again",
                          icon='ERROR')
        else:
            col.operator("batch_render_pro.bake_timeline", text=f"Bake to Timeline ({total_renders} Frames)", icon='ACTION')


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = (
    BRP_UL_TextureSlots,
    BRP_UL_QueueEntries,
    BRP_UL_Cameras,
    BRP_PT_MainPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
