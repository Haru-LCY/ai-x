# Multicast completion plan

## Implementation status (2026-08-07)

M1--M5 are implemented and gated by automated regression:

- M1: unified mode/source/destination/round/packet/seed parameters and
  duplicate/unexpected/missing-delivery tracking;
- M2: runnable replicated-XY-unicast baseline, including local delivery and
  retry-safe partial injection;
- M3: per-flit 64-bit destination bitmap with pruned tree branches and SerDes
  preservation;
- M4: 1--64 flit packets with persistent branch VCs, atomic fanout credit
  checks, interleaved-round buffering, and tail-driven release;
- M5: latency/throughput modes, bounded outstanding requests,
  warmup/measurement/cooldown phases, deterministic uniform-random
  background traffic, protocol/link/stall/latency statistics, and paired
  CSV/JSON comparison output.

The implementation remains intentionally limited to at most 64 Routers per
multicast destination bitmap. Bypass was outside this milestone, but its later
G1--G10 implementation and multicast interaction are now complete; see
`bypass.md`, `report/bypass_g9.md`, and `report/bypass_g10.md`.

Final accepted evidence: 208/208 paired correctness cases and 162/162 paired
performance cases (324 raw runs). The performance snapshot reports 39.2% mean
internal-link traffic reduction and 3.59x median completion-latency speedup,
while retaining 10/162 negative throughput cases.

## 1. Goal and completion boundary

本阶段只完成 Topic 3 的 multicast 部分，不实现 bypass。目标是在相同 Mesh、源节点、目的集合、payload、注入时刻和退出条件下，公平比较：

1. `naive_unicast`：源 NI 为每个目的节点分别发送一份普通 XY unicast；
2. `tree_multicast`：源只注入一个逻辑 packet，由 Router 沿 multicast tree 复制；
3. `ideal_lower_bound`：只作为分析参考，给出一棵覆盖目的集合的最少 tree-edge traversal，不作为可运行硬件方案，也不计入主要 speedup 结论。

只有本文所有 correctness、performance、reproducibility gate 都通过，才开始 bypass。现有 all-reduce 的 reduce+broadcast 流程与 multicast 语义不同，不能作为 multicast baseline。

## 2. Common workload contract

所有可比较方案必须使用完全一致的 logical multicast request：

```text
round_id
source_router
destination_set
payload_bytes / packet_flits
injection_time
```

完成定义为：`destination_set` 中每个 Router 恰好收到一次相同 payload。比较时必须固定：

- 相同的 `Mesh_XY` topology、router/link latency、link width、VC 数和 buffer 深度；
- 相同的 source、destination set、round 数、packet size 和 random seed；
- 相同的 warmup、measurement、cooldown 区间；
- 相同的 completion condition，而不是用 `sim-cycles` timeout 充当成功；
- 相同的背景 traffic 和 offered load；
- source 是否属于 destination set 必须显式配置，默认包含 source，但本地交付不计 internal-link traversal。

主要比较必须同时报告 isolated latency 和 contention/throughput，不能只报告无竞争的 single-flit 单轮结果。

## 3. Baselines

### 3.1 Required baseline: naive replicated unicast

源端针对 `destination_set` 中每个非本地目的节点生成一份普通 unicast packet，全部走标准 deterministic XY。源端应在 VC/credit 允许时尽快注入所有副本，不能人为逐个 round 延迟，否则会夸大 tree multicast 收益。

需要满足：

- 每个副本保留共同的 `round_id` 和 logical multicast ID；
- network-level tracker 按 `(round_id, destination_router)` 去重和判定完成；
- logical request 只计一次，physical packets/flits 按实际副本计数；
- 支持和 tree multicast 完全相同的 destination subset；
- 使用普通 Garnet router pipeline，不允许调用 tree replication path。

优先复用 Garnet NI 对 multi-destination `NetDest` 的 unicast decomposition；如果当前 synthetic protocol 无法构造完整 `NetDest`，则在 tester/NI 增加显式 baseline mode，但不能复制 tree multicast Router 逻辑。

### 3.2 Tree multicast under test

源端每个 logical request 只注入一次。Router 根据 destination mask/subtree mask，仅向包含目标节点的 child branch 复制；不能永远广播到全部 Router 后把 full broadcast 称为任意 multicast。

现有实现可作为第一阶段的 `destination_set = all routers` single-flit correctness 起点，但最终需要支持：

- arbitrary one-to-N destination subset；
- source included/excluded；
- multi-flit packet；
- backpressure 下的安全复制；
- 多轮和多个 source 的性能 workload。

### 3.3 Analytical reference

离线计算相同 source/destination set 在当前 tree 上需要的 unique internal edges，得到：

