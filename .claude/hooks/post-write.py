#!/usr/bin/env python3
"""
Post-Write Hook - Automated Code Quality Checks (Python Version)

Features:
1. Automatically run Black formatting
2. Automatically run isort import sorting
3. Run Flake8 checks (critical errors only)

Differences from Shell version:
- Uses Python subprocess to call tools
- Better error handling
- Easier to extend
- Slightly slower startup (~50ms) but minimal impact on user experience
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def load_input():
    """Load JSON input from stdin (if available)"""
    try:
        if not sys.stdin.isatty():
            return json.load(sys.stdin)
        return None
    except json.JSONDecodeError:
        return None


def should_run_checks(file_path):
    """Check if quality checks should be run"""
    # Only run on Python files
    if not file_path.endswith(".py"):
        return False

    # Exclude virtual environments and cache directories
    exclude_patterns = [
        "/venv/",
        "/env/",
        "/.venv/",
        "/site-packages/",
        "/__pycache__/",
        "/.pytest_cache/",
        "/node_modules/",
    ]

    return not any(pattern in file_path for pattern in exclude_patterns)


def is_api_file(file_path):
    """Check if this is an API route file"""
    api_patterns = [
        "/app/api/",
        "/app/route/",
    ]
    return any(pattern in file_path for pattern in api_patterns)


def run_black(file_path, project_dir):
    """Run Black formatting"""
    try:
        print(f"🎨 Running Black formatter on {file_path}...", file=sys.stderr)

        # Try to use black from virtual environment
        venv_black = os.path.join(project_dir, "venv", "bin", "black")
        black_cmd = venv_black if os.path.exists(venv_black) else "black"

        result = subprocess.run(
            [black_cmd, file_path], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return {"success": True, "message": "Black formatting applied successfully"}
        else:
            return {
                "success": False,
                "message": f"Black failed: {result.stderr or result.stdout}",
                "can_continue": True,
            }

    except FileNotFoundError:
        return {
            "success": False,
            "message": "Black not found. Install: pip install black",
            "can_continue": True,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Black timed out", "can_continue": True}
    except Exception as e:
        return {
            "success": False,
            "message": f"Black error: {str(e)}",
            "can_continue": True,
        }


def run_isort(file_path, project_dir):
    """Run isort import sorting"""
    try:
        print(f"📦 Running isort on {file_path}...", file=sys.stderr)

        # Try to use isort from virtual environment
        venv_isort = os.path.join(project_dir, "venv", "bin", "isort")
        isort_cmd = venv_isort if os.path.exists(venv_isort) else "isort"

        result = subprocess.run(
            [isort_cmd, file_path], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            return {"success": True, "message": "Import sorting applied successfully"}
        else:
            return {
                "success": False,
                "message": f"isort failed: {result.stderr or result.stdout}",
                "can_continue": True,
            }

    except FileNotFoundError:
        return {
            "success": False,
            "message": "isort not found. Install: pip install isort",
            "can_continue": True,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "isort timed out", "can_continue": True}
    except Exception as e:
        return {
            "success": False,
            "message": f"isort error: {str(e)}",
            "can_continue": True,
        }


def run_flake8(file_path, project_dir):
    """Run Flake8 checks (critical errors only)"""
    try:
        print(f"🔍 Running Flake8 critical checks on {file_path}...", file=sys.stderr)

        # Try to use flake8 from virtual environment
        venv_flake8 = os.path.join(project_dir, "venv", "bin", "flake8")
        flake8_cmd = venv_flake8 if os.path.exists(venv_flake8) else "flake8"

        # Only check critical errors: E9, F63, F7, F82
        result = subprocess.run(
            [flake8_cmd, "--select=E9,F63,F7,F82", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {"success": True, "message": "No critical errors found"}
        else:
            # Flake8 returns non-zero when errors are found
            errors = result.stdout or result.stderr
            return {
                "success": False,
                "message": f"Critical errors found:\n{errors}",
                "can_continue": False,  # Critical errors should be fixed
                "errors": parse_flake8_errors(errors),
            }

    except FileNotFoundError:
        return {
            "success": False,
            "message": "Flake8 not found. Install: pip install flake8",
            "can_continue": True,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Flake8 timed out", "can_continue": True}
    except Exception as e:
        return {
            "success": False,
            "message": f"Flake8 error: {str(e)}",
            "can_continue": True,
        }


def parse_flake8_errors(output):
    """Parse Flake8 error output"""
    errors = []
    for line in output.strip().split("\n"):
        if line.strip():
            # Format: file.py:line:col: CODE message
            parts = line.split(":", 3)
            if len(parts) >= 4:
                errors.append(
                    {
                        "file": parts[0],
                        "line": int(parts[1]) if parts[1].isdigit() else 0,
                        "column": int(parts[2]) if parts[2].isdigit() else 0,
                        "message": parts[3].strip(),
                    }
                )
    return errors


def generate_report(results):
    """Generate quality check report"""
    lines = ["\n📊 Code Quality Report\n"]
    lines.append("═" * 50)

    # Black results
    if results["black"]:
        icon = "✅" if results["black"]["success"] else "⚠️"
        lines.append(f"\n{icon} Black Formatter")
        lines.append(f'   {results["black"]["message"]}')

    # isort results
    if results["isort"]:
        icon = "✅" if results["isort"]["success"] else "⚠️"
        lines.append(f"\n{icon} isort")
        lines.append(f'   {results["isort"]["message"]}')

    # Flake8 results
    if results["flake8"]:
        icon = "✅" if results["flake8"]["success"] else "❌"
        lines.append(f"\n{icon} Flake8 Critical Checks")
        lines.append(f'   {results["flake8"]["message"]}')

        if results["flake8"].get("errors"):
            lines.append("\n   Errors to fix:")
            for error in results["flake8"]["errors"]:
                lines.append(f'   - Line {error["line"]}: {error["message"]}')

    lines.append("\n" + "═" * 50)
    return "\n".join(lines)


def main():
    # Get file path
    input_data = load_input()

    if input_data:
        # Get from JSON input (Claude Code invocation)
        tool_input = input_data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        project_dir = input_data.get("cwd", os.getcwd())
    else:
        # Get from environment variables (manual testing)
        file_path = os.environ.get("TOOL_INPUT_file_path", "")
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    if not file_path:
        print("No file path provided", file=sys.stderr)
        sys.exit(1)

    # Check if quality checks should be run
    if not should_run_checks(file_path):
        sys.exit(0)  # Silent exit for non-Python files

    # Run all checks
    results = {
        "black": run_black(file_path, project_dir),
        "isort": run_isort(file_path, project_dir),
        "flake8": run_flake8(file_path, project_dir),
    }

    # Generate report
    report = generate_report(results)

    # Check if this is an API file for additional suggestions
    if is_api_file(file_path):
        report += "\n\n💡 API endpoint detected!"
        report += "\n   Run /api-test to validate this endpoint automatically."
        report += "\n   (Tests API response + database validation)"

    # Decide if user attention is needed
    has_critical_errors = (
        results["flake8"]
        and not results["flake8"]["success"]
        and not results["flake8"].get("can_continue", False)
    )

    # Output in JSON format for Claude Code
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "displayText": report,
        }
    }

    # For critical errors, block the operation
    if has_critical_errors:
        output["hookSpecificOutput"]["permissionDecision"] = "block"
        output["hookSpecificOutput"][
            "permissionDecisionReason"
        ] = "Critical Flake8 errors must be fixed before proceeding"
        print(json.dumps(output), file=sys.stdout)
        sys.exit(1)

    # For warnings or success, show the report
    print(json.dumps(output), file=sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
