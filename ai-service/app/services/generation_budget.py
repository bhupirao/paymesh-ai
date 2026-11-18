"""One inference in flight per process across chat and investigation. Never queue model work."""
from threading import BoundedSemaphore
_SLOT = BoundedSemaphore(1)

def run_bounded(callback):
    from app.services.local_provider import GenerationFailure
    if not _SLOT.acquire(blocking=False):
        raise GenerationFailure('UNAVAILABLE')
    try:
        return callback()
    finally:
        _SLOT.release()
