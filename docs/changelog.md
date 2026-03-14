# Changelog

## 0.9.0 (unreleased)

### Python 3.9+ modernization

Minimum Python version: 3.9. All source files now use `from __future__ import annotations`.

**Type annotations (PEP 585 / PEP 604)**

- `List[str]` → `list[str]`, `List[MotionProgram]` → `list[MotionProgram]`, etc.
- `Union[X, Y]` → `X | Y`, `Optional[X]` → `X | None`
- `Callable` → `collections.abc.Callable`
- Removed `from typing import List, Union, Optional, Callable, TYPE_CHECKING`
- Added `EGMConfig` type alias for the EGM config union

**Imports cleaned up**

- Replaced `from .rapid_types import *` with explicit imports
- Replaced `TYPE_CHECKING` guard in `util.py` with direct imports (now safe via `__future__.annotations`)
- Sorted and grouped imports per isort conventions

**Idiomatic Python**

- `for i in range(len(x)):` → `for i, cmd in enumerate(...)` (4 instances)
- `for i in range(len(filenames)): upload(filenames[i], b[i])` → `for filename, data in files:` (2 instances)
- `not x == y` → `x != y` (8 instances)
- `not len(x) > 0` → `not x` (3 instances)

**Error handling**

- Bare `except: pass` → `except Exception:` with `logger.debug(...)` (2 instances)
- `raise Exception(...)` → specific types: `ValueError`, `RuntimeError`, `TypeError`, `AttributeError`
- String concatenation in error messages → f-strings

**Code quality**

- All files formatted with `ruff format`
- Fixed `confdata_to_bin` type hint (was `robtarget`, should be `confdata`)
- `nums_to_rapid_array` parameter type: `list[float]` → `Iterable[float]` (accepts ndarrays)
- Loop variable `l` → `entry` (shadowed builtin)
- Loop variable `l` → `ld` in `loaddata_to_bin` (ambiguous name)
- Added return type annotations to all functions in `util.py`
- Added `logging` import and `logger` for both sync and async clients

### Previous releases

See [GitHub releases](https://github.com/rpiRobotics/abb_motion_program_exec/releases) for earlier versions.
