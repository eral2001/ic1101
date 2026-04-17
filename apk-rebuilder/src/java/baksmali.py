from pathlib import Path

from java._jar_cli import JarCli


class Baksmali(JarCli):
    """Python wrapper around the baksmali jar's command-line interface.

    Each public method maps one-to-one to a baksmali subcommand.
    """

    async def deodex(
        self,
        *,
        input_odex: Path,
        output_dir: Path,
        api_level: int,
        bootclasspath: list[Path],
        dep_dirs: list[Path] | None = None,
    ) -> None:
        """Run `baksmali deodex` against a single .odex file.

        Args:
            input_odex: The .odex file to deodex.
            output_dir: Directory where the resulting .smali files will
                be written.
            api_level: Android API level the .odex was compiled for.
            bootclasspath: Jars that form the bootclasspath baksmali
                will use to resolve class references. Joined with `:`
                and passed as `--bootclasspath`.
            dep_dirs: Additional directories baksmali will load class
                definitions from. Each is passed as a separate
                `--classpath-dir` flag. None means no `--classpath-dir`
                flags are passed.
        """
        args = [
            "--api",
            str(api_level),
            "--bootclasspath",
            ":".join(str(j) for j in bootclasspath),
        ]
        for d in dep_dirs or []:
            args += ["--classpath-dir", str(d)]
        args += ["--output", str(output_dir), str(input_odex)]
        await self._invoke("deodex", args)
