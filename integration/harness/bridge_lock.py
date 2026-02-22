#!/usr/bin/env python3
"""POSIX file locking utilities for STS Bridge coordination.

Provides exclusive access to the CommunicationMod bridge using kernel-managed
file locks that auto-release on process death.

Usage:
    from harness.bridge_lock import bridge_lock, get_lock_info, BridgeLockedError

    # Context manager (blocks until lock acquired)
    with bridge_lock("my_project"):
        # Exclusive access guaranteed
        game.get_state()

    # Non-blocking check
    info = get_lock_info()
    if info:
        print(f"Bridge locked by {info['project']} (PID {info['pid']})")

    # With timeout
    try:
        with bridge_lock("my_project", timeout=30.0):
            game.get_state()
    except TimeoutError:
        print("Could not acquire lock within 30 seconds")
"""
import fcntl
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


# Default lock file location
LOCK_DIR = Path("/tmp/sts_bridge/.coordinator")
LOCK_FILE = LOCK_DIR / "lock"


@dataclass
class LockInfo:
    """Information about a held lock."""
    project: str
    pid: int
    acquired_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "pid": self.pid,
            "acquired_at": self.acquired_at
        }


class BridgeLockedError(Exception):
    """Raised when bridge is locked by another process."""
    def __init__(self, lock_info: Optional[LockInfo], lock_file: Path):
        self.lock_info = lock_info
        self.lock_file = lock_file
        if lock_info:
            message = (
                f"Bridge is locked by '{lock_info.project}' (PID {lock_info.pid})\n"
                f"Lock file: {lock_file}\n\n"
                f"Options:\n"
                f"  1. Wait for the current process to finish\n"
                f"  2. Kill the process: kill {lock_info.pid}\n"
                f"  3. Force remove lock: rm {lock_file}\n"
                f"     (Only if the process has crashed)"
            )
        else:
            message = f"Bridge is locked\nLock file: {lock_file}"
        super().__init__(message)


