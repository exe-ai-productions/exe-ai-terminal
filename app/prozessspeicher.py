"""How much memory one running process holds right now, in GiB.

The resident set is the honest live number the operating system will give
without a profiler: what the process actually has in physical memory at
this moment. On machines with unified memory that is also where the model
weights and the growing context sit, so the readout moves while a server
works — which is exactly what it is for.
"""

from __future__ import annotations

import subprocess
import sys


def rss_gb(pid: int) -> float | None:
    """Resident memory of the process in GiB, or None when it cannot be read."""
    try:
        if sys.platform == "win32":
            import ctypes

            class _Zaehler(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            griff = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)
            )
            if not griff:
                return None
            try:
                zaehler = _Zaehler()
                zaehler.cb = ctypes.sizeof(_Zaehler)
                ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                    griff, ctypes.byref(zaehler), zaehler.cb
                )
                if not ok:
                    return None
                rohe = int(zaehler.WorkingSetSize)
            finally:
                ctypes.windll.kernel32.CloseHandle(griff)
        else:
            # ps reports resident kilobytes on macOS and Linux alike — the
            # one spelling both systems agree on without extra packages.
            aus = subprocess.run(
                ["ps", "-o", "rss=", "-p", str(int(pid))],
                capture_output=True,
                text=True,
                timeout=5,
            )
            zeile = aus.stdout.strip()
            if aus.returncode != 0 or not zeile:
                return None
            rohe = int(zeile) * 1024
    except (OSError, ValueError, subprocess.SubprocessError, AttributeError):
        return None
    return round(rohe / 1024**3, 1)
