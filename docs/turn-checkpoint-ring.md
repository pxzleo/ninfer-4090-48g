# Turn checkpoint ring

`--turn-checkpoints N` keeps up to N past turn checkpoints per slot in host memory.
A prompt that diverges from the resident session in the middle of its history then
restores at the deepest checkpoint below the divergence point. The server
re-prefills only the suffix after that checkpoint. Even with the ring disabled,
ordinary Text/Vision and MTP requests retain the latest generation checkpoint on
the GPU and the current user-turn checkpoint in host memory.

The flag defaults to `0` (off). The recommended production value on Qwen3.8-27B is
`32`. The policy mirrors llama.cpp's `--ctx-checkpoints`, adapted to this engine's
hybrid attention.

## Why the engine needs checkpoints at all

Qwen3.8-27B is a hybrid model: 16 of its 64 layers use full attention, the other
48 use GDN linear attention. The two halves age differently when a prompt edits
history:

- Full-attention KV is positional. The engine can truncate it to any frontier and
  the entries below the edit stay valid.
- Each GDN layer keeps one running recurrent state per slot. That state integrates
  every token in order and cannot rewind. The engine can resume only at a point
  where the state was copied aside.

The resident checkpoint is at the end of the latest generation assistant header,
before the thinking opener. Generated token IDs need not be the canonical encoding
of their decoded text; a client round trip can therefore change token IDs without
changing text. This checkpoint bounds the resulting rewind to the latest response.
The independent host checkpoint remains at the first assistant header after the
last user message, so edits to earlier assistant responses in the same tool loop
can still rewind the current user turn. The ring retains additional older copies.
All reuse still requires exact token, position, and media identity below the frontier.

## What one checkpoint holds

| Component | Content | Size on Qwen3.8-27B |
|---|---|---:|
| Recurrent state | 48 layers x 128x128x48 fp32 | 144 MiB |
| Convolution state | 48 layers x 10240x3 bf16 | 2.9 MiB |
| Boundary hidden | 5120 bf16 | 10 KiB |

One entry therefore costs about 147 MiB of pageable host memory. The attention KV
is not copied. An entry stays valid only while the token ledger below its frontier
is untouched, so the slot's paged KV still holds those positions on the GPU.

## How to run it

Add the flag to any serve line:

```bash
ninfer-serve models/qwen3_8_27b.ninfer ... --turn-checkpoints 32
```

Host memory cost is `N x 147 MiB x --max-concurrency`, plus one user-turn
checkpoint and one pinned staging entry, about 294 MiB per slot in total even
when N is zero (about 2.3 GiB for eight slots). GPU memory is unchanged.

| `--turn-checkpoints` | Host memory per slot | History covered |
|---:|---:|---:|
| 0 | 294 MiB | current user turn and latest generation |
| 8 | 1.4 GiB | ~33K tokens |
| 32 | 4.9 GiB | ~131K tokens |
| 64 | 9.5 GiB | ~262K tokens |

The history coverage follows from the compaction spacing described below.
The supported maximum ring capacity is 64 entries.

## Capture and compaction

Prefill first captures the current user boundary when needed, copies its complete
GDN state and boundary hidden to host memory, and waits for that copy before
reusing the single device checkpoint slot. It then captures the latest generation
boundary. A cold prompt containing tool history can therefore split prefill at
two frontiers. The mandatory user copy adds host-transfer latency to that capture;
it is reused throughout the same unchanged user turn. When the history ring is
enabled, the generation copy is staged asynchronously and folded into the ring
at the next request or snapshot save. A staged copy above the next request's
reuse frontier is discarded.

Ring compaction runs at each fold:

1. An entry with the same frontier is replaced.
2. Intermediate entries within 4,096 tokens of the previous retained entry are
   folded away (`kTurnCheckpointMinStep`). The oldest and newest survive this
   spacing step; capacity eviction can still remove the oldest.
3. Above capacity, the oldest entry is evicted.

Intermediate retained entries are spaced by more than 4,096 tokens; the newest
can be closer. The table's coverage is approximate, not a retention guarantee.
A rewind to an unretained point uses the deepest matching checkpoint below the
divergence and re-prefills the gap. The independent user anchor is not compacted
or evicted by this ring policy.

## Restore

Reuse planning first tries exact frontier extension. Otherwise it selects the
deepest exactly matching checkpoint from:

1. The resident generation checkpoint.
2. The independent current user-turn checkpoint.
3. The optional history ring.

A ring restore uploads the entry back into the device checkpoint slot and then
follows the ordinary `RestoreTurnCheckpoint` path: the KV is truncated to the
entry's frontier, the GDN state is rewound to the copy, and the suffix is
re-prefilled. Generation after a ring restore is identical to a cold prefill of
the same prompt; the end-to-end test verifies greedy-exact output on the real
artifact.

## Observability

`GET /slots` lists each retained slot's checkpoints, oldest first:

```json
"checkpoints": [
  {"frontier": 12480, "session_digest": "a1b2c3d4e5f60718"},
  {"frontier": 30976, "session_digest": "18f7e6d5c4b3a291"}
]
```

`frontier` is the ledger depth the entry rewinds to. `session_digest` is the
FNV-1a 64 hash of the token ledger up to that frontier, in the same encoding as
the slot's `session_digest`. Two slots that report the same checkpoint digest hold
an identical history up to that point.

## Persistence and eviction

Slot snapshots (`--slot-save-path`) always use format version 3 and carry the
resident generation checkpoint, independent user anchor, and optional ring.
Earlier snapshot versions are rejected; create fresh snapshots with this binary.
A restore into a server with a smaller ring keeps the newest entries that fit;
ring capacity zero discards historical entries while preserving the user anchor.

The ring lives and dies with slot residency. Anything that evicts the resident
session also discards its ring:

- admission of a new session when every slot is retained (the cheapest slot is
  evicted: an empty one first, then the shallowest),
- `POST /slots/{id}?action=erase` or a restore over the slot,
- a server restart.

The snapshot path is the tolerance mechanism for slot churn. When clients rotate
more sessions than `--max-concurrency` slots, save each session to disk before it
loses its slot; the ring returns with the restore. A session evicted without a
snapshot starts cold and rebuilds its ring one turn per request.

`--auto-save-evicted` closes the remaining gap: before an involuntary eviction
destroys a retained session, the server spills it (ring included) back to the
slot file it was last saved to or restored from. Sessions that never touched a
slot file are not covered, and an explicit `erase` never auto-saves. The device
snapshot runs on the eviction path and costs a few hundred milliseconds; the
file write runs on a background thread. Requires `--slot-save-path`.

## Limits

- DFlash keeps its existing single user-turn device checkpoint. The host anchor,
  ring, and persistence are unsupported because its cyclic local cache cannot
  rebuild arbitrary older entries.
- Checkpoints exist at user and generation boundaries only. An edit inside the first user input, or
  before the oldest retained entry, still takes a full re-prefill.
- A ring restore is not free: the suffix between the checkpoint and the new
  frontier is re-prefilled, and the 147 MiB upload from pageable memory costs
  roughly 15 ms before the prefill starts.
- Tool or system-prompt edits diverge near token zero, below every checkpoint.
  The ring cannot help there; keep volatile content out of the prompt prefix
  instead.