def _ensure_lock_dir():
    """Ensure the lock directory exists."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)


def get_lock_info() -> Optional[LockInfo]:
    """Get information about who holds the lock.

    Returns:
        LockInfo if lock is held, None otherwise.
    """
    _ensure_lock_dir()

    if not LOCK_FILE.exists():
        return None

    try:
        with open(LOCK_FILE, 'r') as f:
            content = f.read().strip()

        lines = content.split('\n')
        if len(lines) >= 2:
            project = lines[0]
            pid = int(lines[1])
            acquired_at = float(lines[2]) if len(lines) > 2 else None

            # Check if process is still alive
            try:
                os.kill(pid, 0)  # Signal 0 = check if process exists
                return LockInfo(project=project, pid=pid, acquired_at=acquired_at)
            except OSError:
                # Process is dead, stale lock file
                # Clean it up
                try:
                    LOCK_FILE.unlink()
                except FileNotFoundError:
                    pass
                return None
        return None
    except (FileNotFoundError, ValueError, IndexError):
        return None


def is_locked() -> bool:
    """Check if the bridge is currently locked.

    Returns:
        True if locked, False otherwise.
    """
    return get_lock_info() is not None


def try_acquire_lock(project: str) -> bool:
    """Try to acquire the lock without blocking.

    Args:
        project: Name of the project acquiring the lock.

    Returns:
        True if lock acquired, False if already locked.
    """
    _ensure_lock_dir()

    try:
        with open(LOCK_FILE, 'w') as f:
            # Write lock info first
            f.write(f"{project}\n{os.getpid()}\n{time.time()}\n")
            f.flush()

            # Try non-blocking lock
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                # Lock held by another process
                # Clean up our file write
                try:
                    LOCK_FILE.unlink()
                except FileNotFoundError:
                    pass
                return False
    except Exception:
        return False


def release_lock():
    """Release the lock if held by current process.

    This is normally called automatically by the context manager,
    but can be called manually if needed.
    """
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def bridge_lock(project: str, timeout: Optional[float] = None):
    """Acquire exclusive lock on the bridge.

    Args:
        project: Name of the project acquiring the lock.
        timeout: Maximum seconds to wait for lock (None = wait forever).

    Yields:
        LockInfo for the acquired lock.

    Raises:
        TimeoutError: If timeout is specified and lock not acquired in time.
        BridgeLockedError: If non-blocking check finds lock held by another.

    Example:
        with bridge_lock("my_test", timeout=30.0) as info:
            print(f"Lock acquired for {info.project}")
            # Do work with exclusive bridge access
    """
    _ensure_lock_dir()

    start_time = time.time()
    lock_file = None

    while True:
        # Check if already locked
        existing = get_lock_info()
        if existing and existing.pid != os.getpid():
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(
                        f"Could not acquire lock within {timeout}s. "
                        f"Locked by '{existing.project}' (PID {existing.pid})"
                    )
            time.sleep(0.1)
            continue

        # Try to acquire
        try:
            lock_file = open(LOCK_FILE, 'w')
            lock_file.write(f"{project}\n{os.getpid()}\n{time.time()}\n")
            lock_file.flush()

            if timeout is None:
                # Blocking lock
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            else:
                # Non-blocking with timeout (already handled above)
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    # Race condition - another process got it
                    lock_file.close()
                    continue

            # Success!
            break

        except Exception as e:
            if lock_file:
                try:
                    lock_file.close()
                except:
                    pass
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(f"Could not acquire lock: {e}")
            time.sleep(0.1)
            continue

    # Lock acquired
    info = LockInfo(project=project, pid=os.getpid(), acquired_at=time.time())

    try:
        yield info
    finally:
        # Release lock
        try:
            if lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
        except:
            pass

        # Clean up lock file
        try:
            LOCK_FILE.unlink()
        except FileNotFoundError:
            pass


def wait_for_lock(timeout: Optional[float] = None, poll_interval: float = 0.5) -> bool:
    """Wait until the bridge is unlocked.

    Args:
        timeout: Maximum seconds to wait (None = wait forever).
        poll_interval: Seconds between checks.

    Returns:
        True if bridge is now unlocked, False if timeout.
    """
    start_time = time.time()

    while True:
        if not is_locked():
            return True

        if timeout is not None:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return False

        time.sleep(poll_interval)


# CLI interface for testing and debugging
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="STS Bridge Lock Utility")
    parser.add_argument(
        "command",
        choices=["status", "wait", "acquire", "release", "test"],
        help="Command to execute"
    )
    parser.add_argument(
        "--project",
        type=str,
        default="cli",
        help="Project name for acquire command"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds"
    )

    args = parser.parse_args()

    if args.command == "status":
        info = get_lock_info()
        if info:
            print(f"Bridge locked by '{info.project}' (PID {info.pid})")
            if info.acquired_at:
                elapsed = time.time() - info.acquired_at
                print(f"Held for: {elapsed:.1f} seconds")
            print(f"Lock file: {LOCK_FILE}")
            sys.exit(1)  # Exit code 1 = locked
        else:
            print("Bridge is unlocked")
            sys.exit(0)  # Exit code 0 = unlocked

    elif args.command == "wait":
        if wait_for_lock(timeout=args.timeout):
            print("Bridge is now unlocked")
            sys.exit(0)
        else:
            print(f"Timeout waiting for lock after {args.timeout}s")
            sys.exit(1)

    elif args.command == "acquire":
        try:
            with bridge_lock(args.project, timeout=args.timeout) as info:
                print(f"Lock acquired for '{info.project}' (PID {info.pid})")
                print("Press Ctrl+C to release...")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nLock released")
        except TimeoutError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "release":
        info = get_lock_info()
        if info:
            if info.pid == os.getpid():
                release_lock()
                print("Lock released")
            else:
                print(f"Lock held by PID {info.pid}, not by current process ({os.getpid()})")
                print(f"Use 'kill {info.pid}' or 'rm {LOCK_FILE}' to force release")
                sys.exit(1)
        else:
            print("No lock held")

    elif args.command == "test":
        # Run lock acquisition test
        print(f"Testing lock acquisition... (PID: {os.getpid()})")
        print(f"Lock file: {LOCK_FILE}")

        with bridge_lock("test", timeout=5.0) as info:
            print(f"Lock acquired: project={info.project}, pid={info.pid}")

            # Check status
            status = get_lock_info()
            if status:
                print(f"Status check confirms lock held by PID {status.pid}")
            else:
                print("ERROR: Status check shows no lock!")
                sys.exit(1)

            # Hold for a moment
            time.sleep(0.5)

        # Check released
        status = get_lock_info()
        if status:
            print(f"ERROR: Lock still held after release! PID {status.pid}")
            sys.exit(1)
        else:
            print("Lock released successfully")
            print("Test PASSED")
