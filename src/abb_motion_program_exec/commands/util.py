# Copyright 2022 Wason Technology LLC, Rensselaer Polytechnic Institute
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import io
import struct
from collections.abc import Iterable

import numpy as np

from .rapid_types import (
    confdata,
    jointtarget,
    loaddata,
    pose,
    robtarget,
    speeddata,
    tooldata,
    wobjdata,
    zonedata,
)

_speeddata_struct_fmt = struct.Struct("<4f")


def speeddata_to_bin(z: speeddata) -> bytes:
    return _speeddata_struct_fmt.pack(z.v_tcp, z.v_ori, z.v_leax, z.v_reax)


_zonedata_struct_fmt = struct.Struct("<7f")


def zonedata_to_bin(z: zonedata) -> bytes:
    return _zonedata_struct_fmt.pack(
        1.0 if z.finep else 0.0,
        z.pzone_tcp,
        z.pzone_ori,
        z.pzone_eax,
        z.zone_ori,
        z.zone_leax,
        z.zone_reax,
    )


def fix_array(arr: list | np.ndarray, length: int) -> np.ndarray:
    if isinstance(arr, list):
        if len(arr) != length:
            raise ValueError(f"Invalid array, expected length {length}")
        return np.array(arr, dtype=np.float64)
    if arr.shape == (length,):
        return arr
    if arr.shape == (length, 1) or arr.shape == (1, length):
        return arr.flatten()
    raise ValueError(f"Invalid array, expected length {length}")


_jointtarget_struct_fmt = struct.Struct("<12f")


def jointtarget_to_bin(j: jointtarget) -> bytes:
    r = fix_array(j.robax, 6).tolist()
    e = fix_array(j.extax, 6).tolist()
    return _jointtarget_struct_fmt.pack(*r, *e)


_pose_struct_fmt = struct.Struct("<7f")


def pose_to_bin(p: pose) -> bytes:
    p1 = fix_array(p.trans, 3).tolist()
    q = fix_array(p.rot, 4).tolist()
    return _pose_struct_fmt.pack(*p1, *q)


_confdata_struct_fmt = struct.Struct("<4f")


def confdata_to_bin(c: confdata) -> bytes:
    return _confdata_struct_fmt.pack(c.cf1, c.cf4, c.cf6, c.cfx)


_robtarget_extax_struct_fmt = struct.Struct("<6f")


def robtarget_to_bin(r: robtarget) -> bytes:
    p1 = fix_array(r.trans, 3).tolist()
    q = fix_array(r.rot, 4).tolist()
    pose_bin = _pose_struct_fmt.pack(*p1, *q)
    robconf_bin = confdata_to_bin(r.robconf)
    extax = fix_array(r.extax, 6).tolist()
    extax_bin = _robtarget_extax_struct_fmt.pack(*extax)
    return pose_bin + robconf_bin + extax_bin


_num_struct_fmt = struct.Struct("<f")


def num_to_bin(f: float) -> bytes:
    return _num_struct_fmt.pack(f)


_intnum_struct_fmt = struct.Struct("<i")


def intnum_to_bin(f: int) -> bytes:
    return _intnum_struct_fmt.pack(f)


def str_to_bin(s: str) -> bytes:
    if len(s) > 32:
        raise ValueError("String length must be <= 32")
    s_bin = s.encode("ascii")
    pad_len = 32 - len(s_bin)
    if pad_len > 0:
        s_bin += b" " * pad_len
    return num_to_bin(len(s)) + s_bin


_loaddata_struct_fmt = struct.Struct("<11f")


def loaddata_to_bin(ld: loaddata) -> bytes:
    cog = fix_array(ld.cog, 3)
    aom = fix_array(ld.aom, 4)
    return _loaddata_struct_fmt.pack(ld.mass, *cog, *aom, ld.ix, ld.iy, ld.iz)


def tooldata_to_bin(td: tooldata) -> bytes:
    robhold_bin = num_to_bin(1.0 if td.robhold else 0.0)
    tframe_bin = pose_to_bin(td.tframe)
    tload_bin = loaddata_to_bin(td.tload)
    return robhold_bin + tframe_bin + tload_bin


def wobjdata_to_bin(wd: wobjdata) -> bytes:
    robhold_bin = num_to_bin(1.0 if wd.robhold else 0.0)
    ufprog_bin = num_to_bin(1.0 if wd.ufprog else 0.0)
    ufmec_bin = str_to_bin(wd.ufmec)
    uframe_bin = pose_to_bin(wd.uframe)
    oframe_bin = pose_to_bin(wd.oframe)
    return robhold_bin + ufprog_bin + ufmec_bin + uframe_bin + oframe_bin


def read_num(f: io.IOBase) -> float:
    b = f.read(4)
    return _num_struct_fmt.unpack(b)[0]


def read_nums(f: io.IOBase, n: int) -> list[float]:
    return [read_num(f) for _ in range(n)]


def read_str(f: io.IOBase) -> str:
    length = int(read_num(f))
    s_ascii = f.read(length)
    return s_ascii.decode("ascii")


def nums_to_rapid_array(nums: Iterable[float]) -> str:
    return "[" + ", ".join([str(n) for n in nums]) + "]"


def bool_to_rapid(b: bool) -> str:
    return "TRUE" if b else "FALSE"
