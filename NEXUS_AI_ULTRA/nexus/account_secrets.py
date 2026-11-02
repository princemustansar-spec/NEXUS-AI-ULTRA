"""Windows user-bound encryption for OAuth credentials; never plaintext fallback."""
import ctypes
from ctypes import wintypes
import os


def transform(data, decrypt=False):
    if os.name!='nt':raise RuntimeError('Windows secure credential storage is required.')
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]
    raw=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(raw,ctypes.POINTER(ctypes.c_byte)));target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        fn=crypt.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        args=(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        fn=crypt.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        args=(ctypes.byref(source),'NEXUS ChatGPT connection',None,None,None,1,ctypes.byref(target))
    fn.restype=wintypes.BOOL
    if not fn(*args):raise RuntimeError('Windows could not unlock or protect the ChatGPT connection.')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)


def protect(data):return transform(data)
def unprotect(data):return transform(data,True)
