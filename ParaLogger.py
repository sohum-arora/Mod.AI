"""
ParaLogger Backend — Team 22985 Paraducks
FastAPI server that pulls logs from FTC Control Hub via ADB over WiFi,
parses ParaLogger entries, and serves filtered post-match data.

Requirements:
    pip install fastapi uvicorn adb-shell

Usage:
    python paralogger_server.py
    Then open http://localhost:8000 in your browser.

ADB WiFi Setup (do once per session):
    1. Connect Control Hub via USB
    2. Run: adb tcpip 5555
    3. Disconnect USB
    4. Run: adb connect 192.168.43.1:5555  (Control Hub default IP on RC WiFi)
    OR just hit /api/connect?ip=192.168.43.1 from the frontend
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import subprocess
import re
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

app = FastAPI(title="ParaLogger", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve frontend ────────────────────────────────────────────────────────────
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(FRONTEND_PATH):
    app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

@app.get("/")
def serve_frontend():
    index = os.path.join(FRONTEND_PATH, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "ParaLogger API running. Place index.html in /static/"}

# ── ADB Helpers ───────────────────────────────────────────────────────────────

def run_adb(args: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Run an adb command, return (success, output)."""
    try:
        result = subprocess.run(
            ["adb"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "adb not found. Install Android Platform Tools and add to PATH."
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out."
    except Exception as e:
        return False, str(e)


def is_connected() -> bool:
    ok, out = run_adb(["devices"])
    lines = [l for l in out.splitlines() if l and "List of devices" not in l]
    return any("device" in l for l in lines)


# ── Log Parsing ───────────────────────────────────────────────────────────────

# Matches ParaLogger output format: [D/I/W/E][OpModeName/TAG] message
# e.g.: I/ParaLogger(1234): [I][TeleOp/TURRET] State → LOCKED
PARALOGGER_PATTERN = re.compile(
    r"\[([DIWE])\]\[([^/]+)/([^\]]+)\]\s+(.+)"
)

LEVEL_MAP = {"D": "DEBUG", "I": "INFO", "W": "WARN", "E": "ERROR"}

def parse_log_line(line: str) -> Optional[dict]:
    """Parse a single logcat line for ParaLogger entries."""
    match = PARALOGGER_PATTERN.search(line)
    if not match:
        return None
    level_char, opmode, tag, message = match.groups()
    return {
        "level":  LEVEL_MAP.get(level_char, level_char),
        "opmode": opmode.strip(),
        "tag":    tag.strip(),
        "msg":    message.strip(),
        "raw":    line.strip(),
    }


def fetch_logs_from_device(lines: int = 2000) -> list[dict]:
    """Pull recent logcat lines from connected Control Hub."""
    ok, out = run_adb([
        "logcat", "-d",           # dump and exit
        "-t", str(lines),         # last N lines
        "-s", "ParaLogger:*"      # only ParaLogger tag
    ], timeout=15)

    if not ok:
        raise HTTPException(status_code=503, detail=f"ADB error: {out}")

    entries = []
    for i, line in enumerate(out.splitlines()):
        parsed = parse_log_line(line)
        if parsed:
            parsed["id"] = i
            entries.append(parsed)
    return entries


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    """Check ADB + device connection status."""
    connected = is_connected()
    ok, devices_out = run_adb(["devices"])
    return {
        "adb_available": ok or "not found" not in devices_out,
        "device_connected": connected,
        "devices_raw": devices_out,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/connect")
def connect_wifi(ip: str = Query(default="192.168.43.1", description="Control Hub IP")):
    """Connect to Control Hub over WiFi ADB."""
    ok, out = run_adb(["connect", f"{ip}:5555"], timeout=8)
    return {
        "success": ok or "connected" in out.lower(),
        "message": out,
        "ip": ip,
    }


@app.get("/api/disconnect")
def disconnect():
    ok, out = run_adb(["disconnect"])
    return {"success": ok, "message": out}


@app.get("/api/logs")
def get_logs(
    lines: int = Query(default=2000, ge=100, le=10000, description="How many logcat lines to pull"),
):
    """
    Pull all ParaLogger logs from the connected device.
    Returns every entry (DEBUG, INFO, WARN, ERROR).
    """
    if not is_connected():
        raise HTTPException(status_code=503, detail="No device connected. Hit /api/connect first.")
    entries = fetch_logs_from_device(lines)
    return {
        "total": len(entries),
        "entries": entries,
        "pulled_at": datetime.now().isoformat(),
    }


@app.get("/api/match-review")
def match_review(
    lines: int = Query(default=2000, ge=100, le=10000),
):
    """
    Post-match review endpoint.
    Returns only WARN and ERROR entries, grouped by subsystem tag.
    This is the main endpoint the frontend uses after a match.
    """
    if not is_connected():
        raise HTTPException(status_code=503, detail="No device connected. Hit /api/connect first.")

    all_entries = fetch_logs_from_device(lines)

    # Filter to WARN + ERROR only
    flagged = [e for e in all_entries if e["level"] in ("WARN", "ERROR")]

    # Group by tag
    by_tag: dict[str, list] = {}
    for entry in flagged:
        by_tag.setdefault(entry["tag"], []).append(entry)

    # Summary stats
    error_count = sum(1 for e in flagged if e["level"] == "ERROR")
    warn_count  = sum(1 for e in flagged if e["level"] == "WARN")

    # Per-subsystem summary
    subsystem_summary = [
        {
            "tag":    tag,
            "errors": sum(1 for e in entries if e["level"] == "ERROR"),
            "warns":  sum(1 for e in entries if e["level"] == "WARN"),
            "entries": entries,
        }
        for tag, entries in sorted(by_tag.items(), key=lambda x: -len(x[1]))
    ]

    return {
        "total_flagged": len(flagged),
        "error_count":   error_count,
        "warn_count":    warn_count,
        "clean":         len(flagged) == 0,
        "subsystems":    subsystem_summary,
        "pulled_at":     datetime.now().isoformat(),
    }


@app.get("/api/clear-log")
def clear_logcat():
    """Clear the logcat buffer on the device (run before a match to start fresh)."""
    if not is_connected():
        raise HTTPException(status_code=503, detail="No device connected.")
    ok, out = run_adb(["logcat", "-c"])
    return {"success": ok, "message": out or "Logcat cleared."}


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n╔══════════════════════════════════════╗")
    print("║   ParaLogger Server — 22985 Paraducks ║")
    print("╚══════════════════════════════════════╝")
    print("  → http://localhost:8000")
    print("  → API docs: http://localhost:8000/docs\n")
    uvicorn.run("ParaLogger:app", host="localhost", port=8000)