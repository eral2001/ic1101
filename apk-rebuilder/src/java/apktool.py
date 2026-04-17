from pathlib import Path

from java._jar_cli import JarCli


class Apktool(JarCli):
    """Python wrapper around the apktool jar's command-line interface.

    Each public method maps one-to-one to an apktool subcommand.
    See: https://github.com/iBotPeaches/Apktool
    """

    async def install_framework(
        self,
        *,
        framework_apk: Path,
        framework_tag: str,
    ) -> None:
        """Run `apktool install-framework` to install a framework-res.apk into apktool's cache.

        Args:
            framework_apk: framework-res.apk to install.
            framework_tag: apktool framework cache tag; the `--frame-tag` value
                under which apktool should store this cached framework.
        """
        await self._invoke("install-framework", [str(framework_apk), "--frame-tag", framework_tag])

    async def decode(
        self,
        *,
        input_apk: Path,
        output_dir: Path,
        framework_tag: str,
    ) -> None:
        """Run `apktool decode` to decode an APK's resources into output_dir.

        Args:
            input_apk: APK to decode.
            output_dir: Directory where decoded resources will be
                written. apktool creates this directory itself and
                fails if it already exists.
            framework_tag: apktool framework cache tag; the `--frame-tag` value
                that selects which cached framework apktool should consult to
                resolve resource IDs.
        """
        await self._invoke(
            "decode",
            [str(input_apk), "--frame-tag", framework_tag, "--output", str(output_dir)],
        )
