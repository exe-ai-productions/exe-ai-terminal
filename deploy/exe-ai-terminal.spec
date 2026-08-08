# PyInstaller build description — one file, one double click.
#
# Run from the project root:
#
#     .venv/bin/pyinstaller deploy/exe-ai-terminal.spec
#
# What ships is everything the program only reads: the built interface, the
# translations, the shipped skills and tool servers, the example
# configuration. What the user owns — database, own settings, models, own
# skills — is deliberately NOT in here; it is created next to their other
# application data on first start (app/paketierung.py).
#
# `static/app` has to be built beforehand (`cd frontend && npm run build`),
# otherwise the program ships with an interface older than itself. There is
# no check for that here, because a build description that quietly fixes
# things hides exactly the mistake it should be showing.

import re
import sys
from pathlib import Path

WURZEL = Path(SPECPATH).parent

# The one version, read where it lives — a second number here would drift.
VERSION = re.search(
    r'__version__ = "(.+)"', (WURZEL / "app" / "__init__.py").read_text()
).group(1)

mitgeliefert = [
    (str(WURZEL / "static"), "static"),
    (str(WURZEL / "app" / "locales"), "app/locales"),
    (str(WURZEL / "app" / "db" / "schema.sql"), "app/db"),
    (str(WURZEL / "skills"), "skills"),
    (str(WURZEL / "mcp"), "mcp"),
    (str(WURZEL / "prompts"), "prompts"),
    (str(WURZEL / "config.example.yaml"), "."),
    (str(WURZEL / "mcp_servers.json"), "."),
]

# Found by name at runtime rather than imported, so the collector cannot see
# them: the tool servers behind the --mcp switch, and uvicorn's own workers.
versteckt = [
    "ddgs_server",
    "searxng_server",
    "mcp_schleife",
    "webseite_lesen",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "app.main",
]

analyse = Analysis(
    [str(WURZEL / "start.py")],
    pathex=[str(WURZEL), str(WURZEL / "mcp")],
    binaries=[],
    datas=mitgeliefert,
    hiddenimports=versteckt,
    hookspath=[],
    runtime_hooks=[],
    # Test machinery has no business in a shipped program.
    excludes=["pytest", "_pytest", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(analyse.pure)

exe = EXE(
    pyz,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="Exe AI Terminal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # The program serves the browser; its own window would be a second one.
    # On Windows that means no console — a black box next to the app reads
    # as broken, and a failed start explains itself in the log files. On
    # macOS and Linux the bare binary keeps talking to whoever starts it
    # from a terminal; the double-click path goes through the app bundle
    # below, which opens no terminal to begin with.
    console=(sys.platform != "win32"),
    icon=str(WURZEL / "deploy" / "icon.ico") if sys.platform == "win32" else None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS gets a real application folder around the same file: an icon, a
# name, and a double click that opens no terminal window. The service has
# no window of its own, so the bundle stays out of the Dock — the browser
# is the window, and a dockless background program cannot sit there
# bouncing forever.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Exe AI Terminal.app",
        icon=str(WURZEL / "deploy" / "icon.icns"),
        bundle_identifier="net.exe-hq.exe-ai-terminal",
        version=VERSION,
        info_plist={
            "CFBundleName": "Exe AI Terminal",
            "CFBundleDisplayName": "Exe AI Terminal",
            "CFBundleShortVersionString": VERSION,
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
        },
    )
