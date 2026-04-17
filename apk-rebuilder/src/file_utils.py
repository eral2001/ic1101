import logging
import re
import shutil
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

_EXTENSION_RE: Final[re.Pattern[str]] = re.compile(r"\.[a-zA-Z0-9]+")


def delete_and_recreate_dir_dangerous(path: Path) -> None:
    """Remove `path` if it exists, then recreate it as an empty directory."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()


def resolve_empty_dir(path: Path) -> Path:
    """Resolve `path` and ensure it is usable as a fresh output directory.

    If `path` does not exist, it is created (its parent must already exist).
    If `path` exists, it must be an empty directory.

    Returns the resolved path.

    Raises:
        NotADirectoryError: `path` exists but is not a directory.
        FileExistsError: `path` exists and is a non-empty directory.
        FileNotFoundError: `path`'s parent directory does not exist.
    """
    path = path.resolve(strict=False)
    if path.exists():
        if not path.is_dir():
            raise NotADirectoryError(f"{path} exists and is not a directory")
        if any(path.iterdir()):
            raise FileExistsError(f"{path} is non-empty; delete it or pick a new path")
    path.mkdir(exist_ok=True)
    return path


def check_binary_exists(binary: str) -> None:
    """Verify `binary` is resolvable on PATH; raise otherwise.

    Args:
        binary: Name of the executable to look up (e.g., "java", "adb").

    Raises:
        FileNotFoundError: If the binary is not found on PATH.
    """
    logger.info("Checking if %s is installed...", binary)
    path = shutil.which(binary)
    if path is None:
        raise FileNotFoundError(f"'{binary}' not found in your PATH.")
    logger.info("Found %s at: %s", binary, path)


def check_file_exists(path: Path) -> None:
    """Verify `path` points at an existing regular file; raise otherwise.

    Raises:
        FileNotFoundError: If `path` does not exist.
        OSError: If `path` exists but is not a regular file.
    """
    if not path.exists():
        raise FileNotFoundError(f"file not found at {path}")
    if not path.is_file():
        raise OSError(f"path is not a regular file: {path}")


def find_paired_files(parent_dir: Path, source_ext: str, companion_ext: str) -> list[Path]:
    """Find files with `source_ext` that have a companion with `companion_ext`.

    Args:
        parent_dir: Directory to search.
        source_ext: Extension of files to return (e.g. ".odex").
        companion_ext: Extension the companion must have (e.g. ".jar").

    Returns:
        Sorted list of paths with `source_ext` whose same-stem
        companion with `companion_ext` exists.
    """
    logger.info(
        "Getting paths to %s files (with %s companions) inside %s",
        source_ext,
        companion_ext,
        parent_dir,
    )
    for name, value in (("source_ext", source_ext), ("companion_ext", companion_ext)):
        if not _EXTENSION_RE.fullmatch(value):
            raise ValueError(f"{name} must be a dot followed by alphanumerics, got {value!r}")
    if not parent_dir.is_dir():
        raise ValueError(f"{parent_dir!r} is not a directory")

    matches: list[Path] = []
    for source_path in parent_dir.glob(f"*{source_ext}"):
        companion = source_path.with_suffix(companion_ext)
        if companion.is_file():
            matches.append(source_path)

    return sorted(matches)


def find_files_with_extension_non_recursive(parent_dir: Path, ext: str) -> list[Path]:
    """Return sorted paths to all files in `parent_dir` whose name ends with `ext`.

    Args:
        parent_dir: Directory to search (non-recursive).
        ext: File extension *with* a leading period, e.g. ".apk"
            or ".jar". Matches the convention used by `pathlib.Path.suffix`.

    Raises:
        ValueError: If `ext` is not a dot followed by alphanumerics,
            or `parent_dir` is not an existing directory.
    """
    if not _EXTENSION_RE.fullmatch(ext):
        raise ValueError(f"ext must be a dot followed by alphanumerics, got {ext!r}")
    if not parent_dir.is_dir():
        raise ValueError(f"{parent_dir!r} is not a directory")
    logger.info("Getting paths to %s files inside %s", ext, parent_dir)
    return sorted(parent_dir.glob(f"*{ext}"))
