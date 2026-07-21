# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the frozen MCP server (Windows/macOS).

onedir (NOT onefile): a ~150MB onefile would self-extract on every server
spawn and trips AV heuristics more often. Console mode is REQUIRED — the
MCP server speaks JSON-RPC over stdin/stdout.

Bundles: spaCy + en_core_web_sm (NER on by default since the random-names
requirement), Presidio's dynamically-loaded recognizers and conf files,
and the generic sample deny-lists (NO real team names ship in the package).
"""
import os

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

datas = []
binaries = []
hiddenimports = []

# spaCy stack + the bundled NER model: heavy dynamic imports and data files
for pkg in [
    "spacy",
    "thinc",
    "blis",
    "preshed",
    "cymem",
    "murmurhash",
    "srsly",
    "catalogue",
    "confection",
    "wasabi",
    "en_core_web_sm",
    "tkinterdnd2",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# spacy validates model compatibility via importlib.metadata
datas += copy_metadata("spacy") + copy_metadata("en_core_web_sm")

# presidio loads recognizers dynamically and reads yaml conf from package data
datas += collect_data_files("presidio_analyzer")
datas += collect_data_files("presidio_anonymizer")
hiddenimports += collect_submodules("presidio_analyzer")
hiddenimports += collect_submodules("presidio_anonymizer")

# bundled generic sample deny-lists (loader resolves them relative to the
# maskingtool package dir inside the bundle)
datas += [
    (
        os.path.join(SPECPATH, "..", "..", "src", "maskingtool", "resources"),
        "maskingtool/resources",
    )
]

a = Analysis(
    [os.path.join(SPECPATH, "..", "..", "src", "maskingtool", "mcp_server", "server.py")],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "IPython", "jupyter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="maskingtool-server",
    debug=False,
    strip=False,
    upx=False,  # UPX-packed exes trip AV heuristics
    console=True,  # stdio transport
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="maskingtool-server",
)
