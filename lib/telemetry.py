import urllib.parse
import urllib.request
import uuid
from typing import Any

import sublime

from .config import get_settings

__doc__ = "Telemetry module: sends anonymous Emmet usage stats to improve user experience"

TRACK_ID = "UA-171521327-1"
HOST = "https://www.google-analytics.com/batch"
MAX_BATCH = 20


scheduled = False
queue: list[dict[str, Any]] = []
"Queue for pending tracking records"


def track_action(action: str, label: str | None = None, value: str | None = None) -> None:
    if get_settings("telemetry"):
        send_tracking_action(action, label, value)


def send_tracking_action(action: str, label: str | None = None, value: str | None = None) -> None:
    payload = {"t": "event", "ec": "Actions", "ea": action}

    if label is not None:
        payload["el"] = label

    if value is not None:
        payload["ev"] = value

    push_queue(payload)


def push_queue(item: dict[str, Any]) -> None:
    queue.append(item)
    schedule_send()


def schedule_send() -> None:
    global scheduled
    if not scheduled:
        scheduled = True
        sublime.set_timeout_async(_flush_queue, 30000)


def get_user_agent() -> str:
    platforms = {
        "osx": "Macintosh",
        "linux": "X11; Linux",
        "windows": "Windows NT 10.0; Win64; x64",
    }

    try:
        version = sublime.load_resource(f"Packages/{__name__.split('.')[0]}/VERSION")
    except OSError:
        version = "1.0.0"

    return f"Mozilla/5.0 ({platforms.get(sublime.platform())}) EmmetTracker/{version.strip()}"


def _flush_queue() -> None:
    global scheduled, queue
    scheduled = False
    if not queue:
        # Seems like plugin was reloaded, skip queue
        return

    _queue = queue[:MAX_BATCH]
    queue = queue[MAX_BATCH:]
    entries = []

    for q in _queue:
        params = {"v": 1, "tid": TRACK_ID, "cid": get_settings("uid", "000")}
        params.update(q)
        entries.append(urllib.parse.urlencode(params))

    data = "\n".join(entries).encode("ascii")
    req = urllib.request.Request(
        HOST,
        data,
        method="POST",
        headers={"User-Agent": get_user_agent(), "Content-Length": str(len(data))},
    )
    # print('send req %s to %s as %s' % (req, HOST, ua))
    # print('payload: %s' % data)

    try:
        with urllib.request.urlopen(req):  # noqa: S310 - fixed https:// HOST
            pass
    except OSError as err:  # URLError, timeouts, TLS errors: telemetry is best effort
        print(f"Emmet: telemetry request failed: {err}")

    if queue:
        # print('schedule next request')
        schedule_send()


def check_telemetry() -> None:
    settings = sublime.load_settings("Emmet.sublime-settings")
    updated = False
    if not settings.get("uid"):
        uid = str(uuid.uuid4())
        settings.set("uid", uid)
        send_tracking_action("Init", "install")
        updated = True

    if settings.get("telemetry", None) is None:
        allow_telemetry = ask_for_telemetry()
        send_tracking_action("Init", "Enable Telemetry", str(allow_telemetry))
        settings.set("telemetry", bool(allow_telemetry))
        updated = True

    if updated:
        sublime.save_settings("Emmet.sublime-settings")


def ask_for_telemetry() -> bool:
    return sublime.ok_cancel_dialog(
        """
Would you like to enable anonymous usage stats for Emmet?

It will help me better understand how Emmet is used and prioritize future improvements.

You can enable/disable telemetry later via Preferences > Package Settings > Emmet > Settings
""",
        "Yes, enable telemetry",
    )
