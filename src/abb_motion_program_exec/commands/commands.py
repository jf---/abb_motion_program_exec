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

import io
from dataclasses import dataclass

from . import util
from .command_base import CommandBase
from .rapid_types import CirPathModeSwitch, jointtarget, robtarget, speeddata, zonedata


@dataclass
class MoveAbsJCommand(CommandBase):
    """Move to absolute joint position."""

    command_opcode = 1

    to_joint_pos: jointtarget
    speed: speeddata
    zone: zonedata

    def write_params(self, f: io.IOBase):
        f.write(util.jointtarget_to_bin(self.to_joint_pos))
        f.write(util.speeddata_to_bin(self.speed))
        f.write(util.zonedata_to_bin(self.zone))

    def to_rapid(self, sync_move=False, cmd_num=0, **kwargs) -> str:
        sync_id = "" if not sync_move else f"\\ID:={cmd_num},"
        return (
            f"MoveAbsJ {self.to_joint_pos.to_rapid()}, "
            f"{sync_id}{self.speed.to_rapid()}, {self.zone.to_rapid()}, "
            f"motion_program_tool\\Wobj:=motion_program_wobj;"
        )


@dataclass
class MoveJCommand(CommandBase):
    """Move to Cartesian position using joint interpolation."""

    command_opcode = 2

    to_point: robtarget
    speed: speeddata
    zone: zonedata

    def write_params(self, f: io.IOBase):
        f.write(util.robtarget_to_bin(self.to_point))
        f.write(util.speeddata_to_bin(self.speed))
        f.write(util.zonedata_to_bin(self.zone))

    def to_rapid(self, sync_move=False, cmd_num=0, **kwargs) -> str:
        sync_id = "" if not sync_move else f"\\ID:={cmd_num},"
        return (
            f"MoveJ {self.to_point.to_rapid()}, "
            f"{sync_id}{self.speed.to_rapid()}, {self.zone.to_rapid()}, "
            f"motion_program_tool\\Wobj:=motion_program_wobj;"
        )


@dataclass
class MoveLCommand(CommandBase):
    """Move to Cartesian position using linear interpolation."""

    command_opcode = 3

    to_point: robtarget
    speed: speeddata
    zone: zonedata

    def write_params(self, f: io.IOBase):
        f.write(util.robtarget_to_bin(self.to_point))
        f.write(util.speeddata_to_bin(self.speed))
        f.write(util.zonedata_to_bin(self.zone))

    def to_rapid(self, sync_move=False, cmd_num=0, **kwargs) -> str:
        sync_id = "" if not sync_move else f"\\ID:={cmd_num},"
        return (
            f"MoveL {self.to_point.to_rapid()}, "
            f"{sync_id}{self.speed.to_rapid()}, {self.zone.to_rapid()}, "
            f"motion_program_tool\\Wobj:=motion_program_wobj;"
        )


@dataclass
class MoveCCommand(CommandBase):
    """Move along a circular arc through a via point to a destination."""

    command_opcode = 4

    cir_point: robtarget
    to_point: robtarget
    speed: speeddata
    zone: zonedata

    def write_params(self, f: io.IOBase):
        f.write(util.robtarget_to_bin(self.cir_point))
        f.write(util.robtarget_to_bin(self.to_point))
        f.write(util.speeddata_to_bin(self.speed))
        f.write(util.zonedata_to_bin(self.zone))

    def to_rapid(self, sync_move=False, cmd_num=0, **kwargs) -> str:
        sync_id = "" if not sync_move else f"\\ID:={cmd_num},"
        return (
            f"MoveC {self.cir_point.to_rapid()}, "
            f"{sync_id}{self.to_point.to_rapid()}, "
            f"{self.speed.to_rapid()}, {self.zone.to_rapid()}, "
            f"motion_program_tool\\Wobj:=motion_program_wobj;"
        )


@dataclass
class WaitTimeCommand(CommandBase):
    """Wait for a specified time in seconds."""

    command_opcode = 5

    t: float

    def write_params(self, f: io.IOBase):
        f.write(util.num_to_bin(self.t))

    def to_rapid(self, **kwargs) -> str:
        return f"WaitTime {self.t};"


@dataclass
class CirPathModeCommand(CommandBase):
    """Set circular path reorientation mode for MoveC commands."""

    command_opcode = 6

    switch: CirPathModeSwitch

    def write_params(self, f: io.IOBase):
        val = self.switch.value
        if not (1 <= val <= 6):
            raise ValueError("Invalid CirPathMode switch")
        f.write(util.num_to_bin(val))

    def to_rapid(self, **kwargs) -> str:
        if self.switch == 1:
            return r"CirPathMode\PathFrame;"
        if self.switch == 2:
            return r"CirPathMode\ObjectFrame;"
        if self.switch == 3:
            return r"CirPathMode\CirPointOri;"
        if self.switch == 4:
            return r"CirPathMode\Wrist45;"
        if self.switch == 5:
            return r"CirPathMode\Wrist46;"
        if self.switch == 6:
            return r"CirPathMode\Wrist56;"
        raise ValueError("Invalid CirPathMode switch")


@dataclass
class SyncMoveOnCommand(CommandBase):
    """Enable synchronized MultiMove motion."""

    command_opcode = 7

    def write_params(self, f: io.IOBase):
        pass

    def to_rapid(self, **kwargs) -> str:
        return "SyncMoveOn motion_program_sync1,task_list;"


class SyncMoveOffCommand(CommandBase):
    """Disable synchronized MultiMove motion."""

    command_opcode = 8

    def write_params(self, f: io.IOBase):
        pass

    def to_rapid(self, **kwargs) -> str:
        return "SyncMoveOff motion_program_sync2;"
