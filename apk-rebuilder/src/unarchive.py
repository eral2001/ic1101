import shutil
import zipfile
from pathlib import Path


def _extract_flat(zip_path: Path, dest_dir: Path):
    """
    Extracts a zip file, ignoring a top-level directory and putting contents directly into dest_dir.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        # List all the file paths in the archive
        all_names = [info.filename for info in zf.infolist() if info.filename.strip()]
        # Find their top-level directory names
        tops = {name.split("/", 1)[0] for name in all_names if "/" in name}
        # If there's exactly one, we'll treat it as the root
        root = tops.pop() if len(tops) == 1 else None

        for info in zf.infolist():
            orig = info.filename
            # Skip any "empty" entries
            if not orig or orig.endswith("/"):
                continue

            # Compute the "stripped" path
            rel_path = Path(orig)
            if root and rel_path.parts[0] == root:
                rel_path = Path(*rel_path.parts[1:])  # drop the root folder

            target = dest_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)

            # Extract file
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)


def _verify_file(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Input file doesn't match our expected format, please open a bug report: path does not exist: {file_path}"
        )
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Input file doesn't match our expected format, please open a bug report: "
            f"path exists but is not a file: {file_path}"
        )


def _verify_dir(dir_path: Path) -> None:
    if not dir_path.exists():
        raise FileNotFoundError(
            f"Input file doesn't match our expected format, please open a bug report: path does not exist: {dir_path}"
        )
    if not dir_path.is_dir():
        raise FileNotFoundError(
            f"Input file doesn't match our expected format, please open a bug report: "
            f"path exists but is not a directory: {dir_path}"
        )


def unzip_outer_zip(zip_path: Path, dest_dir: Path, update_id: str) -> Path:
    """
    Extracts the user-provided .zip file and checks that it's a valid update file.
    Returns the path to the SwUpdate.mdt file contained inside the .zip archive.

    `update_id` names the directory inside the archive that holds the SwUpdate.mdt file;
    this value changes across update images.
    """
    _extract_flat(zip_path, dest_dir=dest_dir)

    # Check that unzipped archive looks reasonable.
    path_sw_update = dest_dir / "SwUpdate2.txt"
    path_update_id = dest_dir / update_id
    path_sw_update_mdt = path_update_id / "SwUpdate.mdt"

    _verify_file(path_sw_update)
    _verify_dir(path_update_id)
    _verify_file(path_sw_update_mdt)

    return path_sw_update_mdt


def unzip_mdt_zip(zip_path: Path, dest_dir: Path) -> None:
    _extract_flat(zip_path, dest_dir=dest_dir)

    # Check that Android system directory looks reasonable.
    _verify_dir(dest_dir / "system")
    _verify_dir(dest_dir / "system" / "app")
    _verify_dir(dest_dir / "system" / "framework")
    _verify_dir(dest_dir / "system" / "lib")
    _verify_dir(dest_dir / "system" / "vendor")

    # Check that Android system/vendor directory looks reasonable.
    _verify_dir(dest_dir / "system" / "vendor" / "app")
    _verify_dir(dest_dir / "system" / "vendor" / "framework")
    _verify_dir(dest_dir / "system" / "vendor" / "lib")
