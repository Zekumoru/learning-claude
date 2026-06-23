from __future__ import annotations

from anthropic.types import ToolParam
from datetime import datetime, timedelta
from pathlib import Path
from shutil import which
from typing import Any
from uuid import uuid4

import os
import platform
import plistlib
import shlex
import subprocess

set_reminder_schema = ToolParam(
    {
        "name": "set_reminder",
        "description": (
            "Schedules a one-time desktop reminder on the user's local machine using the operating system's native scheduler. "
            "Use this tool when the user asks to be reminded about something at a specific future date and time. "
            "Do not use it for recurring reminders, vague reminder times, or reminders that should work across devices or cloud accounts. "
            "Supports two modes: (1) relative — provide 'duration' and 'unit' to schedule from now (preferred for 'remind me in X minutes' requests, avoids multi-step delay), "
            "or (2) absolute — provide 'timestamp' for a specific date/time. Do not provide both. "
            "Returns the reminder id, scheduled timestamp, detected platform, and scheduler backend used."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": (
                        "The reminder message to show to the user when the reminder fires. "
                        "Must be a non-empty human-readable string."
                    ),
                    "minLength": 1,
                    "maxLength": 500,
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": (
                        "The exact future date and time when the reminder should fire, formatted as an RFC3339/ISO-8601 datetime string. "
                        "Include a timezone offset whenever possible, for example '2026-06-17T15:30:00+02:00'. "
                        "Mutually exclusive with 'duration' and 'unit'. "
                        "If your runtime calls set_reminder directly, parse this string into a Python datetime first."
                    ),
                },
                "duration": {
                    "type": "number",
                    "description": (
                        "The amount of time from now until the reminder should fire. "
                        "Must be positive. Used together with 'unit'. Mutually exclusive with 'timestamp'."
                    ),
                    "exclusiveMinimum": 0,
                    "examples": [1, 5, 30],
                },
                "unit": {
                    "type": "string",
                    "description": "The unit of time for 'duration'. Required when 'duration' is provided.",
                    "enum": ["seconds", "minutes", "hours", "days", "weeks"],
                    "default": "minutes",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    }
)


class ReminderError(RuntimeError):
    pass


def parse_tool_datetime(value: str) -> datetime:
    """
    Parses an RFC3339/ISO-8601 datetime string from tool input.
    Example: "2026-06-17T15:30:00+02:00"
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def set_reminder(
    content: str,
    timestamp: datetime | None = None,
    duration: int | float | None = None,
    unit: str = "minutes",
) -> dict[str, Any]:
    if not content.strip():
        raise ValueError("content cannot be empty")

    has_timestamp = timestamp is not None
    has_duration = duration is not None

    if has_timestamp and has_duration:
        raise ValueError("provide either 'timestamp' or 'duration'/'unit', not both")

    if not has_timestamp and not has_duration:
        raise ValueError("provide either 'timestamp' or 'duration' with 'unit'")

    if has_duration:
        allowed_units = {"seconds", "minutes", "hours", "days", "weeks"}
        if unit not in allowed_units:
            raise ValueError(
                f"Unsupported unit '{unit}'. Supported: {', '.join(sorted(allowed_units))}"
            )
        if duration <= 0:
            raise ValueError("duration must be positive")
        scheduled_at = (
            datetime.now().astimezone() + timedelta(**{unit: duration})
        )
    else:
        if not isinstance(timestamp, datetime):
            raise TypeError("timestamp must be a datetime object")
        scheduled_at = _normalize_datetime(timestamp)
        if scheduled_at <= datetime.now().astimezone():
            raise ValueError("timestamp must be in the future")

    # macOS launchd and Windows schtasks are minute-granular.
    scheduled_at = _round_to_nearest_minute(scheduled_at)

    reminder_id = uuid4().hex
    system = platform.system()

    if system == "Darwin":
        backend = _schedule_macos(content, scheduled_at, reminder_id)
    elif system == "Windows":
        backend = _schedule_windows(content, scheduled_at, reminder_id)
    elif system == "Linux":
        backend = _schedule_linux(content, scheduled_at, reminder_id)
    else:
        raise ReminderError(f"Unsupported operating system: {system}")

    return {
        "id": reminder_id,
        "content": content,
        "scheduled_for": scheduled_at.isoformat(),
        "platform": system,
        "backend": backend,
    }


def _normalize_datetime(value: datetime) -> datetime:
    # Naive datetime is interpreted as local time.
    if value.tzinfo is None:
        return value.astimezone()

    return value.astimezone()


def _round_to_nearest_minute(value: datetime) -> datetime:
    if value.second == 0 and value.microsecond == 0:
        return value

    if value.second >= 30:
        return (value + timedelta(minutes=1)).replace(second=0, microsecond=0)

    return value.replace(second=0, microsecond=0)


def _run(command: list[str], *, input_text: str | None = None) -> None:
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise ReminderError(message or f"Command failed: {command[0]}")


def _schedule_macos(content: str, scheduled_at: datetime, reminder_id: str) -> str:
    if which("launchctl") is None:
        raise ReminderError("macOS reminder scheduling requires launchctl")

    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    data_dir = Path.home() / ".local" / "share" / "python-reminders"

    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    label = f"local.python_reminder.{reminder_id}"
    plist_path = launch_agents_dir / f"{label}.plist"
    script_path = data_dir / f"{label}.sh"

    escaped_content = _escape_applescript_string(content)

    script_path.write_text(
        f"""#!/bin/sh
