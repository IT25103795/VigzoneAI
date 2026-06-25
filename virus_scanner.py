"""
Vigzone AI - Virus Scanner
===========================
Scans uploaded file bytes for malware using ClamAV (clamscan CLI).

Strategy:
  1. Write bytes to a secure temp file.
  2. Call `clamscan --no-summary <file>` via subprocess.
  3. Parse stdout for FOUND/OK/ERROR.
  4. Remove the temp file.

If ClamAV is not installed or signatures are missing we emit a warning
but do NOT block the upload — the admin can enforce strict mode via
VIRUS_SCAN_STRICT=true in .env.

Exit codes from clamscan:
  0  → clean
  1  → virus found
  2  → error (missing DB, permission, etc.)
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# If True, reject uploads when scanner is unavailable (no ClamAV / no DB).
# If False (default), allow uploads with a warning when scanner can't run.
STRICT_MODE: bool = os.getenv("VIRUS_SCAN_STRICT", "false").lower() in ("1", "true", "yes")

# Timeout in seconds for a single scan (10 MB file scan is usually < 2 s).
SCAN_TIMEOUT: int = int(os.getenv("VIRUS_SCAN_TIMEOUT", "30"))


@dataclass
class ScanResult:
    clean: bool           # True  → no threat detected
    threat: str | None    # e.g. "Win.Malware.Agent-123" or None
    scanner_available: bool
    message: str          # human-readable summary


def _clamscan_available() -> bool:
    """Check if clamscan binary exists in PATH."""
    try:
        result = subprocess.run(
            ["clamscan", "--version"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


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
        fd, tmp_path = tempfile.mkstemp(prefix="vigzone_scan_", suffix=f"_{filename}")
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
        msg = f"Virus scanner error: {err_detail}"
        logger.error("clamscan error on '%s': %s", filename, err_detail)
        if STRICT_MODE:
            return ScanResult(clean=False, threat="SCANNER_ERROR",
                              scanner_available=True, message=msg)
        return ScanResult(clean=True, threat=None,
                          scanner_available=True,
                          message=f"Scanner warning (non-fatal): {err_detail}")

    except subprocess.TimeoutExpired:
        msg = "Virus scan timed out."
        logger.error("clamscan timed out scanning '%s'", filename)
        if STRICT_MODE:
            return ScanResult(clean=False, threat="SCAN_TIMEOUT",
                              scanner_available=True, message=msg)
        return ScanResult(clean=True, threat=None,
                          scanner_available=True, message=msg)

    except Exception as exc:
        msg = f"Virus scanner exception: {exc}"
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