```text
ideal_tree_link_traversals = unique edges in the pruned multicast tree
naive_xy_link_traversals = sum of XY path lengths to every destination
```

该结果用于解释流量下界和实测差距，不替代 runnable baseline。

## 4. Required architecture work

### Phase M1 — Mode-neutral workload and completion tracker

增加统一模式参数，例如：

```text
--multicast-mode=naive_unicast|tree_multicast
--multicast-destinations=all|comma-separated-list|random:K
--multicast-source=<router id>
--multicast-rounds=<N>
--multicast-packet-flits=<N>
--multicast-seed=<N>
```

将当前仅面向 collective 的 tracker 泛化为 logical multicast tracker。每轮记录 expected destination bitmap、received bitmap、first injection tick 和 last delivery tick。任何 missing、duplicate、wrong payload、wrong round 或越界 destination 都必须 fatal。

验收：2x2 和 3x3 上，两个 mode 对多个 destination subset 产生完全相同的交付结果和主动退出原因。

### Phase M2 — Naive unicast baseline

实现 source-side replication baseline，并验证实际 physical packet 数：

```text
logical_requests = rounds
physical_unicast_packets = rounds * remote_destination_count
```

本地目的只完成一次 local delivery，不产生 internal-link traversal。baseline 必须支持连续注入，正确处理 VC 不足和 retry，不能因为部分副本已经发出而重复整个 logical request。

验收：2x2/3x3/4x4，多 root、多个 group size、至少 100 轮；无 duplicate、hang、credit leak。

### Phase M3 — Arbitrary subset tree pruning

为 tree multicast 携带 destination bitmap 或等价 subtree metadata。Router 只复制到与目标集合相交的 child branch，并只在本 Router 属于 destination set 时生成 local copy。

验收：枚举 2x2 的全部非空 destination subsets；3x3/4x4 使用固定 seed 随机 subset，并与 naive baseline 的 destination bitmap 逐轮一致。

### Phase M4 — Multi-flit packet support

当前 scalar collective 的 single `HEAD_TAIL` 限制保留给 all-reduce，但 multicast 必须扩展为真实 packet：`HEAD/BODY/TAIL` 全部保持相同 logical ID、round ID 和 destination metadata。

必须明确复制策略：

- head 建立每个 branch 的 replication state；
- body/tail 沿相同 branch set 传播；
- 某个 child 无 VC/credit 时不能丢弃或重复其他 branch；
- tail 完成后释放所有 branch state 和上游 credit；
- serialization/deserialization 后 metadata 不丢失。

建议依次验收 1、2、4、8、16、64 flits，并使用小 buffer/低 VC 配置主动制造 backpressure。

### Phase M5 — Performance workload modes

增加两类测量：

1. `latency`：同一时刻只允许一个 outstanding logical multicast，测 isolated completion latency；
2. `throughput`：按 injection rate 或固定 gap 注入，允许多个 outstanding rounds，测 steady-state completed multicasts/cycle。

吞吐 workload 需要 warmup/measurement/cooldown，且达到 sim-cycle 上限但未完成 expected requests 时必须判失败。至少支持：

```text
--multicast-injection-rate
--multicast-max-outstanding
--multicast-warmup-rounds
--multicast-measurement-rounds
--multicast-background-traffic
```

背景流量至少覆盖 none 和 uniform-random unicast；随机实验固定并打印 seed。

## 5. Required statistics

统计必须区分 logical work、physical packets、physical flits 和 flit-link activity。

### 5.1 Correctness and completion

- `multicast_logical_requests_injected`
- `multicast_logical_requests_completed`
- `multicast_destinations_expected`
- `multicast_destinations_delivered`
- `multicast_duplicate_deliveries`
- `multicast_incomplete_requests`
- per-round completion tick，至少输出 average/min/max；建议增加 p50/p95/p99

### 5.2 Traffic and replication

- source-generated physical packets/flits；
- Router-generated physical flits；
- local deliveries；
- internal-link flit traversals；
- per-vnet internal/external link traversals；
- Router replication events 和 fanout histogram；
- tree edges used、pruned branches；
- logical bytes delivered / physical byte-hops。

当前通用 `average_hops` 不能直接作为 tree multicast 总流量指标，因为 Router replication 会生成新 flit 并重置 route state。主要结论必须使用实际 internal-link flit traversal；average hops 只作为辅助指标。

### 5.3 Latency, congestion, and throughput

- logical multicast completion latency；
- per-destination latency；
- packet/flit network latency；
- packet/flit queueing latency；
- completed logical multicasts per cycle；
- delivered logical bytes per cycle；
- average/max link utilization；
- average/max VC occupancy 或 queue depth；
- stalls due to missing output VC/credit；
- simulation completion tick。

