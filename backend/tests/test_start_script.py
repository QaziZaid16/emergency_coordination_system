import os
from pathlib import Path
import subprocess


START_SCRIPT = Path(__file__).parents[1] / "start.sh"


def _mock_commands(directory: Path):
    directory.mkdir()
    commands = {
        "alembic": """#!/bin/sh
printf 'alembic:%s\\n' "$*" >> "$CALL_LOG"
exit "${ALEMBIC_EXIT_CODE:-0}"
""",
        "uvicorn": """#!/bin/sh
printf 'uvicorn:%s\\n' "$*" >> "$CALL_LOG"
exit 0
""",
        "sleep": """#!/bin/sh
printf 'sleep:%s\\n' "$*" >> "$CALL_LOG"
exit 0
""",
    }
    for name, content in commands.items():
        executable = directory / name
        executable.write_text(content)
        executable.chmod(0o755)


def _run_start(tmp_path, *arguments, port="8000", alembic_exit_code="0"):
    bin_directory = tmp_path / "bin"
    _mock_commands(bin_directory)
    call_log = tmp_path / "calls.log"
    environment = {
        **os.environ,
        "PATH": f"{bin_directory}{os.pathsep}{os.environ.get('PATH', '')}",
        "CALL_LOG": str(call_log),
        "PORT": port,
        "ALEMBIC_EXIT_CODE": alembic_exit_code,
    }
    result = subprocess.run(
        ["sh", str(START_SCRIPT), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    calls = call_log.read_text().splitlines() if call_log.exists() else []
    return result, calls


def test_default_startup_migrates_before_starting_uvicorn(tmp_path):
    result, calls = _run_start(tmp_path, port="8123")

    assert result.returncode == 0
    assert calls == [
        "alembic:upgrade head",
        "uvicorn:app.main:app --host 0.0.0.0 --port 8123",
    ]


def test_migrate_mode_exits_without_starting_uvicorn(tmp_path):
    result, calls = _run_start(tmp_path, "migrate")

    assert result.returncode == 0
    assert calls == ["alembic:upgrade head"]


def test_migration_failure_retries_but_never_starts_uvicorn(tmp_path):
    result, calls = _run_start(tmp_path, alembic_exit_code="1")

    assert result.returncode != 0
    assert calls.count("alembic:upgrade head") == 5
    assert calls.count("sleep:5") == 1
    assert calls.count("sleep:10") == 1
    assert calls.count("sleep:15") == 1
    assert calls.count("sleep:20") == 1
    assert not any(call.startswith("uvicorn:") for call in calls)


def test_unknown_migration_command_is_rejected_before_side_effects(tmp_path):
    result, calls = _run_start(tmp_path, "migrate-and-serve")

    assert result.returncode == 2
    assert calls == []
