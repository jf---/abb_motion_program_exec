# abb_motion_program_exec

[![](https://img.shields.io/badge/python-3.9+-blue.svg)](https://github.com/rpiRobotics/abb_motion_program_exec)
[![](https://img.shields.io/pypi/v/abb-motion-program-exec)](https://pypi.org/project/abb-motion-program-exec/)

`abb_motion_program_exec` provides a simple way to download and run a sequence of
`MoveAbsJ`, `MoveJ`, `MoveL`, `MoveC`, and `WaitTime` commands on
an ABB IRC5 robot controller. Multi-move control of two robots is also
supported. Externally Guided Motion (EGM) is also supported for joint target, pose target, and path correction modes.

## Installation

```
pip install abb-motion-program-exec
```

Begin by installing the software for the robot controller:

* [Single robot setup](robot_setup_manual.md)
* [Multi-Move setup](robot_multimove_setup_manual.md)

## Quick Start

See the full [README](https://github.com/rpiRobotics/abb_motion_program_exec#readme) for detailed usage, examples, and Multi-Move instructions.

**The robot must be in "Auto" mode for this driver to operate.**

```python
import abb_motion_program_exec as abb

j1 = abb.jointtarget([10,20,30,40,50,60],[0]*6)
j2 = abb.jointtarget([-10,15,35,10,95,-95],[0]*6)

mp = abb.MotionProgram()
mp.MoveAbsJ(j1, abb.v1000, abb.fine)
mp.MoveAbsJ(j2, abb.v5000, abb.fine)

client = abb.MotionProgramExecClient(base_url="http://127.0.0.1:80")
log_results = client.execute_motion_program(mp)
```
