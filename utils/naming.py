"""
Batch Render Pro — Output Naming Utility

Generates output file paths using a user-defined naming pattern with token substitution.
Supports tokens like {model}, {texture}, {camera}, {index}, {date}, {time}.

IMPORTANT: Blender's native render pipeline auto-appends the file extension
based on scene.render.image_settings.file_format. Therefore, this utility
returns paths WITHOUT any file extension. Adding one here would cause
double extensions like ".png.png".
"""

import os
import re
from datetime import datetime


# Supported tokens and their descriptions (for UI tooltips)
NAMING_TOKENS = {
    '{name}': 'Custom name of the queue entry (set in the UI)',
    '{model}': 'Name of the active object / model',
    '{texture}': 'Name of the swapped texture file (without extension)',
    '{camera}': 'Name of the camera used for this render',
    '{index}': 'Zero-padded index of the current render (e.g., 001)',
    '{slot}': 'Name of the texture slot being swapped',
    '{date}': 'Current date in YYYY-MM-DD format',
    '{time}': 'Current time in HH-MM-SS format',
}


def sanitize_filename(name):
    """
    Remove or replace characters that are unsafe for filenames across OS platforms.
    """
    # Replace common problematic characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Strip leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    return sanitized if sanitized else 'unnamed'


def get_texture_basename(filepath):
    """
    Extract the texture name from a file path, without the extension.
    e.g., '/textures/design_red.png' -> 'design_red'
    """
    return os.path.splitext(os.path.basename(filepath))[0]


def generate_output_path(
    output_dir,
    naming_pattern,
    model_name='',
    texture_path='',
    camera_name='',
    slot_name='',
    entry_name='',
    render_index=0,
    file_format='PNG',
    subfolder_mode='NONE',
):
    """
    Generate the full output file path for a single render.
    Does NOT include the file extension — Blender appends it automatically.

    Args:
        output_dir (str): Base output directory.
        naming_pattern (str): Pattern string with {tokens}.
        model_name (str): Name of the active model/object.
        texture_path (str): File path of the current texture being used.
        camera_name (str): Name of the active camera.
        slot_name (str): Name of the texture slot.
        entry_name (str): Custom name of the queue entry.
        render_index (int): Current render index in the batch.
        file_format (str): Output format (used only for subfolder logic, not extension).
        subfolder_mode (str): 'NONE', 'PER_TEXTURE', 'PER_CAMERA', 'PER_BOTH'.

    Returns:
        str: Full absolute path for the output file (WITHOUT extension).
    """
    # Build the token replacement map
    texture_name = get_texture_basename(texture_path) if texture_path else 'no_texture'
    now = datetime.now()

    token_map = {
        '{name}': sanitize_filename(entry_name) if entry_name else 'unnamed',
        '{model}': sanitize_filename(model_name) if model_name else 'model',
        '{texture}': sanitize_filename(texture_name),
        '{camera}': sanitize_filename(camera_name) if camera_name else 'camera',
        '{index}': str(render_index).zfill(3),
        '{slot}': sanitize_filename(slot_name) if slot_name else 'slot',
        '{date}': now.strftime('%Y-%m-%d'),
        '{time}': now.strftime('%H-%M-%S'),
    }

    # Apply token substitution
    filename = naming_pattern
    for token, value in token_map.items():
        filename = filename.replace(token, value)

    # Sanitize the final filename (no extension added — Blender handles that)
    filename = sanitize_filename(filename)

    # Build subfolder path
    subfolder = ''
    if subfolder_mode == 'PER_TEXTURE':
        subfolder = sanitize_filename(texture_name)
    elif subfolder_mode == 'PER_CAMERA':
        subfolder = sanitize_filename(camera_name) if camera_name else 'camera'
    elif subfolder_mode == 'PER_BOTH':
        tex_folder = sanitize_filename(texture_name)
        cam_folder = sanitize_filename(camera_name) if camera_name else 'camera'
        subfolder = os.path.join(tex_folder, cam_folder)

    # Construct full path
    full_dir = os.path.join(output_dir, subfolder) if subfolder else output_dir

    # Ensure the output directory exists
    os.makedirs(full_dir, exist_ok=True)

    return os.path.join(full_dir, filename)


def preview_naming(naming_pattern):
    """
    Generate a preview string showing what the naming pattern will produce.
    Useful for displaying in the UI so the user knows what to expect.
    """
    preview_map = {
        '{name}': 'CustomName',
        '{model}': 'MyModel',
        '{texture}': 'design_red',
        '{camera}': 'Camera_Front',
        '{index}': '001',
        '{slot}': 'FrontDesign',
        '{date}': '2026-04-14',
        '{time}': '15-30-00',
    }

    result = naming_pattern
    for token, value in preview_map.items():
        result = result.replace(token, value)

    return result
