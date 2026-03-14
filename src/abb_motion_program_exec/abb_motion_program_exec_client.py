# Copyright 2022 Wason Technology, LLC
#                     Rensselaer Polytechnic Institute
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


import datetime
import io
import logging
import re
from typing import NamedTuple

import numpy as np

from .commands import commands, egm_commands, util
from .commands.command_base import CommandBase, command_append_method
from .commands.egm_commands import *  # noqa: F401,F403
from .commands.egm_commands import EGMConfig
from .commands.rapid_types import *  # noqa: F401,F403
from .commands.rapid_types import loaddata, pose, tooldata, wobjdata

logger = logging.getLogger(__name__)

MOTION_PROGRAM_FILE_VERSION = 10011


class MotionProgramResultLog(NamedTuple):
    """Result log from an executed motion program.

    Returned by ``execute_motion_program`` and ``read_motion_program_result_log``.
    """

    timestamp: str
    """Timestamp of the motion program execution (YYYY-MM-DD-HH-MM-SS-MSMS)."""
    column_headers: list[str]
    """Column names for the data array (e.g. timestamp, command_number, joint positions)."""
    data: np.ndarray
    """Recorded data as float32 array, shape (n_samples, n_columns). Wire format is
    single-precision; use ``.astype(np.float64)`` if double precision is needed."""


def _unpack_motion_program_result_log(b: bytes) -> MotionProgramResultLog:
    f = io.BytesIO(b)
    file_ver = util.read_num(f)
    if file_ver != MOTION_PROGRAM_FILE_VERSION:
        raise ValueError(f"Invalid file version {file_ver}")
    timestamp_str = util.read_str(f)
    header_str = util.read_str(f)
    headers = header_str.split(",")
    data_flat = np.frombuffer(b[f.tell() :], dtype=np.float32)
    data = data_flat.reshape((-1, len(headers)))
    return MotionProgramResultLog(timestamp_str, headers, data)


def _get_motion_program_file(
    path: str,
    motion_program: "MotionProgram",
    task: str = "T_ROB1",
    preempt_number: int | None = None,
    seqno: int | None = None,
) -> tuple[str, bytes]:
    b = motion_program.get_program_bytes(seqno)
    if not b:
        raise ValueError("Motion program must not be empty")
    filename = f"{path}/motion_program"
    if task != "T_ROB1":
        task_m = re.match(r"^.*[A-Za-z_](\d+)$", task)
        if task_m:
            filename = f"{filename}{int(task_m.group(1))}"
    if preempt_number is not None:
        filename = f"{filename}_p{preempt_number}"
    filename = f"{filename}.bin"
    return filename, b


def _validate_multimove(
    motion_programs: list["MotionProgram"], tasks: list[str] | None
) -> list[str]:
    """Validate and resolve task list for MultiMove programs. Returns resolved tasks."""
    if tasks is None:
        tasks = [f"T_ROB{i + 1}" for i in range(len(motion_programs))]
    if len(motion_programs) != len(tasks):
        raise ValueError(
            f"Motion program count ({len(motion_programs)}) != task count ({len(tasks)})"
        )
    if len(tasks) <= 1:
        raise ValueError("Multimove program must have at least two tasks")
    return tasks


def _prepare_multimove_files(
    ramdisk: str,
    motion_programs: "list[MotionProgram]",
    tasks: list[str],
    preempt_number: int | None = None,
    seqno: int | None = None,
) -> list[tuple[str, bytes]]:
    """Build (filename, bytes) pairs for each task in a MultiMove program."""
    return [
        _get_motion_program_file(ramdisk, mp, task, preempt_number, seqno=seqno)
        for mp, task in zip(motion_programs, tasks)
    ]