/usr/bin/osascript -e 'display notification "{escaped_content}" with title "Reminder"'

/bin/launchctl bootout "gui/$(/usr/bin/id -u)" {shlex.quote(str(plist_path))} >/dev/null 2>&1 \\
  || /bin/launchctl unload {shlex.quote(str(plist_path))} >/dev/null 2>&1

/bin/rm -f {shlex.quote(str(plist_path))} "$0"
""",
        encoding="utf-8",
    )

    script_path.chmod(0o700)

    plist = {
        "Label": label,
        "ProgramArguments": ["/bin/sh", str(script_path)],
        "StartCalendarInterval": {
            "Year": scheduled_at.year,
            "Month": scheduled_at.month,
            "Day": scheduled_at.day,
            "Hour": scheduled_at.hour,
            "Minute": scheduled_at.minute,
        },
        "RunAtLoad": False,
        "StandardOutPath": str(data_dir / f"{label}.out.log"),
        "StandardErrorPath": str(data_dir / f"{label}.err.log"),
    }

    with plist_path.open("wb") as file:
        plistlib.dump(plist, file)

    try:
        _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)])
    except ReminderError:
        _run(["launchctl", "load", str(plist_path)])

    return "launchd"


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _schedule_windows(content: str, scheduled_at: datetime, reminder_id: str) -> str:
    schtasks = which("schtasks.exe") or which("schtasks")
    powershell = which("powershell.exe") or which("powershell")

    if schtasks is None:
        raise ReminderError("Windows reminder scheduling requires schtasks.exe")

    if powershell is None:
        raise ReminderError("Windows reminders require PowerShell")

    local_app_data = os.environ.get("LOCALAPPDATA")
    data_dir = (
        Path(local_app_data) / "PythonReminders"
        if local_app_data
        else Path.home() / "AppData" / "Local" / "PythonReminders"
    )

    data_dir.mkdir(parents=True, exist_ok=True)

    task_name = f"PythonReminder_{reminder_id}"
    script_path = data_dir / f"{task_name}.ps1"

    ps_content = _escape_powershell_single_quoted_string(content)
    ps_task_name = _escape_powershell_single_quoted_string(task_name)

    script_path.write_text(
        f"""
$content = '{ps_content}'

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show($content, 'Reminder') | Out-Null

Unregister-ScheduledTask -TaskName '{ps_task_name}' -Confirm:$false -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
""".strip(),
        encoding="utf-8",
    )

    task_command = subprocess.list2cmdline(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
    )

    _run(
        [
            schtasks,
            "/Create",
            "/SC",
            "ONCE",
            "/TN",
            task_name,
            "/TR",
            task_command,
            "/SD",
            scheduled_at.strftime("%m/%d/%Y"),
            "/ST",
            scheduled_at.strftime("%H:%M"),
            "/F",
            "/IT",
        ]
    )

    return "schtasks"


def _escape_powershell_single_quoted_string(value: str) -> str:
    return value.replace("'", "''")


def _schedule_linux(content: str, scheduled_at: datetime, reminder_id: str) -> str:
    notify_send = which("notify-send")

    if notify_send is None:
        raise ReminderError("Linux desktop reminders require notify-send")

    systemd_run = which("systemd-run")

    if systemd_run is not None:
        unit_name = f"python-reminder-{reminder_id}"
        on_calendar = scheduled_at.strftime("%Y-%m-%d %H:%M:%S")

        try:
            _run(
                [
                    systemd_run,
                    "--user",
                    f"--unit={unit_name}",
                    f"--on-calendar={on_calendar}",
                    "--collect",
                    notify_send,
                    "Reminder",
                    content,
                ]
            )
        except ReminderError:
            _run(
                [
                    systemd_run,
                    "--user",
                    f"--unit={unit_name}",
                    f"--on-calendar={on_calendar}",
                    notify_send,
                    "Reminder",
                    content,
                ]
            )

        return "systemd-run"

    at = which("at")

    if at is not None:
        at_time = scheduled_at.strftime("%H:%M %Y-%m-%d")

        display = os.environ.get("DISPLAY", "")
        dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")

        job = "\n".join(
            [
                f"export DISPLAY={shlex.quote(display)}",
                f"export DBUS_SESSION_BUS_ADDRESS={shlex.quote(dbus)}",
                f"{shlex.quote(notify_send)} {shlex.quote('Reminder')} {shlex.quote(content)}",
            ]
        )

        _run([at, at_time], input_text=job)
        return "at"

    raise ReminderError("Linux reminder scheduling requires either systemd-run or at")
