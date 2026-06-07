"""
Batch Render Pro — Texture Swapping Utility

NATIVE IMAGE SEQUENCE STRATEGY
──────────────────────────────
Instead of swapping Image datablocks (which crashes Cycles' OIIO),
we convert each texture slot into a Blender **Image Sequence**.

During the Bake step:
 1. A temp folder is created inside the output directory.
 2. For each enabled texture slot, the source images are converted
    to PNG and saved as sequentially numbered files (0001.png, …).
 3. The Image Texture node is pointed at this sequence with
    use_auto_refresh=True.

When Render Animation (Ctrl+F12) runs, Blender natively loads the
correct PNG per frame — no Python handlers, no OIIO JPEG crash.
"""

import bpy
import os
import shutil


# ─────────────────────────────────────────────
#  Path helpers
# ─────────────────────────────────────────────

def _norm(path):
    """Normalise a file path for reliable comparisons on Windows."""
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(
            bpy.path.abspath(path)
        )))
    except Exception:
        return os.path.normcase(os.path.normpath(path))


def _abs(path):
    """Resolve to absolute path, preserving original case."""
    if not path:
        return ""
    try:
        return os.path.normpath(os.path.abspath(bpy.path.abspath(path)))
    except Exception:
        return os.path.normpath(path)


# ─────────────────────────────────────────────
#  Format Safety & Conversion
# ─────────────────────────────────────────────

# The crash is in OIIO's jpeg_imageio plugin — ONLY JPEG is unsafe.
# All other formats (PNG, WebP, EXR, TIFF, etc.) work fine.
_JPEG_EXTENSIONS = {'.jpg', '.jpeg', '.jpe', '.jfif'}


def _is_jpeg(path):
    """Check if a file is JPEG format (the only format that crashes)."""
    return os.path.splitext(path)[1].lower() in _JPEG_EXTENSIONS


def _convert_jpeg_to_png(src_path, dst_path):
    """
    Convert a JPEG image to PNG using Blender's image system.

    Uses save_render() with 'Standard' view transform, which
    round-trips sRGB textures correctly.  Falls back to pixel-copy
    if save_render doesn't produce a file.

    Returns True if the PNG was created successfully.
    """
    scene = bpy.context.scene
    img = None
    try:
        img = bpy.data.images.load(src_path, check_existing=False)
        w, h = img.size
        if w == 0 or h == 0:
            print(f"[BatchRenderPro] ERROR: Could not decode {src_path}")
            return False

        # ── Method 1: save_render with Standard view transform ──
        ris = scene.render.image_settings
        cm = scene.view_settings

        orig_format = ris.file_format
        orig_mode = ris.color_mode
        orig_depth = ris.color_depth
        orig_transform = cm.view_transform

        ris.file_format = 'PNG'
        ris.color_mode = 'RGBA'
        ris.color_depth = '8'
        cm.view_transform = 'Standard'

        try:
            img.save_render(filepath=dst_path, scene=scene)
        finally:
            ris.file_format = orig_format
            ris.color_mode = orig_mode
            ris.color_depth = orig_depth
            cm.view_transform = orig_transform

        if os.path.exists(dst_path) and os.path.getsize(dst_path) > 100:
            return True

        # ── Method 2: Pixel copy fallback ──
        print(f"[BatchRenderPro] save_render failed, trying pixel copy...")
        pixels = list(img.pixels)
        out_img = bpy.data.images.new("_brp_convert", width=w, height=h, alpha=True)
        out_img.pixels = pixels
        out_img.file_format = 'PNG'
        out_img.filepath_raw = dst_path
        out_img.save()
        bpy.data.images.remove(out_img)

        return os.path.exists(dst_path) and os.path.getsize(dst_path) > 100

    except Exception as e:
        print(f"[BatchRenderPro] JPEG→PNG conversion error: {e}")
        return False
    finally:
        if img is not None:
            try:
                bpy.data.images.remove(img)
            except Exception:
                pass


# ─────────────────────────────────────────────
#  Native Image Sequence Builder
# ─────────────────────────────────────────────

_sequence_dir = ""          # Root temp directory for sequences
_sequence_images = {}       # (mat_name, node_name) → sequence Image datablock


def _resolve_slot_image(entry, target_slot_idx, enabled_slots):
    """
    Determine which image file a given slot should show for a queue entry.
    """
    # Check explicit mapping for this slot index
    for mapping in entry.mappings:
        if mapping.slot_index == target_slot_idx and mapping.image_path:
            return mapping.image_path

    # Fallback: primary image_path → first enabled slot only
    if entry.image_path and enabled_slots:
        first_enabled_idx = enabled_slots[0][0]
        if target_slot_idx == first_enabled_idx:
            return entry.image_path

    return None


