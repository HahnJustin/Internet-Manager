# assets.py
import os
import sys
import __main__
from libuniversal import Paths

APP_DATA_FOLDER = "InternetManager"


def app_base_dir() -> str:
    """
    Folder containing the running exe (PyInstaller) or the *entry script* (dev).
    Important: in dev, assets.py might live in a subfolder, so __file__ can be wrong.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    # Prefer the entrypoint file (gui.py/server.py)
    main_file = getattr(__main__, "__file__", None)
    if main_file:
        return os.path.dirname(os.path.abspath(main_file))

    # Fallback
    if sys.argv and sys.argv[0]:
        return os.path.dirname(os.path.abspath(sys.argv[0]))

    return os.getcwd()


def resource_path(relative_path: str) -> str:
    """
    Absolute path to bundled resources.

    - PyInstaller one-file: files are extracted to sys._MEIPASS
    - Otherwise: relative to app_base_dir() (NOT cwd)
    """
    base_path = getattr(sys, "_MEIPASS", app_base_dir())
    return os.path.join(base_path, relative_path.lstrip("/\\"))


def _stable_data_root() -> str:
    override = os.environ.get("IM_DATA_DIR")
    if override:
        return override

    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        return os.path.join(programdata, APP_DATA_FOLDER)

    localappdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if localappdata:
        return os.path.join(localappdata, APP_DATA_FOLDER)

    return app_base_dir()


def storage_dir() -> str:
    """
    Stable folder where storage/config live (unless JSON_FILE is absolute).
    """
    json_file = Paths.JSON_FILE.value if hasattr(Paths.JSON_FILE, "value") else str(Paths.JSON_FILE)

    if os.path.isabs(json_file):
        d = os.path.dirname(os.path.abspath(json_file))
        os.makedirs(d, exist_ok=True)
        return d

    d = _stable_data_root()
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    cfg_file = Paths.CONFIG_FILE.value if hasattr(Paths.CONFIG_FILE, "value") else str(Paths.CONFIG_FILE)
    return os.path.join(storage_dir(), cfg_file)


def portable_custom_dir() -> str:
    """
    Custom overrides next to the app (where gui.py/server.py is).
    """
    return os.path.join(app_base_dir(), "custom")


def custom_dir() -> str:
    """
    Prefer portable custom/ next to the app if it exists; otherwise use stable custom/.
    """
    p = portable_custom_dir()
    if os.path.isdir(p):
        return p

    d = os.path.join(storage_dir(), "custom")
    os.makedirs(d, exist_ok=True)
    return d


def resolve_user_override(filename: str, fallback_rel: str | None = None) -> str | None:
    """
    Search order (portable first for GUI friendliness):
      1) <app_base_dir>/custom/<filename>
      2) <storage_dir>/custom/<filename>
      3) <app_base_dir>/<filename>
      4) <storage_dir>/<filename>
      5) packaged fallback (resource_path) if provided
    """
    p_app_custom = os.path.join(portable_custom_dir(), filename)
    if os.path.exists(p_app_custom):
        return p_app_custom

    p_stable_custom = os.path.join(storage_dir(), "custom", filename)
    if os.path.exists(p_stable_custom):
        return p_stable_custom

    p_app = os.path.join(app_base_dir(), filename)
    if os.path.exists(p_app):
        return p_app

    p_stable = os.path.join(storage_dir(), filename)
    if os.path.exists(p_stable):
        return p_stable

    if fallback_rel is None:
        return None

    return resource_path(fallback_rel)
