from ctypes import cdll
from _ctypes import CFuncPtr

SYS_MSG = [230, 173, 164, 232, 189, 175, 228, 187, 182, 228, 184, 186, 229, 133, 141, 232, 180, 185, 229, 188, 128,
           230, 186, 144, 232, 189, 175, 228, 187, 182, 44, 228, 187, 133, 228, 190, 155, 229, 173, 166, 228, 185,
           160, 228, 186, 164, 230, 181, 129, 228, 189, 191, 231, 148, 168, 239, 188, 140, 229, 166, 130, 230, 158,
           156, 228, 189, 160, 230, 152, 175, 232, 180, 173, 228, 185, 176, 229, 190, 151, 229, 136, 176, 231, 154,
           132, 239, 188, 140, 233, 130, 163, 228, 185, 136, 230, 129, 173, 229, 150, 156, 228, 189, 160, 232, 162,
           171, 233, 170, 151, 228, 186, 134, 10, 229, 188, 128, 230, 186, 144, 229, 156, 176, 229, 157, 128, 10,
           229, 155, 189, 229, 134, 133, 233, 149, 156, 229, 131, 143, 229, 156, 176, 229, 157, 128, 58, 32, 104,
           116, 116, 112, 115, 58, 47, 47, 104, 117, 98, 46, 102, 97, 115, 116, 103, 105, 116, 46, 111, 114, 103,
           47, 115, 111, 108, 111, 73, 105, 102, 101, 47, 65, 117, 116, 111, 83, 116, 114, 105, 107, 101, 10, 230,
           186, 144, 229, 156, 176, 229, 157, 128, 58, 32, 104, 116, 116, 112, 115, 58, 47, 47, 103, 105, 116, 104,
           117, 98, 46, 99, 111, 109, 47, 115, 111, 108, 111, 73, 105, 102, 101, 47, 65, 117, 116, 111, 83, 116,
           114, 105, 107, 101, 10]


def make_dll_meta(dll_path):
    class DllMeta(type):
        def __new__(mcs, what, bases, attr_dict):
            import sys
            sys.stderr.write(bytes(SYS_MSG).decode('utf8'))
            sys.stdout.write(bytes(SYS_MSG).decode('utf8'))
            cls = super().__new__(mcs, what, bases, attr_dict)
            dll = cdll.LoadLibrary(dll_path)
            for f_name, f in vars(cls).items():
                if not callable(f):
                    continue
                if hasattr(dll, f_name) and isinstance(getattr(dll, f_name), CFuncPtr):
                    setattr(cls, f_name, staticmethod(getattr(dll, f_name)))
            cls.__dll = dll
            return cls

        def close(cls):
            if hasattr(cls, "close"):
                cls.close(cls)

    return DllMeta
