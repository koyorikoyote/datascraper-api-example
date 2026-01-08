"""Application logging utilities.

Logs are currently emitted to stdout using Python's ``logging`` module.
In the future these logs should be forwarded to AWS CloudWatch.
"""

import logging
import os
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Default formatter now includes module & line number so the origin of each
# message is clear even if every file logs through the root logger.
# ---------------------------------------------------------------------------
DEFAULT_FORMAT = "%(asctime)s - %(module)s:%(lineno)d - %(levelname)s - %(message)s"


def setup_logging(
    level: int = logging.INFO,
    stream: Optional[object] = None,
    fmt: str = DEFAULT_FORMAT,
) -> None:
    """Configure the root logger exactly once; safe to call repeatedly.

    * If the ``LOG_LEVEL`` environment variable is set, it overrides *level*.
    * The formatter now shows ``module`` and ``lineno`` so you can call the
      top-level helpers (``logging.info`` etc.) without defining a per-module
      logger object.
    """
    # Environment override ---------------------------------------------------
    env_level = os.getenv("LOG_LEVEL")
    if env_level:
        level = getattr(logging, env_level.upper(), level)

    if stream is None:
        stream = sys.stdout

    root = logging.getLogger()

    # Configure handlers only the first time ---------------------------------
    if not root.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)

    # Always (re)set the level so later calls can raise/lower it -------------
    root.setLevel(level)

    # Ensure Uvicorn logs go through the same handlers -----------------------
    for pkg in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(pkg).handlers = root.handlers
        logging.getLogger(pkg).setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (kept for backward compatibility).

    You *can* still call this, but after calling ``setup_logging`` once at
    startup you may simply:

        import logging
        logging.info("...")

    which will use the root logger configured above.
    """
    setup_logging()
    return logging.getLogger(name)
