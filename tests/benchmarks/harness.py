"""Tiny benchmark harness that runs inside Sublime Text's plugin host.

Not a plugin (Sublime only loads top-level .py files) and not a test (not named
test*.py). Load it from a bench script with runpy so nothing is cached in
sys.modules across packages:

    H = runpy.run_path(str(Path(__file__).with_name("harness.py")))
    bench = H["Bench"]("MyPackage")

Run the bench script with $SCRATCH/tools/st-run.sh <script> -- --out <file.json>.
"""

import contextlib
import gc
import io
import json
import platform
import random
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any

import sublime
import sublime_plugin

# Internals used below (all_callbacks, view_event_listeners, reload_plugin, ...)
# are not part of the public API stubs.
_sp: Any = sublime_plugin

RUNS = 20
WARMUP = 3
SIZES = {"small": 200, "10k": 10_000, "100k": 100_000}

_WORDS = [
    *("alpha", "beta", "gamma", "delta", "epsilon", "zeta", "theta", "lambda", "sigma"),
    *("omega", "value", "index", "result", "config", "handler", "buffer", "render"),
    *("widget", "module", "import", "return", "class"),
]


def fixture_text(lines: int, kind: str = "code", seed: int = 1) -> str:
    """Deterministic text with `lines` lines. kind: code | css | prose."""
    rnd = random.Random(seed)
    out = []
    for i in range(lines):
        w = rnd.sample(_WORDS, 4)
        if kind == "css":
            out.append(
                f".{w[0]}-{i} {{ {w[1]}: {rnd.randint(0, 999)}px; color: #{i % 4096:03x}; }}"
            )
        elif kind == "prose":
            out.append(" ".join(rnd.choice(_WORDS) for _ in range(rnd.randint(4, 14))))
        else:
            indent = "    " * (i % 4)
            out.append(f"{indent}{w[0]}_{i} = {w[1]}({w[2]!r}, {rnd.randint(0, 9999)})  # {w[3]}")
    return "\n".join(out) + "\n"


def scratch_view(window: sublime.Window, text: str, syntax: str | None = None) -> sublime.View:
    """New scratch tab (never prompts to save) filled with `text`."""
    view = window.new_file()
    view.set_scratch(True)
    view.settings().set("auto_complete", False)
    if syntax:
        view.assign_syntax(syntax)
    view.run_command("append", {"characters": text, "force": True, "scroll_to_end": False})
    return view


def close_views(*views: sublime.View) -> None:
    for v in views:
        if v.is_valid():
            v.set_scratch(True)
            v.close()


def event_listeners(event: str, module_prefix: str) -> list[Any]:
    """EventListener instances of one package registered for `event`."""
    return [
        obj
        for obj in _sp.all_callbacks.get(event, [])
        if type(obj).__module__.startswith(module_prefix)
    ]


def view_listeners(view: sublime.View, module_prefix: str) -> list[Any]:
    """ViewEventListener instances of one package attached to `view`."""
    return [
        obj
        for obj in _sp.view_event_listeners.get(view.view_id, [])
        if type(obj).__module__.startswith(module_prefix)
    ]


class Bench:
    def __init__(self, package: str) -> None:
        self.package = package
        self.results: list[dict[str, Any]] = []
        self.out: str | None = None
        if "--out" in sys.argv:
            self.out = sys.argv[sys.argv.index("--out") + 1]

    def time(
        self,
        name: str,
        fn: Callable[[Any], Any],
        *,
        setup: Callable[[], Any] | None = None,
        runs: int = RUNS,
        warmup: int = WARMUP,
    ) -> dict[str, Any]:
        """Median of `runs` timed calls of fn(setup()) after `warmup` untimed ones.

        setup() runs before every call and is not timed; its return value is
        passed to fn (None if there is no setup). GC is paused while timing.
        """
        samples = []
        for i in range(warmup + runs):
            arg = setup() if setup else None
            gc.collect()
            gc.disable()
            try:
                t0 = time.perf_counter()
                fn(arg)
                dt = time.perf_counter() - t0
            finally:
                gc.enable()
            if i >= warmup:
                samples.append(dt * 1000)
        r = {
            "name": name,
            "unit": "ms",
            "median": statistics.median(samples),
            "min": min(samples),
            "max": max(samples),
            "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
            "runs": runs,
        }
        self.results.append(r)
        print(
            f"{name:<50} median {r['median']:9.3f} ms   min {r['min']:9.3f}   max {r['max']:9.3f}"
        )
        return r

    def memory(self, name: str, fn: Callable[[], Any]) -> dict[str, Any]:
        """Python heap allocated by fn() and still alive afterwards (tracemalloc), in KiB."""
        gc.collect()
        tracemalloc.start()
        try:
            before = tracemalloc.take_snapshot()
            keep = fn()  # noqa: F841 - keep the result alive while measuring
            after = tracemalloc.take_snapshot()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        retained = sum(s.size_diff for s in after.compare_to(before, "filename"))
        r = {"name": name, "unit": "KiB", "median": retained / 1024, "peak_kib": peak / 1024}
        self.results.append(r)
        print(f"{name:<50} retained {r['median']:9.1f} KiB   peak {r['peak_kib']:9.1f} KiB")
        return r

    def reload_time(self, module: str, **kw: Any) -> dict[str, Any]:
        """Plugin load time: fresh import + registration + plugin_loaded()."""

        def run(_: Any) -> None:
            with contextlib.redirect_stdout(io.StringIO()):  # drop "reloading plugin" lines
                _sp.unload_plugin(module)
                _sp.reload_plugin(module)

        return self.time(f"load: {module}", run, **kw)

    def save(self) -> None:
        meta = {
            "package": self.package,
            "st_build": sublime.version(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
            "when": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self.out:
            Path(self.out).write_text(json.dumps({"meta": meta, "results": self.results}, indent=2))
            print(f"saved {len(self.results)} results -> {self.out}")
