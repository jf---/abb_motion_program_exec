# abb_motion_program_exec

ABB IRC5 Controller Motion Program command client.

This module contains types found on the ABB Robot Controller. Documentation is taken from the
ABB Robotics manual "Technical reference manual RAPID Instructions, Functions and Data types,
Document ID: 3HAC 16581-1". Note that most of the following data structures are all direct copies of the
underlying ABB types.

## abb_motion_program_exec

::: abb_motion_program_exec
    options:
      members:
        - speeddata
        - zonedata
        - jointtarget
        - pose
        - confdata
        - robtarget
        - loaddata
        - CirPathModeSwitch
        - tooldata
        - wobjdata
        - egm_minmax
        - EGMStreamConfig
        - EGMJointTargetConfig
        - egmframetype
        - EGMPoseTargetConfig
        - EGMPathCorrectionConfig
        - MotionProgramExecClient
        - MotionProgram
