"""Round-trip and edge-case tests for binary serialization and RAPID generation.

All tests are pure — no hardware, no network, no mocking.
"""

from __future__ import annotations

import io
import struct

import numpy as np
import pytest

from abb_motion_program_exec import (
    MotionProgram,
)
from abb_motion_program_exec.abb_motion_program_exec_client import (
    MOTION_PROGRAM_FILE_VERSION,
    _get_motion_program_file,
    _unpack_motion_program_result_log,
    load0,
    tool0,
    wobj0,
)
from abb_motion_program_exec.commands.rapid_types import (
    CirPathModeSwitch,
    confdata,
    fine,
    jointtarget,
    pose,
    robtarget,
    tooldata,
    v100,
    v500,
    wobjdata,
    z10,
)
from abb_motion_program_exec.commands.util import (
    bool_to_rapid,
    confdata_to_bin,
    fix_array,
    jointtarget_to_bin,
    loaddata_to_bin,
    num_to_bin,
    nums_to_rapid_array,
    pose_to_bin,
    read_num,
    read_str,
    robtarget_to_bin,
    speeddata_to_bin,
    str_to_bin,
    tooldata_to_bin,
    wobjdata_to_bin,
    zonedata_to_bin,
)


# ---------------------------------------------------------------------------
# util.py: num round-trip
# ---------------------------------------------------------------------------


class TestNumBin:
    def test_roundtrip_zero(self):
        assert read_num(io.BytesIO(num_to_bin(0.0))) == 0.0

    def test_roundtrip_positive(self):
        assert read_num(io.BytesIO(num_to_bin(3.14))) == pytest.approx(3.14, rel=1e-6)

    def test_roundtrip_negative(self):
        assert read_num(io.BytesIO(num_to_bin(-42.5))) == pytest.approx(-42.5)

    def test_size_is_4_bytes(self):
        assert len(num_to_bin(1.0)) == 4


# ---------------------------------------------------------------------------
# util.py: str round-trip
# ---------------------------------------------------------------------------


class TestStrBin:
    def test_roundtrip(self):
        f = io.BytesIO(str_to_bin("hello"))
        assert read_str(f) == "hello"

    def test_empty_string(self):
        f = io.BytesIO(str_to_bin(""))
        assert read_str(f) == ""

    def test_max_length_32(self):
        s = "a" * 32
        f = io.BytesIO(str_to_bin(s))
        assert read_str(f) == s

    def test_exceeds_32_raises(self):
        with pytest.raises(ValueError, match="<= 32"):
            str_to_bin("a" * 33)

    def test_binary_size_is_36_bytes(self):
        # 4 bytes length + 32 bytes padded content
        assert len(str_to_bin("hi")) == 36


# ---------------------------------------------------------------------------
# util.py: fix_array
# ---------------------------------------------------------------------------


class TestFixArray:
    def test_list_to_ndarray(self):
        result = fix_array([1.0, 2.0, 3.0], 3)
        np.testing.assert_array_equal(result, [1.0, 2.0, 3.0])
        assert result.dtype == np.float64

    def test_ndarray_passthrough(self):
        arr = np.array([1.0, 2.0], dtype=np.float64)
        assert fix_array(arr, 2) is arr

    def test_column_vector_flattened(self):
        arr = np.array([[1.0], [2.0], [3.0]])
        result = fix_array(arr, 3)
        assert result.shape == (3,)

    def test_row_vector_flattened(self):
        arr = np.array([[1.0, 2.0, 3.0]])
        result = fix_array(arr, 3)
        assert result.shape == (3,)

    def test_wrong_length_list_raises(self):
        with pytest.raises(ValueError, match="expected length 3"):
            fix_array([1.0, 2.0], 3)

    def test_wrong_shape_ndarray_raises(self):
        with pytest.raises(ValueError, match="expected length 3"):
            fix_array(np.zeros((2, 2)), 3)


# ---------------------------------------------------------------------------
# util.py: RAPID type serialization
# ---------------------------------------------------------------------------


