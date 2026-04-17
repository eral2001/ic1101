import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Final

import apk_resources
import deodex_pipeline
import process
from file_utils import (
    check_binary_exists,
    check_file_exists,
    delete_and_recreate_dir_dangerous,
    find_files_with_extension_non_recursive,
    resolve_empty_dir,
)
from java import JarCli, SubprocessInvoker
from java.apktool import Apktool
from java.baksmali import Baksmali
from java.smali import Smali
from logger import configure_logging
from unarchive import unzip_mdt_zip, unzip_outer_zip

logger = logging.getLogger(__name__)

_DIR_NAME_OUTPUT_UNZIPPED_ZIP: Final[str] = "unzipped-zip"
_DIR_NAME_OUTPUT_UNZIPPED_MDT: Final[str] = "unzipped-mdt"
_DIR_NAME_OUTPUT_SYSTEM_APP_SMALI: Final[str] = "system-app-smali"
_DIR_NAME_OUTPUT_SYSTEM_APP_CLASSES: Final[str] = "system-app-classes"
_DIR_NAME_OUTPUT_SYSTEM_APP_APKS_REPACKED: Final[str] = "system-app-apks-repacked"
_DIR_NAME_OUTPUT_VENDOR_APP_SMALI: Final[str] = "vendor-app-smali"
_DIR_NAME_OUTPUT_VENDOR_APP_CLASSES: Final[str] = "vendor-app-classes"
_DIR_NAME_OUTPUT_VENDOR_APP_APKS_REPACKED: Final[str] = "vendor-app-apks-repacked"
_DIR_NAME_OUTPUT_SYSTEM_FRAMEWORK_SMALI: Final[str] = "system-framework-smali"
_DIR_NAME_OUTPUT_SYSTEM_FRAMEWORK_CLASSES: Final[str] = "system-framework-classes"
_DIR_NAME_OUTPUT_SYSTEM_FRAMEWORK_JARS_REPACKED: Final[str] = "system-framework-jars-repacked"
_DIR_NAME_OUTPUT_VENDOR_FRAMEWORK_SMALI: Final[str] = "vendor-framework-smali"
_DIR_NAME_OUTPUT_VENDOR_FRAMEWORK_CLASSES: Final[str] = "vendor-framework-classes"
_DIR_NAME_OUTPUT_VENDOR_FRAMEWORK_JARS_REPACKED: Final[str] = "vendor-framework-jars-repacked"
_DIR_NAME_OUTPUT_APKTOOL_SYSTEM_APPS: Final[str] = "apktool-system-apps"
_DIR_NAME_OUTPUT_APKTOOL_VENDOR_APPS: Final[str] = "apktool-vendor-apps"
_DIR_NAME_OUTPUT_APKTOOL_VENDOR_FRAMEWORK: Final[str] = "apktool-vendor-framework"

# Source URLs and SHA-256 sums for jars (provided for verification):
# https://bitbucket.org/JesusFreke/smali/downloads/smali-2.5.2.jar
#   sha256: 9544299578b16f771d8aa8eaefe0d3718ca03478c16f3c356f2fcf1366bfb116
# https://bitbucket.org/JesusFreke/smali/downloads/baksmali-2.5.2.jar
#   sha256: d3116248cce4f82ec5a31eb7f95ee75daff42ddf6eed0ab573973dc53fbad2e5
# https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.12.1.jar
#   sha256: 66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa
_JAR_NAME_SMALI: Final[str] = "smali-2.5.2.jar"
_JAR_NAME_BAKSMALI: Final[str] = "baksmali-2.5.2.jar"
_JAR_NAME_APKTOOL: Final[str] = "apktool_2.12.1.jar"

# apktool framework cache tag for the Mitsubishi vendor framework.
# Passed to `apktool install-framework` and `apktool decode`
# so that apktool looks up the right cached framework-res.apk in its on-disk cache.
_APKTOOL_FRAMEWORK_TAG: Final[str] = "mitsubishi"

# Update ID directory name inside the outer MRC .zip archive.
# The .zip contains a single directory named after the update ID,
# and this ID changes across update images
# (e.g., "2250" for MRC_EU_SW_v12_4.zip, may differ for other images).
_UPDATE_ID: Final[str] = "2250"

