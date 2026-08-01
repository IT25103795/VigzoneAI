"""
Vigzone AI - Virus Scanner
===========================
Scans uploaded file bytes for malware using ClamAV (clamscan CLI).

Strategy:
  1. Write bytes to a secure temp file.
  2. Call `clamscan --no-summary <file>` via subprocess.
  3. Parse stdout for FOUND/OK/ERROR.
  4. Remove the temp file.

Production startup requires strict mode and a working signature database.
Development can opt into warning-only behavior with VIRUS_SCAN_STRICT=false.

Exit codes from clamscan:
  0  → clean
  1  → virus found
  2  → error (missing DB, permission, etc.)
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# If True, reject uploads when scanner is unavailable (no ClamAV / no DB).
# If False (default), allow uploads with a warning when scanner can't run.
STRICT_MODE: bool = os.getenv("VIRUS_SCAN_STRICT", "false").lower() in ("1", "true", "yes")

# Timeout in seconds for a single scan (10 MB file scan is usually < 2 s).
SCAN_TIMEOUT: int = int(os.getenv("VIRUS_SCAN_TIMEOUT", "30"))
_availability_cache: tuple[float, bool] = (0.0, False)


@dataclass
class ScanResult:
    clean: bool           # True  → no threat detected
    threat: str | None    # e.g. "Win.Malware.Agent-123" or None
    scanner_available: bool
    message: str          # human-readable summary


def _clamscan_available() -> bool:
    """Check if clamscan binary exists in PATH."""
    global _availability_cache
    now = time.monotonic()
    if now - _availability_cache[0] < 60:
        return _availability_cache[1]
    try:
        result = subprocess.run(
            ["clamscan", "--version"],
            capture_output=True, timeout=5
        )
        available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        available = False
    _availability_cache = (now, available)
    return available


def scanner_healthcheck() -> bool:
    """Return true only when ClamAV can complete a real harmless scan."""

    result = scan_bytes(b"Vigzone AI scanner health check\n", "healthcheck.txt")
    return bool(result.clean and result.scanner_available)


def scan_bytes(data: bytes, filename: str = "upload") -> ScanResult:
    """
    Scan *data* for viruses. Returns a ScanResult.

    Never raises — caller inspects .clean and .scanner_available.
    """
    if not _clamscan_available():
        msg = "ClamAV is not installed. Virus scanning is unavailable."
        logger.warning(msg)
        if STRICT_MODE:
            # Treat as blocked in strict mode
            return ScanResult(clean=False, threat="SCANNER_UNAVAILABLE",
                              scanner_available=False, message=msg)
        return ScanResult(clean=True, threat=None,
                          scanner_available=False, message=msg)

    # Write to a named temp file (clamscan needs a path, not stdin)
    tmp_path: str | None = None
    try:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename))[:80]
        fd, tmp_path = tempfile.mkstemp(prefix="vigzone_scan_", suffix=f"_{safe_name}")
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

        result = subprocess.run(
            ["clamscan", "--no-summary", tmp_path],
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0:
            return ScanResult(
                clean=True, threat=None, scanner_available=True,
                message="No threats detected."
            )

        if result.returncode == 1:
            # Parse "path: ThreatName FOUND"
            threat = "Unknown"
            for line in stdout.splitlines():
                if "FOUND" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        threat = parts[-1].replace("FOUND", "").strip()
                    break
            msg = f"Threat detected: {threat}"
            logger.warning("Virus scan blocked upload '%s': %s", filename, threat)
            return ScanResult(clean=False, threat=threat,
                              scanner_available=True, message=msg)

        # returncode == 2  → scanner error (usually missing virus DB)
        err_detail = stderr or stdout or "unknown error"
        msg = "Virus scanner could not complete the scan."
        logger.error("clamscan error on '%s': %s", filename, err_detail)
        if STRICT_MODE:
            return ScanResult(clean=False, threat="SCANNER_ERROR",
                              scanner_available=False, message=msg)
        return ScanResult(clean=True, threat=None,
                          scanner_available=False,
                          message="Scanner warning: scan could not be completed.")

    except subprocess.TimeoutExpired:
        msg = "Virus scan timed out."
        logger.error("clamscan timed out scanning '%s'", filename)
        if STRICT_MODE:
            return ScanResult(clean=False, threat="SCAN_TIMEOUT",
                              scanner_available=False, message=msg)
        return ScanResult(clean=True, threat=None,
                          scanner_available=False, message=msg)

    except Exception:
        msg = "Virus scanner encountered an unexpected error."
        logger.exception("Unexpected error during virus scan of '%s'", filename)
        if STRICT_MODE:
            return ScanResult(clean=False, threat="SCAN_ERROR",
                              scanner_available=False, message=msg)
        return ScanResult(clean=True, threat=None,
                          scanner_available=False, message=msg)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
