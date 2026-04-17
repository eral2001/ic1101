from pathlib import Path

from java.subprocess_invoker import SubprocessInvoker


class JarCli:
    """Base class for wrappers around executable jar command-line tools.

    Subclasses add one method per subcommand. Each method builds the argv
    list specific to that subcommand and delegates to `_invoke`.
    Subclasses should never spawn processes directly.
    """

    def __init__(self, jar: Path, invoker: SubprocessInvoker) -> None:
        self._jar = jar
        self._invoker = invoker

    async def _invoke(self, subcommand: str, args: list[str]) -> None:
        await self._invoker(["java", "-jar", str(self._jar), subcommand, *args])
