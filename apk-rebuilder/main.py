import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from typing import List
import zipfile
from dataclasses import dataclass

DIR_NAME_OUTPUT = "output"
DIR_NAME_INPUT = "input"
DIR_NAME_UNZIPPED_ZIP = "unzipped-zip"
DIR_NAME_UNZIPPED_MDT = "unzipped-mdt"
DIR_NAME_SYSTEM_APP_SMALI = "system-app-smali"
DIR_NAME_SYSTEM_APP_CLASSES = "system-app-classes"
DIR_NAME_SYSTEM_APP_APKS_REPACKED = "system-app-apks-repacked"
DIR_NAME_VENDOR_APP_SMALI = "vendor-app-smali"
DIR_NAME_VENDOR_APP_CLASSES = "vendor-app-classes"
DIR_NAME_VENDOR_APP_APKS_REPACKED = "vendor-app-apks-repacked"
DIR_NAME_SYSTEM_FRAMEWORK_SMALI = "system-framework-smali"
DIR_NAME_SYSTEM_FRAMEWORK_CLASSES = "system-framework-classes"
DIR_NAME_SYSTEM_FRAMEWORK_JARS_REPACKED = "system-framework-jars-repacked"
DIR_NAME_VENDOR_FRAMEWORK_SMALI = "vendor-framework-smali"
DIR_NAME_VENDOR_FRAMEWORK_CLASSES = "vendor-framework-classes"
DIR_NAME_VENDOR_FRAMEWORK_JARS_REPACKED = "vendor-framework-jars-repacked"
DIR_NAME_APKTOOL_SYSTEM_APPS = "apktool-system-apps"
DIR_NAME_APKTOOL_VENDOR_APPS = "apktool-vendor-apps"
DIR_NAME_APKTOOL_VENDOR_FRAMEWORK = "apktool-vendor-framework"

# Source URLs and SHA-256 sums for jars (provided for verification):
# https://bitbucket.org/JesusFreke/smali/downloads/smali-2.5.2.jar
#   sha256: 9544299578b16f771d8aa8eaefe0d3718ca03478c16f3c356f2fcf1366bfb116
# https://bitbucket.org/JesusFreke/smali/downloads/baksmali-2.5.2.jar
#   sha256: d3116248cce4f82ec5a31eb7f95ee75daff42ddf6eed0ab573973dc53fbad2e5
# https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.12.1.jar
#   sha256: 66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa
JAR_NAME_SMALI = "smali-2.5.2.jar"
JAR_NAME_BAKSMALI = "baksmali-2.5.2.jar"
JAR_NAME_APKTOOL = "apktool_2.12.1.jar"


def get_script_dir() -> Path:
    script_file = Path(__file__).resolve()
    return script_file.parent


def get_output_dir() -> Path:
    return get_script_dir() / DIR_NAME_OUTPUT


def get_input_dir() -> Path:
    return get_script_dir() / DIR_NAME_INPUT



def clean_dir(path: Path):
    """Remove the directory if it exists."""
    if path.exists():
        shutil.rmtree(path)


def reset_dir(path: Path):
    # Remove the directory if it exists
    if path.exists():
        shutil.rmtree(path)
    # Create the directory
    path.mkdir()


@dataclass
class JarPaths:
    smali_jar: Path
    baksmali_jar: Path


def get_jars() -> JarPaths:
    """
    Returns paths to smali and baksmali jars in the inputs directory,
    after verifying they exist.
    """
    inputs_dir = get_input_dir()
    jar_path_smali = inputs_dir / JAR_NAME_SMALI
    jar_path_baksmali = inputs_dir / JAR_NAME_BAKSMALI

    if not jar_path_smali.exists():
        sys.exit(f"Error: {jar_path_smali} does not exist")
    if not jar_path_smali.is_file():
        sys.exit(f"Error: {jar_path_smali} is not a file")
    if not jar_path_baksmali.exists():
        sys.exit(f"Error: {jar_path_baksmali} does not exist")
    if not jar_path_baksmali.is_file():
        sys.exit(f"Error: {jar_path_baksmali} is not a file")

    return JarPaths(smali_jar=jar_path_smali, baksmali_jar=jar_path_baksmali)


def zip_path_type(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"'{p}' does not exist or is not a file.")
    if p.suffix.lower() != ".zip":
        raise argparse.ArgumentTypeError(f"'{p}' is not a .zip file.")
    return p


def extract_flat(zip_path: Path, dest_dir: Path):
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


