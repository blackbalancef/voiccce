"""Detect whether any audio input device (microphone) is currently in use.

Used to optionally pause spoken notifications while the mic is live, so TTS does
not leak into a recording or call. Reads CoreAudio's
``kAudioDevicePropertyDeviceIsRunningSomewhere`` for every input-capable device —
the same underlying state that drives the orange mic indicator.

Pure stdlib (ctypes), matching the project's zero-dependency runtime. Reading a
device's run-state never opens an IO proc, so it needs no microphone (TCC)
permission and never triggers a prompt. Best-effort and fail-open: any error
(non-macOS, missing framework, future API change) returns False, so a detection
glitch can never silence notifications.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import sys


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode("ascii"), "big")


# CoreAudio HAL selectors / scopes (AudioHardware.h).
_SYSTEM_OBJECT = 1
_ELEMENT_MAIN = 0
_SCOPE_GLOBAL = _fourcc("glob")
_SCOPE_INPUT = _fourcc("inpt")
_PROP_DEVICES = _fourcc("dev#")  # kAudioHardwarePropertyDevices
_PROP_STREAMS = _fourcc("stm#")  # kAudioDevicePropertyStreams
_PROP_IS_RUNNING_SOMEWHERE = _fourcc("gone")  # kAudioDevicePropertyDeviceIsRunningSomewhere


class _PropertyAddress(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


_core_audio: ctypes.CDLL | None = None


def _load() -> ctypes.CDLL | None:
    """Load and configure CoreAudio once; return None off macOS or on failure."""
    global _core_audio
    if _core_audio is not None:
        return _core_audio
    if sys.platform != "darwin":
        return None
    path = ctypes.util.find_library("CoreAudio")
    if not path:
        return None
    lib = ctypes.CDLL(path)
    lib.AudioObjectGetPropertyData.restype = ctypes.c_int32
    lib.AudioObjectGetPropertyData.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(_PropertyAddress),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    lib.AudioObjectGetPropertyDataSize.restype = ctypes.c_int32
    lib.AudioObjectGetPropertyDataSize.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(_PropertyAddress),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    _core_audio = lib
    return lib


def _address(selector: int, scope: int) -> _PropertyAddress:
    return _PropertyAddress(selector, scope, _ELEMENT_MAIN)


def _has_input_streams(lib: ctypes.CDLL, device: int) -> bool:
    addr = _address(_PROP_STREAMS, _SCOPE_INPUT)
    size = ctypes.c_uint32(0)
    if lib.AudioObjectGetPropertyDataSize(device, ctypes.byref(addr), 0, None, ctypes.byref(size)) != 0:
        return False
    return size.value > 0


def _is_running_somewhere(lib: ctypes.CDLL, device: int) -> bool:
    addr = _address(_PROP_IS_RUNNING_SOMEWHERE, _SCOPE_GLOBAL)
    out = ctypes.c_uint32(0)
    size = ctypes.c_uint32(ctypes.sizeof(out))
    if lib.AudioObjectGetPropertyData(device, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(out)) != 0:
        return False
    return out.value != 0


def _input_device_ids(lib: ctypes.CDLL) -> list[int]:
    addr = _address(_PROP_DEVICES, _SCOPE_GLOBAL)
    size = ctypes.c_uint32(0)
    if lib.AudioObjectGetPropertyDataSize(_SYSTEM_OBJECT, ctypes.byref(addr), 0, None, ctypes.byref(size)) != 0:
        return []
    count = size.value // ctypes.sizeof(ctypes.c_uint32)
    if count == 0:
        return []
    devices = (ctypes.c_uint32 * count)()
    if (
        lib.AudioObjectGetPropertyData(
            _SYSTEM_OBJECT, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.cast(devices, ctypes.c_void_p)
        )
        != 0
    ):
        return []
    return [device for device in devices if _has_input_streams(lib, device)]


def microphone_in_use() -> bool:
    """Return True if any input-capable audio device is currently running.

    Checks every input device (not just the default), so a recording from a
    non-default mic is caught too. Returns False on any platform/API error.
    """
    try:
        lib = _load()
        if lib is None:
            return False
        return any(_is_running_somewhere(lib, device) for device in _input_device_ids(lib))
    except Exception:
        return False