class TestSpeeddata:
    def test_bin_size(self):
        assert len(speeddata_to_bin(v100)) == 16  # 4 floats * 4 bytes

    def test_values_preserved(self):
        b = speeddata_to_bin(v500)
        vals = struct.unpack("<4f", b)
        assert vals == (500.0, 500.0, 5000.0, 1000.0)

    def test_to_rapid(self):
        assert v100.to_rapid() == "[100, 500, 5000, 1000]"


class TestZonedata:
    def test_bin_size(self):
        assert len(zonedata_to_bin(z10)) == 28  # 7 floats * 4 bytes

    def test_fine_point_flag(self):
        b_fine = zonedata_to_bin(fine)
        b_zone = zonedata_to_bin(z10)
        # first float: 1.0 for fine, 0.0 for zone
        assert struct.unpack("<f", b_fine[:4])[0] == 1.0
        assert struct.unpack("<f", b_zone[:4])[0] == 0.0


class TestJointtarget:
    def test_bin_size(self):
        jt = jointtarget(np.zeros(6), np.zeros(6))
        assert len(jointtarget_to_bin(jt)) == 48  # 12 floats * 4 bytes

    def test_values_preserved(self):
        robax = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
        extax = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        jt = jointtarget(robax, extax)
        b = jointtarget_to_bin(jt)
        vals = struct.unpack("<12f", b)
        np.testing.assert_allclose(vals[:6], robax, atol=1e-5)
        np.testing.assert_allclose(vals[6:], extax, atol=1e-5)

    def test_to_rapid(self):
        jt = jointtarget(np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]), np.zeros(6))
        rapid = jt.to_rapid()
        assert rapid.startswith("[[")
        assert rapid.endswith("]]")


class TestPose:
    def test_bin_size(self):
        p = pose([0, 0, 0], [1, 0, 0, 0])
        assert len(pose_to_bin(p)) == 28  # 7 floats

    def test_to_rapid(self):
        p = pose([100, 200, 300], [1, 0, 0, 0])
        assert "100" in p.to_rapid()
        assert "300" in p.to_rapid()


class TestConfdata:
    def test_bin_size(self):
        c = confdata(0, 0, 0, 0)
        assert len(confdata_to_bin(c)) == 16  # 4 floats


class TestRobtarget:
    def test_bin_size(self):
        rt = robtarget([0, 0, 0], [1, 0, 0, 0], confdata(0, 0, 0, 0), np.zeros(6))
        assert len(robtarget_to_bin(rt)) == 68  # 7 + 4 + 6 = 17 floats * 4 bytes


class TestLoaddata:
    def test_bin_size(self):
        assert len(loaddata_to_bin(load0)) == 44  # 11 floats


class TestTooldata:
    def test_bin_size(self):
        assert len(tooldata_to_bin(tool0)) == 76  # 1 + 7 + 11 = 19 floats


class TestWobjdata:
    def test_bin_size(self):
        assert len(wobjdata_to_bin(wobj0)) == 100  # 1 + 1 + 36(str) + 7 + 7 = varies
        # 2 bools(8) + str(36) + 2*pose(56) = 100


# ---------------------------------------------------------------------------
# util.py: RAPID string helpers
# ---------------------------------------------------------------------------


class TestRapidHelpers:
    def test_nums_to_rapid_array(self):
        assert nums_to_rapid_array([1, 2, 3]) == "[1, 2, 3]"

    def test_nums_to_rapid_array_empty(self):
        assert nums_to_rapid_array([]) == "[]"

    def test_nums_to_rapid_array_ndarray(self):
        result = nums_to_rapid_array(np.array([1.0, 2.0]))
        assert result == "[1.0, 2.0]"

    def test_bool_to_rapid(self):
        assert bool_to_rapid(True) == "TRUE"
        assert bool_to_rapid(False) == "FALSE"


# ---------------------------------------------------------------------------
# MotionProgram: build + serialize
# ---------------------------------------------------------------------------


