# Port ledger

The RTX 4090 fork (this repository, branch `rtx4090-port`) and the RTX 5090 fork
([sergiuszm/ninfer-5090](https://github.com/sergiuszm/ninfer-5090), branch
`nuntius-serve`) share almost all of their engine and serve code. Features are
born in one tree and cherry-picked into the other. This ledger records, per
feature, the commit hash in each tree, so coverage stays checkable without
archaeology.

Maintenance rules:

- Cherry-pick with `git cherry-pick -x`, so the destination commit records its
  source hash. Each repository holds the other as a local remote
  (`local-5090` here, `local-4090` there).
- Port in the session that ships the feature. Delayed ports pay a growing
  adaptation cost; `f640b404` on the 5090 side is the receipt.
- When a feature is deliberately not ported, record the decision here instead
  of leaving a silent gap.

## Feature rows

| Feature | 4090 (`rtx4090-port`) | 5090 (`nuntius-serve`) | Notes |
|---|---|---|---|
| `context_window` in `/v1/models` | `0f308358` | `ed606ed5` | |
| Prometheus `/metrics` | (commit series) | `fc582982`, `5fa5ffa1` | |
| Retained depth on idle `/slots` | `b0893e79` | `1a9640f1` | |
| Vision modality in `/v1/models` | `b6172f24` | `61013cf1` | Born on the 5090 side |
| fp16-accumulate PV tiles | part of `ce50e995` | `4483c820` | 4090 folds it into the sm_89 retune |
| 413 body fix + media prompt cap | `85f685a3`, `bde2765c` | `66423552`, `e9093c77` | Born on the 5090 side |
| sws_scale stride pad | `5a08683d` | `060bb320` | Born on the 5090 side |
| Tool content-part arrays | `d78df936` | `b0a0a6fe` | |
| llama.cpp-compatible `timings` | `0f95b32e` | `0834b6cb` | From the shantanusingh16 fork |
| Final-chunk usage param fix | `265011d9` | `51857983` | |
| Slot save/restore to disk | `beaeb70a` | `aeaf3f28` | 5090 needed `f640b404` (KV modes) |
| Session digests + `if_digest` | `8e478945` | `40504615` | |
| Cheapest-lane reuse tie-break | `1614ef54` | `59cb1afb` | |
| `/slots` snapshot publishing | `4a4fa92b` | `93fadf94` | |
| Live llamacpp `/metrics` counters | `656b0df7` | `b38ae92d` | |
| Turn checkpoint ring | `3a2e7f07`, `cba2c1f8`, `2cbe488d`, `3419fe43` | `6826b8b0`, `1ac61caf`, `8b28e502`, `66401303` | Picked with `-x` |
| Auto-save on eviction | `8093c640` | `cad0218e` | Picked with `-x` |
| Causal-tile key-block partition | `694e01f0` | `b5179823` | i8 body re-applied per schedule; bf16 and common taken verbatim |
| E8 codec hardening | `bc569eb8`, `a0e03d37` | not applicable | The 5090 tree carries no E8 code. Third-hand from upstream PR #35 through the sibling fork; authorship preserved |
| Production E8 codec test | `94830b3f` | not applicable | Same reason. Also registers the standalone oracle, which ctest had never run |
| GDN QK norm XOR butterfly | `6e239351` | open | Bit-exact over 6.4M lanes, measures near zero. Port is cheap; value is consistency, not throughput |
| GDN uniform value pack | `c4d09b61` | open | Bit-exact over all 65536 bf16 patterns, measures near zero. Born here, not a port |
| Nested `chat_template_kwargs.enable_thinking` | working tree (from `032b2533`, `6f3e6056`) | open | Adapted from Neroued PR #50; conflicting aliases are rejected |
| Chat cached-token usage details | working tree (from `7503d8a4`) | open | Adapted from Neroued PR #55 for plain, tool, and streaming usage |
| Schema-aware tool string arguments | working tree (from `99d39090`) | open | Adapted from Neroued PR #65; explicit string schemas preserve JSON-looking text |
| Per-image token budget | working tree (from `eb413c76`) | open | Adapted from Neroued PR #61 to this frontend's image pixel ceiling |
| Greedy penalty bypass | working tree (from `957046f5`) | open | From the sergiuszm fork; grammar rejection still applies before exact argmax |
| CUDA Graph allowance floor | working tree (from `87a58c37`) | open | From the sergiuszm fork; 40 MiB plus 8 MiB per execution slot |
| Q5 Ada 17-64-token schedule | working tree (from `7a780455`) | not applicable | From UDPSendToFailed; numerical tests pass and matched short-prefill median improved about 1.9% on the 48 GB RTX 4090 |

## Deliberate non-ports

| Feature | Lives in | Decision |
|---|---|---|
| sm_89 attention retune (`ce50e995`) | 4090 | Architecture-specific by design |
| E8 lattice KV modes (`c3a6e5c4`, `ec56f922`, series) | 4090 | Declined for the 5090 on 2026-08-19: 32 GB fits the full 262K context on `int8`, so E8 would buy only the decode-at-depth gain. **Revisit if NVFP4 becomes the goal**: upstream PR #35 ports E8 to sm_120a, and NVFP4 cannot reach 262K on `int8` at all. Wait for that PR to merge rather than hand-porting it. See `docs/udp-fork-comparison.md` |
| `--vision-max-tokens` (`0c3d2bee`, `73b42127`) | 4090 | Open: the 5090 fits the legacy 32K scratchpad next to 262K + vision, so nothing forces the port |
| Single-token W8 column-store fix (`68e2d0be`) | 4090 | Not applicable: the 5090 tree's `w8_linear_add_gemm_splitk.cu` is the upstream variant without the vulnerable tail dispatch |
| NVFP4 weights profile | 5090 (upstream) | Ada has no FP4 tensor cores; the 4090 gates the A4 tests off instead |

## Long-term direction

The measured divergence between the trees is about 40 files once in-flight
ports land: roughly half architecture-specific kernels, half platform
configuration. The plan of record is to converge on one repository with two
architecture profiles (`sm_89` and `sm_120a` behind a CMake switch) and retire
the second tree to a deploy configuration. Until then, this ledger is the
source of truth for coverage.
