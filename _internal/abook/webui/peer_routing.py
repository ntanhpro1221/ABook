"""Bounded TLS selection, shared by callers of one identity, isolated from other peers' DNS.

Only the selecting caller owns its winning socket. Waiters share the selected address,
never the socket (and never an HTTP operation). At most two pending I/O jobs per peer.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED

from . import tls, peer_addresses


class _Peer:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="peer-tls")
        self.pending = {}
        self.round = None
        self.failure = None
        self.used = time.monotonic()
        self.cursor = 0


class Resolver:
    FAILURE_SECONDS = 2.0
    MAX_PEERS = 32

    def __init__(self):
        self.lock = threading.Lock()
        self.peers = {}

    def invalidate(self, identity):
        with self.lock:
            if peer := self.peers.get(identity):
                peer.failure = None

    def reset(self):
        with self.lock:
            for peer in self.peers.values():
                peer.pool.shutdown(wait=False, cancel_futures=True)
            self.peers.clear()

    def connect(self, identity, targets, dial, seconds, *, network=None):
        targets = peer_addresses.candidates(targets)
        if not targets:
            raise OSError("Máy đã ghép chưa có địa chỉ; bạn hãy ghép lại")
        signature = frozenset(targets)
        # Give the preferred route a short head start, then cover every candidate in two lanes.
        budget = seconds * ((len(targets) + 1) // 2) + (min(seconds, 0.15) if len(targets) > 1 else 0)
        deadline = time.monotonic() + budget
        while True:
            with self.lock:
                peer = self.peers.get(identity)
                if peer is None:
                    if len(self.peers) >= self.MAX_PEERS:
                        for key, old in list(self.peers.items()):
                            if old.round is None and all(job.done() for job in old.pending):
                                old.pool.shutdown(wait=False, cancel_futures=True)
                                del self.peers[key]
                                break
                        else:
                            raise OSError("Bộ chọn đường đang bận; bạn hãy thử lại")
                    peer = self.peers[identity] = _Peer()
                peer.used = time.monotonic()
                left = deadline - peer.used
                if left <= 0:
                    raise TimeoutError("Hết thời gian chọn đường")
                if peer.failure:
                    failed_at, failed_targets, failed_network, error = peer.failure
                    if signature == failed_targets and network == failed_network and peer.used - failed_at < self.FAILURE_SECONDS:
                        raise error
                leader = peer.round is None
                if leader:
                    shared = peer.round = Future()
                else:
                    shared = peer.round
            if leader:
                break
            # A waiter gets its own socket via the same two slots. Time spent waiting counts
            # against this call's original deadline; a DNS-stalled redial never runs on the caller.
            target = shared.result(timeout=left)
            targets = (target, *(candidate for candidate in targets if candidate != target))
        try:
            connection, target = self._select(peer, targets, dial, seconds, deadline - time.monotonic())
        except BaseException as error:
            with self.lock:
                if isinstance(error, (OSError, tls.PinError)):
                    peer.failure = (time.monotonic(), signature, network, error)
                peer.round = None
                shared.set_exception(error)
            raise
        with self.lock:
            peer.failure = None
            peer.round = None
            shared.set_result(target)
        return connection, target

    def _select(self, peer, targets, dial, seconds, budget):
        deadline = time.monotonic() + budget
        # If an earlier DNS call outlives its round, do not queue more work behind it.
        peer.pending = {job: target for job, target in peer.pending.items() if not job.done()}
        start = peer.cursor % len(targets)
        remaining = [target for target in targets[start:] + targets[:start] if target not in peer.pending.values()]
        jobs = {}
        winner = None
        error = OSError("Không kết nối được máy kia")

        def submit():
            target = remaining.pop(0)
            job = peer.pool.submit(dial, target)
            jobs[job] = target
            peer.pending[job] = target
            peer.cursor = (targets.index(target) + 1) % len(targets)

        try:
            if remaining and len(peer.pending) < 2:
                submit()
            # Prefer the last working route before racing the remaining candidates.
            first_deadline = min(deadline, time.monotonic() + min(seconds, 0.15))
            while jobs or remaining:
                peer.pending = {job: target for job, target in peer.pending.items() if not job.done() or job in jobs}
                now = time.monotonic()
                preferred = len(jobs) == 1 and len(remaining) == len(targets) - 1 and now < first_deadline
                while remaining and len(peer.pending) < (1 if preferred else 2):
                    submit()
                if not jobs:
                    break  # two old DNS jobs still occupy this peer's slots; no hidden queue
                until = min(deadline, first_deadline) if preferred else deadline
                done, _ = wait(jobs, timeout=max(0, until - now), return_when=FIRST_COMPLETED)
                for job in done:
                    target = jobs.pop(job)
                    peer.pending.pop(job, None)
                    try:
                        winner = job.result()
                        peer.cursor = 0
                        return winner, target
                    except (OSError, tls.PinError) as failure:
                        if not isinstance(error, tls.PinError):
                            error = failure
                if time.monotonic() >= deadline:
                    break
                # A finished preferred attempt releases the second lane immediately.
                if done:
                    first_deadline = 0
            raise error
        finally:
            def close_loser(job):
                try:
                    connection = job.result()
                    if connection is not winner:
                        connection.close()
                except Exception:
                    pass
            for job in jobs:
                if not job.cancel():
                    job.add_done_callback(close_loser)
