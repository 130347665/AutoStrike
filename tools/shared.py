from typing import Any
import json
import numpy as np
from ctypes import c_uint8, sizeof, POINTER, cast, WinError
from typing import Union, List
import os
import secrets
from .filelock import FileLock
from multiprocessing.shared_memory import SharedMemory

base_dir = os.path.abspath(os.path.dirname(__file__))
_SHM_SAFE_NAME_LENGTH = 14
_SHM_NAME_PREFIX = 'wnsm_'


def make_filename():
    "Create a random filename for the shared memory object."
    # number of random bytes to use for name
    nbytes = (_SHM_SAFE_NAME_LENGTH - len(_SHM_NAME_PREFIX)) // 2
    assert nbytes >= 2, '_SHM_NAME_PREFIX too long'
    name = _SHM_NAME_PREFIX + secrets.token_hex(nbytes)
    assert len(name) <= _SHM_SAFE_NAME_LENGTH
    return name


def _make_filename():
    "Create a random filename for the shared memory object."
    # number of random bytes to use for name
    nbytes = (_SHM_SAFE_NAME_LENGTH - len(_SHM_NAME_PREFIX)) // 2
    assert nbytes >= 2, '_SHM_NAME_PREFIX too long'
    name = _SHM_NAME_PREFIX + secrets.token_hex(nbytes)
    assert len(name) <= _SHM_SAFE_NAME_LENGTH
    return name


#
# def release_last_sm(cache_names_file):
#     print("release_last_sm .....")
#     if os.path.exists(cache_names_file):
#         for name, size, shm_id in json.loads(open(cache_names_file, 'rb').read()):
#             try:
#                 sm = SharedMemory(name, False, size)
#                 sm.close()
#                 sm.unlink()
#             except Exception as e:
#                 print(e)
#         os.remove(cache_names_file)


class SharedMemoryRecorder:
    cache_names_file = f"{base_dir}/.sm_names"
    lock = FileLock(f"{base_dir}/.lock")

    @classmethod
    def load_cache(cls):
        if os.path.exists(cls.cache_names_file):
            return json.loads(open(cls.cache_names_file, 'rb').read())
        return []

    @classmethod
    def release_last_sm(cls):
        print("release_last_sm .....")
        with cls.lock:
            if os.path.exists(cls.cache_names_file):
                for name, size, shm_id in cls.load_cache():
                    try:
                        sm = SharedMemory(name, False, size)
                        sm.close()
                        sm.unlink()
                    except Exception as e:
                        print(str(e).split()[-1], end=";")
                print()
                os.remove(cls.cache_names_file)

    @classmethod
    def save_sm_name(cls, name, size, shm_id=None):
        with cls.lock:
            data = cls.load_cache()
            data.append([name, size, shm_id])
            open(cls.cache_names_file, 'wb').write(json.dumps(data).encode("utf8"))


def release_last_shm():
    return SharedMemoryRecorder.release_last_sm()


class Array(np.ndarray, SharedMemoryRecorder):

    def __new__(cls, shape, dtype: Union[str, np.dtype, np.object] = None, name=None, create=True, offset=0,
                strides=None, order=None):
        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)
        size = int(np.prod(shape) * dtype.itemsize)
        buf = SharedMemory(name, create=create, size=size)
        obj = super().__new__(cls, shape, dtype, buf.buf, offset, strides, order)
        obj.buf = buf
        cls.save_sm_name(buf.name, buf.size)
        return obj

    def close(self):
        if hasattr(self, "buf"):
            self.buf.close()
            self.buf.unlink()

    def __reduce__(self):
        return Array, (self.shape, self.dtype, self.buf.name, False)

    def __del__(self):
        self.close()


class Value:
    def __init__(self, c_type, value=0, name=None, create=None):
        self.data = Array(1, c_type, name, create)
        self.data[0] = value

    @property
    def value(self):
        return self.data[0]


def zeros_like(a: np.ndarray, dtype=None, name=None, create=True):
    dtype = dtype or a.dtype
    shape = a.shape
    return Array(shape, dtype, name, create)


def zeros(shape, dtype=None, name=None, create=True):
    dtype = dtype or np.uint8
    return Array(shape, dtype, name, create)


def full_like(a, fill_value, dtype=None, name=None, create=True):
    dtype = dtype or a.dtype
    shape = a.shape
    arr = Array(shape, dtype, name, create)
    arr[:] = fill_value
    return arr


def full(shape, fill_value, dtype=None, name=None, create=True):
    dtype = dtype or np.uint8
    arr = Array(shape, dtype, name, create)
    arr[:] = fill_value
    return arr


class Dict(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, item):
        return object.__getattribute__(self, item)

    def __len__(self):
        return len(self.__dict__)

    def __getitem__(self, item):
        return self.__dict__[item]

    def __setitem__(self, key, value):
        self.__dict__[key] = value


class SharedStructure(SharedMemoryRecorder):

    def __init__(self, *var_ls, name=None, create=True, **kwargs):
        self.sm = None
        self._vars = {}
        self.fields = Dict()
        self.__total_size = 0
        for v in var_ls:
            self.add(*v)
        for k, v in kwargs.items():
            self.add(k, *v)
        self.alloc(name, create)

    def __setstate__(self, state):
        self.__dict__.update(state)
        name = self.name
        self.alloc(name, False)

    def __getstate__(self):
        return self.__dict__

    def add(self, name, length, c_type: Any = c_uint8):
        assert name not in self._vars
        size = length * sizeof(c_type)
        self.__total_size += size
        self._vars[name] = (length, c_type, size)

    def alloc(self, sm_name=None, create=True):
        sm_name = sm_name or _make_filename()
        self.sm = SharedMemory(sm_name, create, self.__total_size)
        buffer = self.sm.buf
        offset = 0
        total_size = 0
        for name, (length, c_type, size) in self._vars.items():
            self.fields[name] = np.ndarray((length,), c_type, buffer, offset=offset)
            offset += size
            total_size += size
        print("sm_name", sm_name, create, "alloc_size", total_size, "true_size", self.sm.size)
        self.save_sm_name(sm_name, total_size, self.sm.shm_id if hasattr(self.sm, "shm_id") else None)  # 保存已经创建的name

    def close(self):
        if hasattr(self, "sm"):
            self.sm.close()

    @property
    def name(self):
        return self.sm.name


if __name__ == '__main__':
    a = Array(10, "uint8")
    print(a)
