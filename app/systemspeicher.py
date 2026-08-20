"""How much memory this machine has, in round gigabytes.

On Apple Silicon the graphics card and the processor share one pool, so the
machine total IS the honest ceiling for a model plan — there is no separate
VRAM number that would say more. Reported once, as a fact about the machine,
next to the estimate of what a planned server start will take.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys


def gesamt_gb() -> float | None:
    """The machine's physical memory in GiB, or None where it cannot be read.

    Binary gigabytes on purpose: the number on the spec sheet of every
    machine is counted that way, and a readout that says 68.7 on a
    "64 GB" machine reads as a bug, not as precision."""
    try:
        if sys.platform == "win32":
            import ctypes

            class _Status(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            lage = _Status()
            lage.dwLength = ctypes.sizeof(_Status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(lage)):
                return None
            rohe = int(lage.ullTotalPhys)
        else:
            rohe = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, AttributeError):
        return None
    return round(rohe / 1024**3, 1)


def belegt_gb() -> float | None:
    """How much of that pool is in use right now, in GiB, or None.

    On macOS the sum of active, wired and compressor pages from ``vm_stat``
    — the same figure Activity Monitor calls "Memory Used". Free plus
    inactive pages are NOT counted: the file cache empties itself under
    pressure, and a readout that calls a warm cache "full" would cry wolf
    on every healthy machine. On Windows the total minus what the kernel
    reports as available, which follows the same idea.
    """
    try:
        if sys.platform == "win32":
            import ctypes

            class _Status(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            lage = _Status()
            lage.dwLength = ctypes.sizeof(_Status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(lage)):
                return None
            rohe = int(lage.ullTotalPhys) - int(lage.ullAvailPhys)
        elif sys.platform == "darwin":
            lauf = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5
            )
            if lauf.returncode != 0:
                return None
            seiten = 0
            for zeile in lauf.stdout.splitlines():
                if re.match(
                    r"Pages (active|wired down|occupied by compressor):", zeile
                ):
                    zahl = re.search(r"(\d+)\.?$", zeile.strip())
                    if zahl:
                        seiten += int(zahl.group(1))
            if not seiten:
                return None
            rohe = seiten * os.sysconf("SC_PAGE_SIZE")
        else:
            return None
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return None
    return round(rohe / 1024**3, 1)
