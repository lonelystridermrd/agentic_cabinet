#!/usr/bin/env python3
"""doxygenize.py - ensure every function has a Doxygen header.

Generates:
    /**
     * @brief <purpose>.
     *
     * @param fd <meaning>.
     * @return <contract>.
     */

Usage:
  python .dsh/tools/doxygenize.py --check src/*.c
  python .dsh/tools/doxygenize.py --apply src/*.c

Existing plain /* name - text */ blocks (from the earlier pass) are replaced.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

START = re.compile(
    r"^(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w \t\*]*?\b(\w+)\s*\([^;]*$"
)

PURPOSE = {
    "wake_fd": "best-effort eventfd signal; EAGAIN means a wakeup is already pending",
    "drain_fd": "consume the eventfd counter so the next epoll_wait can block again",
    "ring_empty": "SPSC emptiness check: producer tail equals consumer head",
    "ring_is_empty": "SPSC emptiness check used before deciding to wake a worker",
    "iomux_now_ms": "monotonic milliseconds; never wall clock, so NTP jumps cannot skew timers",
    "iomux_log": "forward to cfg.log; silent when no sink is configured",
    "next_pow2": "round up to a power of two for the bucket array",
    "fd_hash": "Knuth multiplicative hash over the fd number",
    "cfg_valid": "reject configs that would break invariants (worker range, power-of-two queue)",
    "iomux_cfg_default": "fill a config with safe defaults; every field may be overridden",
    "watcher_link": "insert into the fd hash chain (reactor thread only)",
    "watcher_unlink": "remove from the fd hash chain; safe when not linked",
    "watcher_alloc": "take a zeroed watcher slot from the preallocated pool",
    "watcher_free": "return a watcher slot; caller must have unlinked it",
    "alloc_watchers": "preallocate watcher pool and buckets; no malloc after init",
    "fd_identity": "capture (st_dev, st_ino) so fd-number reuse can be detected",
    "pending_add": "queue a watcher whose target worker queue was full",
    "pending_flush": "retry pending dispatches once per reactor iteration",
    "choose_worker": "hash affinity when registered, round-robin otherwise",
    "watcher_rearm": "re-arm EPOLLONESHOT after a callback; drop the watcher if fd identity changed",
    "iomux_reap": "completion handler: rearm a live watcher, free a dead one",
    "drain_completions": "drain every worker completion ring; reactor thread only",
    "handle_event": "mark INFLIGHT, pick a worker, enqueue; fall back to pending on a full queue",
    "cmd_add": "register fd: reject duplicates, replace a stale same-number watcher",
    "cmd_mod": "change the interest mask; -EBUSY while a callback is in flight",
    "cmd_del": "unregister; defer the free to completion when INFLIGHT",
    "cmd_exec": "execute one queued command on the reactor thread",
    "cmd_submit": "enqueue a command and block until the reactor reports a real errno",
    "call_cmd": "inline before run(), queued while running, -ESHUTDOWN after stop",
    "drain_commands": "pop commands one by one and signal each completion",
    "iomux_stop": "idempotent stop: clear running and wake the reactor",
    "called_from_worker": "detect reactor/worker self-call to avoid a join deadlock",
    "iomux_free": "stop, join workers, release memory; -EDEADLK on self-call",
    "iomux_new": "validate config, create epoll/eventfds, preallocate, start workers",
    "iomux_run": "reactor loop: wait, dispatch, expire timers, run commands, reap",
    "iomux_mod": "validate arguments, then submit a MOD command",
    "iomux_del": "validate arguments, then submit a DEL command",
    "iomux_add": "validate arguments, then submit an ADD command",
    "iomux_timer_add": "validate arguments, then submit a timer ADD",
    "iomux_timer_cancel": "cancel by id; -ENOENT when it already fired or was cancelled",
    "iomux_timer_push": "validate arguments, take a slot, and insert into the expiry heap",
    "iomux_stats": "return the internal counter block; owned by the poller",
    "iomux_strerror": "map library error codes to static English strings",
    "iomux_ring_init": "allocate an SPSC ring; capacity must be a power of two",
    "iomux_ring_destroy": "release the ring buffer",
    "iomux_ring_push": "producer side; returns -EAGAIN when the ring is full",
    "iomux_ring_pop": "consumer side; release/acquire pairs with the producer",
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
    "completion_push": "return a finished task to the reactor; spin only while the ring is full",
    "worker_drain": "run queued callbacks, then report completion",
    "worker_main": "block on the wake eventfd, drain the queue, exit on stop",
    "iomux_worker_start": "create worker threads with an explicit stack size from RLIMIT_STACK",
    "iomux_worker_stop": "set the stop flag and wake every worker",
    "iomux_worker_join": "join started workers and release their rings",
}

PARAM_DOC = {
    "p": "poller instance",
    "cfg": "configuration; NULL selects defaults",
    "t": "task descriptor",
    "w": "watcher slot",
    "w2": "watcher slot",
    "r": "ring buffer",
    "c": "command entry",
    "fd": "registered descriptor",
    "events": "EPOLL* interest mask",
    "cb": "callback executed on a worker",
    "arg": "opaque user pointer",
    "bind": "optional worker binding; NULL means round-robin",
    "id_out": "out: allocated timer id",
    "delay_ms": "first expiry in milliseconds",
    "interval_ms": "0 for one-shot, >0 for periodic",
    "err": "out: 0 on success, -errno on failure",
    "dev": "out: st_dev of the descriptor",
    "ino": "out: st_ino of the descriptor",
}

RETURN_DOC = {
    "int": "0 on success, negative errno on failure",
    "uint64_t": "timer id, or 0 on failure (see err)",
    "void": None,
    "const char *": "static string; never NULL",
    "const struct iomux_stats *": "internal counters; owned by the poller",
    "struct iomux_poller *": "new poller, or NULL on failure",
}


def parse_def(lines: list[str], idx: int) -> tuple[str, str, list[str]] | None:
    """Return (return_type, name, params) for the definition starting at idx."""
    joined = ""
    depth = 0
    started = False
    for j in range(idx, min(idx + 8, len(lines))):
        piece = lines[j].strip()
        joined += (" " if joined else "") + piece
        for ch in piece:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                depth -= 1
        if started and depth <= 0:
            break
    m = re.match(
        r"^(?:static\s+)?(?:inline\s+)?(.+?)\b(\w+)\s*\((.*)\)\s*\{?\s*$", joined
    )
    if not m:
        return None
    ret, name, body = m.group(1).strip(), m.group(2), m.group(3).strip()
    if body in ("", "void"):
        params: list[str] = []
    else:
        params = [x.strip() for x in body.split(",") if x.strip()]
    return ret, name, params


def param_name(spec: str) -> str:
    spec = spec.replace("[]", "")
    m = re.search(r"(\w+)\s*$", spec)
    return m.group(1) if m else spec


def build_block(name: str, ret: str, params: list[str]) -> list[str]:
    purpose = PURPOSE.get(name, "internal helper")
    out = ["/**", f" * @brief {purpose[0].upper() + purpose[1:]}."]
    if params or RETURN_DOC.get(ret):
        out.append(" *")
    for spec in params:
        pname = param_name(spec)
        out.append(f" * @param {pname} {PARAM_DOC.get(pname, 'input parameter')}.")
    rd = RETURN_DOC.get(ret)
    if rd:
        out.append(f" * @return {rd[0].upper() + rd[1:]}.")
    out.append(" */")
    return out


def existing_doxy(lines: list[str], idx: int) -> bool:
    k = idx - 1
    while k >= 0 and not lines[k].strip():
        k -= 1
    if k < 0 or not lines[k].strip().endswith("*/"):
        return False
    start = k
    while start >= 0 and not lines[start].strip().startswith("/*"):
        start -= 1
    return start >= 0 and lines[start].strip().startswith("/**")


def plain_block_range(lines: list[str], idx: int) -> tuple[int, int] | None:
    """Range of an injected '/* name - text. */' block directly above idx."""
    k = idx - 1
    while k >= 0 and not lines[k].strip():
        k -= 1
    if k < 0 or not lines[k].strip().endswith("*/"):
        return None
    end = k
    start = end
    while start >= 0 and not lines[start].strip().startswith("/*"):
        start -= 1
    if start < 0:
        return None
    head = lines[start].strip()
    if head.startswith("/**"):
        return None
    return start, end


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = 0
    changed = 0
    for raw in args.files:
        path = Path(raw)
        lines = path.read_text(encoding="utf-8").splitlines()
        edits: list[tuple[int, int, list[str]]] = []  # start, end, block
        i = 0
        while i < len(lines):
            m = START.match(lines[i])
            if m:
                parsed = parse_def(lines, i)
                if parsed is not None:
                    ret, name, params = parsed
                    total += 1
                    if not existing_doxy(lines, i):
                        rng = plain_block_range(lines, i)
                        block = build_block(name, ret, params)
                        if rng is not None:
                            edits.append((rng[0], rng[1] + 1, block))
                        else:
                            edits.append((i, i, block))
            i += 1
        if not edits:
            continue
        changed += len(edits)
        if not args.apply:
            print(f"{path}: would fix {len(edits)} headers")
            continue
        for start, end, block in sorted(edits, reverse=True):
            lines[start:end] = block
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{path}: fixed {len(edits)} headers")

    print(f"\nTOTAL functions={total} fixed={changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