class TestMotionProgram:
    def test_empty_program_bytes(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        b = mp.get_program_bytes()
        assert len(b) > 0

    def test_single_moveabsj(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        jt = jointtarget(np.zeros(6), np.zeros(6))
        mp.MoveAbsJ(jt, v100, fine)
        b = mp.get_program_bytes()
        # header + tooldata + wobjdata + loaddata + str + seqno + egm + 1 command
        assert len(b) > 200

    def test_multiple_commands(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        jt = jointtarget(np.zeros(6), np.zeros(6))
        mp.MoveAbsJ(jt, v100, fine)
        mp.MoveAbsJ(jt, v500, z10)
        mp.WaitTime(1.0)
        b = mp.get_program_bytes()
        assert len(b) > 300

    def test_custom_tool_wobj(self):
        t = tooldata(True, pose([0, 0, 100], [1, 0, 0, 0]), load0)
        w = wobjdata(
            False,
            True,
            "",
            pose([500, 0, 0], [1, 0, 0, 0]),
            pose([0, 0, 0], [1, 0, 0, 0]),
        )
        mp = MotionProgram(tool=t, wobj=w, timestamp="2024-01-01-12-00-00-0000")
        b = mp.get_program_bytes()
        assert len(b) > 0

    def test_invalid_timestamp_raises(self):
        with pytest.raises(ValueError, match="timestamp"):
            MotionProgram(timestamp="not-a-timestamp")

    def test_seqno_override(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000", seqno=42)
        b1 = mp.get_program_bytes()
        b2 = mp.get_program_bytes(seqno=99)
        # different seqno → different bytes
        assert b1 != b2


# ---------------------------------------------------------------------------
# MotionProgram: RAPID generation
# ---------------------------------------------------------------------------


class TestMotionProgramRapid:
    def test_rapid_output_has_module_structure(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        jt = jointtarget(np.zeros(6), np.zeros(6))
        mp.MoveAbsJ(jt, v100, fine)
        rapid = mp.get_program_rapid()
        assert "MODULE motion_program_exec_gen" in rapid
        assert "ENDMODULE" in rapid
        assert "PROC main()" in rapid
        assert "ENDPROC" in rapid
        assert "MoveAbsJ" in rapid

    def test_rapid_sync_move(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        jt = jointtarget(np.zeros(6), np.zeros(6))
        mp.MoveAbsJ(jt, v100, fine)
        rapid = mp.get_program_rapid(sync_move=True)
        assert "syncident" in rapid
        assert "task_list" in rapid
        assert "\\ID:=" in rapid

    def test_rapid_movel(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        rt = robtarget([500, 0, 500], [1, 0, 0, 0], confdata(0, 0, 0, 0), np.zeros(6))
        mp.MoveL(rt, v100, z10)
        rapid = mp.get_program_rapid()
        assert "MoveL" in rapid

    def test_rapid_movec(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        rt1 = robtarget(
            [500, 100, 500], [1, 0, 0, 0], confdata(0, 0, 0, 0), np.zeros(6)
        )
        rt2 = robtarget(
            [500, 200, 500], [1, 0, 0, 0], confdata(0, 0, 0, 0), np.zeros(6)
        )
        mp.MoveC(rt1, rt2, v100, z10)
        rapid = mp.get_program_rapid()
        assert "MoveC" in rapid

    def test_rapid_waittime(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        mp.WaitTime(2.5)
        rapid = mp.get_program_rapid()
        assert "WaitTime 2.5;" in rapid

    def test_rapid_cirpathmode(self):
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        mp.CirPathMode(CirPathModeSwitch.ObjectFrame)
        rapid = mp.get_program_rapid()
        assert r"CirPathMode\ObjectFrame;" in rapid


# ---------------------------------------------------------------------------
# _unpack_motion_program_result_log
# ---------------------------------------------------------------------------


class TestResultLogParsing:
    def _make_log_bytes(self, timestamp: str, headers: str, data: np.ndarray) -> bytes:
        """Construct a valid binary result log for testing.

        Note: read_str reads exactly len(s) bytes after the 4-byte length field,
        NOT the full 32-byte padded field. So the data offset depends on the
        actual string lengths, not the padded field size. We use str_to_bin
        (which pads to 32) but read_str under-reads. The parser uses f.tell()
        to find the data start, so we must account for this.
        """
        buf = io.BytesIO()
        buf.write(num_to_bin(MOTION_PROGRAM_FILE_VERSION))
        # write version + length(4) + timestamp chars (no padding consumed by reader)
        buf.write(num_to_bin(len(timestamp)))
        buf.write(timestamp.encode("ascii"))
        # write length(4) + header chars (no padding consumed by reader)
        buf.write(num_to_bin(len(headers)))
        buf.write(headers.encode("ascii"))
        # data immediately follows
        buf.write(data.astype(np.float32).tobytes())
        return buf.getvalue()

    def test_roundtrip(self):
        data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        b = self._make_log_bytes("2024-01-01-12-00-00-0000", "time,value", data)
        log = _unpack_motion_program_result_log(b)
        assert log.timestamp == "2024-01-01-12-00-00-0000"
        assert log.column_headers == ["time", "value"]
        np.testing.assert_array_equal(log.data, data)

    def test_wrong_version_raises(self):
        buf = io.BytesIO()
        buf.write(num_to_bin(99999))
        buf.write(num_to_bin(2))
        buf.write(b"ts")
        buf.write(num_to_bin(1))
        buf.write(b"h")
        with pytest.raises(ValueError, match="file version"):
            _unpack_motion_program_result_log(buf.getvalue())

    def test_single_column(self):
        data = np.array([[1.0], [2.0], [3.0]], dtype=np.float32)
        b = self._make_log_bytes("2024-01-01-12-00-00-0000", "joint1", data)
        log = _unpack_motion_program_result_log(b)
        assert log.data.shape == (3, 1)


# ---------------------------------------------------------------------------
# _get_motion_program_file
# ---------------------------------------------------------------------------


class TestGetMotionProgramFile:
    def _mp(self) -> MotionProgram:
        mp = MotionProgram(timestamp="2024-01-01-12-00-00-0000")
        mp.MoveAbsJ(jointtarget(np.zeros(6), np.zeros(6)), v100, fine)
        return mp

    def test_default_task(self):
        filename, b = _get_motion_program_file("/ramdisk", self._mp())
        assert filename == "/ramdisk/motion_program.bin"
        assert len(b) > 0

    def test_task_rob2(self):
        filename, _ = _get_motion_program_file("/ramdisk", self._mp(), task="T_ROB2")
        assert filename == "/ramdisk/motion_program2.bin"

    def test_task_rob3(self):
        filename, _ = _get_motion_program_file("/ramdisk", self._mp(), task="T_ROB3")
        assert filename == "/ramdisk/motion_program3.bin"

    def test_preempt(self):
        filename, _ = _get_motion_program_file("/ramdisk", self._mp(), preempt_number=1)
        assert filename == "/ramdisk/motion_program_p1.bin"

    def test_preempt_rob2(self):
        filename, _ = _get_motion_program_file(
            "/ramdisk", self._mp(), task="T_ROB2", preempt_number=2
        )
        assert filename == "/ramdisk/motion_program2_p2.bin"


# ---------------------------------------------------------------------------
# CommandBase ABC enforcement
# ---------------------------------------------------------------------------


class TestCommandBaseABC:
    def test_cannot_instantiate_base(self):
        from abb_motion_program_exec.commands.command_base import CommandBase

        with pytest.raises(TypeError):
            CommandBase()

    def test_incomplete_subclass_raises(self):
        from abb_motion_program_exec.commands.command_base import CommandBase
        from dataclasses import dataclass

        @dataclass
        class BadCommand(CommandBase):
            command_opcode = 999
            # missing write_params and to_rapid

        with pytest.raises(TypeError):
            BadCommand()


# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_tool0_identity_frame(self):
        np.testing.assert_array_equal(tool0.tframe.trans, [0, 0, 0])
        np.testing.assert_array_equal(tool0.tframe.rot, [1, 0, 0, 0])

    def test_wobj0_world_frame(self):
        assert wobj0.robhold is False
        assert wobj0.ufprog is True

    def test_load0_near_zero(self):
        assert load0.mass == pytest.approx(0.001)