def _parse_event_log_for_result(log_after_raw: list, prev_seqnum: int) -> str:
    """Extract result log filename from event log entries after execution.

    Returns the log filename. Raises RuntimeError on failure or errors.
    """
    log_after = []
    for entry in log_after_raw:
        if entry.seqnum > prev_seqnum:
            log_after.append(entry)
        elif prev_seqnum > 61440 and entry.seqnum < 4096:
            # Handle uint16 wraparound
            log_after.append(entry)
        else:
            break

    failed = False
    for entry in log_after:
        if (
            entry.msgtype >= 2
            and entry.args
            and entry.args[0].lower() == "motion program failed"
        ):
            raise RuntimeError(
                f"{entry.args[1]} {entry.args[2]} {entry.args[3]} {entry.args[4]}"
            )
        if entry.msgtype >= 3:
            failed = True

    if failed:
        raise RuntimeError("Motion Program Failed, see robot error log for details")

    found_log_open = False
    found_log_close = False
    log_filename = ""

    for entry in reversed(log_after):
        if entry.code == 80003:
            if entry.args[0].lower() == "motion program log file closed":
                if found_log_open:
                    if found_log_close:
                        raise RuntimeError("Found more than one log closed message")
                    found_log_close = True

            if entry.args[0].lower() == "motion program log file opened":
                if found_log_open:
                    raise RuntimeError("Found more than one log opened message")
                found_log_open = True
                log_filename_m = re.search(r"(log\-[\d\-]+\.bin)", entry.args[1])
                if not log_filename_m:
                    raise RuntimeError("Invalid log opened message")
                log_filename = log_filename_m.group(1)

    if not (found_log_open and found_log_close and log_filename):
        raise RuntimeError("Could not find log file messages in robot event log")

    return log_filename


tool0 = tooldata(
    True,
    pose([0, 0, 0], [1, 0, 0, 0]),
    loaddata(0.001, [0, 0, 0.001], [1, 0, 0, 0], 0, 0, 0),
)
"""Default tool — identity frame, near-zero mass. Matches ABB RAPID built-in ``tool0``."""

wobj0 = wobjdata(
    False, True, "", pose([0, 0, 0], [1, 0, 0, 0]), pose([0, 0, 0], [1, 0, 0, 0])
)
"""Default work object — world frame. Matches ABB RAPID built-in ``wobj0``."""

load0 = loaddata(0.001, [0, 0, 0.001], [1, 0, 0, 0], 0, 0, 0)
"""Default payload — near-zero mass (0.001 kg avoids division-by-zero in dynamics).
Matches ABB RAPID built-in ``load0``."""


