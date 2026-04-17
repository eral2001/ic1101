import logging
import shutil
from pathlib import Path

from java.apktool import Apktool

logger = logging.getLogger(__name__)


async def decode_apps(
    apktool: Apktool,
    framework_res_apk: Path,
    framework_tag: str,
    apk_paths: list[Path],
    output_dir: Path,
) -> None:
    """Decode a batch of APKs' resources with apktool.

    Installs `framework_res_apk` into apktool's framework cache under
    `framework_tag`, then runs `apktool d` against each APK in
    `apk_paths`, writing decoded resources under
    `output_dir/<apk_stem>/`.

    Args:
        apktool: An Apktool instance whose invoker will receive the
            subprocess invocations.
        framework_res_apk: framework-res.apk to install into apktool's
            framework cache.
        framework_tag: apktool framework cache tag; the `-t` value
            passed to both `apktool if` and `apktool d`.
        apk_paths: APKs to decode.
        output_dir: Directory that will be wiped and recreated to
            contain the per-APK decoded subdirectories.

    Raises:
        FileNotFoundError: If `framework_res_apk` does not exist.
        subprocess.CalledProcessError: If any apktool invocation
            returns a non-zero exit code.
    """
    if not framework_res_apk.is_file():
        raise FileNotFoundError(f"Framework APK not found at {framework_res_apk}")

    # Wipe and recreate the output directory.
    # apktool d will create per-APK subdirectories below it.
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    logger.info("Installing framework into apktool (tag=%s)", framework_tag)
    await apktool.install_framework(framework_apk=framework_res_apk, framework_tag=framework_tag)

    logger.info("Decoding APKs with apktool")
    for apk_path in apk_paths:
        apk_name = apk_path.stem
        apk_output_dir = output_dir / apk_name
        logger.info("Decoding %s.apk", apk_name)
        await apktool.decode(
            input_apk=apk_path,
            output_dir=apk_output_dir,
            framework_tag=framework_tag,
        )
        logger.info(
            "apktool returned a zero status code; output likely written to %s",
            apk_output_dir,
        )


async def decode_framework(
    apktool: Apktool,
    framework_res_apk: Path,
    framework_tag: str,
    output_dir: Path,
) -> None:
    """Decode a framework-res.apk's own resources with apktool.

    Installs `framework_res_apk` into apktool's framework cache under
    `framework_tag`, then runs `apktool d` against the same
    framework-res.apk to extract its resources directly into
    `output_dir`.

    Args:
        apktool: An Apktool instance whose invoker will receive the
            subprocess invocations.
        framework_res_apk: framework-res.apk to both install into
            apktool's cache and decode.
        framework_tag: apktool framework cache tag
        output_dir: Directory that will be wiped so apktool can
            recreate it from scratch.

    Raises:
        FileNotFoundError: If `framework_res_apk` does not exist.
        subprocess.CalledProcessError: If any apktool invocation
            returns a non-zero exit code.
    """
    if not framework_res_apk.is_file():
        raise FileNotFoundError(f"Framework APK not found at {framework_res_apk}")

    # Wipe the output directory if it exists; apktool d will recreate
    # it. Unlike decode_apps we don't mkdir afterward; apktool d
    # creates its own output directory and fails if one already exists.
    if output_dir.exists():
        shutil.rmtree(output_dir)

    logger.info("Installing framework into apktool (tag=%s)", framework_tag)
    await apktool.install_framework(framework_apk=framework_res_apk, framework_tag=framework_tag)

    logger.info("Decoding framework-res.apk with apktool")
    await apktool.decode(
        input_apk=framework_res_apk,
        output_dir=output_dir,
        framework_tag=framework_tag,
    )
    logger.info(
        "apktool returned a zero status code; output likely written to %s",
        output_dir,
    )
