"""Scope-checked cleanup; Windows uses the Recycle Bin without a delete fallback."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


def recycle_windows(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

        @classmethod
        def parse(cls, value: str) -> "GUID":
            return cls.from_buffer_copy(uuid.UUID(value).bytes_le)

    def check(result: int) -> None:
        if result < 0:
            raise OSError(f"Recycle Bin operation failed (HRESULT 0x{result & 0xffffffff:08x}); no permanent-delete fallback")

    def call(pointer: ctypes.c_void_p, slot: int, types: tuple, *args: object) -> int:
        table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(table[slot])
        return function(pointer, *args)

    ole = ctypes.OleDLL("ole32")
    shell = ctypes.OleDLL("shell32")
    ole.CoInitializeEx.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoCreateInstance.argtypes = (ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
    ole.CoCreateInstance.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = ()
    ole.CoUninitialize.restype = None
    shell.SHCreateItemFromParsingName.argtypes = (wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
    shell.SHCreateItemFromParsingName.restype = ctypes.c_long
    initialized = False
    operation, item = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        check(ole.CoInitializeEx(None, 2))
        initialized = True
        clsid = GUID.parse("3ad05575-8857-4850-9277-11b85bdb8e09")
        interface = GUID.parse("947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8")
        check(ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(interface), ctypes.byref(operation)))
        # RECYCLEONDELETE forces recycling; EARLYFAILURE prevents continuing after an error.
        flags = 0x00080000 | 0x00100000 | 0x0400 | 0x0010 | 0x0004
        check(call(operation, 5, (wintypes.DWORD,), flags))
        item_interface = GUID.parse("43826d1e-e718-42ee-bc55-a1e261c37bfe")
        check(shell.SHCreateItemFromParsingName(str(path), None, ctypes.byref(item_interface), ctypes.byref(item)))
        check(call(operation, 18, (ctypes.c_void_p, ctypes.c_void_p), item, None))
        check(call(operation, 21, ()))
        aborted = wintypes.BOOL()
        check(call(operation, 22, (ctypes.POINTER(wintypes.BOOL),), ctypes.byref(aborted)))
        if aborted.value or os.path.lexists(path):
            raise OSError(f"Recycle Bin cleanup did not complete; content retained: {path}")
    finally:
        if item.value:
            call(item, 2, ())
        if operation.value:
            call(operation, 2, ())
        if initialized:
            ole.CoUninitialize()


def discard_path(path: Path, scope: Path) -> None:
    root = scope.expanduser().resolve()
    candidate = path.expanduser().absolute()
    candidate = candidate.parent.resolve() / candidate.name
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError(f"Cleanup path must stay inside its authorized scope: {candidate}")
    if not os.path.lexists(candidate):
        return
    if os.name == "nt":
        recycle_windows(candidate)
    elif candidate.is_symlink() or candidate.is_file():
        candidate.unlink()
    else:
        shutil.rmtree(candidate)
