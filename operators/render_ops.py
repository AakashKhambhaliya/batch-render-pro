"""
Batch Render Pro — Native Timeline Render Engine

Fully native approach: the Bake operator sets up Blender's timeline
so that Render Animation (Ctrl+F12) works out of the box.

 • Texture changes:  Native Image Sequences on the Image Texture node.
   Blender/Cycles load the correct image per frame automatically.
 • Camera changes:   Native Timeline Markers with bound cameras.
   Blender switches cameras per frame automatically.

No Python texture swapping happens during render.  The only handlers
are for custom output-path naming and file renaming.
"""

import bpy
import os
import time
from bpy.types import Operator

from ..utils.naming import generate_output_path
from ..utils.texture_swap import (
    capture_current_state,
    create_image_sequences,
    cleanup_image_sequences,
)

# ─────────────────────────────────────────────
#  Global State for Baked Animation
# ─────────────────────────────────────────────

_baked_queue = []            # (entry_index, camera_index) per frame
_original_camera = None
_original_filepath = ''
_original_textures = []
_original_frame_start = 1
_original_frame_end = 1
_original_frame_current = 1

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _log(scene, msg, status='SUCCESS'):
    props = scene.batch_render_pro
    entry = props.render_log.add()
    entry.message = msg
    entry.status = status
    entry.timestamp = time.strftime("%H:%M:%S")
    props.active_log_index = len(props.render_log) - 1
    print(f"[BatchRenderPro] [{status}] {msg}")


def _get_frame_data(scene):
    """Look up baked queue entry + camera for the current frame."""
    props = scene.batch_render_pro
    if not props.is_timeline_baked:
        return None, None, None

    frame = scene.frame_current
    queue_idx = frame - scene.frame_start

    if queue_idx < 0 or queue_idx >= len(_baked_queue):
        return None, None, None

    entry_idx, camera_idx = _baked_queue[queue_idx]
    entry = props.queue_entries[entry_idx]
    camera_item = props.cameras[camera_idx]
    return entry, camera_item, queue_idx


def _set_output_path(scene, entry, camera_item, queue_idx):
    """Set scene.render.filepath for the current frame."""
    props = scene.batch_render_pro

    # Use the object that actually owns an enabled texture slot for {model};
    # falling back to '' lets generate_output_path apply its 'model' default.
    model_name = ''
    for slot in props.texture_slots:
        if slot.enabled and slot.object_name:
            model_name = slot.object_name
            break

    out_path = generate_output_path(
        output_dir=bpy.path.abspath(props.output_dir),
        naming_pattern=props.naming_pattern,
        model_name=model_name,
        texture_path=entry.image_path,
        camera_name=camera_item.camera_name,
        entry_name=entry.name,
        render_index=queue_idx + 1,
        file_format=scene.render.image_settings.file_format,
        subfolder_mode=props.subfolder_mode,
    )
    scene.render.filepath = out_path


# ─────────────────────────────────────────────
#  Handlers  (output naming only — NO texture swapping)
# ─────────────────────────────────────────────

@bpy.app.handlers.persistent
def _on_frame_change(scene, *args):
    """
    Set the output path when scrubbing the timeline.
    Texture changes are handled natively by Image Sequences.
    Camera changes are handled natively by Timeline Markers.
    """
    entry, camera_item, queue_idx = _get_frame_data(scene)
    if entry is None:
        return
    _set_output_path(scene, entry, camera_item, queue_idx)


@bpy.app.handlers.persistent
def _on_render_pre(scene, *args):
    """Set the output filepath before each frame renders."""
    entry, camera_item, queue_idx = _get_frame_data(scene)
    if entry is None:
        return
    _set_output_path(scene, entry, camera_item, queue_idx)


@bpy.app.handlers.persistent
def _on_render_post(scene, *args):
    """
    Rename the rendered file from Blender's numbered format to the
    user's naming pattern.
    """
    # Going through _get_frame_data ensures we only act when the timeline
    # is actually baked AND the global queue matches this frame (e.g. it
    # bails out cleanly if the .blend was reloaded with a stale baked flag).
    entry, camera_item, queue_idx = _get_frame_data(scene)
    if entry is None:
        return

    frame = scene.frame_current

    # Let Blender tell us exactly what it wrote (correct frame padding AND
    # the correct extension for every file format, e.g. .exr / .tif / .tga),
    # and what the un-numbered name should be.
    blender_output = scene.render.frame_path(frame=frame)
    desired_output = scene.render.filepath + scene.render.file_extension

    try:
        if os.path.exists(blender_output) and blender_output != desired_output:
            if os.path.exists(desired_output):
                os.remove(desired_output)
            os.rename(blender_output, desired_output)
            _log(scene, f"Saved: {os.path.basename(desired_output)}")
    except Exception as e:
        _log(scene, f"Error renaming frame {frame}: {e}", 'ERROR')


@bpy.app.handlers.persistent
def _on_render_complete(scene, *args):
    print("[BatchRenderPro] Animation render completed.")


