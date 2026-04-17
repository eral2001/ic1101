import asyncio
import logging
import re
import subprocess
from typing import Protocol

logger = logging.getLogger(__name__)


class LineWriter(Protocol):
    def write(self, s: str, /) -> int: ...


async def _copy_lines(reader: asyncio.StreamReader, writer: LineWriter) -> None:
    """Read lines from `reader` and write them to `writer` until EOF.

    Bytes are decoded as UTF-8 with `errors="replace"` so the copy
    never crashes on malformed output from a misbehaving child process.
    """
    while True:
        line = await reader.readline()
        if not line:
            break
        writer.write(line.decode("utf-8", errors="replace"))


async def run(cmd: list[str], stdout: LineWriter, stderr: LineWriter) -> None:
    """Run a subprocess, streaming its output to caller-supplied writers.

    Because the output bridging happens in this process rather than at
    the kernel level, `stdout` and `stderr` only need to implement
    `.write(str)`; they don't need a real OS file descriptor, so
    in-memory streams like `io.StringIO` and adapter classes that wrap
    a logger are fully supported.

    Args:
        cmd: Argv list for the child process.
        stdout: Writer to receive the child's stdout, line by line.
        stderr: Writer to receive the child's stderr, line by line.

    Raises:
        subprocess.CalledProcessError: If the child exits non-zero.
    """
    logger.info("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None and proc.stderr is not None
    try:
        await asyncio.gather(
            _copy_lines(proc.stdout, stdout),
            _copy_lines(proc.stderr, stderr),
        )
    except BaseException:
        proc.kill()
        await proc.wait()
        raise
    rc = await proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


class _FilteredWriter:
    def __init__(self, downstream: LineWriter, drop_patterns: list[re.Pattern[str]]) -> None:
        self._downstream = downstream
        self._drop_patterns = drop_patterns

    def write(self, line: str, /) -> int:
        if any(p.match(line) for p in self._drop_patterns):
            # Honor the write contract by reporting the line as
            # "written" even though we silently dropped it.
            return len(line)
        return self._downstream.write(line)


def filter_lines(downstream: LineWriter, drop_patterns: list[re.Pattern[str]]) -> LineWriter:
    return _FilteredWriter(downstream, drop_patterns)
