bl_info = {
    "name": "Batch Render Pro",
    "author": "Antigravity",
    "version": (1, 0, 1),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar (N) > Batch Render",
    "description": "Automated batch rendering with dynamic texture swapping and multi-camera support.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import importlib
import sys


# ─────────────────────────────────────────────
#  Module management for hot-reload support
# ─────────────────────────────────────────────

# List of submodule paths relative to this package, in dependency order.
# Properties must register BEFORE operators/panels that reference them.
_submodule_names = [
    "utils.texture_swap",
    "utils.folder_import",
    "utils.naming",
    "properties",
    "operators.texture_ops",
    "operators.queue_ops",
    "operators.camera_ops",
    "operators.render_ops",
    "panels.main_panel",
]


def _import_submodules():
    """Import (or reload) all submodules."""
    package = __name__  # 'batch_render_pro'
    modules = []
    for name in _submodule_names:
        full_name = f"{package}.{name}"
        if full_name in sys.modules:
            mod = importlib.reload(sys.modules[full_name])
        else:
            mod = importlib.import_module(f".{name}", package)
        modules.append(mod)
    return modules


_modules = _import_submodules()


# ─────────────────────────────────────────────
#  Register / Unregister
# ─────────────────────────────────────────────

def register():
    for mod in _modules:
        if hasattr(mod, 'register'):
            mod.register()


def unregister():
    for mod in reversed(_modules):
        if hasattr(mod, 'unregister'):
            mod.unregister()


if __name__ == "__main__":
    register()