@bpy.app.handlers.persistent
def _on_render_cancel(scene, *args):
    print("[BatchRenderPro] Animation render cancelled.")


# ─────────────────────────────────────────────
#  Operators
# ─────────────────────────────────────────────

class BRP_OT_BakeTimeline(Operator):
    """Bake the Batch Queue into the Timeline for native animation rendering"""
    bl_idname = "batch_render_pro.bake_timeline"
    bl_label = "Bake Queue to Timeline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _baked_queue, _original_camera, _original_filepath, _original_textures
        global _original_frame_start, _original_frame_end, _original_frame_current

        scene = context.scene
        props = scene.batch_render_pro

        # ── Validation ──
        enabled_entries = [i for i, e in enumerate(props.queue_entries) if e.enabled]
        enabled_cameras = [i for i, c in enumerate(props.cameras) if c.enabled]

        if not enabled_entries:
            self.report({'ERROR'}, "Queue is empty or all entries are disabled.")
            return {'CANCELLED'}
        if not enabled_cameras:
            self.report({'ERROR'}, "No cameras selected. Use 'Scan Cameras' first.")
            return {'CANCELLED'}

        output_dir = bpy.path.abspath(props.output_dir)
        if not output_dir:
            self.report({'ERROR'}, "Output directory is not set.")
            return {'CANCELLED'}
        os.makedirs(output_dir, exist_ok=True)

        # ── Build Queue ──
        _baked_queue = []
        for e_idx in enabled_entries:
            for c_idx in enabled_cameras:
                _baked_queue.append((e_idx, c_idx))

        total_frames = len(_baked_queue)

        # ── Save Original State ──
        # (MUST happen before create_image_sequences changes node.image)
        _original_camera = scene.camera.name if scene.camera else None
        _original_filepath = scene.render.filepath
        _original_textures = capture_current_state(props.texture_slots)
        _original_frame_start = scene.frame_start
        _original_frame_end = scene.frame_end
        _original_frame_current = scene.frame_current

        # ── Create Native Image Sequences ──
        # Copies each texture into sequentially numbered files and
        # configures the Image Texture node to use the sequence.
        # After this, Blender handles per-frame image loading natively.
        create_image_sequences(
            props.texture_slots,
            _baked_queue,
            props.queue_entries,
            output_dir,
        )

        # ── Setup Timeline ──
        scene.frame_start = 1
        scene.frame_end = total_frames
        scene.frame_current = 1

        # Turn off Stereoscopy
        if hasattr(scene.render, 'use_multiview'):
            scene.render.use_multiview = False

        # ── Bind Cameras to Timeline Markers ──
        scene.timeline_markers.clear()
        for i, (e_idx, c_idx) in enumerate(_baked_queue):
            frame_num = i + 1
            cam_name = props.cameras[c_idx].camera_name
            cam_obj = scene.objects.get(cam_name)
            if cam_obj and cam_obj.type == 'CAMERA':
                marker = scene.timeline_markers.new(name=cam_name, frame=frame_num)
                marker.camera = cam_obj

        # ── Finalize ──
        props.is_timeline_baked = True
        props.total_render_count = total_frames
        props.render_log.clear()

        self.report({'INFO'},
                    f"Baked {total_frames} combinations into Timeline! "
                    f"Press CTRL+F12 to render.")
        return {'FINISHED'}


class BRP_OT_ClearTimeline(Operator):
    """Restore the timeline and textures back to their original state"""
    bl_idname = "batch_render_pro.clear_timeline"
    bl_label = "Clear Bake"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _baked_queue, _original_camera, _original_filepath, _original_textures
        global _original_frame_start, _original_frame_end, _original_frame_current

        scene = context.scene
        props = scene.batch_render_pro

        # Restore camera
        if _original_camera:
            cam = scene.objects.get(_original_camera)
            if cam:
                scene.camera = cam

        # Restore filepath
        if _original_filepath:
            scene.render.filepath = _original_filepath

        # Restore original images and clean up sequences + temp files
        cleanup_image_sequences(_original_textures)

        # Restore timeline range
        scene.frame_start = _original_frame_start
        scene.frame_end = _original_frame_end
        scene.frame_current = _original_frame_current

        scene.timeline_markers.clear()

        _baked_queue = []
        props.is_timeline_baked = False

        self.report({'INFO'}, "Timeline unbaked and original state restored.")
        return {'FINISHED'}


# ─────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────

classes = (
    BRP_OT_BakeTimeline,
    BRP_OT_ClearTimeline,
)

_handler_pairs = [
    ('frame_change_pre',  _on_frame_change),
    ('render_pre',        _on_render_pre),
    ('render_post',       _on_render_post),
    ('render_complete',   _on_render_complete),
    ('render_cancel',     _on_render_cancel),
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    for attr, fn in _handler_pairs:
        handler_list = getattr(bpy.app.handlers, attr)
        if fn not in handler_list:
            handler_list.append(fn)


def unregister():
    for attr, fn in _handler_pairs:
        handler_list = getattr(bpy.app.handlers, attr)
        if fn in handler_list:
            handler_list.remove(fn)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