def verify_file(file_path: Path) -> None:
    if not file_path.exists():
        message = (
            "⚠️🐛 File doesn't match our expected format. Please open a bug report!"
        )
        print(message, file=sys.stderr)
        sys.exit(f"Error: path does not exist: {file_path}")
    if not file_path.is_file():
        message = (
            "⚠️🐛 File doesn't match our expected format. Please open a bug report!"
        )
        print(message, file=sys.stderr)
        sys.exit(f"Error: path exists but is not a file: '{file_path}'")


def verify_dir(dir_path: Path) -> None:
    if not dir_path.exists():
        message = (
            "⚠️🐛 File doesn't match our expected format. Please open a bug report!"
        )
        print(message, file=sys.stderr)
        sys.exit(f"Error: path does not exist: {dir_path}")
    if not dir_path.is_dir():
        message = (
            "⚠️🐛 File file doesn't match our expected format. Please open a bug report!"
        )
        print(message, file=sys.stderr)
        sys.exit(f"Error: path exists but is not a directory: {dir_path}")


def unzip_outer_zip(zip_path: Path, dest_dir) -> Path:
    """
    Extracts the user-provided .zip file and checks that it's a valid MELCO Running Change (MRC) update file.
    Returns the path to the SwUpdate.mdt file contained inside the .zip archive.
    """

    # Extract the .zip file.
    try:
        extract_flat(zip_path, dest_dir=dest_dir)
    except zipfile.BadZipFile as e:
        sys.exit(f"Bad ZIP file: {e}")
    except Exception as e:
        sys.exit(f"Extraction error: {e}")

    # Check that unzipped archive looks reasonable.
    path_sw_update = dest_dir / "SwUpdate2.txt"
    path_update_id = dest_dir / "2250"
    path_sw_update_mdt = dest_dir / "2250" / "SwUpdate.mdt"

    verify_file(path_sw_update)
    verify_dir(path_update_id)
    verify_file(path_sw_update_mdt)

    return path_sw_update_mdt


def unzip_mdt_zip(zip_path: Path, dest_dir):
    # Extract the .mdt file.
    try:
        extract_flat(zip_path, dest_dir=dest_dir)
    except zipfile.BadZipFile as e:
        sys.exit(f"Bad ZIP file: {e}")
    except Exception as e:
        sys.exit(f"Extraction error: {e}")

    # Check that Android system directory looks reasonable.
    verify_dir(dest_dir / "system")
    verify_dir(dest_dir / "system" / "app")
    verify_dir(dest_dir / "system" / "framework")
    verify_dir(dest_dir / "system" / "lib")
    verify_dir(dest_dir / "system" / "vendor")

    # Check that Android system/vendor directory looks reasonable.
    verify_dir(dest_dir / "system" / "vendor" / "app")
    verify_dir(dest_dir / "system" / "vendor" / "framework")
    verify_dir(dest_dir / "system" / "vendor" / "lib")


def check_java_exists() -> None:
    java_path = shutil.which("java")
    if java_path is None:
        print("Error: 'java' not found in your PATH.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Found Java at: {java_path}", file=sys.stderr)


def get_apk_paired_odex_paths(parent_dir: str | Path) -> list[Path]:
    """Returns paths to .odex files that have a matching .apk companion."""
    print(f"Getting paths to .odex files (with .apk companions) inside {parent_dir}", file=sys.stderr)
    dir = Path(parent_dir)
    if not dir.is_dir():
        raise ValueError(f"{dir!r} is not a directory")

    matches: List[Path] = []
    for odex_path in dir.glob("*.odex"):
        apk_path = odex_path.with_suffix(".apk")
        if apk_path.exists() and apk_path.is_file():
            matches.append(odex_path)

    return matches


def get_jar_paired_odex_paths(parent_dir: str | Path) -> list[Path]:
    """Returns paths to .odex files that have a matching .jar companion."""
    print(f"Getting paths to .odex files (with .jar companions) inside {parent_dir}", file=sys.stderr)
    dir = Path(parent_dir)
    if not dir.is_dir():
        raise ValueError(f"{dir!r} is not a directory")

    matches: List[Path] = []
    for odex_path in dir.glob("*.odex"):
        jar_path = odex_path.with_suffix(".jar")
        if jar_path.exists() and jar_path.is_file():
            matches.append(odex_path)

    return matches


def get_system_app_apk_paths(system_app_dir: Path) -> list[Path]:
    """Returns paths to all .apk files in the system app directory."""
    print(f"Getting paths to .apk files inside {system_app_dir}", file=sys.stderr)
    if not system_app_dir.is_dir():
        raise ValueError(f"{system_app_dir!r} is not a directory")
    return sorted(system_app_dir.glob("*.apk"))


