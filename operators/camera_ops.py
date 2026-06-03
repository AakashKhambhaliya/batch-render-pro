"""
Batch Render Pro — Camera Operators

Helpers to discover scene cameras and batch select/deselect.
"""

import bpy
from bpy.types import Operator


class BRP_OT_ScanCameras(Operator):
    """Find all cameras in the current scene and add them to the list"""
    bl_idname = "batch_render_pro.scan_cameras"
    bl_label = "Scan Cameras"
    bl_description = "Find all camera objects in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.batch_render_pro
        props.cameras.clear()
        
        cameras = [obj for obj in context.scene.objects if obj.type == 'CAMERA']
        
        if not cameras:
            self.report({'WARNING'}, "No cameras found in scene.")
            return {'FINISHED'}
            
        for cam in cameras:
            item = props.cameras.add()
            item.camera_name = cam.name
            item.enabled = True
            
        self.report({'INFO'}, f"Found {len(cameras)} camera(s).")
        return {'FINISHED'}


class BRP_OT_SetAllCameras(Operator):
    """Enable or disable all cameras in the list"""
    bl_idname = "batch_render_pro.set_all_cameras"
    bl_label = "Set All Cameras"
    bl_description = "Enable or disable all cameras"
    bl_options = {'REGISTER', 'UNDO'}
    
    state: bpy.props.BoolProperty(default=True)
    
    def execute(self, context):
        props = context.scene.batch_render_pro
        for item in props.cameras:
            item.enabled = self.state
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = (
    BRP_OT_ScanCameras,
    BRP_OT_SetAllCameras,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
