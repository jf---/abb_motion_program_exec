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

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable

from abb_robot_client.rws_aio import RWS_AIO

from .abb_motion_program_exec_client import (
    MotionProgram,
    MotionProgramResultLog,
    _get_motion_program_file,
    _unpack_motion_program_result_log,
)

logger = logging.getLogger(__name__)


class MotionProgramExecClientAIO:
    """Client to execute motion programs on an ABB IRC5 controller using AsyncIO."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:80",
        username: str = "Default User",
        password: str = "robotics",
        abb_client_aio: RWS_AIO | None = None,
    ):
        self.abb_client_aio: RWS_AIO = (
            abb_client_aio
            if abb_client_aio is not None
            else RWS_AIO(base_url, username, password)
        )

    async def execute_motion_program(
        self,
        motion_program: MotionProgram,
        task: str = "T_ROB1",
        wait: bool = True,
        seqno: int | None = None,
    ) -> MotionProgramResultLog | int:
        """Execute a motion program.

        If ``wait`` is True, uploads, executes, waits for completion, and returns the result log.
        If ``wait`` is False, returns the event log seqnum for later retrieval.
        """
        filename, b = _get_motion_program_file(
            await self.abb_client_aio.get_ramdisk_path(),
            motion_program,
            task,
            seqno=seqno,
        )

        async def _upload():
            await self.abb_client_aio.upload_file(filename, b)

        prev_seqnum = await self._download_and_start_motion_program([task], _upload)
        if not wait:
            return prev_seqnum
        await self.wait_motion_program_complete()
        return await self.read_motion_program_result_log(prev_seqnum)

    async def preempt_motion_program(
        self,
        motion_program: MotionProgram,
        task: str = "T_ROB1",
        preempt_number: int = 1,
        preempt_cmdnum: int = -1,
        seqno: int | None = None,
    ):
        """Preempt a running motion program with a replacement."""
        filename, b = _get_motion_program_file(
            await self.abb_client_aio.get_ramdisk_path(),
            motion_program,
            task,
            preempt_number,
            seqno=seqno,
        )
        await self.abb_client_aio.upload_file(filename, b)
        await self.abb_client_aio.set_analog_io(
            "motion_program_preempt_cmd_num", preempt_cmdnum
        )
        await self.abb_client_aio.set_analog_io(
            "motion_program_preempt", preempt_number
        )

    async def get_current_cmdnum(self) -> int:
        """Get the currently executing ``cmdnum``"""
        return await self.abb_client_aio.get_analog_io("motion_program_current_cmd_num")

    async def get_queued_cmdnum(self) -> int:
        """Get the currently queued ``cmdnum``."""
        return await self.abb_client_aio.get_analog_io("motion_program_queued_cmd_num")

    async def get_current_preempt_number(self) -> int:
        """Get the current preempt_number"""
        return await self.abb_client_aio.get_analog_io("motion_program_preempt_current")

    async def execute_multimove_motion_program(
        self,
        motion_programs: list[MotionProgram],
        tasks: list[str] | None = None,
        wait: bool = True,
        seqno: int | None = None,
    ):
        """Execute a motion program on a MultiMove system with multiple robots."""
        if tasks is None:
            tasks = [f"T_ROB{i + 1}" for i in range(len(motion_programs))]

        if len(motion_programs) != len(tasks):
            raise ValueError("Motion program list and task list must have same length")
        if len(tasks) <= 1:
            raise ValueError("Multimove program must have at least two tasks")

        ramdisk = await self.abb_client_aio.get_ramdisk_path()
        files = [
            _get_motion_program_file(ramdisk, mp, task, seqno=seqno)
            for mp, task in zip(motion_programs, tasks)
        ]

        async def _upload():
            for filename, data in files:
                await self.abb_client_aio.upload_file(filename, data)

        prev_seqnum = await self._download_and_start_motion_program(tasks, _upload)
        if not wait:
            return prev_seqnum
        await self.wait_motion_program_complete()
        return await self.read_motion_program_result_log(prev_seqnum)

    async def preempt_multimove_motion_program(
        self,
        motion_programs: list[MotionProgram],
        tasks: list[str] | None = None,
        preempt_number: int = 1,
        preempt_cmdnum: int = -1,
        seqno: int | None = None,
    ):
        """Preempt a MultiMove motion program."""
        if tasks is None:
            tasks = [f"T_ROB{i + 1}" for i in range(len(motion_programs))]

        if len(motion_programs) != len(tasks):
            raise ValueError("Motion program list and task list must have same length")
        if len(tasks) <= 1:
            raise ValueError("Multimove program must have at least two tasks")

        ramdisk = await self.abb_client_aio.get_ramdisk_path()
        for mp, task in zip(motion_programs, tasks):
            filename, b = _get_motion_program_file(
                ramdisk, mp, task, preempt_number, seqno=seqno
            )
            await self.abb_client_aio.upload_file(filename, b)
        await self.abb_client_aio.set_analog_io(
            "motion_program_preempt_cmd_num", preempt_cmdnum
        )
        await self.abb_client_aio.set_analog_io(
            "motion_program_preempt", preempt_number
        )

    async def _download_and_start_motion_program(
        self, tasks: list[str], upload_fn: Callable[[], None]
    ) -> int:
        exec_state = await self.abb_client_aio.get_execution_state()
        if exec_state.ctrlexecstate != "stopped":
            raise RuntimeError(
                "Controller must be stopped before executing motion program"
            )
        ctrl_state = await self.abb_client_aio.get_controller_state()
        if ctrl_state != "motoron":
            raise RuntimeError(
                "Controller must be motor on before executing motion program"
            )

        log_before = await self.abb_client_aio.read_event_log()
        prev_seqnum = log_before[0].seqnum

        await self.abb_client_aio.resetpp()
        await upload_fn()
        await self.abb_client_aio.start(cycle="once", tasks=tasks)

        return prev_seqnum

    async def is_motion_program_running(self) -> bool:
        """Returns True if motion program is running"""
        exec_state = await self.abb_client_aio.get_execution_state()
        return exec_state.ctrlexecstate == "running"

    async def wait_motion_program_complete(self):
        """Wait for motion program to complete"""
        while True:
            exec_state = await self.abb_client_aio.get_execution_state()
            if exec_state.ctrlexecstate != "running":
                break
            await asyncio.sleep(0.05)

    async def read_motion_program_result_log(
        self, prev_seqnum: int
    ) -> MotionProgramResultLog:
        """Read a motion program result log after completion."""
        log_after_raw = await self.abb_client_aio.read_event_log()
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

        ramdisk = await self.abb_client_aio.get_ramdisk_path()
        log_contents = await self.abb_client_aio.read_file(f"{ramdisk}/{log_filename}")
        try:
            await self.abb_client_aio.delete_file(f"{ramdisk}/{log_filename}")
        except Exception:
            logger.debug("Failed to delete log file %s", log_filename, exc_info=True)
        return _unpack_motion_program_result_log(log_contents)

    async def stop_motion_program(self):
        """Stop a motion program."""
        await self.abb_client_aio.stop()

    async def stop_egm(self):
        """Stop a long running EGM command."""
        await self.abb_client_aio.set_digital_io("motion_program_stop_egm", 1)

    async def enable_motion_logging(self):
        """Enable motion logging"""
        await self.abb_client_aio.set_digital_io("motion_program_log_motion", 1)

    async def disable_motion_logging(self):
        """Disable motion logging"""
        await self.abb_client_aio.set_digital_io("motion_program_log_motion", 0)

    async def get_motion_logging_enabled(self) -> bool:
        """Return if motion logging is enabled"""
        return await self.abb_client_aio.get_digital_io("motion_program_log_motion") > 0