def get_vendor_app_apk_paths(vendor_app_dir: Path) -> list[Path]:
    """Returns paths to all .apk files in the vendor app directory."""
    print(f"Getting paths to .apk files inside {vendor_app_dir}", file=sys.stderr)
    if not vendor_app_dir.is_dir():
        raise ValueError(f"{vendor_app_dir!r} is not a directory")
    return sorted(vendor_app_dir.glob("*.apk"))


def disassemble_odex(
    baksmali_jar: Path,
    unzipped_mdt_dir: Path,
    output_smali_dir: Path,
    input_odex: Path,
    api_level: int = 17,
) -> None:
    """
    Runs baksmali on a single .odex, pointing at the correct framework jars
    and dumping output to output_smali_dir/<odex-stem>.

    :param baksmali_jar: Path to the baksmali jar file
    :param unzipped_mdt_dir: Path to the root of your unzipped .mdt image (contains the Android filesystem)
    :param output_smali_dir: Path where per-APK smali folders will be created
    :param input_odex: Path to the .odex file to disassemble
    :param api_level: Android API level (default: 17 for Android 4.2.2)
    """
    # Ensure that baksmali jar exists.
    if not baksmali_jar.is_file():
        raise FileNotFoundError(f"Cannot find baksmali JAR at {baksmali_jar}")

    # Standard API-17 framework jars.
    framework_dir = unzipped_mdt_dir / "system/framework"
    core_jar = framework_dir / "core.jar"
    ext_jar = framework_dir / "ext.jar"
    framework_jar = framework_dir / "framework.jar"
    services_jar = framework_dir / "services.jar"
    for jar in (core_jar, ext_jar, framework_jar, services_jar):
        if not jar.is_file():
            raise FileNotFoundError(f"Missing framework jar: {jar}")

    # Build bootclasspath string
    bootclasspath = ":".join(map(str, [core_jar, ext_jar, framework_jar, services_jar]))

    # Vendor framework directory
    vendor_fw_dir = unzipped_mdt_dir / "system/vendor/framework"
    if not vendor_fw_dir.is_dir():
        raise FileNotFoundError(f"Vendor framework dir not found: {vendor_fw_dir}")

    # Output directory named after the odex stem
    out_dir = output_smali_dir / input_odex.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build the command
    cmd = [
        "java",
        "-jar",
        str(baksmali_jar),
        "disassemble",
        "--api",
        str(api_level),
        "--bootclasspath",
        bootclasspath,
        "-d",
        str(vendor_fw_dir),
        "-o",
        str(out_dir),
        str(input_odex),
    ]

    # Execute
    print("Running:", " ".join(cmd), file=sys.stderr)
    subprocess.run(
        cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def assemble_smali_to_dex(
    smali_jar: Path, smali_dir: Path, classes_dir: Path, apk_name: str
) -> Path:
    """
    Assembles a directory of smali files into a classes.dex file.

    :param smali_jar: Path to the smali jar file
    :param smali_dir: Path to the root of your smali output (contains subdirs named by odex stem)
    :param classes_dir: Path where per-APK classes.dex files should be written
    :param odex_path:   Path to the original .odex file (used only for its stem)
    :return: Path to the newly created classes.dex
    """
    # Ensure that smali_jar exists.
    if not smali_jar.is_file():
        raise FileNotFoundError(f"Cannot find smali JAR at {smali_jar}")

    # Determine the smali input directory.
    smali_input = smali_dir / apk_name
    if not smali_input.is_dir():
        raise FileNotFoundError(f"Smali directory not found: {smali_input}")

    # Prepare the output directory and path.
    out_dir = classes_dir / apk_name
    out_dir.mkdir(parents=True, exist_ok=True)
    dex_path = out_dir / "classes.dex"

    # Build and run the command
    cmd = [
        "java",
        "-jar",
        str(smali_jar),
        "assemble",
        str(smali_input),
        "-o",
        str(dex_path),
    ]
    print("Running:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)

    return dex_path


def rebuild_apk_with_dex(
    original_apk: Path, classes_dir: Path, output_apps_dir: Path, stem: str
) -> Path:
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
        with zipfile.ZipFile(
            rebuilt_apk, "w", compression=zipfile.ZIP_DEFLATED
        ) as out_zip:
            # Copy all original entries
            for item in src_zip.infolist():
                data = src_zip.read(item.filename)
                out_zip.writestr(item, data)
            # Now inject the new classes.dex
            out_zip.write(dex_path, arcname="classes.dex")

    return rebuilt_apk


def rebuild_jar_with_dex(
    original_jar: Path, classes_dir: Path, output_jars_dir: Path, stem: str
) -> Path:
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
        with zipfile.ZipFile(
            rebuilt_jar, "w", compression=zipfile.ZIP_DEFLATED
        ) as out_zip:
            # Copy all original entries
            for item in src_zip.infolist():
                data = src_zip.read(item.filename)
                out_zip.writestr(item, data)
            # Now inject the new classes.dex
            out_zip.write(dex_path, arcname="classes.dex")

    return rebuilt_jar


def process_system_apps(
    unzipped_mdt_dir: Path,
    input_apps_dir: Path,
    jars: JarPaths,
    output_smali_dir: Path,
    output_classes_dir: Path,
    output_apps_dir: Path,
) -> list[Path]:
    """
    Process system apps (system/app/*.odex).

    :param unzipped_mdt_dir: Path to the root of your unzipped image (contains the Android filesystem)
    :param input_apps_dir: Path to the directory containing the *.apk and *.odex files
    :param jars: Class containing paths to baksmali and smali .jar files
    :param output_smali_dir: Where smali files will be written (under <output_smali_dir>/<apk-name>)
    :param output_classes_dir: Where classes.dex files will be written (under <output_classes_dir>/<apk-name>)
    :param output_apps_dir: Where rebuilt APKs (APKs with injected classes.dex files) will be written
    :return: List of paths to .odex files that were processed
    """
    # Clean up the directories.
    reset_dir(output_smali_dir)
    reset_dir(output_classes_dir)
    reset_dir(output_apps_dir)

    # Get paths to all of the .odex files in input_apps_dir.
    odex_paths = get_apk_paired_odex_paths(input_apps_dir)
    # Deodex the .odex files to produce .smali files.
    print(f"Attempting to deodex system app .odex files from {input_apps_dir}", file=sys.stderr)
    for odex_path in odex_paths:
        disassemble_odex(
            baksmali_jar=jars.baksmali_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            output_smali_dir=output_smali_dir,
            input_odex=odex_path,
        )

    # Use the .smali files to generate classes.dex files.
    print("Attempting to build classes.dex from system app smali files", file=sys.stderr)
    for odex_path in odex_paths:
        assemble_smali_to_dex(
            smali_jar=jars.smali_jar,
            smali_dir=output_smali_dir,
            classes_dir=output_classes_dir,
            apk_name=odex_path.stem,
        )

    # Inject the classes.dex files into copies of the APKs.
    for odex_path in odex_paths:
        original_apk = unzipped_mdt_dir / "system" / "app" / f"{odex_path.stem}.apk"
        rebuild_apk_with_dex(
            original_apk=original_apk,
            classes_dir=output_classes_dir,
            output_apps_dir=output_apps_dir,
            stem=odex_path.stem,
        )

    return odex_paths


def process_vendor_apps(
    unzipped_mdt_dir: Path,
    input_apps_dir: Path,
    jars: JarPaths,
    output_smali_dir: Path,
    output_classes_dir: Path,
    output_apps_dir: Path,
) -> list[Path]:
    """
    Process apps in a given input_apps_dir directory.

    :param unzipped_mdt: Path to the root of your unzipped image (contains the Android filesystem)
    :param input_apps_dir: Path to the directory containing the *.apk and *.odex files
    :param jars: Class containing paths to baksmali and smali .jar files
    :param output_smali_dir: Where smali files will be written (under <output_smali_dir>/<apk-name>)
    :param output_classes_dir: Where classes.dex files will be written (under <output_classes_dir>/<apk-name>)
    :param output_apps_dir: Where rebuilt APKs (APKs with injected classes.dex files) will be written
    :return: List of paths to .odex files that were processed
    """
    # Clean up the directories.
    reset_dir(output_smali_dir)
    reset_dir(output_classes_dir)
    reset_dir(output_apps_dir)

    # Get paths to all of the .odex files in input_apps_dir.
    odex_paths = get_apk_paired_odex_paths(input_apps_dir)
    # Deodex the .odex files to produce .smali files.
    print(f"Attempting to deodex .odex files from {input_apps_dir}", file=sys.stderr)
    for odex_path in odex_paths:
        disassemble_odex(
            baksmali_jar=jars.baksmali_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            output_smali_dir=output_smali_dir,
            input_odex=odex_path,
        )

    # Use the .smali files to generate classes.dex files.
    print("Attempting to build classes.dex from smali files", file=sys.stderr)
    for odex_path in odex_paths:
        assemble_smali_to_dex(
            smali_jar=jars.smali_jar,
            smali_dir=output_smali_dir,
            classes_dir=output_classes_dir,
            apk_name=odex_path.stem,
        )

    # Inject the classes.dex files into copies of the APKs.
    for odex_path in odex_paths:
        original_apk = unzipped_mdt_dir / "system" / "vendor" / "app" / f"{odex_path.stem}.apk"
        rebuild_apk_with_dex(
            original_apk=original_apk,
            classes_dir=output_classes_dir,
            output_apps_dir=output_apps_dir,
            stem=odex_path.stem,
        )

    return odex_paths


def process_system_framework_libs(
    unzipped_mdt_dir: Path,
    input_framework_dir: Path,
    jars: JarPaths,
    output_smali_dir: Path,
    output_classes_dir: Path,
    output_jars_dir: Path,
) -> list[Path]:
    """
    Process system framework libraries (system/framework/*.odex).

    :param unzipped_mdt_dir: Path to the root of your unzipped image (contains the Android filesystem)
    :param input_framework_dir: Path to the directory containing the *.jar and *.odex files
    :param jars: Class containing paths to baksmali and smali .jar files
    :param output_smali_dir: Where smali files will be written (under <output_smali_dir>/<lib-name>)
    :param output_classes_dir: Where classes.dex files will be written (under <output_classes_dir>/<lib-name>)
    :param output_jars_dir: Where rebuilt JARs (JARs with injected classes.dex files) will be written
    :return: List of paths to .odex files that were processed
    """
    # Clean up the directories.
    reset_dir(output_smali_dir)
    reset_dir(output_classes_dir)
    reset_dir(output_jars_dir)

    # Get paths to all of the .odex files in input_framework_dir.
    odex_paths = get_jar_paired_odex_paths(input_framework_dir)
    # Deodex the .odex files to produce .smali files.
    print(f"Attempting to deodex system framework .odex files from {input_framework_dir}", file=sys.stderr)
    for odex_path in odex_paths:
        disassemble_odex(
            baksmali_jar=jars.baksmali_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            output_smali_dir=output_smali_dir,
            input_odex=odex_path,
        )

    # Use the .smali files to generate classes.dex files.
    print("Attempting to build classes.dex from system framework smali files", file=sys.stderr)
    for odex_path in odex_paths:
        assemble_smali_to_dex(
            smali_jar=jars.smali_jar,
            smali_dir=output_smali_dir,
            classes_dir=output_classes_dir,
            apk_name=odex_path.stem,
        )

    # Inject the classes.dex files into copies of the JARs.
    for odex_path in odex_paths:
        original_jar = unzipped_mdt_dir / "system" / "framework" / f"{odex_path.stem}.jar"
        rebuild_jar_with_dex(
            original_jar=original_jar,
            classes_dir=output_classes_dir,
            output_jars_dir=output_jars_dir,
            stem=odex_path.stem,
        )

    return odex_paths


def process_vendor_framework_libs(
    unzipped_mdt_dir: Path,
    input_framework_dir: Path,
    jars: JarPaths,
    output_smali_dir: Path,
    output_classes_dir: Path,
    output_jars_dir: Path,
) -> list[Path]:
    """
    Process vendor framework libraries (system/vendor/framework/*.odex).

    :param unzipped_mdt_dir: Path to the root of your unzipped image (contains the Android filesystem)
    :param input_framework_dir: Path to the directory containing the *.jar and *.odex files
    :param jars: Class containing paths to baksmali and smali .jar files
    :param output_smali_dir: Where smali files will be written (under <output_smali_dir>/<lib-name>)
    :param output_classes_dir: Where classes.dex files will be written (under <output_classes_dir>/<lib-name>)
    :param output_jars_dir: Where rebuilt JARs (JARs with injected classes.dex files) will be written
    :return: List of paths to .odex files that were processed
    """
    # Clean up the directories.
    reset_dir(output_smali_dir)
    reset_dir(output_classes_dir)
    reset_dir(output_jars_dir)

    # Get paths to all of the .odex files in input_framework_dir.
    odex_paths = get_jar_paired_odex_paths(input_framework_dir)
    # Deodex the .odex files to produce .smali files.
    print(f"Attempting to deodex vendor framework .odex files from {input_framework_dir}", file=sys.stderr)
    for odex_path in odex_paths:
        disassemble_odex(
            baksmali_jar=jars.baksmali_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            output_smali_dir=output_smali_dir,
            input_odex=odex_path,
        )

    # Use the .smali files to generate classes.dex files.
    print("Attempting to build classes.dex from vendor framework smali files", file=sys.stderr)
    for odex_path in odex_paths:
        assemble_smali_to_dex(
            smali_jar=jars.smali_jar,
            smali_dir=output_smali_dir,
            classes_dir=output_classes_dir,
            apk_name=odex_path.stem,
        )

    # Inject the classes.dex files into copies of the JARs.
    for odex_path in odex_paths:
        original_jar = unzipped_mdt_dir / "system" / "vendor" / "framework" / f"{odex_path.stem}.jar"
        rebuild_jar_with_dex(
            original_jar=original_jar,
            classes_dir=output_classes_dir,
            output_jars_dir=output_jars_dir,
            stem=odex_path.stem,
        )

    return odex_paths


def get_apktool_jar() -> Path:
    """
    Returns the path to the apktool jar in the inputs directory.
    """
    apktool_jar = get_input_dir() / JAR_NAME_APKTOOL
    if not apktool_jar.is_file():
        sys.exit(f"Error: apktool jar not found at {apktool_jar}")
    return apktool_jar


def install_apktool_framework(apktool_jar: Path, framework_res_apk: Path) -> None:
    """
    Installs the Mitsubishi framework-res.apk into apktool.

    :param apktool_jar: Path to the apktool jar file
    :param framework_res_apk: Path to the framework-res.apk file
    """
    if not framework_res_apk.is_file():
        raise FileNotFoundError(f"Framework APK not found at {framework_res_apk}")

    cmd = [
        "java",
        "-jar",
        str(apktool_jar),
        "if",
        str(framework_res_apk),
        "-t",
        "mitsubishi",
    ]

    print("Running:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def decode_apk_with_apktool(
    apktool_jar: Path, input_apk: Path, output_dir: Path
) -> None:
    """
    Decodes an APK using apktool with the mitsubishi framework.

    :param apktool_jar: Path to the apktool jar file
    :param input_apk: Path to the APK file to decode
    :param output_dir: Path where decoded resources will be written
    """
    if not input_apk.is_file():
        raise FileNotFoundError(f"APK not found at {input_apk}")

    cmd = [
        "java",
        "-jar",
        str(apktool_jar),
        "d",
        str(input_apk),
        "-t",
        "mitsubishi",
        "-o",
        str(output_dir),
    ]

    print("Running:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def process_apps_with_apktool(
    apktool_jar: Path,
    unzipped_mdt_dir: Path,
    apk_paths: list[Path],
    output_apktool_dir: Path,
) -> None:
    """
    Process apps with apktool to decode resources.

    :param apktool_jar: Path to the apktool jar file
    :param unzipped_mdt_dir: Path to the root of your unzipped image (contains the Android filesystem)
    :param apk_paths: List of .apk file paths to decode
    :param output_apktool_dir: Path where decoded APK resources will be written
    """
    # Clean up the output directory.
    reset_dir(output_apktool_dir)

    # Install the Mitsubishi framework into apktool.
    framework_res_apk = unzipped_mdt_dir / "system" / "vendor" / "framework" / "framework-res.apk"
    print("Installing Mitsubishi framework into apktool", file=sys.stderr)
    install_apktool_framework(apktool_jar, framework_res_apk)

    # Decode each APK.
    print("Decoding APKs with apktool", file=sys.stderr)
    for apk_path in apk_paths:
        apk_name = apk_path.stem
        output_dir = output_apktool_dir / f"{apk_name}"

        print(f"Decoding {apk_name}.apk", file=sys.stderr)
        decode_apk_with_apktool(apktool_jar, apk_path, output_dir)
        print(f"apktool returned a zero status code; output likely written to {DIR_NAME_OUTPUT}/{output_apktool_dir.name}/{apk_name}", file=sys.stderr)


def decode_vendor_framework_with_apktool(
    apktool_jar: Path,
    unzipped_mdt_dir: Path,
    output_framework_dir: Path,
) -> None:
    """
    Decodes the vendor framework-res.apk using apktool.

    :param apktool_jar: Path to the apktool jar file
    :param unzipped_mdt_dir: Path to the root of your unzipped image (contains the Android filesystem)
    :param output_framework_dir: Path where decoded framework resources will be written
    """
    # Clean up the output directory if it exists; let apktool create it.
    clean_dir(output_framework_dir)

    # Install the Mitsubishi framework into apktool.
    framework_res_apk = unzipped_mdt_dir / "system" / "vendor" / "framework" / "framework-res.apk"
    print("Installing Mitsubishi framework into apktool", file=sys.stderr)
    install_apktool_framework(apktool_jar, framework_res_apk)

    # Decode the framework-res.apk itself.
    print("Decoding framework-res.apk with apktool", file=sys.stderr)
    decode_apk_with_apktool(apktool_jar, framework_res_apk, output_framework_dir)
    print(f"apktool returned a zero status code; output likely written to {DIR_NAME_OUTPUT}/{DIR_NAME_APKTOOL_VENDOR_FRAMEWORK}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Process a .zip file specified by its path."
    )
    parser.add_argument(
        "zip_path", type=zip_path_type, help="Path to an existing .zip file"
    )
    parser.add_argument(
        "--steps",
        choices=["deodex-system-apps", "deodex-vendor-apps", "deodex-system-framework-jars", "deodex-vendor-framework-jars", "apktool-system-apps", "apktool-vendor-apps", "apktool-vendor-framework", "all"],
        default="all",
        help="Which processing steps to run: 'deodex-system-apps' (deodex system app .odex files), 'deodex-vendor-apps' (deodex vendor app .odex files), 'deodex-system-framework-jars' (deodex system framework .odex files), 'deodex-vendor-framework-jars' (deodex vendor framework .odex files), 'apktool-system-apps' (system app resource decoding), 'apktool-vendor-apps' (vendor app resource decoding), 'apktool-vendor-framework' (vendor framework resource decoding), or 'all' (default)",
    )
    args = parser.parse_args()

    # Get the top-level output directory and ensure it's in a clean state.
    output_dir = get_output_dir()
    reset_dir(output_dir)
    print(f"Output will be written to {output_dir}", file=sys.stderr)

    print("Checking if Java is installed. Needed to run smali, baksmali, and apktool.", file=sys.stderr)
    check_java_exists()

    # Will contain the unzipped MRC_<...>.zip .zip file.
    unzipped_zip_dir = output_dir / DIR_NAME_UNZIPPED_ZIP
    # Will contain the unzipped SwUpdate.mdt file.
    unzipped_mdt_dir = output_dir / DIR_NAME_UNZIPPED_MDT
    # Will contain .smali files from deodexing system/app/*.odex files.
    system_app_smali_dir = output_dir / DIR_NAME_SYSTEM_APP_SMALI
    # Will contain classes.dex files from reassembling system app .smali files.
    system_app_classes_dir = output_dir / DIR_NAME_SYSTEM_APP_CLASSES
    # Will contain reconstructed system/app/*.apk files with classes.dex files.
    output_system_apps_repacked_dir = output_dir / DIR_NAME_SYSTEM_APP_APKS_REPACKED
    # Will contain .smali files from deodexing system/vendor/app/*.odex files.
    vendor_app_smali_dir = output_dir / DIR_NAME_VENDOR_APP_SMALI
    # Will contain classes.dex files from reassembling .smali files.
    vendor_app_classes_dir = output_dir / DIR_NAME_VENDOR_APP_CLASSES
    # Will contain reconstructed system/vendor/app/*.apk files with classes.dex files.
    output_vendor_apps_repacked_dir = output_dir / DIR_NAME_VENDOR_APP_APKS_REPACKED
    # Will contain .smali files from deodexing system/framework/*.odex files.
    system_framework_smali_dir = output_dir / DIR_NAME_SYSTEM_FRAMEWORK_SMALI
    # Will contain classes.dex files from reassembling system framework .smali files.
    system_framework_classes_dir = output_dir / DIR_NAME_SYSTEM_FRAMEWORK_CLASSES
    # Will contain reconstructed system/framework/*.jar files with classes.dex files.
    output_system_framework_jars_repacked_dir = output_dir / DIR_NAME_SYSTEM_FRAMEWORK_JARS_REPACKED
    # Will contain .smali files from deodexing system/vendor/framework/*.odex files.
    vendor_framework_smali_dir = output_dir / DIR_NAME_VENDOR_FRAMEWORK_SMALI
    # Will contain classes.dex files from reassembling vendor framework .smali files.
    vendor_framework_classes_dir = output_dir / DIR_NAME_VENDOR_FRAMEWORK_CLASSES
    # Will contain reconstructed system/vendor/framework/*.jar files with classes.dex files.
    output_vendor_framework_jars_repacked_dir = output_dir / DIR_NAME_VENDOR_FRAMEWORK_JARS_REPACKED
    # Will contain decoded system APK resources from apktool.
    apktool_system_apps_dir = output_dir / DIR_NAME_APKTOOL_SYSTEM_APPS
    # Will contain decoded vendor APK resources from apktool.
    apktool_vendor_apps_dir = output_dir / DIR_NAME_APKTOOL_VENDOR_APPS
    # Will contain decoded vendor framework resources from apktool.
    apktool_vendor_framework_dir = output_dir / DIR_NAME_APKTOOL_VENDOR_FRAMEWORK

    # Extract contents of MRC_<...>.zip file.
    reset_dir(unzipped_zip_dir)
    print(f"Extracting .zip archive to {unzipped_zip_dir}", file=sys.stderr)
    mdt_file = unzip_outer_zip(args.zip_path, unzipped_zip_dir)

    # Extract contents of SwUpdate.mdt file.
    reset_dir(unzipped_mdt_dir)
    print(f"Extracting .mdt archive to {unzipped_mdt_dir}", file=sys.stderr)
    unzip_mdt_zip(mdt_file, unzipped_mdt_dir)

    print(f"The Android file system has been extracted to '{unzipped_mdt_dir}'.", file=sys.stderr)

    steps = args.steps

    system_apps_dir = unzipped_mdt_dir / "system" / "app"
    vendor_apps_dir = unzipped_mdt_dir / "system" / "vendor" / "app"
    system_framework_dir = unzipped_mdt_dir / "system" / "framework"
    vendor_framework_dir = unzipped_mdt_dir / "system" / "vendor" / "framework"

    if steps in ("deodex-system-apps", "all"):
        print("Verifying smali and baksmali jars exist in inputs directory.", file=sys.stderr)
        jars = get_jars()
        process_system_apps(
            unzipped_mdt_dir=unzipped_mdt_dir,
            input_apps_dir=system_apps_dir,
            jars=jars,
            output_smali_dir=system_app_smali_dir,
            output_classes_dir=system_app_classes_dir,
            output_apps_dir=output_system_apps_repacked_dir,
        )

    if steps in ("deodex-vendor-apps", "all"):
        print("Verifying smali and baksmali jars exist in inputs directory.", file=sys.stderr)
        jars = get_jars()
        process_vendor_apps(
            unzipped_mdt_dir=unzipped_mdt_dir,
            input_apps_dir=vendor_apps_dir,
            jars=jars,
            output_smali_dir=vendor_app_smali_dir,
            output_classes_dir=vendor_app_classes_dir,
            output_apps_dir=output_vendor_apps_repacked_dir,
        )

    if steps in ("deodex-system-framework-jars", "all"):
        print("Verifying smali and baksmali jars exist in inputs directory.", file=sys.stderr)
        jars = get_jars()
        process_system_framework_libs(
            unzipped_mdt_dir=unzipped_mdt_dir,
            input_framework_dir=system_framework_dir,
            jars=jars,
            output_smali_dir=system_framework_smali_dir,
            output_classes_dir=system_framework_classes_dir,
            output_jars_dir=output_system_framework_jars_repacked_dir,
        )

    if steps in ("deodex-vendor-framework-jars", "all"):
        print("Verifying smali and baksmali jars exist in inputs directory.", file=sys.stderr)
        jars = get_jars()
        process_vendor_framework_libs(
            unzipped_mdt_dir=unzipped_mdt_dir,
            input_framework_dir=vendor_framework_dir,
            jars=jars,
            output_smali_dir=vendor_framework_smali_dir,
            output_classes_dir=vendor_framework_classes_dir,
            output_jars_dir=output_vendor_framework_jars_repacked_dir,
        )

    if steps in ("apktool-system-apps", "all"):
        apktool_jar = get_apktool_jar()
        apk_paths = get_system_app_apk_paths(system_apps_dir)
        process_apps_with_apktool(
            apktool_jar=apktool_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            apk_paths=apk_paths,
            output_apktool_dir=apktool_system_apps_dir,
        )

    if steps in ("apktool-vendor-apps", "all"):
        apktool_jar = get_apktool_jar()
        apk_paths = get_vendor_app_apk_paths(vendor_apps_dir)
        process_apps_with_apktool(
            apktool_jar=apktool_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            apk_paths=apk_paths,
            output_apktool_dir=apktool_vendor_apps_dir,
        )

    if steps in ("apktool-vendor-framework", "all"):
        apktool_jar = get_apktool_jar()
        decode_vendor_framework_with_apktool(
            apktool_jar=apktool_jar,
            unzipped_mdt_dir=unzipped_mdt_dir,
            output_framework_dir=apktool_vendor_framework_dir,
        )


if __name__ == "__main__":
    main()
