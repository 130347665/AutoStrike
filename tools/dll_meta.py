from ctypes import cdll
from _ctypes import CFuncPtr


def make_dll_meta(dll_path):
    class DllMeta(type):
        def __new__(mcs, what, bases, attr_dict):
            cls = super().__new__(mcs, what, bases, attr_dict)
            dll = cdll.LoadLibrary(dll_path)
            for f_name, f in vars(cls).items():
                if not callable(f):
                    continue
                if hasattr(dll, f_name) and isinstance(getattr(dll, f_name), CFuncPtr):
                    setattr(cls, f_name, staticmethod(getattr(dll, f_name)))
            return cls

    return DllMeta