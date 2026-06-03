"""
Batch Render Pro — UI Panels

Layouts and UILists for the 3D Viewport properties panel.
"""

import bpy
from bpy.types import Panel, UIList

# ─────────────────────────────────────────────
#  UI Lists (Draw items in the property collections)
# ─────────────────────────────────────────────

class BRP_UL_TextureSlots(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.display_label, icon='TEXTURE')
        row.label(text=f"({item.material_name})", icon='MATERIAL')


class BRP_UL_QueueEntries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon='IMAGE_DATA')
        # Display primary image path summary
        if item.image_path:
            row.label(text=bpy.path.basename(item.image_path))
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


        # --- 2. Image Queue ---
        layout.separator()
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Image Queue:", icon='LINENUMBERS_ON')
        
        row = col.row()
        row.template_list("BRP_UL_QueueEntries", "", props, "queue_entries", props, "active_queue_entry_index", rows=5)
        
        btns = col.row(align=True)
        btns.operator("batch_render_pro.import_folder", text="Import Folder", icon='FILE_FOLDER')
        btns.operator("batch_render_pro.remove_queue_entry", text="", icon='REMOVE')
        btns.operator("batch_render_pro.clear_queue", text="", icon='X')

        # Reorder buttons
        move = col.row(align=True)
        op = move.operator("batch_render_pro.move_queue_entry", text="", icon='TRIA_UP')
        op.direction = 'UP'
        op = move.operator("batch_render_pro.move_queue_entry", text="", icon='TRIA_DOWN')
        op.direction = 'DOWN'


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
        for token in ['{name}', '{texture}', '{camera}', '{index}']:
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
            box.label(text=f"Baked {total_renders} frames to Timeline.", icon='INFO')
            box.label(text="Press CTRL+F12 to Render Animation", icon='RENDER_ANIMATION')
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
