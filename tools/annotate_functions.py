#!/usr/bin/env python3
"""annotate_functions.py - insert a header comment above every function.

Usage:
  python .dsh/tools/annotate_functions.py --check src/*.c
  python .dsh/tools/annotate_functions.py --apply src/*.c

Comments come from the table below (shared by iomux and iomux_v2). Unknown
functions are reported and left untouched. Line numbers are not preserved on
purpose: the tool inserts whole lines and never edits code.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

START = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w \t\*]*?\b(\w+)\s*\([^;]*$"
)

COMMENTS = {
    # ---- shared helpers -------------------------------------------------
    "wake_fd": "best-effort eventfd signal; EAGAIN means a wakeup is already pending",
    "drain_fd": "consume the eventfd counter so the next epoll_wait can block again",
    "ring_empty": "SPSC emptiness check: producer tail equals consumer head",
    "ring_is_empty": "SPSC emptiness check used before deciding to wake a worker",
    "iomux_now_ms": "monotonic milliseconds; never wall clock, so NTP jumps cannot skew timers",
    "iomux_log": "forward to cfg.log; silent when no sink is configured",
    "next_pow2": "round up to a power of two for the bucket array",
    "fd_hash": "Knuth multiplicative hash over the fd number",
    "cfg_valid": "reject configs that would break invariants (worker range, power-of-two queue)",
    "iomux_cfg_default": "safe defaults; every field may be overridden by the caller",

    # ---- fd table -------------------------------------------------------
    "watcher_link": "insert into the fd hash chain (reactor thread only)",
    "watcher_unlink": "remove from the fd hash chain; safe when not linked",
    "watcher_alloc": "take a zeroed watcher slot from the preallocated pool",
    "watcher_free": "return a watcher slot; caller must have unlinked it",
    "alloc_watchers": "preallocate watcher pool and buckets; no malloc after init",
    "fd_identity": "capture (st_dev, st_ino) so fd-number reuse can be detected",

    # ---- dispatch / completion -----------------------------------------
    "pending_add": "queue a watcher whose target worker queue was full",
    "pending_flush": "retry pending dispatches once per reactor iteration",
    "choose_worker": "hash affinity when registered, round-robin otherwise",
    "watcher_rearm": "re-arm EPOLLONESHOT after a callback; drop the watcher if fd identity changed",
    "iomux_reap": "completion handler: rearm a live watcher, free a dead one",
    "drain_completions": "drain every worker completion ring; reactor thread only",
    "handle_event": "mark INFLIGHT, pick a worker, enqueue; fall back to pending on full queue",

    # ---- commands -------------------------------------------------------
    "cmd_add": "register fd: reject duplicates, replace a stale same-number watcher",
    "cmd_mod": "change the interest mask; -EBUSY while a callback is in flight",
    "cmd_del": "unregister; defer the free to completion when INFLIGHT",
    "cmd_exec": "execute one queued command on the reactor thread",
    "cmd_submit": "enqueue a command and block until the reactor reports a real errno",
    "call_cmd": "inline before run(), queued while running, -ESHUTDOWN after stop",
    "drain_commands": "pop commands one by one and signal each completion",

    # ---- lifecycle ------------------------------------------------------
    "iomux_stop": "idempotent stop: clear running and wake the reactor",
    "called_from_worker": "detect reactor/worker self-call to avoid a join deadlock",
    "iomux_free": "stop, join workers, release memory; -EDEADLK on self-call",
    "iomux_new": "validate config, create epoll/eventfds, preallocate, start workers",
    "iomux_run": "reactor loop: wait, dispatch, expire timers, run commands, reap",
    "iomux_mod": "public wrapper: validate arguments, then submit a MOD command",
    "iomux_del": "public wrapper: validate arguments, then submit a DEL command",
    "iomux_add": "public wrapper: validate arguments, then submit an ADD command",
    "iomux_timer_add": "public wrapper: validate arguments, then submit a timer ADD",
    "iomux_timer_cancel": "cancel by id; -ENOENT when it already fired or was cancelled",
    "iomux_timer_push": "validate arguments, take a slot, and insert into the expiry heap",
    "iomux_stats": "return the internal counter block; owned by the poller",
    "iomux_strerror": "map library error codes to static English strings",

    # ---- ring -----------------------------------------------------------
    "iomux_ring_init": "allocate an SPSC ring; capacity must be a power of two",
    "iomux_ring_destroy": "release the ring buffer",
    "iomux_ring_push": "producer side; returns -EAGAIN when the ring is full",
    "iomux_ring_pop": "consumer side; release/acquire pairs with the producer",

    # ---- timer heap -----------------------------------------------------
    "heap_less": "min-heap order: expire time, then id for stability",
    "heap_swap": "swap two heap slots and fix their heap_idx back-pointers",
    "heap_up": "sift a node up after insert",
    "heap_down": "sift a node down after pop/remove",
    "heap_insert": "insert and record heap_idx; O(log n)",
    "heap_remove_at": "remove by index; O(log n) thanks to heap_idx",
    "timer_alloc": "take a zeroed timer slot from the preallocated pool",
    "timer_free": "return a timer slot; callback must have finished",
    "iomux_timer_init": "preallocate timer slots and the heap array",
    "iomux_timer_destroy": "release timer storage",
    "iomux_timer_remove": "scan the heap by id; ids are not indexed separately",
    "iomux_timer_fire": "pop due timers, reinsert periodic ones, drop a tick while INFLIGHT",
    "iomux_timer_next_ms": "timeout for epoll_wait; -1 when no timer is armed",
    "iomux_timer_reap": "free one-shot timers, idle periodic ones",

    # ---- worker ---------------------------------------------------------
    "completion_push": "return a finished task to the reactor; spin only while the ring is full",
    "worker_drain": "run queued callbacks, then report completion",
    "worker_main": "block on the wake eventfd, drain the queue, exit on stop",
    "iomux_worker_start": "create worker threads with an explicit stack size from RLIMIT_STACK",
    "iomux_worker_stop": "set the stop flag and wake every worker",
    "iomux_worker_join": "join started workers and release their rings",
}


def find_defs(lines: list[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = START.match(line)
        if not m:
            continue
        if line.lstrip().startswith(("#", "//", "*", "/*")):
            continue
        name = m.group(1)
        if name in ("if", "for", "while", "switch", "return", "sizeof"):
            continue
        # The opening brace must appear within the next few lines.
        for j in range(i + 1, min(i + 8, len(lines))):
            s = lines[j].strip()
            if s.startswith("{"):
                out.append((i, name))
                break
            if s and not s.startswith(")") and not s.startswith(",") and ";" in s:
                break
    return out


def has_comment(lines: list[str], idx: int) -> bool:
    k = idx - 1
    while k >= 0 and not lines[k].strip():
        k -= 1
    return k >= 0 and lines[k].strip().endswith("*/")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = 0
    added = 0
    unknown: set[str] = set()

    for raw in args.files:
        path = Path(raw)
        lines = path.read_text(encoding="utf-8").splitlines()
        defs = find_defs(lines)
        total += len(defs)
        inserts: list[tuple[int, list[str]]] = []
        for idx, name in defs:
            if has_comment(lines, idx):
                continue
            text = COMMENTS.get(name)
            if text is None:
                unknown.add(name)
                continue
            inserts.append((idx, ["/*", f" * {name} - {text}.", " */"]))
        if not inserts:
            continue
        added += len(inserts)
        if not args.apply:
            print(f"{path}: would add {len(inserts)} comments")
            continue
        for idx, block in sorted(inserts, reverse=True):
            lines[idx:idx] = block
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{path}: added {len(inserts)} comments")

    print(f"\nTOTAL defs={total} added={added} unknown={sorted(unknown)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
