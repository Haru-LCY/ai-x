# Tensor All-Reduce Replay Contract (v1)

Schema: `lab4.garnet_tensor_allreduce_replay.v1`

This contract fixes the tensor semantics before the datapath (H2+) is
modified. It is produced by
`util/lab4_trace/compile_tensor_allreduce_replay.py` and validated by
`util/lab4_trace/validate_replay.py::validate_tensor_allreduce_replay`.

## Core mapping

- One **logical all-reduce request** corresponds to one measured `all_reduce`
  event in the source trace (15 events for the eight-H100 measurement phase).
- One **flit** is one 64-bit reduction lane.
- A request's tensor (`scaled_event_bytes`) is split into **chunks**
  (`chunk_bytes`, default 4096). Each chunk becomes a **packet** of
  `packet_flits` flits, and each flit in the chunk is a lane with a global
  `lane_start` offset inside the tensor.

## Fields

Top level: `schema`, `source_trace_schema`, `world_size`, `rank_to_router`,
`network_clock_ghz`, `flit_bytes`, `chunk_bytes`, `byte_scale`, `time_scale`,
`selected_phases`, `reduction_root_rank`, `reduction_root_router`, `lowering`,
`source_event_count`, `selected_all_reduce_event_count`, `request_count`,
`total_tensor_bytes`, `total_tensor_flits`, `total_chunk_count`,
`total_contribution_flits`, `requests`.

Each request:

| field | meaning |
|---|---|
| `id` / `trace_event_id` | logical request id (one per event) |
| `operation` | `all_reduce` |
| `participant_routers` | full mapped world, sorted |
| `reduction_root_router` | router that broadcasts the reduced tensor |
| `release_cycle` | non-negative, monotonic across requests |
| `scaled_event_bytes` | `ceil(source bytes * byte_scale)`, padded to a whole number of flits |
| `tensor_flits` | `scaled_event_bytes // flit_bytes` |
| `chunks[]` | `chunk_id`, `payload_bytes`, `packet_flits`, `lane_start`, `lane_count` |

## Invariants enforced by the validator

- Request ids unique; release cycles non-negative and monotonic.
- `tensor_flits == scaled_event_bytes // flit_bytes`; payloads are whole
  numbers of flits (`payload_bytes % flit_bytes == 0`) -- no partial lanes.
- Chunks exactly tile the tensor: first `lane_start == 0`, starts are
  contiguous, `payload_bytes` sum to `scaled_event_bytes`, chunk payloads
  never exceed `chunk_bytes`, and `lane_count == packet_flits`.
- `participant_routers == sorted(rank_to_router)`; root is a mapped router.
- Top-level totals equal the sums over requests.

## Expected eight-H100 measurement values (1/1024 byte and time scale)

| metric | value |
|---|---:|
| logical requests | 15 |
| scaled tensor bytes per rank | 107,520 |
| tensor flits per rank | 6,720 |
| total contribution flits | 53,760 |
