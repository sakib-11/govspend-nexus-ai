"""Cross-service import helper.

Solves the problem of a top-level `models/` package shadowing
service-specific `models/` packages by temporarily replacing
sys.modules['models''] with a merged namespace.
"""

import importlib
import importlib.util
import os
import sys
import types
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Service directory → package prefix mapping
_SERVICES: Dict[str, str] = {
    "digital-twin-svc": "dts",
    "explanation-svc": "expl",
    "llm-prompt-svc": "llm",
    "unmask-svc": "unmask",
    "masked-evidence-svc": "masked",
    "rag-retriever-svc": "rag",
}

_loaded = set()


def _svc_root(svc_name: str) -> str:
    return os.path.join(PROJECT_ROOT, "services", svc_name)


def _register_pkg(svc_root: str, pkg_name: str, pkg_dir: str) -> types.ModuleType:
    """Register a package module from a directory."""
    if pkg_name in sys.modules:
        return sys.modules[pkg_name]

    init_path = os.path.join(pkg_dir, "__init__.py")
    if os.path.exists(init_path):
        spec = importlib.util.spec_from_file_location(pkg_name, init_path,
                                                        submodule_search_locations=[pkg_dir])
    else:
        # Create a namespace package
        spec = importlib.util.spec_from_file_location(pkg_name, None,
                                                        submodule_search_locations=[pkg_dir])

    mod = importlib.util.module_from_spec(spec)
    mod.__path__ = [pkg_dir]
    mod.__package__ = pkg_name
    sys.modules[pkg_name] = mod
    return mod


def _register_submodules(pkg_name: str, pkg_dir: str):
    """Register all .py files in a package directory."""
    for fname in os.listdir(pkg_dir):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        mod_name = f"{pkg_name}.{fname[:-3]}"
        if mod_name in sys.modules:
            continue
        fpath = os.path.join(pkg_dir, fname)
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)


def load_service_module(svc_name: str, rel_path: str) -> Any:
    """Load a module from a service, handling all namespace conflicts.

    Uses unique prefixes (dts_models, expl_models, etc.) for each service's
    internal packages, then patches the service's code to use those prefixes.

    Simpler approach: just pre-register everything and ensure the service
    root is first in sys.path with the top-level models/ removed.
    """
    svc_root = _svc_root(svc_name)
    file_path = os.path.join(svc_root, rel_path)
    mod_name = f"_svc_{svc_name.replace('-', '_')}_{rel_path.replace('/', '_').replace('.py', '')}"

    if mod_name in sys.modules:
        return sys.modules[mod_name]

    # Ensure svc_root is first on sys.path
    if svc_root in sys.path:
        sys.path.remove(svc_root)
    sys.path.insert(0, svc_root)

    # Temporarily hide the top-level models/ package
    saved_models = sys.modules.pop("models", None)
    saved_utils = sys.modules.pop("utils", None)

    try:
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        # Restore top-level models (but keep service-specific ones)
        if saved_models is not None:
            # Merge: keep any new service models that were registered
            new_entries = {
                k: v for k, v in sys.modules.items()
                if k.startswith("models.") and k not in ("models",)
            }
            sys.modules["models"] = saved_models
            for k, v in new_entries.items():
                if k not in sys.modules:
                    sys.modules[k] = v
        if saved_utils is not None:
            new_entries = {
                k: v for k, v in sys.modules.items()
                if k.startswith("utils.") and k not in ("utils",)
            }
            sys.modules["utils"] = saved_utils
            for k, v in new_entries.items():
                if k not in sys.modules:
                    sys.modules[k] = v