def create_image_sequences(texture_slots, baked_queue, queue_entries, output_dir):
    """
    Build native Blender Image Sequences for each enabled texture slot.

    Converts source images to PNG (to avoid OIIO JPEG threading crash),
    copies them as sequentially numbered files, and configures the
    Image Texture node to use the sequence.
    """
    global _sequence_dir, _sequence_images

    # Clean up any previous run
    seq_base = os.path.join(output_dir, '_brp_sequences')
    if os.path.exists(seq_base):
        try:
            shutil.rmtree(seq_base)
        except Exception:
            pass
    os.makedirs(seq_base, exist_ok=True)
    _sequence_dir = seq_base
    _sequence_images = {}

    total_frames = len(baked_queue)
    if total_frames == 0:
        print("[BatchRenderPro] ERROR: No frames in baked queue")
        return

    # Collect enabled slots
    enabled_slots = [(i, s) for i, s in enumerate(texture_slots) if s.enabled]
    if not enabled_slots:
        print("[BatchRenderPro] ERROR: No enabled texture slots")
        return

    print(f"[BatchRenderPro] Building sequences: {total_frames} frames, "
          f"{len(enabled_slots)} slot(s)")

    for slot_idx, slot in enabled_slots:
        mat = bpy.data.materials.get(slot.material_name)
        if not mat or not mat.use_nodes:
            print(f"[BatchRenderPro] WARNING: Material '{slot.material_name}' not found")
            continue
        node = mat.node_tree.nodes.get(slot.node_name)
        if not node or node.type != 'TEX_IMAGE' or not node.image:
            print(f"[BatchRenderPro] WARNING: Node '{slot.node_name}' not found or has no image")
            continue

        key = (slot.material_name, slot.node_name)

        # ── Gather source images per frame ──
        frame_sources = []
        for entry_idx, camera_idx in baked_queue:
            entry = queue_entries[entry_idx]
            img_path = _resolve_slot_image(entry, slot_idx, enabled_slots)
            frame_sources.append(img_path)

        # Debug: show what was resolved
        for i, src in enumerate(frame_sources):
            print(f"[BatchRenderPro]   Frame {i+1}: {os.path.basename(src) if src else 'NONE'}")

        # ── Create slot directory ──
        slot_dir = os.path.join(seq_base, f"slot_{slot_idx}")
        os.makedirs(slot_dir, exist_ok=True)

        # ── Determine target extension ──
        # JPEG is the ONLY format that crashes Cycles' OIIO — it must be
        # converted to PNG. All other formats (WebP, PNG, EXR, TIFF, ...) are
        # safe and can be copied directly. Inspect ALL source files, not just
        # the first: a Blender image sequence requires every frame to share one
        # filename extension, so if the sources contain JPEG or a mix of
        # formats we normalise everything to PNG. Only a single uniform safe
        # format is copied directly (fast, no quality loss).
        present_exts = {
            os.path.splitext(_abs(src))[1].lower()
            for src in frame_sources if src
        }
        any_jpeg = any(_is_jpeg(src) for src in frame_sources if src)

        if any_jpeg or len(present_exts) != 1:
            needs_conversion = True
            target_ext = '.png'
        else:
            needs_conversion = False
            target_ext = present_exts.pop()

        if needs_conversion:
            print(f"[BatchRenderPro] JPEG detected → converting to PNG")
        else:
            print(f"[BatchRenderPro] Safe format ({target_ext}) → direct copy")

        # ── Copy / convert files ──
        converted_count = 0
        converted_cache = {}  # abs_src → dst_path

        for frame_num, src_path in enumerate(frame_sources, start=1):
            if not src_path:
                print(f"[BatchRenderPro] WARNING: No image for frame {frame_num}")
                continue

            abs_src = _abs(src_path)
            if not os.path.isfile(abs_src):
                print(f"[BatchRenderPro] WARNING: File not found: {abs_src}")
                continue

            dst = os.path.join(slot_dir, f"{frame_num:04d}{target_ext}")

            # If same source already processed, just copy
            if abs_src in converted_cache:
                try:
                    shutil.copy2(converted_cache[abs_src], dst)
                    converted_count += 1
                except Exception as e:
                    print(f"[BatchRenderPro] Copy error: {e}")
                continue

            if needs_conversion:
                # JPEG → PNG conversion
                success = _convert_jpeg_to_png(abs_src, dst)
                if success:
                    converted_cache[abs_src] = dst
                    converted_count += 1
                    print(f"[BatchRenderPro] ✓ Converted: {os.path.basename(abs_src)} "
                          f"→ {os.path.basename(dst)} "
                          f"({os.path.getsize(dst)} bytes)")
                else:
                    print(f"[BatchRenderPro] ✗ FAILED to convert: {abs_src}")
            else:
                # Safe format — direct copy (fast)
                try:
                    shutil.copy2(abs_src, dst)
                    converted_cache[abs_src] = dst
                    converted_count += 1
                    print(f"[BatchRenderPro] ✓ Copied: {os.path.basename(abs_src)} "
                          f"→ {os.path.basename(dst)}")
                except Exception as e:
                    print(f"[BatchRenderPro] Copy error: {e}")

        if converted_count == 0:
            print(f"[BatchRenderPro] ERROR: No images converted for slot {slot_idx}")
            continue

        # ── Verify all frame files exist ──
        missing = []
        for fnum in range(1, total_frames + 1):
            fpath = os.path.join(slot_dir, f"{fnum:04d}{target_ext}")
            if not os.path.exists(fpath):
                missing.append(fnum)
        if missing:
            print(f"[BatchRenderPro] WARNING: Missing sequence frames: {missing}")

        # ── Create the sequence Image datablock ──
        first_frame_path = os.path.join(slot_dir, f"0001{target_ext}")
        if not os.path.exists(first_frame_path):
            print(f"[BatchRenderPro] ERROR: First frame not found: {first_frame_path}")
            continue

        # Remember original colour settings
        orig_colorspace = node.image.colorspace_settings.name
        orig_alpha = node.image.alpha_mode

        # Load first frame and configure as sequence
        seq_img = bpy.data.images.load(first_frame_path, check_existing=False)
        seq_img.source = 'SEQUENCE'
        seq_img.name = f"_BRP_seq_{slot.material_name}_{slot.node_name}"

        # Assign to the Image Texture node
        node.image = seq_img

        # Restore colour space / alpha from original
        try:
            seq_img.colorspace_settings.name = orig_colorspace
            seq_img.alpha_mode = orig_alpha
        except Exception:
            pass

        # Configure the image user for native sequence playback
        iu = node.image_user
        iu.frame_start = 1
        iu.frame_duration = total_frames
        iu.frame_offset = 0
        iu.use_cyclic = False
        iu.use_auto_refresh = True

        _sequence_images[key] = seq_img

        print(f"[BatchRenderPro] ✓ Sequence ready: {seq_img.name}")
        print(f"[BatchRenderPro]   source={seq_img.source}, "
              f"frames={iu.frame_start}-{iu.frame_start + iu.frame_duration - 1}, "
              f"auto_refresh={iu.use_auto_refresh}")
        print(f"[BatchRenderPro]   node.image.name={node.image.name}, "
              f"filepath={node.image.filepath}")


