# Bypass / Express-Link implementation plan

## Implementation status (2026-08-07)

G1--G10 are implemented and accepted. The audited G8 sweep contains 7,680
successful gem5 runs and 6,144 paired seed cases; G9 records cost-aware and
distance-scaled conclusions, and G10 covers 624 multicast-interaction runs.
Optimistic links are treated only as an upper bound. Distance-scaled low-load
means regress for both diagonal and stride placement, so the project does not
claim a universal bypass speedup.

The later tree-sharing-aware policy activates bypass for a sparse diagonal
destination (3,500 versus 4,000 ticks on the directed 2x2 gate) but preserves
ordinary XY edges for shared trees. The complete 30-request H100 broadcast
replay uses zero express flits and ties Mesh_XY; this is an intentional policy
decision, not an unimplemented path. Evidence is in `report/bypass_g9.md`,
`report/bypass_g10.md`, and `topic4_trace_replay_t3.md`.

## 1. Topic interpretation and scope

Topic 3 要求为 NoC 增加可以跨过中间节点的额外链路，例如连接对角节点，并选择合适 baseline 比较性能。本项目把本阶段的 **bypass** 明确定义为：

> 在保留原始 2D Mesh 全部 Router 和普通链路的基础上，增加少量 bidirectional physical express links。一个 express-link traversal 可以跨过原本需要经过的一个或多个中间 Router。

本阶段不是完整复刻 Express Virtual Channel (EVC) 或 SMART。EVC/SMART 主要让 packet 沿既有物理方向跳过 Router pipeline；本项目首先实现 assignment 直接要求的“额外 links”。如果后续增加 speculative switch bypass 或 single-cycle multi-hop，它必须作为独立模式，不能与 express-link 收益混在一起。

本阶段也不修改已经验收的 multicast 语义。主实验先比较普通 unicast traffic 上的 plain Mesh 与 bypass Mesh；最后再做 `multicast on/off × bypass on/off` 的正交组合实验，区分两种机制各自的收益。

## 2. Literature basis

规划主要依据以下原始工作和 Garnet 官方机制：

