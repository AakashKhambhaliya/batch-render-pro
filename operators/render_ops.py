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

Bake state (per-frame naming data and everything needed to restore the
scene) is stored as JSON on the scene, so a baked .blend can be saved,
reopened or rendered from the command line and still be cleared.
"""

import bpy
import json
import os
import time
from datetime import datetime
from bpy.types import Operator

from ..utils.naming import generate_output_path
from ..utils.multi_material import mapped_images
from ..utils.texture_swap import (
    capture_current_state,
    create_image_sequences,
    cleanup_image_sequences,
    _resolve_slot_image,
)

_STATE_VERSION = 1

# Parsed bake state per scene, keyed by scene name → (raw json, parsed)
_state_cache = {}


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


def _load_state(scene):
    """Parsed bake state for a scene, or None when not baked."""
    props = getattr(scene, 'batch_render_pro', None)
    if props is None or not props.is_timeline_baked or not props.bake_state:
        return None
    raw = props.bake_state
    cached = _state_cache.get(scene.name)
    if cached and cached[0] == raw:
        return cached[1]
    try:
        state = json.loads(raw)
    except ValueError:
        return None
    _state_cache[scene.name] = (raw, state)
    return state


def _save_state(scene, state):
    raw = json.dumps(state)
    scene.batch_render_pro.bake_state = raw
    _state_cache[scene.name] = (raw, state)


def _get_frame_data(scene):
    """Per-frame snapshot (entry name, images, camera, ...) for the current
    frame, and its 0-based queue index — or (None, None)."""
    state = _load_state(scene)
    if not state:
        return None, None
    queue_idx = scene.frame_current - 1   # bake always starts at frame 1
    frames = state.get('frames', [])
    if queue_idx < 0 or queue_idx >= len(frames):
        return None, None
    return frames[queue_idx], queue_idx


def _output_path(scene, frame, queue_idx, now=None, create_dirs=True):
    props = scene.batch_render_pro
    return generate_output_path(
        output_dir=bpy.path.abspath(props.output_dir),
        naming_pattern=props.naming_pattern,
        model_name=frame.get('model', ''),
        texture_path=frame.get('image_path', ''),
        texture_paths=frame.get('texture_paths', []),
        camera_name=frame.get('camera', ''),
        entry_name=frame.get('name', ''),
        render_index=queue_idx + 1,
        file_format=scene.render.image_settings.file_format,
        subfolder_mode=props.subfolder_mode,
        now=now,
        create_dirs=create_dirs,
    )


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
    frame, queue_idx = _get_frame_data(scene)
    if frame is None:
        return
    scene.render.filepath = _output_path(scene, frame, queue_idx, create_dirs=False)


@bpy.app.handlers.persistent
def _on_render_pre(scene, *args):
    """Set the output filepath before each frame renders."""
    frame, queue_idx = _get_frame_data(scene)
    if frame is None:
        return
    scene.render.filepath = _output_path(scene, frame, queue_idx)


@bpy.app.handlers.persistent
def _on_render_post(scene, *args):
    """
    Rename the rendered file from Blender's numbered format to the
    user's naming pattern.
    """
    frame_data, queue_idx = _get_frame_data(scene)
    if frame_data is None:
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


@bpy.app.handlers.persistent
def _on_load_post(*args):
    """
    Bake state lives in the .blend, so a baked file reopens still baked and
    can be rendered or cleared. Only files baked by v1.0 (flag set but no
    stored state) can't be restored; reset their flag.
    """
    _state_cache.clear()
    for scene in bpy.data.scenes:
        brp = getattr(scene, 'batch_render_pro', None)
        if brp is not None and brp.is_timeline_baked and not brp.bake_state:
            brp.is_timeline_baked = False


# ─────────────────────────────────────────────
#  Operators
# ─────────────────────────────────────────────

class BRP_OT_BakeTimeline(Operator):
    """Bake the Batch Queue into the Timeline for native animation rendering"""
    bl_idname = "batch_render_pro.bake_timeline"
    bl_label = "Bake Queue to Timeline"
    bl_options = {'REGISTER', 'UNDO'}

    def _fail(self, msg):
        self.report({'ERROR'}, msg)
        return {'CANCELLED'}

    def execute(self, context):
        scene = context.scene
        props = scene.batch_render_pro
        render = scene.render

        # ── Validation ──
        # Baking again while already baked would snapshot the swapped sequence
        # images as the "original" state and corrupt restore — require a clear.
        if props.is_timeline_baked:
            return self._fail("Already baked. Use 'Clear Bake' first.")

        enabled_entries = [i for i, e in enumerate(props.queue_entries) if e.enabled]
        enabled_cameras = [i for i, c in enumerate(props.cameras) if c.enabled]
        enabled_slots = [(i, s) for i, s in enumerate(props.texture_slots) if s.enabled]

        if not enabled_entries:
            return self._fail("Queue is empty or all entries are disabled.")
        if not enabled_cameras:
            return self._fail("No cameras selected. Use 'Scan Cameras' first.")
        for c_idx in enabled_cameras:
            name = props.cameras[c_idx].camera_name
            cam = scene.objects.get(name)
            if cam is None or cam.type != 'CAMERA':
                return self._fail(f"Camera '{name}' is no longer in the scene. "
                                  f"Use 'Scan Cameras' again.")
        if not enabled_slots:
            return self._fail("No texture slots enabled. Use 'Scan Materials' and "
                              "tick the textures to swap.")
        if not any(_resolve_slot_image(props.queue_entries[e], i, s, enabled_slots)
                   for e in enabled_entries for i, s in enabled_slots):
            return self._fail("No queue entry sets an image for the enabled texture slots.")

        if render.is_movie_format:
            return self._fail("Output format is a video. Set an image format "
                              "(PNG, JPEG, EXR, ...) in Output Properties.")

        if props.output_dir.startswith('//') and not bpy.data.filepath:
            return self._fail("Output path is relative to the .blend file. "
                              "Save the .blend first, or choose an absolute output folder.")
        output_dir = bpy.path.abspath(props.output_dir)
        if not output_dir:
            return self._fail("Output directory is not set.")

        # ── Build Queue + per-frame naming snapshot ──
        model_name = next((s.object_name for _, s in enabled_slots if s.object_name), '')
        frames = []
        for e_idx in enabled_entries:
            entry = props.queue_entries[e_idx]
            for c_idx in enabled_cameras:
                frames.append({
                    'entry_index': e_idx,
                    'camera_index': c_idx,
                    'name': entry.name,
                    'image_path': entry.image_path,
                    'texture_paths': mapped_images(entry, props.texture_slots),
                    'camera': props.cameras[c_idx].camera_name,
                    'model': model_name,
                })
        total_frames = len(frames)

        # Two renders writing the same file would silently overwrite each other.
        now = datetime.now()
        seen = {}
        for i, f in enumerate(frames):
            key = (_output_path(scene, f, i, now=now, create_dirs=False)
                   + render.file_extension).lower()
            if key in seen:
                return self._fail(
                    f"Renders {seen[key] + 1} and {i + 1} would both be saved as "
                    f"'{os.path.basename(key)}'. Add {{index}}, {{name}} or {{camera}} "
                    f"to the naming pattern.")
            seen[key] = i

        os.makedirs(output_dir, exist_ok=True)

        # ── Save Original State ──
        # (MUST happen before create_image_sequences changes node.image)
        original_textures = capture_current_state(props.texture_slots)
        original = {
            'camera': scene.camera.name if scene.camera else None,
            'filepath': render.filepath,
            'frame_start': scene.frame_start,
            'frame_end': scene.frame_end,
            'frame_current': scene.frame_current,
            'frame_step': scene.frame_step,
            'use_multiview': getattr(render, 'use_multiview', False),
            'markers': [
                {'name': m.name, 'frame': m.frame, 'select': m.select,
                 'camera': m.camera.name if m.camera else None}
                for m in scene.timeline_markers
            ],
            'textures': original_textures,
        }

        # Original textures lose their last user while the sequences are
        # assigned; a fake user keeps them in the .blend if it's saved baked.
        for t in original_textures:
            img = bpy.data.images.get(t['image_name'])
            if img is not None:
                img.use_fake_user = True

        # ── Create Native Image Sequences ──
        # Copies each texture into sequentially numbered files and
        # configures the Image Texture node to use the sequence.
        # After this, Blender handles per-frame image loading natively.
        sequence_dir, sequence_images = create_image_sequences(
            props.texture_slots,
            [(f['entry_index'], f['camera_index']) for f in frames],
            props.queue_entries,
            output_dir,
        )

        # ── Setup Timeline ──
        scene.frame_start = 1
        scene.frame_end = total_frames
        scene.frame_step = 1          # any other step would skip renders
        scene.frame_current = 1

        # Turn off Stereoscopy (restored by Clear Bake)
        if hasattr(render, 'use_multiview'):
            render.use_multiview = False

        # ── Bind Cameras to Timeline Markers ──
        scene.timeline_markers.clear()
        for i, f in enumerate(frames):
            cam_obj = scene.objects.get(f['camera'])
            marker = scene.timeline_markers.new(name=f['camera'], frame=i + 1)
            marker.camera = cam_obj

        # ── Finalize ──
        _save_state(scene, {
            'version': _STATE_VERSION,
            'frames': frames,
            'original': original,
            'sequence_dir': sequence_dir,
            'sequence_images': sequence_images,
        })
        props.is_timeline_baked = True
        props.total_render_count = total_frames
        props.render_log.clear()

        # Point the output path at frame 1 right away
        scene.frame_set(1)

        self.report({'INFO'},
                    f"Baked {total_frames} combinations into Timeline! "
                    f"Press CTRL+F12 to render.")
        return {'FINISHED'}


class BRP_OT_ClearTimeline(Operator):
    """Restore the timeline and textures back to their original state"""
    bl_idname = "batch_render_pro.clear_timeline"
    bl_label = "Clear Bake"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.batch_render_pro.is_timeline_baked

    def execute(self, context):
        scene = context.scene
        props = scene.batch_render_pro

        state = _load_state(scene)
        if not state:
            props.is_timeline_baked = False
            props.bake_state = ""
            self.report({'WARNING'}, "No stored bake state to restore; bake flag reset.")
            return {'FINISHED'}

        original = state.get('original', {})

        # Restore original images and clean up sequences + temp files
        cleanup_image_sequences(
            original.get('textures', []),
            state.get('sequence_dir', ''),
            state.get('sequence_images', []),
        )

        # Restore timeline range
        scene.frame_start = original.get('frame_start', scene.frame_start)
        scene.frame_end = original.get('frame_end', scene.frame_end)
        scene.frame_step = original.get('frame_step', scene.frame_step)

        # Restore the user's markers
        scene.timeline_markers.clear()
        for m in original.get('markers', []):
            marker = scene.timeline_markers.new(name=m['name'], frame=m['frame'])
            marker.select = m.get('select', False)
            if m.get('camera'):
                marker.camera = scene.objects.get(m['camera'])

        # Unbake before changing frame so the handler leaves filepath alone
        props.is_timeline_baked = False
        props.bake_state = ""
        _state_cache.pop(scene.name, None)

        scene.frame_set(original.get('frame_current', scene.frame_current))

        # Restore camera, output path and stereoscopy (after frame_set, which
        # lets markers switch the camera)
        cam_name = original.get('camera')
        scene.camera = scene.objects.get(cam_name) if cam_name else None
        scene.render.filepath = original.get('filepath', scene.render.filepath)
        if hasattr(scene.render, 'use_multiview'):
            scene.render.use_multiview = original.get('use_multiview', False)

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
    ('load_post',         _on_load_post),
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