### 5.4 Derived comparison metrics

每个 paired case 自动计算：

```text
latency_speedup = naive_completion_latency / tree_completion_latency
traffic_reduction = 1 - tree_link_traversals / naive_link_traversals
throughput_improvement = tree_throughput / naive_throughput - 1
queueing_reduction = 1 - tree_queueing_latency / naive_queueing_latency
```

同时报告绝对值，不能只报告百分比。

## 6. Experiment matrix

### 6.1 Quick regression on every protocol change

- Mesh: 2x2、3x3；
- source: corner、center（存在时）；
- destination set: all、single remote、同 row、同 column、随机 50%；
- packet: 1、4 flits；
- mode: naive/tree；
- rounds: 5；
- background: none；
- 检查 correctness、completion-driven exit 和精确流量计数。

### 6.2 Full correctness matrix

- Mesh: 2x2、3x3、4x4；
- source: corner、edge、center；
- group size: 1、25%、50%、75%、100%；
- packet: 1、2、4、8、16、64 flits；
- VC/buffer: default 和受限 backpressure 配置；
- rounds: 至少 100；
- mode: naive/tree。

### 6.3 Performance matrix

- Mesh: 4x4 为主，2x2/3x3 用于趋势核对；
- group size: 25%、50%、100%；
- packet: 1、4、16、64 flits；
- source placement: corner、center；
- offered multicast load: low、medium、saturation sweep；
- background unicast load: 0、0.1、0.2 或根据 saturation 点归一化；
- 每项至少 3 个固定 seed；
- naive/tree paired run 必须使用同一 seed 和 destination sequence。

输出 CSV/JSON summary，至少包含 case parameters、raw metrics、derived speedup 和 artifact path。绘图脚本生成：

- completion latency vs. group size；
- link traversals vs. group size；
- throughput vs. offered load；
- latency vs. offered load；
- queueing latency/link utilization heatmap；
- packet size sensitivity。

## 7. Automation and file layout

建议在现有 `tests/gem5/lab4/` 下扩展：

```text
tests/gem5/lab4/
  run_multicast_correctness.py
  run_multicast_performance.py
  analyze_multicast.py
  cases/
    quick.json
    full_correctness.json
    performance.json
```

runner 负责并行执行和失败汇总；analyzer 只读取 raw stats，不重新运行仿真。每个 case 保存 command、git revision、binary path、seed、`config.ini`、`stats.txt` 和 `sim.log`。

现有 `run_collective_matrix.py` 保留为 scalar collective regression，不直接充当最终 multicast performance runner。

## 8. Sequential acceptance gates

严格按以下顺序推进，前一 gate 通过后才能进入下一项：

1. **G1 — Common semantics**：两个 mode 使用同一 logical request 和 destination tracker；
2. **G2 — Naive baseline**：source replication 正确，多轮无 duplicate/hang；
3. **G3 — Arbitrary subset**：tree pruning 与 naive 逐轮交付集合一致；
4. **G4 — Multi-flit/backpressure**：1--64 flits 和受限 buffer/VC 全通过；
5. **G5 — Statistics audit**：小拓扑手算 traffic/latency 与 stats 精确一致；
6. **G6 — Quick/full regression**：correctness matrix 全绿；
7. **G7 — Performance study**：paired matrix、CSV/JSON、图表和至少 3 seeds 完成；
8. **G8 — Multicast conclusion**：文档说明收益、代价、饱和点、失败场景和限制。

G8 之前不开始 bypass。不能用“仿真正常退出”“单轮更快”或“Router flit 更少”单独替代上述验收。

## 9. Definition of done

Multicast 只有同时满足以下条件才算完成：

- runnable naive unicast baseline 和 tree multicast 使用相同 workload contract；
- full destination set 与 arbitrary subset 均正确；
- 1--64 flit packet 在 backpressure 下无丢包、重复、死锁和 credit leak；
- isolated latency、contention throughput 和背景 traffic 均有 paired comparison；
- logical/physical/link-level stats 经手算和自动测试审计；
- 2x2/3x3/4x4 correctness matrix 全绿；
- performance results 可由一个命令复现并输出 raw data 与图表；
- 报告同时给出绝对值、speedup、traffic reduction、硬件/状态开销和限制；
- README 与实际参数、测试命令、当前完成边界一致。

以上 Definition of Done 已满足。随后创建并完成了独立 `bypass.md` 的
G1--G10；真实 H100 broadcast replay 又以 30/30 requests、6,720 flits
验证了 trace consumer。完整数据和限制见 `report/multicast_report.pdf`。
