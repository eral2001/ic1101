import asyncio
import logging
import subprocess
import zipfile
from pathlib import Path

from file_utils import delete_and_recreate_dir_dangerous, find_paired_files
from java.baksmali import Baksmali
from java.smali import Smali

logger = logging.getLogger(__name__)


async def _deodex_single_odex(
    baksmali: Baksmali,
    input_odex: Path,
    bootclasspath: list[Path],
    dep_dirs: list[Path],
    api_level: int,
    output_smali_dir: Path,
) -> bool:
    """Run baksmali deodex on a single .odex.

    Args:
        baksmali: The Baksmali wrapper to invoke.
        input_odex: The .odex file to deodex.
        bootclasspath: Pre-resolved ordered list of jar paths forming
            the device's BOOTCLASSPATH.
        dep_dirs: Directories to pass as baksmali `-d` flags for
            additional class resolution.
        api_level: Android API level for the .odex.
        output_smali_dir: Parent directory under which a per-odex
            subdirectory will be created.

    Returns:
        True if baksmali produced output, even with partial failures.
        Raises CalledProcessError if baksmali produced nothing at all.
    """
    for d in dep_dirs:
        if not d.is_dir():
            raise FileNotFoundError(f"Dependency dir not found: {d}")

    out_dir = output_smali_dir / input_odex.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        await baksmali.deodex(
            input_odex=input_odex,
            output_dir=out_dir,
            api_level=api_level,
            bootclasspath=bootclasspath,
            dep_dirs=dep_dirs,
        )
    except subprocess.CalledProcessError as e:
        # baksmali still writes output for classes it *can* resolve,
        # so check if it produced anything useful.
        out_dir_files = list(out_dir.rglob("*.smali"))
        if out_dir_files:
            logger.warning(
                "baksmali deodex returned exit code %d for %s — %d classes were "
                "still deodexed successfully, some may have unresolved opcodes",
                e.returncode,
                input_odex.name,
                len(out_dir_files),
            )
            return True
        else:
            raise
    return True


async def _assemble_smali_to_dex(smali: Smali, smali_dir: Path, classes_dir: Path, apk_name: str) -> Path:
    """Assemble a directory of smali files into a classes.dex.

    Args:
        smali: The Smali wrapper to invoke.
        smali_dir: Root of the smali output (contains subdirs named by
            odex stem).
        classes_dir: Directory where the per-APK classes.dex output
            subdirectory will be created.
        apk_name: Name of the APK; used to locate the smali subdir
            and to name the output subdir.

    Returns:
        Path to the newly created classes.dex.
    """
    smali_input = smali_dir / apk_name
    if not smali_input.is_dir():
        raise FileNotFoundError(f"Smali directory not found: {smali_input}")

    out_dir = classes_dir / apk_name
    out_dir.mkdir(parents=True, exist_ok=True)
    dex_path = out_dir / "classes.dex"

    await smali.assemble(input_dir=smali_input, output_dex=dex_path)

    return dex_path


def _rebuild_apk_with_dex(original_apk: Path, classes_dir: Path, output_apps_dir: Path, stem: str) -> Path:
    """
    Rebuild an APK by injecting a freshly assembled classes.dex.

    :param original_apk: Path to the original APK file
    :param classes_dir: Path to the directory containing per-APK classes.dex subdirs
    :param output_apps_dir: Path where rebuilt APKs should be written
    :param stem: Name stem (e.g. "AirCon") used to locate the classes.dex subdir and name the output
    :return: Path to the newly created APK
    """
    # Locate the generated classes.dex
    dex_path = classes_dir / stem / "classes.dex"
    if not dex_path.is_file():
        raise FileNotFoundError(f"Missing classes.dex at {dex_path}")

    if not original_apk.is_file():
        raise FileNotFoundError(f"Original APK not found at {original_apk}")

    # Prepare output directory & path
    output_apps_dir.mkdir(parents=True, exist_ok=True)
    rebuilt_apk = output_apps_dir / f"{stem}.apk"

    # Rebuild: copy original entries + inject classes.dex at root
    with zipfile.ZipFile(original_apk, "r") as src_zip:
        with zipfile.ZipFile(rebuilt_apk, "w", compression=zipfile.ZIP_DEFLATED) as out_zip:
            # Copy all original entries
            for item in src_zip.infolist():
                data = src_zip.read(item.filename)
                out_zip.writestr(item, data)
            # Now inject the new classes.dex
            out_zip.write(dex_path, arcname="classes.dex")

    return rebuilt_apk