1. Ogras 等人的 long-range link 工作在规则 Mesh 中插入少量长链路，以降低平均节点距离并改善拥塞临界负载；论文同时强调 bounded buffers、任意 packet size、deadlock-free routing，以及长线的 repeaters/面积成本。这与本 Topic 的“额外 shortcut links”最直接对应：
   - [Application-Specific Network-on-Chip Architecture Customization via Long-Range Link Insertion, ICCAD 2005](https://doi.org/10.1109/ICCAD.2005.1560072)
   - [Communication Architecture Optimization: Making the Shortest Path Shorter in Regular Networks-on-Chip, DATE 2006](https://past.date-conference.com/proceedings-archive/2006/DATE06/PDFFILES/06F_3.PDF)
2. Flattened Butterfly 说明高 radix/长连接可以降低 network diameter 和中间 Router traversal，但同时改变 Router port 数、布线和 bisection bandwidth。因此不能只报告 hop reduction，必须报告额外链路与 radix 成本：[Flattened Butterfly Topology for On-Chip Networks, MICRO 2007](https://cva.stanford.edu/publications/2007/MICRO_FBFLY.pdf)。
3. EVC 证明跳过中间 Router pipeline 可以降低 latency/energy，并提醒我们区分“physical hop”“Router traversal”和“wire distance”：[Express Virtual Channels: Towards the Ideal Interconnection Fabric, ISCA 2007](https://doi.org/10.1145/1250662.1250681)。
4. SMART 展示 single-cycle multi-hop bypass，但它需要不同的 link/crossbar/control microarchitecture，故仅作为后续 stretch reference：[SMART: A Single-Cycle Reconfigurable NoC for SoC Applications, DATE 2013](https://people.csail.mit.edu/suvinay/pubs/2013.smart.date.pdf)。
5. Garnet 允许 topology 为每条 internal link 指定方向、weight 和 latency，并支持 table-based shortest path 或 `routing_algorithm=2` 的 custom routing；Router 使用 VC/credit flow control：[gem5 Garnet 2.0 documentation](https://www.gem5.org/documentation/general_docs/ruby/garnet-2/)。

由此得到本项目的原则：先做少量显式长链路；路由必须可证明或可机械审计无 channel-dependency cycle；长链路 latency 和 wiring cost 必须显式建模；性能结论必须与 plain Mesh paired 比较。

## 3. Baselines and variants

### 3.1 Required baseline: `mesh_xy`

保留现有 `Mesh_XY`，不增加链路，使用 deterministic XY。它是主要 runnable baseline。baseline 与 bypass variant 必须保持相同：

- Router 数和端节点映射；
- clock、普通 Router latency、普通 link latency/width；
- vnet、VC 数、buffer depth 和 packet size；
- source/destination sequence、injection time、seed 和完成条件；
- warmup/measurement/cooldown 与背景 traffic。

### 3.2 Design under test: `mesh_bypass`

新建独立 topology（建议 `configs/topologies/Mesh_Bypass.py`），复制 plain Mesh 的普通链路，再按确定性规则增加 express links。不要直接改写 `Mesh_XY.py`，避免 baseline 随设计一起变化。

第一版支持两种 link family：

1. `diagonal`：连接 `(x, y)` 与 `(x+1, y+1)` 或 `(x+1, y-1)`，一次 traversal 替代两个 Manhattan hops，直接覆盖 Topic 示例；
2. `stride`：连接同行或同列、距离为 `S >= 2` 的 Router，一次 traversal 跳过 `S-1` 个中间 Router。

每条逻辑双向连接必须由两条 Garnet unidirectional internal links 和对应 credit links 构成。默认只选择固定、对称、可复现的 link set；随机或 traffic-aware link placement 只能作为后续 variant，并固定 seed/预算。

建议参数：

```text
--bypass-mode=none|diagonal|stride
--bypass-stride=<N>
--bypass-link-budget=<undirected links>
--bypass-placement=checkerboard|symmetric|file:<json>
--bypass-routing=deterministic|table
--bypass-link-latency=<cycles>
--bypass-wire-model=optimistic|distance_scaled
```

### 3.3 Cost-matched sensitivity baseline

增加 express links 会同时增加容量、端口和布线。主要 baseline 仍是 plain Mesh，但完整报告至少增加一种 sensitivity：

- `distance_scaled`：express link latency 随几何长度增加；
- `equal_wire_budget`：不同 placement 使用相同的总 Manhattan wire length 和相同 undirected-link budget；
- 如实现成本允许，再增加 `local_capacity`：把同等链路预算用于重复热点附近的普通短链路，用于区分“更多带宽”和“更短路径”。

`local_capacity` 是增强 baseline，不阻塞最小 Topic 完成；但没有 wire-aware sensitivity 时不得宣称硬件效率更高。

### 3.4 Analytical references

每个 topology 离线计算以下静态值，用来审计实现，不充当 runnable baseline：

```text
diameter
mean shortest-path physical hops
mean Router traversals
total added unidirectional links
total Manhattan wire length
maximum / average Router radix
```

## 4. Routing and deadlock contract

### 4.1 Why existing XY is insufficient

`RoutingUnit::outportComputeXY()` 只认识 East/West/North/South，并假设每次移动一个坐标单位；它不会自动使用 diagonal/stride link。Garnet table routing能根据 link weights 生成 shortest paths，但任意长链路可能引入新的 channel dependency cycle。有限轮测试不 hang 不能代替 deadlock argument。

### 4.2 Required first routing policy

第一版使用 deterministic bypass-aware routing，并满足：

- 每一步必须严格降低预计算的 remaining route rank/cost；
- 同一 `(source, destination)` 只有一个 next hop；
- head 选择的路径被 body/tail 复用；
- local destination 不进入 internal link；
- express link unavailable 时不能静默改走可能形成环的任意路径；
- ordered vnet 的 packet ordering 不被破坏。

实现前由 route oracle 枚举所有 source/destination pair，输出完整 next-hop/path table，并构建 channel-dependency graph。只有所有路径可达、无 loop、终点正确且 dependency graph 为 DAG，路由 gate 才通过。

如果 minimal shortest-path routing 的 dependency graph 有环，优先采用以下两种方法之一，而不是仅靠增大超时：

1. 限制 express-link 使用阶段/turn，使 channel class 单调变化；
2. 增加专用 escape VC，escape VC 只走 deadlock-free XY，并禁止从 escape 返回 express class。

具体选择必须由自动 dependency audit 验证。仅仅使用 `TABLE_` 和 link weight 不构成 deadlock-free 证明。

### 4.3 Link latency models

至少同时报告两种模型：

- `optimistic`：所有 express link 与普通 link latency 相同，用于展示 Router-hop bypass 的上界；
- `distance_scaled`：按 physical span 设置 link latency，例如 diagonal length 取保守的 2 Manhattan segments，stride-S 取 S segments，或明确给出采用的 ceil/serialization 公式。

任何主结论必须包含 `distance_scaled`。只用 1-cycle long link 的结果标记为 upper bound，不能作为最终收益。

## 5. Required implementation work

### Phase B1 — Freeze topology and baseline contract

- 新增 `Mesh_Bypass.py`，`none` 模式生成与 `Mesh_XY` 等价的 Router/internal-link graph；
- 为每条普通/express link 记录 source、destination、physical span、latency 和 stable name；
- 新增 topology dump/oracle，输出 JSON；
- plain/bypass paired runner 固定完全相同的 workload 参数。

验收：2x2、3x3、4x4 上，`none` 与 `Mesh_XY` 的节点、普通链路、路由和关键 stats 一致；所有 express link 双向和 credit connection 完整；无重复 port name/link id。

### Phase B2 — Bypass-aware routing

- 增加 custom routing 或经过严格约束的 table routing；
- 离线枚举所有 source/destination path；
- 校验 reachability、终点、loop freedom、determinism 和 channel-dependency DAG；
- 单独统计 ordinary/bypass traversal。

验收：对每个 topology/link placement 穷举 all-to-all single-packet route；预期可用 shortcut 的 pair 必须实际经过 express link，其他 pair 与 route oracle 完全一致。

### Phase B3 — Multi-flit and backpressure safety

- 验证 HEAD/BODY/TAIL 沿同一路径；
- 小 buffer、1 VC、高 router/link latency 下制造 backpressure；
- 覆盖多个并发 source、相反方向 express-link contention 和普通/express 交叉 contention；
- 检查 credit conservation、无 duplicate/drop/reorder。

验收：packet size 1、2、4、8、16、64 flit；至少 100 rounds；default 与受限 VC/buffer 两套配置均 completion-driven 正常退出。

### Phase B4 — Workload and statistics

复用 Garnet synthetic traffic，并增加 paired runner。至少支持：

- latency：单 outstanding，测 zero/low-load latency；
- throughput：offered-load sweep，允许多个 outstanding；
- traffic：uniform random、transpose、bit complement、hotspot；
- mechanism-directed：只用于 sanity 的 diagonal/stride endpoint traffic；
- warmup/measurement/cooldown 和固定 seeds。

达到 sim-cycle limit 但 expected packets 未完成必须判失败，不能把 timeout 当性能结果。

### Phase B5 — Performance study and report

- 自动输出 raw CSV/JSON、paired summary、command、git revision、seed 和 artifact path；
- 对 `mesh_xy` 与每个 bypass variant 做 paired comparison；
- 同时报告 optimistic 与 distance-scaled link model；
- 分析收益、饱和点、热点转移、无收益/退化 case 和硬件成本。

### Phase B6 — Multicast interaction

在 bypass 单播机制独立验收后，再运行 2×2 factorial：

```text
naive_unicast + mesh_xy
tree_multicast + mesh_xy
naive_unicast + mesh_bypass
tree_multicast + mesh_bypass
```

同一 case 固定 multicast source、destination bitmap、packet size、seed 和 injection schedule。该阶段回答两种优化是否叠加，不得用组合结果替代 bypass 的单独 baseline。

## 6. Required statistics

### 6.1 Correctness

- injected/completed packets；
- expected/delivered destinations；
- duplicate、dropped、misrouted、out-of-order packets；
- completion reason 和 incomplete requests；
- per-path route-oracle mismatch。

### 6.2 Traffic and bypass usage

- ordinary internal-link flit traversals；
- express-link flit traversals；
- packets/flits using at least one bypass；
- Router traversals；
- physical hops skipped；
- physical wire-flit distance：`sum(flits * link_span)`；
- per-link utilization，分 ordinary/express；
- bypass useful rate 和 endpoint contention。

### 6.3 Latency, throughput and congestion

- packet/flit network latency 与 queueing latency；
- end-to-end average/min/max/p50/p95/p99；
- accepted traffic 和 completed packets/cycle；
- saturation injection rate；
- average/max link utilization；
- VC occupancy、output-VC/credit/switch-allocation stalls；
- total completion tick。

### 6.4 Cost accounting

- extra uni/bi-directional link count；
- total normalized wire length；
- Router radix distribution 与最大 radix；
- extra input/output ports、VCs 和 buffers；
- optimistic area/energy proxy（若没有 DSENT/物理模型，必须明确标为 proxy）。

派生指标至少包括：

```text
latency_speedup = mesh_xy_latency / mesh_bypass_latency
throughput_improvement = mesh_bypass_throughput / mesh_xy_throughput - 1
router_traversal_reduction = 1 - bypass_router_traversals / mesh_router_traversals
wire_traffic_change = bypass_wire_flit_distance / mesh_wire_flit_distance - 1
```

必须同时报告绝对值；不能只报告百分比或 average hops。

## 7. Experiment matrix

### 7.1 Quick correctness on every change

- Mesh：2x2、3x3、4x4；
- bypass：none、diagonal、stride-2；
- traffic：all-to-all single packet、directed shortcut、reverse direction；
- packet：1、4 flit；
- VC/buffer：default；
- 检查 route oracle、精确 link traversal、completion 和 clean exit。

### 7.2 Full correctness

- Mesh：2x2、3x3、4x4，条件允许再加 8x8；
- placement：checkerboard diagonal、symmetric stride-2、至少一个 JSON 固定 link set；
- packet：1、2、4、8、16、64 flit；
- source/destination：all-to-all 与多个并发 source；
- router/link latency：1 和 4；
- VC：1 和 default；
- rounds：至少 100；
- 所有 route graph 与 channel-dependency audit 必须通过。

### 7.3 Performance

- 主网络：4x4、8x8；
- traffic：uniform random、transpose、bit complement、hotspot；
- packet：1、4、16、64 flit；
- offered load：从低负载扫到饱和后至少两个点；
- link model：optimistic、distance_scaled；
- 每项至少 3 个固定 seed；
- `mesh_xy`/bypass paired run 使用同一 destination sequence。

输出图表：

- latency vs offered load；
- accepted throughput vs offered load；
- p95 latency 与 saturation point；
- Router traversals 和 wire-flit distance；
- ordinary/express link utilization heatmap；
- speedup vs link budget / total wire length；
- packet-size 和 placement sensitivity。

## 8. Sequential acceptance gates

严格按顺序推进，前一 gate 验收成功才能开始下一项：

1. **G1 — Baseline equivalence**：`Mesh_Bypass(mode=none)` 与 `Mesh_XY` 图和结果一致；
2. **G2 — Link construction**：额外链路、credit、port、latency 和 topology JSON 精确正确；
3. **G3 — Routing proof/audit**：all-pairs 可达、deterministic、loop-free，channel dependency 无环或有已验证 escape VC；
4. **G4 — Single-flit function**：目标 pair 使用 shortcut，路径和 traversal stats 可手算；
5. **G5 — Multi-flit/backpressure**：1--64 flit、多源、受限 VC/buffer 无丢包、重复、乱序和 credit leak；
6. **G6 — Statistics audit**：小拓扑的 Router traversal、wire distance、latency 与手算完全一致；
7. **G7 — Full correctness**：完整矩阵全绿，旧 collective/multicast 回归无退化；
8. **G8 — Performance study**：paired sweep、3 seeds、CSV/JSON 和图表完成；
9. **G9 — Cost-aware conclusion**：同时给出收益、成本、distance-scaled 结果、退化场景和限制；
10. **G10 — Multicast interaction**：只有 G9 后才评估组合效果。

每个 gate 单独提交。不能用“跑完未 hang”“hop 更少”或 optimistic 1-cycle long link 单独替代验收。

## 9. Proposed files

```text
configs/topologies/Mesh_Bypass.py
configs/example/garnet_synth_traffic.py
src/mem/ruby/network/garnet/RoutingUnit.{hh,cc}
src/mem/ruby/network/garnet/GarnetNetwork.{hh,cc,py}
tests/gem5/lab4/run_bypass_matrix.py
tests/gem5/lab4/run_bypass_performance.py
tests/gem5/lab4/analyze_bypass.py
tests/gem5/lab4/bypass_cases/*.json
bypass.md
```

尽量通过 topology、routing 和 stats 扩展完成，不把 bypass 特例塞进 multicast Router replication path。现有 `run_collective_matrix.py` 和 `run_multicast_matrix.py` 必须作为非退化回归保留。

## 10. Definition of done

Bypass 只有同时满足以下条件才算完成：

- plain `Mesh_XY` 是可运行、未被修改语义的主要 baseline；
- 至少一种 diagonal 和一种 stride express-link placement 可运行；
- 路由有自动 all-pairs 与 channel-dependency audit，而非只靠 timeout；
- 1--64 flit、backpressure、多源 contention 下正确且 credit 守恒；
- latency、throughput、Router traversal、wire distance 和成本统计经过手算审计；
- performance 使用 paired seeds、负载 sweep、optimistic 和 distance-scaled 两种 link model；
- 报告包含绝对值、speedup、饱和点、额外 wire/radix/buffer 成本和退化 case；
- 旧 AllReduce/multicast 回归全部通过；
- README、命令、测试矩阵和代码状态一致，工作区干净。

上述最小 Topic 3 条件已经满足，bypass 实现和成本感知性能结论均已完成。
结论是“机制正确、收益依赖流量与 wire model”，而不是“普遍加速”。真正的
circuit timing/energy、capacity-matched baseline 和 bypass-aware all-reduce
仍是后续扩展。
