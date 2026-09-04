# Topic 4 — Real-GPU Trace Replay Plan

## Goal

Use the audited real-GPU collective trace as an input traffic pattern for
Garnet, then compare `Mesh_XY` and `Mesh_Bypass` under the same replay stream.
The first implementation targets `broadcast`, because its one-source to
many-destination semantics match the already validated multicast mechanism.
`all_reduce` remains a separate phase until reduction semantics are modeled.

## Current baseline (measured)

`traces/h100_8gpu_collectives.json` validates as
`lab4.ai_collective_trace.v1`: 8 ranks, 48 events, and 30 measurement events
(15 `all_reduce`, 15 `broadcast`). The compiler produces
`traces/h100_8gpu_broadcast_replay.json`: 30 requests and 6,720 scaled flits.
The source trace is real-GPU execution data; the replay uses explicit 1/1024
byte/time scaling and must not be reported as native GPU traffic.

## Phases and acceptance gates

### T1 — Contract and audit (this change)

- Validate replay schema, rank map, request IDs, release cycles, destinations,
  payload/flit arithmetic, and scaling metadata.
- Reject malformed or semantically ambiguous replay files.
- Add deterministic tests with measured counts and flit totals.

Gate: the checked-in H100 replay passes validation with zero errors and the
validator independently reports 30 requests and 6,720 flits. **Passed.**

### T2 — Garnet consumer

- Add a trace-replay traffic mode to the Garnet synthetic tester.
- Inject requests at their `release_cycle`, preserving source, destination
  bitmap, packet flits, and event ID.
- Track request completion and fail on missing/duplicate delivery or timeout.

Gate: a small replay (2–3 requests) completes on 2x2/4x4 with exact expected
request and destination counts for both Mesh and Bypass. The first smoke gate
now passes on 2x2 Mesh_XY: 2 requests, 3 destinations each, 2 source flits,
and completion at tick 11,500. Bypass pairing remains to be run in T3.

### T3 — Paired trace experiment

- Run the same replay on `Mesh_XY`, `Mesh_Bypass` optimistic, and
  `Mesh_Bypass` distance-scaled.
- Record completion latency, p95, ordinary/express flits, wire-distance flits,
  and express-link utilization.

Status: **complete for the broadcast replay scope.** The final audited
artifacts are under `/tmp/lab4-t3-final-p95/`, and the acceptance summary is in
`topic4_trace_replay_t3.md`.

Gate: every paired run is completion-driven, has zero correctness errors, and
emits raw JSON/CSV plus command, seed, revision, and scaling provenance.

The first full replay gate passed on 2026-08-07 with the checked-in 30-request
replay and a 30,000,000-cycle limit. Both designs completed all 30 requests,
delivered 6,720 source flits, and reported 30 measured requests. Mesh_XY and
Mesh_Bypass (diagonal, four links, distance-scaled) both measured 17,047,500
ticks; this tree replay used zero express-link flits and 47,040 ordinary
internal-link flits in both cases. The raw artifacts are under
`/tmp/lab4-trace-replay-full-r2/`.

The bypass-aware multicast extension then passed its directed gate: on a 2x2
diagonal topology, two one-flit requests completed at 3,500 ticks each versus
4,000 on Mesh_XY, with two observed express-link flits. On the complete replay,
all 30 requests and 6,720 source flits completed, and all 6,720 source flits
used an express link. Under the required distance-scaled model this increased
the measurement window from 17,047,500 to 20,346,500 ticks (ratio 1.194),
wire-flit distance from 47,040 to 53,760 (ratio 1.143), and produced 13,380
multicast credit stalls. This is a valid negative performance result: the
shortcut helps tiny packets but its long-wire serialization/backpressure cost
dominates this scaled H100 broadcast replay.

A tree-sharing-aware policy now rejects an express branch when any ordinary XY
edge on that destination's path is already shared by another destination. Its
directed gates distinguish the two cases: a shared three-destination 2x2
broadcast uses zero express flits and completes each round in 4,000 ticks,
while a sparse diagonal-only destination uses two express flits and completes
each round in 3,500 ticks. On the complete all-rank replay, the policy safely
falls back to the shared XY tree: 30/30 requests, 6,720 flits, 17,047,500
measurement ticks, 47,040 wire-flit distance, zero express flits, and zero
credit stalls. Thus it removes the prior 19.4% regression without disabling
bypass for sparse multicast groups.

### T4 — AI-communication extension

- Add all-reduce lowering only after deciding whether it is modeled as staged
  ring/tree communication or true in-network reduction.
- Never call a unicast decomposition a hardware reduction implementation.

Status: **complete for scalar-lane in-network all-reduce replay.** Each scaled
tensor is lowered into independent one-flit lanes because the implemented
router reduction datapath is scalar. Every lane executes a real router-side
reduce followed by tree broadcast; it is not a unicast decomposition. The
audited H100 input produces 15 measurement events, 6,720 lanes, and 53,760
rank contribution flits at 1/1024 byte/time scaling.

Gate: both Mesh_XY and Mesh_Bypass completed all 6,720 lanes with exact counts:
53,760 source flits, 53,760 reduce merges, 53,760 rank deliveries, and 147,840
collective router flits. Both measured 80,638,000 ticks for the replay window,
10,000 ticks p95 per lane, and 94,080 wire-flit distance. The current
all-reduce convergence tree uses ordinary XY links, so Mesh_Bypass correctly
reported zero express flits and no speedup. Full evidence is in
`topic4_trace_replay_t4.md` and `/tmp/lab4-t4-final-r2/`.

## Non-goals

- Claiming end-to-end H800/H100 model-training speedup.
- Treating scaled replay bytes as native tensor bytes.
- Implementing circuit-level H800 hardware or true reduction in T1–T3.

## Reproducibility

Every result must retain the source trace hash, replay hash, byte/time scale,
rank map, topology, wire model, gem5 revision, command line, seed, and raw
statistics. A timeout or incomplete request is a failed experiment, not a
performance result.
