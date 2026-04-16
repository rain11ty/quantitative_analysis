# -*- coding: utf-8 -*-
"""Runtime UTF-8 helpers for Windows-friendly console and web output."""

from __future__ import annotations

import os
import sys
from typing import TextIO


UTF8 = 'utf-8'


def configure_utf8_environment() -> None:
    """Force the current Python process to prefer UTF-8 IO behavior."""
    os.environ.setdefault('PYTHONUTF8', '1')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            try:
                reconfigure(encoding=UTF8, errors='replace')
            except Exception:
                continue


def _fallback_text(value: str) -> str:
    return value.encode('ascii', errors='replace').decode('ascii')


def safe_console_write(message: str, stream: TextIO | None = None) -> None:
    """Write logs/messages to console without raising encoding errors."""
    configure_utf8_environment()
    target = stream or sys.stdout
    text = str(message)

    try:
        target.write(text)
    except UnicodeEncodeError:
        buffer = getattr(target, 'buffer', None)
        if buffer is not None:
            buffer.write(text.encode(UTF8, errors='replace'))
        else:
            target.write(_fallback_text(text))
    finally:
        try:
            target.flush()
        except Exception:
            pass