# On-device BOOTCLASSPATH. Required by baksmali.
# These were extracted from our MRC_EU_SW_v12_4.zip image
# (sha256sum: 8ff66ea276e941b4428230a2cecbd2f824af334b1116fb4a5d981ab7e172969b)
# and recovered by unpacking boot.img -> ramdisk -> init.rc
# and reading the `export BOOTCLASSPATH ...` line.
#
# The specific jars used and the order of these jars is critical.
# On pre-ART Android (this image is API 17 / Android 4.2.2),
# .odex files encode virtual method calls as vtable indices
# computed by the on-device Dalvik verifier at build time,
# walking the bootclasspath in order and merging each class's vtable with its superclass.
# To re-resolve those indices correctly,
# baksmali must see *the same set of classes in the same order*.
#
# The last 6 jars here are from vendor framework and
# live in system/vendor/framework/ in the unzipped image,
# even though init.rc references them under /system/framework/.
_BOOTCLASSPATH_JAR_NAMES: Final[list[str]] = [
    "core.jar",
    "core-junit.jar",
    "bouncycastle.jar",
    "ext.jar",
    "framework.jar",
    "telephony-common.jar",
    "mms-common.jar",
    "android.policy.jar",
    "services.jar",
    "apache-xml.jar",
    "UiLib.jar",
    "HondaNavigationLib.jar",
    "HondaTelematicsLib.jar",
    "WhitelistLib.jar",
    "honda-framework.jar",
    "HeaderService.jar",
]

# Android API level for this image (Android 4.2.2).
_BAKSMALI_DEODEX_API_LEVEL: Final[int] = 17

# Ignore specific JVM stderr warnings that baksmali-2.5.2 emits on every `deodex` invocation.
# Only add lines here that are genuinely noise; don't use this to hide actual errors.
_BAKSMALI_DEODEX_IGNORE_LINE_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"^WARNING: A terminally deprecated method in sun\.misc\.Unsafe has been called$"),
    re.compile(
        r"^WARNING: sun\.misc\.Unsafe::objectFieldOffset has been called by "
        r"com\.google\.common\.util\.concurrent\.AbstractFuture\$UnsafeAtomicHelper "
        r"\(file:.*baksmali-2\.5\.2\.jar\)$"
    ),
    re.compile(
        r"^WARNING: Please consider reporting this to the maintainers of class "
        r"com\.google\.common\.util\.concurrent\.AbstractFuture\$UnsafeAtomicHelper$"
    ),
    re.compile(r"^WARNING: sun\.misc\.Unsafe::objectFieldOffset will be removed in a future release$"),
]


def _build_jar_cli[T: JarCli](cls: type[T], jar_path: Path, invoker: SubprocessInvoker) -> T:
    check_file_exists(jar_path)
    return cls(jar_path, invoker)


def _resolve_files_in_dirs(names: list[str], search_dirs: list[Path]) -> list[Path]:
    """Resolve each filename against the search directories, in order.

    Duplicate names and duplicate search directories are silently
    ignored so callers don't need to deduplicate their inputs.

    Args:
        names: Ordered list of filenames to resolve. Duplicates
            are skipped; only the first occurrence is resolved.
        search_dirs: Directories to search for each file. The first
            match wins. Duplicates are ignored.

    Returns:
        Ordered list of resolved Paths, one per unique name.

    Raises:
        FileNotFoundError: If any expected file cannot be found in any of
            the search directories.
    """
    unique_dirs = list(dict.fromkeys(search_dirs))
    resolved: list[Path] = []
    seen_names: set[str] = set()
    for name in names:
        if name in seen_names:
            continue
        seen_names.add(name)
        for d in unique_dirs:
            candidate = d / name
            if candidate.is_file():
                resolved.append(candidate)
                break
        else:
            searched = ", ".join(str(d) for d in unique_dirs)
            raise FileNotFoundError(f"{name!r} not found in: {searched}")
    return resolved


