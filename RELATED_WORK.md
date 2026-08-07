# Lab4 Related Work

## 1. Positioning

Lab4 implements a router-level, in-network All-Reduce mechanism in gem5 Garnet.
Each node contributes a scalar or vector chunk, routers aggregate contributions
along a deterministic Mesh_XY convergence tree, and the root broadcasts the
result back to all nodes.

The project is inspired by prior work on collective communication,
in-network aggregation, and NoC microarchitecture. The cited work provides
the motivation and baseline algorithms; the Lab4 implementation is a separate
Garnet implementation with its own tree metadata, reduction state, credit
handling, and evaluation.

## 2. Reference groups

### Garnet simulation model

Agarwal et al. introduced GARNET as a detailed on-chip network model inside a
full-system simulator. Lab4 uses gem5 Garnet as the cycle-accurate substrate
for router, link, virtual-channel, and credit experiments.

### Collective reduction algorithms

Rabenseifner presents optimized collective reduction algorithms and provides a
useful theoretical background for tree, ring, and reduce-scatter/allgather
baselines. Horovod is a representative distributed-training system that uses
ring All-Reduce for gradient synchronization. These works motivate the fair
naive/ring/tree comparisons in Lab4; they are not treated as code dependencies.

### In-network aggregation

SHARP and SwitchML demonstrate the value of performing aggregation inside
network devices rather than sending all updates to an endpoint. Lab4 follows
the same high-level motivation, but implements aggregation inside Garnet
Routers and evaluates a deterministic Mesh_XY tree rather than a programmable
datacenter switch.

### Chunking and pipelining

Pipelined MPI All-Reduce work motivates splitting a large gradient tensor into
chunks so that reduction and communication can overlap. Lab4's planned
multi-flit/vector extension will use this idea while keeping bounded router
state and explicit chunk metadata.

### Multicast and bypass

The tree broadcast in Lab4 is a multicast-style operation: one root result is
replicated along several child output paths. If the optional express-link
extension is implemented, bypass NoC work will provide background for shortcut
links and their latency trade-offs.

## 3. Lab4-specific contributions

The following items are implementation contributions of this project, rather
than claims that the underlying ideas were invented here:

1. Automatic parent/children/fan-in metadata derived from Mesh_XY and the
   selected collective root.
2. Router-side accumulation of local and child contributions.
3. Credit-aware consumption of reduction flits and cloning of broadcast flits.
4. Collective flit metadata (`value`, `collective_id`, and `is_reduce`).
5. A reproducible correctness and stability workflow in gem5 Garnet.
6. Planned vector/chunk pipelining and optional bypass ablations.

## 4. Recommended citation policy

- Cite prior papers when describing their algorithms, motivation, or reported
  results.
- Cite Garnet when describing the simulator model.
- Report Lab4 measurements as our own experiments, with command lines and
  configuration details.
- Do not copy figures, prose, or numerical results from previous student
  reports. Those reports are internal examples of presentation style, not
  technical sources for this project.
