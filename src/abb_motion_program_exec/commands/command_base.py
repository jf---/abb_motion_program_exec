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


import abc
import inspect
import io
from typing import ClassVar


class CommandBase(abc.ABC):
    """Base class for all motion program commands.

    Subclasses must define ``command_opcode`` as a class variable and implement
    ``write_params`` (binary serialization) and ``to_rapid`` (RAPID source generation).
    """

    command_opcode: ClassVar[int]

    @abc.abstractmethod
    def write_params(self, f: io.IOBase) -> None: ...

    @abc.abstractmethod
    def to_rapid(self, **kwargs) -> str: ...


class command_append_method:
    """Descriptor that creates a method on MotionProgram which instantiates a command
    and appends it to the program's command list."""

    def __init__(self, command_cls: type[CommandBase]):
        self._command_cls = command_cls

    def __get__(self, obj, cls=None):
        if obj is None:
            raise AttributeError("command_append_method must be called on an instance")

        def command_append_func(*args, **kwargs):
            cmd = self._command_cls(*args, **kwargs)
            obj._append_command(cmd)
            return cmd

        sig = inspect.signature(self._command_cls.__init__)
        sig = sig.replace(parameters=tuple(sig.parameters.values())[1:])
        command_append_func.__signature__ = sig
        command_append_func.__doc__ = self._command_cls.__doc__
        return command_append_func