async def run_pipeline(input_dir: Path, output_dir: Path, jvm_jobs: int) -> None:
    """Run the APK rebuilder pipeline.

    - Extracts input .zip archive to get the inner SwUpdate.mdt archive
    - Extracts the inner SwUpdate.mdt archive to get the Android filesystem tree
    - Deodexes all framework and app .odex files in the tree
    - Reassembles the smali into classes.dex
    - Repacks the originals with real bytecode
    - Decodes APK resources with apktool

    Args:
        input_dir: Directory containing the tool jars (baksmali, smali,
            apktool) and a single .zip update image.
        output_dir: Directory where all pipeline output will be
            written. Wiped and recreated at the start of each run.
        jvm_jobs: Maximum number of Java tool subprocesses to run
            concurrently within each pipeline phase.

    Raises:
        FileNotFoundError: If any required input file or directory is
            missing (java binary, jar files, .zip archive, expected
            archive contents).
        OSError: If a jar path exists but is not a regular file.
        subprocess.CalledProcessError: If any java tool invocation fails.
    """
    # Find the single .zip file in the input directory.
    zip_files = sorted(input_dir.glob("*.zip"))
    if len(zip_files) == 0:
        raise FileNotFoundError(f"No .zip file found in {input_dir}")
    if len(zip_files) > 1:
        names = ", ".join(f.name for f in zip_files)
        raise FileNotFoundError(f"Expected exactly one .zip file in {input_dir}, found {len(zip_files)}: {names}")
    zip_path = zip_files[0]
    logger.info("Found input archive: %s", zip_path)

    output_dir = resolve_empty_dir(output_dir)
    logger.info("Output will be written to %s", output_dir)

    check_binary_exists("java")

    # Redirect baksmali deodex stderr to swallow common/noisy output lines
    baksmali_filtered_stderr = process.filter_lines(sys.stderr, _BAKSMALI_DEODEX_IGNORE_LINE_PATTERNS)

    async def baksmali_invoker(cmd: list[str]) -> None:
        await process.run(cmd, stdout=sys.stderr, stderr=baksmali_filtered_stderr)

    async def default_invoker(cmd: list[str]) -> None:
        await process.run(cmd, stdout=sys.stderr, stderr=sys.stderr)

    # Construct the java tool wrappers.
    baksmali = _build_jar_cli(Baksmali, input_dir / _JAR_NAME_BAKSMALI, baksmali_invoker)
    smali = _build_jar_cli(Smali, input_dir / _JAR_NAME_SMALI, default_invoker)
    apktool = _build_jar_cli(Apktool, input_dir / _JAR_NAME_APKTOOL, default_invoker)

    # Will contain the unzipped MRC_<...>.zip .zip file.
    unzipped_zip_dir = output_dir / _DIR_NAME_OUTPUT_UNZIPPED_ZIP
    # Will contain the unzipped SwUpdate.mdt file.
    unzipped_mdt_dir = output_dir / _DIR_NAME_OUTPUT_UNZIPPED_MDT
    # Will contain .smali files from deodexing system/framework/*.odex files.
    system_framework_smali_dir = output_dir / _DIR_NAME_OUTPUT_SYSTEM_FRAMEWORK_SMALI
    # Will contain classes.dex files from reassembling system framework .smali files.
    system_framework_classes_dir = output_dir / _DIR_NAME_OUTPUT_SYSTEM_FRAMEWORK_CLASSES
    # Will contain reconstructed system/framework/*.jar files with classes.dex files.
    output_system_framework_jars_repacked_dir = output_dir / _DIR_NAME_OUTPUT_SYSTEM_FRAMEWORK_JARS_REPACKED
    # Will contain .smali files from deodexing system/vendor/framework/*.odex files.
    vendor_framework_smali_dir = output_dir / _DIR_NAME_OUTPUT_VENDOR_FRAMEWORK_SMALI
    # Will contain classes.dex files from reassembling vendor framework .smali files.
    vendor_framework_classes_dir = output_dir / _DIR_NAME_OUTPUT_VENDOR_FRAMEWORK_CLASSES
    # Will contain reconstructed system/vendor/framework/*.jar files with classes.dex files.
    output_vendor_framework_jars_repacked_dir = output_dir / _DIR_NAME_OUTPUT_VENDOR_FRAMEWORK_JARS_REPACKED
    # Will contain .smali files from deodexing system/app/*.odex files.
    system_app_smali_dir = output_dir / _DIR_NAME_OUTPUT_SYSTEM_APP_SMALI
    # Will contain classes.dex files from reassembling system app .smali files.
    system_app_classes_dir = output_dir / _DIR_NAME_OUTPUT_SYSTEM_APP_CLASSES
    # Will contain reconstructed system/app/*.apk files with classes.dex files.
    output_system_apps_repacked_dir = output_dir / _DIR_NAME_OUTPUT_SYSTEM_APP_APKS_REPACKED
    # Will contain .smali files from deodexing system/vendor/app/*.odex files.
    vendor_app_smali_dir = output_dir / _DIR_NAME_OUTPUT_VENDOR_APP_SMALI
    # Will contain classes.dex files from reassembling .smali files.
    vendor_app_classes_dir = output_dir / _DIR_NAME_OUTPUT_VENDOR_APP_CLASSES
    # Will contain reconstructed system/vendor/app/*.apk files with classes.dex files.
    output_vendor_apps_repacked_dir = output_dir / _DIR_NAME_OUTPUT_VENDOR_APP_APKS_REPACKED
    # Will contain decoded system APK resources from apktool.
    apktool_system_apps_dir = output_dir / _DIR_NAME_OUTPUT_APKTOOL_SYSTEM_APPS
    # Will contain decoded vendor APK resources from apktool.
    apktool_vendor_apps_dir = output_dir / _DIR_NAME_OUTPUT_APKTOOL_VENDOR_APPS
    # Will contain decoded vendor framework resources from apktool.
    apktool_vendor_framework_dir = output_dir / _DIR_NAME_OUTPUT_APKTOOL_VENDOR_FRAMEWORK

    # Extract contents of MRC_<...>.zip file.
    delete_and_recreate_dir_dangerous(unzipped_zip_dir)
    logger.info("Extracting .zip archive to %s", unzipped_zip_dir)
    mdt_file = unzip_outer_zip(zip_path, unzipped_zip_dir, _UPDATE_ID)

    # Extract contents of SwUpdate.mdt file.
    delete_and_recreate_dir_dangerous(unzipped_mdt_dir)
    logger.info("Extracting .mdt archive to %s", unzipped_mdt_dir)
    unzip_mdt_zip(mdt_file, unzipped_mdt_dir)
    logger.info("The Android file system has been extracted to '%s'.", unzipped_mdt_dir)

    system_apps_dir: Final[Path] = unzipped_mdt_dir / "system" / "app"
    vendor_apps_dir: Final[Path] = unzipped_mdt_dir / "system" / "vendor" / "app"
    system_framework_dir: Final[Path] = unzipped_mdt_dir / "system" / "framework"
    vendor_framework_dir: Final[Path] = unzipped_mdt_dir / "system" / "vendor" / "framework"

    # Vendor resource bundle.
    # apktool needs this installed as its framework cache before it can
    # decode any APK that references vendor resource IDs.
    vendor_framework_res_apk = vendor_framework_dir / "framework-res.apk"

    bootclasspath_jars = _resolve_files_in_dirs(
        _BOOTCLASSPATH_JAR_NAMES,
        [system_framework_dir, vendor_framework_dir],
    )

    # Deodex and repack framework jars first; apps depend on them.

    await deodex_pipeline.deodex_assemble_and_repack(
        label="system framework",
        input_dir=system_framework_dir,
        original_file_dir=system_framework_dir,
        file_suffix=".jar",
        baksmali=baksmali,
        smali=smali,
        bootclasspath=bootclasspath_jars,
        dep_dirs=[vendor_framework_dir],
        api_level=_BAKSMALI_DEODEX_API_LEVEL,
        concurrency=jvm_jobs,
        output_smali_dir=system_framework_smali_dir,
        output_classes_dir=system_framework_classes_dir,
        output_repacked_dir=output_system_framework_jars_repacked_dir,
    )

    await deodex_pipeline.deodex_assemble_and_repack(
        label="vendor framework",
        input_dir=vendor_framework_dir,
        original_file_dir=vendor_framework_dir,
        file_suffix=".jar",
        baksmali=baksmali,
        smali=smali,
        bootclasspath=bootclasspath_jars,
        dep_dirs=[vendor_framework_dir],
        api_level=_BAKSMALI_DEODEX_API_LEVEL,
        concurrency=jvm_jobs,
        output_smali_dir=vendor_framework_smali_dir,
        output_classes_dir=vendor_framework_classes_dir,
        output_repacked_dir=output_vendor_framework_jars_repacked_dir,
    )

    # Build dependency directory list for app deodexing. Apps can depend
    # on classes from both system and vendor framework, so we pass each
    # repacked framework jar directory as a baksmali -d flag.
    dep_dirs: list[Path] = []
    if output_system_framework_jars_repacked_dir.is_dir() and any(
        output_system_framework_jars_repacked_dir.glob("*.jar")
    ):
        dep_dirs.append(output_system_framework_jars_repacked_dir)
    if output_vendor_framework_jars_repacked_dir.is_dir() and any(
        output_vendor_framework_jars_repacked_dir.glob("*.jar")
    ):
        dep_dirs.append(output_vendor_framework_jars_repacked_dir)

    if not dep_dirs:
        logger.warning("no repacked framework jars found, falling back to raw vendor framework dir.")
        dep_dirs = [vendor_framework_dir]

    await deodex_pipeline.deodex_assemble_and_repack(
        label="system app",
        input_dir=system_apps_dir,
        original_file_dir=system_apps_dir,
        file_suffix=".apk",
        baksmali=baksmali,
        smali=smali,
        bootclasspath=bootclasspath_jars,
        dep_dirs=dep_dirs,
        api_level=_BAKSMALI_DEODEX_API_LEVEL,
        concurrency=jvm_jobs,
        output_smali_dir=system_app_smali_dir,
        output_classes_dir=system_app_classes_dir,
        output_repacked_dir=output_system_apps_repacked_dir,
    )

    await deodex_pipeline.deodex_assemble_and_repack(
        label="vendor app",
        input_dir=vendor_apps_dir,
        original_file_dir=vendor_apps_dir,
        file_suffix=".apk",
        baksmali=baksmali,
        smali=smali,
        bootclasspath=bootclasspath_jars,
        dep_dirs=dep_dirs,
        api_level=_BAKSMALI_DEODEX_API_LEVEL,
        concurrency=jvm_jobs,
        output_smali_dir=vendor_app_smali_dir,
        output_classes_dir=vendor_app_classes_dir,
        output_repacked_dir=output_vendor_apps_repacked_dir,
    )

    # Use apktool to decode system apps
    await apk_resources.decode_apps(
        apktool=apktool,
        framework_res_apk=vendor_framework_res_apk,
        framework_tag=_APKTOOL_FRAMEWORK_TAG,
        apk_paths=find_files_with_extension_non_recursive(system_apps_dir, ".apk"),
        output_dir=apktool_system_apps_dir,
    )

    # Use apktool to decode vendor apps
    await apk_resources.decode_apps(
        apktool=apktool,
        framework_res_apk=vendor_framework_res_apk,
        framework_tag=_APKTOOL_FRAMEWORK_TAG,
        apk_paths=find_files_with_extension_non_recursive(vendor_apps_dir, ".apk"),
        output_dir=apktool_vendor_apps_dir,
    )

    # Use apktool to decode vendor framework
    await apk_resources.decode_framework(
        apktool=apktool,
        framework_res_apk=vendor_framework_res_apk,
        framework_tag=_APKTOOL_FRAMEWORK_TAG,
        output_dir=apktool_vendor_framework_dir,
    )


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {n}")
    return n


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deodex and decode an Android update image.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing the tool jars (baksmali, smali, apktool) and the input .zip archive.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where all pipeline output will be written.",
    )
    parser.add_argument(
        "--jvm-jobs",
        type=_positive_int,
        default=os.process_cpu_count() or 1,
        help=(
            "Maximum number of Java tool subprocesses to run concurrently within each "
            "pipeline phase. Higher values use more memory (~100-200MB per JVM) but "
            "reduce wall-clock time roughly proportionally up to the CPU count. "
            "Defaults to the number of CPUs available to this process."
        ),
    )
    args = parser.parse_args()

    configure_logging()

    try:
        await run_pipeline(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            jvm_jobs=args.jvm_jobs,
        )
    except NotADirectoryError as e:
        logger.error("Output path is not a directory: %s", e)
        sys.exit(1)
    except FileExistsError as e:
        logger.error("Output directory already contains files: %s", e)
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error("Required path does not exist: %s", e)
        sys.exit(1)
    except OSError as e:
        logger.error("Filesystem error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