def cleanup_image_sequences(original_state):
    """
    Restore original Image datablocks to nodes, remove sequence
    images from bpy.data, and delete the temp directory.
    """
    global _sequence_dir, _sequence_images

    # Restore original images to nodes
    for entry in original_state:
        mat = bpy.data.materials.get(entry['material_name'])
        if not mat or not mat.use_nodes:
            continue
        node = mat.node_tree.nodes.get(entry['node_name'])
        if not node:
            continue
        original_img = bpy.data.images.get(entry['image_name'])
        if original_img:
            node.image = original_img

    # Remove sequence images from bpy.data.images
    for seq_img in _sequence_images.values():
        try:
            bpy.data.images.remove(seq_img)
        except Exception:
            pass
    _sequence_images = {}

    # Delete temp directory
    if _sequence_dir and os.path.exists(_sequence_dir):
        try:
            shutil.rmtree(_sequence_dir)
            print(f"[BatchRenderPro] Cleaned up temp sequences")
        except Exception as e:
            print(f"[BatchRenderPro] Could not remove temp dir: {e}")
    _sequence_dir = ""


# ─────────────────────────────────────────────
#  Scene Scanning Helpers
# ─────────────────────────────────────────────

def find_image_texture_nodes(obj):
    """
    Scan all materials on an object and return a list of dicts describing
    each Image Texture node found.
    """
    results = []
    if obj is None or obj.type != 'MESH':
        return results

    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None or not mat.use_nodes:
            continue

        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image is not None:
                label = node.label if node.label else node.name
                results.append({
                    'object': obj,
                    'material': mat,
                    'node': node,
                    'label': f"{mat.name} → {label}",
                })

    return results


def find_all_image_texture_nodes_in_scene(scene=None):
    """
    Scan ALL mesh objects in the scene for Image Texture nodes.
    """
    if scene is None:
        scene = bpy.context.scene

    all_results = []
    seen_nodes = set()

    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        for entry in find_image_texture_nodes(obj):
            key = (entry['material'].name, entry['node'].name)
            if key not in seen_nodes:
                seen_nodes.add(key)
                all_results.append(entry)

    return all_results


# ─────────────────────────────────────────────
#  State Capture / Restore
# ─────────────────────────────────────────────

def capture_current_state(slots):
    """
    Capture the current image assignments for the given texture slots
    so they can be restored after the batch render.
    """
    state = []
    for slot in slots:
        if not slot.enabled:
            continue
        mat = bpy.data.materials.get(slot.material_name)
        if mat is None or not mat.use_nodes:
            continue
        node = mat.node_tree.nodes.get(slot.node_name)
        if node is None or node.image is None:
            continue
        state.append({
            'material_name': slot.material_name,
            'node_name': slot.node_name,
            'image_name': node.image.name,
        })
    return state
