"""A re-entrant lock that also excludes OTHER PROCESSES.

The web server and the background worker are separate processes that both read-modify-write
the owner bot's trade history JSON and paper_balance.json. A threading lock only protects
threads inside one process, so the two processes could interleave: one saved a stale copy of
the history over the other's settlement, the trade flipped back to OPEN, and it was settled
and paid a second time (audit finding H4).

Usage is the same as threading.RLock: `with lock: ...` and nesting in one thread is fine.
The OS file lock is taken on the outermost acquire and released on the outermost release.
"""
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_LOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "locks")


class ReentrantProcessLock:
    def __init__(self, name: str, timeout: float = 60.0, lock_dir: str = None):
        self.name = name
        self._path = os.path.join(lock_dir or _LOCK_DIR, f"{name}.lock")
        self._timeout = timeout
        self._rlock = threading.RLock()
        self._depth = 0
        self._fh = None

    def _os_lock(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        fh = open(self._path, "a+b")
        deadline = time.time() + self._timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fh = fh
                return
            except OSError:
                if time.time() > deadline:
                    fh.close()
                    raise TimeoutError(f"Timed out after {self._timeout:.0f}s waiting for {self._path}")
                time.sleep(0.02)

    def _os_unlock(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            logger.warning(f"[ProcLock] Unlock of {self._path} failed: {e}")
        finally:
            fh.close()

    def acquire(self) -> bool:
        self._rlock.acquire()
        if self._depth == 0:
            try:
                self._os_lock()
            except BaseException:
                self._rlock.release()
                logger.error(f"[ProcLock] Could not lock {self.name}; another process is holding it.")
                raise
        self._depth += 1
        return True

    def release(self) -> None:
        self._depth -= 1
        try:
            if self._depth == 0:
                self._os_unlock()
        finally:
            self._rlock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