class MotionProgram:
    """Class representing a Motion Program. A Motion Program is a sequence of robot motion
    primitives that can be executed by the interpreter program running on the robot.

    Motion commands are appended by calling command functions: ``MoveAbsJ``, ``MoveJ``,
    ``MoveL``, ``MoveC``, ``WaitTime``, ``CirPathMode``, ``SyncMoveOn``, ``SyncMoveOff``,
    ``EGMRunJoint``, ``EGMRunPose``, ``EGMMoveL``, and ``EGMMoveC``.
    """

    MoveAbsJ = command_append_method(commands.MoveAbsJCommand)
    MoveJ = command_append_method(commands.MoveJCommand)
    MoveL = command_append_method(commands.MoveLCommand)
    MoveC = command_append_method(commands.MoveCCommand)
    WaitTime = command_append_method(commands.WaitTimeCommand)
    CirPathMode = command_append_method(commands.CirPathModeCommand)
    SyncMoveOn = command_append_method(commands.SyncMoveOnCommand)
    SyncMoveOff = command_append_method(commands.SyncMoveOffCommand)

    EGMRunJoint = command_append_method(egm_commands.EGMRunJointCommand)
    EGMRunPose = command_append_method(egm_commands.EGMRunPoseCommand)
    EGMMoveL = command_append_method(egm_commands.EGMMoveLCommand)
    EGMMoveC = command_append_method(egm_commands.EGMMoveCCommand)

    def __init__(
        self,
        first_cmd_num: int = 1,
        tool: tooldata | None = None,
        wobj: wobjdata | None = None,
        timestamp: str | None = None,
        egm_config: EGMConfig | None = None,
        seqno: int = 0,
        gripload: loaddata | None = None,
    ):
        self._commands: list[CommandBase] = []

        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-2]
        if not re.match(r"^\d{4}\-\d{2}\-\d{2}-\d{2}\-\d{2}\-\d{2}\-\d{4}$", timestamp):
            raise ValueError(
                "Invalid timestamp format. Must be YYYY-MM-DD-HH-MM-SS-MSMS"
            )

        self._timestamp = timestamp
        self.tool = tool if tool is not None else tool0
        self.wobj = wobj if wobj is not None else wobj0
        self.gripload = gripload if gripload is not None else load0
        self._first_cmd_num = first_cmd_num
        self._egm_config = egm_config
        self._seqno = seqno

    def _append_command(self, cmd):
        self._commands.append(cmd)

    def write_program(self, f: io.IOBase, seqno: int | None = None):
        """Write binary motion program to file."""
        f.write(util.num_to_bin(MOTION_PROGRAM_FILE_VERSION))
        f.write(util.tooldata_to_bin(self.tool))
        f.write(util.wobjdata_to_bin(self.wobj))
        f.write(util.loaddata_to_bin(self.gripload))
        f.write(util.str_to_bin(self._timestamp))
        f.write(util.num_to_bin(seqno if seqno is not None else self._seqno))

        egm_commands.write_egm_config(f, self._egm_config)

        for i, cmd in enumerate(self._commands, start=self._first_cmd_num):
            f.write(util.num_to_bin(i))
            f.write(util.num_to_bin(cmd.command_opcode))
            cmd.write_params(f)

    def get_program_bytes(self, seqno: int | None = None) -> bytes:
        """Return binary motion program."""
        f = io.BytesIO()
        self.write_program(f, seqno)
        return f.getvalue()

    def write_program_rapid(
        self, f: io.TextIOBase, module_name="motion_program_exec_gen", sync_move=False
    ):
        """Write equivalent RAPID program. Useful for debugging."""
        ver = MOTION_PROGRAM_FILE_VERSION
        tooldata_str = self.tool.to_rapid()
        wobjdata_str = self.wobj.to_rapid()

        print(f"MODULE {module_name}", file=f)
        print(f"    ! abb_motion_program_exec format version {ver}", file=f)
        print(f"    ! abb_motion_program_exec timestamp {self._timestamp}", file=f)
        print(f"    TASK PERS tooldata motion_program_tool := {tooldata_str};", file=f)
        print(f"    TASK PERS wobjdata motion_program_wobj := {wobjdata_str};", file=f)
        if sync_move:
            print('    PERS tasks task_list{2} := [ ["T_ROB1"], ["T_ROB2"] ];', file=f)
            print("    VAR syncident motion_program_sync1;", file=f)
            print("    VAR syncident motion_program_sync2;", file=f)

        print("    PROC main()", file=f)

        for cmd_num, cmd in enumerate(self._commands, start=self._first_cmd_num):
            print(f"        ! cmd_num = {cmd_num}", file=f)
            print(
                f"        {cmd.to_rapid(sync_move=sync_move, cmd_num=cmd_num)}", file=f
            )

        print("    ENDPROC", file=f)
        print("ENDMODULE", file=f)

    def get_program_rapid(
        self, module_name="motion_program_exec_gen", sync_move=False
    ) -> str:
        """Returns equivalent RAPID program string. Useful for debugging."""
        o = io.StringIO()
        self.write_program_rapid(o, module_name, sync_move)
        return o.getvalue()

    def get_timestamp(self) -> str:
        """Get the timestamp of the motion program"""
        return self._timestamp


# MotionProgramExecClient is auto-generated in _sync_client.py from the async source.
# Import it from there for backward compatibility.
from ._sync_client import MotionProgramExecClient  # noqa: F401,E402
