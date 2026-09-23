# Minimal type stub for UnitTesting (https://github.com/SublimeText/UnitTesting),
# which is a Sublime package, not a pip package. Dev-only: pyright picks up
# ./typings automatically (default stubPath). Covers the public names in
# unittesting/__init__.py (UnitTesting 1.11.x).
import unittest
from collections.abc import Callable
from typing import Any, ClassVar

import sublime

AWAIT_WORKER: object

def expectedFailure(func: Callable[..., Any]) -> Callable[..., Any]: ...
def run_scheduler() -> None: ...

class TestCase(unittest.TestCase): ...

class DeferrableTestCase(TestCase):
    @staticmethod
    def defer(delay: int, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None: ...

class DeferrableMethod: ...

class AsyncTestCase(DeferrableTestCase):
    timeout_ms: ClassVar[int]

class _ViewMixin:
    view_settings: ClassVar[dict[str, Any]]
    panel_name: str
    window: sublime.Window
    view: sublime.View

class ViewTestCase(_ViewMixin, TestCase): ...
class DeferrableViewTestCase(_ViewMixin, DeferrableTestCase): ...
class AsyncViewTestCase(_ViewMixin, AsyncTestCase): ...

class OverridePreferencesTestCase(DeferrableTestCase):
    override_preferences: ClassVar[dict[str, Any]]

class TempDirectoryTestCase(DeferrableTestCase):
    _temp_dir: ClassVar[str]
    window: ClassVar[sublime.Window]