def _rebuild_jar_with_dex(original_jar: Path, classes_dir: Path, output_jars_dir: Path, stem: str) -> Path:
    """
    Rebuild a JAR by injecting a freshly assembled classes.dex.

    :param original_jar: Path to the original JAR file
    :param classes_dir: Path to the directory containing per-lib classes.dex subdirs
    :param output_jars_dir: Path where rebuilt JARs should be written
    :param stem: Name stem (e.g. "UiLib") used to locate the classes.dex subdir and name the output
    :return: Path to the newly created JAR
    """
    # Locate the generated classes.dex
    dex_path = classes_dir / stem / "classes.dex"
    if not dex_path.is_file():
        raise FileNotFoundError(f"Missing classes.dex at {dex_path}")

    if not original_jar.is_file():
        raise FileNotFoundError(f"Original JAR not found at {original_jar}")

    # Prepare output directory & path
    output_jars_dir.mkdir(parents=True, exist_ok=True)
    rebuilt_jar = output_jars_dir / f"{stem}.jar"

    # Rebuild: copy original entries + inject classes.dex at root
    with zipfile.ZipFile(original_jar, "r") as src_zip:
        with zipfile.ZipFile(rebuilt_jar, "w", compression=zipfile.ZIP_DEFLATED) as out_zip:
            # Copy all original entries
            for item in src_zip.infolist():
                data = src_zip.read(item.filename)
                out_zip.writestr(item, data)
            # Now inject the new classes.dex
            out_zip.write(dex_path, arcname="classes.dex")

    return rebuilt_jar


async def deodex_assemble_and_repack(
    *,
    label: str,
    input_dir: Path,
    original_file_dir: Path,
    file_suffix: str,
    baksmali: Baksmali,
    smali: Smali,
    bootclasspath: list[Path],
    dep_dirs: list[Path],
    api_level: int,
    concurrency: int,
    output_smali_dir: Path,
    output_classes_dir: Path,
    output_repacked_dir: Path,
) -> list[Path]:
    """Deodex a directory of .odex files, assemble the smali back into
    classes.dex, and repack the dex into copies of the original archives.

    Args:
        label: Human-readable name for log messages (e.g.
            "system framework", "vendor app").
        input_dir: Directory to scan for .odex files with matching
            companion files.
        original_file_dir: Directory where the original .jar/.apk files
            live. These are copied and repacked with the new classes.dex.
        file_suffix: ".jar" or ".apk". Determines which discovery and
            rebuild helpers are used.
        baksmali: The Baksmali wrapper to invoke for deodexing.
        smali: The Smali wrapper to invoke for assembly.
        bootclasspath: Pre-resolved ordered list of jar paths forming
            the device's BOOTCLASSPATH. Passed through to baksmali
            deodex for vtable resolution.
        dep_dirs: Directories to pass as baksmali `-d` flags for
            additional class resolution.
        api_level: Android API level for the .odex files being
            processed.
        concurrency: Maximum number of subprocesses to run in parallel
            within each phase.
        output_smali_dir: Directory for per-odex smali output. Wiped
            before use.
        output_classes_dir: Directory for per-odex classes.dex output.
            Wiped before use.
        output_repacked_dir: Directory for repacked .jar/.apk output.
            Wiped before use.

    Returns:
        List of .odex paths that were processed.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _limited(coro):  # type: ignore[no-untyped-def]
        async with sem:
            return await coro

    delete_and_recreate_dir_dangerous(output_smali_dir)
    delete_and_recreate_dir_dangerous(output_classes_dir)
    delete_and_recreate_dir_dangerous(output_repacked_dir)

    odex_paths = find_paired_files(input_dir, ".odex", file_suffix)

    # Phase 1: deodex .odex -> .smali
    logger.info("Attempting to deodex %s .odex files from %s (%d concurrent)", label, input_dir, concurrency)
    await asyncio.gather(
        *[
            _limited(
                _deodex_single_odex(
                    baksmali=baksmali,
                    input_odex=odex_path,
                    bootclasspath=bootclasspath,
                    dep_dirs=dep_dirs,
                    api_level=api_level,
                    output_smali_dir=output_smali_dir,
                )
            )
            for odex_path in odex_paths
        ]
    )

    # Phase 2: assemble .smali -> classes.dex
    logger.info("Attempting to build classes.dex from %s smali files (%d concurrent)", label, concurrency)
    await asyncio.gather(
        *[
            _limited(
                _assemble_smali_to_dex(
                    smali=smali,
                    smali_dir=output_smali_dir,
                    classes_dir=output_classes_dir,
                    apk_name=odex_path.stem,
                )
            )
            for odex_path in odex_paths
        ]
    )

    # Phase 3: inject classes.dex into copies of the originals (pure Python, no subprocess)
    for odex_path in odex_paths:
        original = original_file_dir / f"{odex_path.stem}{file_suffix}"
        if file_suffix == ".jar":
            _rebuild_jar_with_dex(
                original_jar=original,
                classes_dir=output_classes_dir,
                output_jars_dir=output_repacked_dir,
                stem=odex_path.stem,
            )
        else:
            _rebuild_apk_with_dex(
                original_apk=original,
                classes_dir=output_classes_dir,
                output_apps_dir=output_repacked_dir,
                stem=odex_path.stem,
            )

    return odex_paths
