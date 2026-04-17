import logging
import sys


class _ColoredFormatter(logging.Formatter):
    """Formatter that wraps the levelname in an ANSI color when stderr is a TTY."""

    _COLORS: dict[int, str] = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    _RESET: str = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        if sys.stderr.isatty():
            color = self._COLORS.get(record.levelno, "")
            if color:
                record.levelname = f"{color}{record.levelname}{self._RESET}"
        return super().format(record)


def configure_logging() -> None:
    """Configure the root logger to emit colorized INFO-level logs to stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_ColoredFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
