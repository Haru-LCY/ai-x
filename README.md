# Lab4 Project — AI Collectives on Mesh NoC

## 1. Introduction

本项目基于 gem5 Garnet，研究 Mesh NoC 中面向分布式 AI 通信的 in-network collective communication。核心设计是让 Mesh Router 参与 AllReduce：各 node 注入局部贡献，Router 沿 XY 路由诱导的 convergence tree 进行部分归约，root 再沿树广播全局结果。

项目采用分阶段路线：先用 single-flit scalar AllReduce 验证协议正确性和 credit 稳定性，再独立完成 multicast 和 bypass/express links，最后接入真实 GPU collective trace。当前 Topic 3 的 multicast/bypass 及其联合路径、Topic 4 的 broadcast/all-reduce trace replay 均已完成实现和实验验收。

项目可定位为 Topic 4（与 interconnection 相关的其他项目），同时 multicast 和 bypass 扩展也覆盖 Topic 3 的 microarchitecture 方向。本仓库同时包含 gem5 实现、运行配置和 `tests/gem5/lab4/` 下的 collective 回归工具。

## 2. Project highlights

项目的研究叙事是：现代分布式 AI 训练受到 collective communication 开销限制；one-to-many traffic 产生重复复制，远距离节点之间的多跳传输增加 latency 和拥塞。因此项目研究 Router-level reduction、tree multicast/broadcast 和 bypass link 如何共同优化 Mesh NoC 上的 AI-style collectives。

当前已实现并验收的主要亮点：

- **Deterministic convergence tree**：根据 `Mesh_XY` 的 XY 路由和 `--collective-root`，预计算每个 Router 的 parent、children 和 expected fan-in。
- **In-network reduction**：Router 对 scalar collective flit 做累加，非 root 只向 parent 发送一个 merged flit。
- **Tree broadcast**：root 得到全局 sum 后沿同一棵树传播，使每个 node 收到相同结果。
- **Complete multicast comparison path**：`naive_unicast` 与 `tree_multicast` 使用相同 logical request；支持任意目的集合、1--64 flit packet、背压、多 outstanding、背景流量和 paired CSV/JSON 报告。
- **Bypass/express links**：支持 diagonal/stride placement、optimistic/distance-scaled wire model、硬件成本统计和 cost-aware multicast 选路；稀疏 2×2 定向流量实测加速 12.5%，完整 all-rank tree 流量安全回退到普通 XY tree。
- **Real-GPU trace replay**：仓库提交了真实执行的 8×H100 NCCL collective microbenchmark、broadcast/all-reduce replay 和严格 paired runner；所有缩放因子、hash、命令和计数均保留。
- **Fair evaluation contract**：timeout 不是成功结果；paired case 使用相同输入和退出条件，并核对 logical request、physical packet、flit、merge、delivery、p95 和 wire-distance 统计。

真实 trace 的 all-reduce 以 6,720 个独立 scalar lanes 回放，每个 lane 都执行 Router reduce + tree broadcast；它不是 unicast 分解，但也不是 multi-flit/vector reduction hardware。当前结果不能外推为完整模型训练或 H100/NVLink 性能。

## 3. Architecture

### 3.1 Network topology

网络使用 `Mesh_XY`。Router id 与坐标的关系为：

```text
x = router_id % columns
y = router_id // columns
```

对于 root `(rx, ry)`，任意 Router `(x, y)` 的 parent 方向由 XY 路由唯一确定：先沿 X 维移动到 `rx`，再沿 Y 维移动到 `ry`。将所有 parent 边反向即可得到 children 集合。

每个 Router 保存以下元数据：

```text
parent_outport       # 向 root 的出方向，root 为空
child_inports        # 子 Router 合并 flit 的入方向
expected_fanin       # len(children) + 1，本地贡献也计入
```

### 3.2 Reduce and broadcast protocol

保底协议的目标流程如下：

```text
local contribution
       │
       ▼
child Routers ── merged flit ──► parent Routers ──► root
                                                      │
                                                      ▼
                         broadcast global sum to every child
```

每个 Router 只维护当前串行 collective 的一组状态：`accum`、`count` 和 `active`。收到 reduce flit 后累加并计数；收齐 fan-in 后，非 root 向 parent 发送一个 merged flit，root 产生最终 sum。broadcast 阶段需要对每个 child 出端口复制 flit，并正确处理 credit。

## 4. Implementation status

### 4.1 Completed

- `Mesh_XY.py`：计算并下发 parent/children/fan-in tree metadata；支持 2×2、3×3、4×4 Mesh 和多个 root。
- Garnet flit：增加并传递 `value`、`collective_id` 和显式 `CollectiveOp`（`Reduce`、`Broadcast`、`Multicast`）。
- Router：实现串行 scalar reduction state (`accum/count/active`)、merged flit 上行和 tree broadcast。
- NetworkInterface：注入 deterministic contribution，eject 时校验最终结果，并按 Router 去重验证全目的端交付。
- Traffic generator：支持 completion-driven AllReduce，以及 multicast latency/throughput、bounded outstanding、warmup/measurement/cooldown 和 deterministic uniform-random background traffic。
- Packet size：scalar AllReduce 仍保留 single-flit 约束；multicast 已解除该约束并验证 1、4、16、64 flit packet。
- Multicast datapath：已实现 replicated-unicast baseline、64-bit destination bitmap、逐跳分支裁剪、Router 内复制、多 flit branch state 和 backpressure-safe credit handling。
- Bypass datapath：已实现额外 express links、deterministic oracle、距离缩放、链路/跨距/Router traversal 统计，以及 tree-sharing-aware multicast policy。
- Trace consumer：broadcast 保留 per-request release cycle 和动态 packet flits；all-reduce 保留 event release eligibility 并展开为独立 scalar reduction lanes。
- 统计与回归：旧 collective 11/11、multicast correctness 208/208、performance 162/162 pairs，以及 T3/T4 完整 trace replay 全部通过。

### 4.2 Optional extensions

- 让 all-reduce convergence tree 在成本约束下使用 bypass；
- 实现 multi-lane 并行或 vector/tensor reduction，而不是当前 scalar-lane 串行 datapath；
- 接入完整模型训练 trace，并补充 naive/ring/tree all-reduce baseline。

### 4.3 Not yet claimed

当前尚未声称完成 tensor-level distributed training、完整 PyTorch/LLM 训练或 AllReduce 三种 baseline 的最终对比。

## 5. Phased roadmap and acceptance criteria

### Phase 1 — Scalar protocol correctness

single-flit、scalar、串行单 collective。验证 Router reduction、fan-in、tree broadcast、credit 回收和正常退出。理论结果为 `sum = N * (N + 1) / 2`。

### Phase 2 — Scalar stability and scale

运行至少 100 轮，覆盖 2×2、3×3、4×4 Mesh，以及角落、边缘和中心 root。所有 node 每轮都必须收到相同 sum，且不能 hang 或留下残留 flit/credit。

### Phase 3 — Fair scalar baselines

实现并统一比较 naive unicast AllReduce、ring AllReduce 和 tree in-network AllReduce。三种方案必须使用相同的 Mesh、root、`f(src)`、轮数和退出条件，并记录 completion cycles、total flits、average hops、network latency 和 queueing latency。

### Phase 4 — Tensor-chunk extension

将 scalar 扩展为 multi-flit/vector element-wise AllReduce，测试不同消息大小和 flit 数量，验证 Router reduction 与 credit/backpressure 在大消息下的行为。

### Phase 5 — Topic-oriented microarchitectural extensions

实现并评估独立 multicast，以及 bypass/express links。Multicast、bypass 和 multicast interaction 均已完成实现、自动验收和定量报告；multicast 解决重复 one-to-many traffic，bypass 解决远距离多跳 traffic。每个扩展都保留独立 baseline、正确性测试和定量结果。

### Phase 6 — Final evaluation and report

完成实验矩阵、架构图、算法伪代码、理论通信量、实测结果、失败场景、限制说明和可复现实验命令，最终报告与代码状态保持一致。

### Current acceptance boundary

课程范围内的 Topic 3 multicast/bypass 与 Topic 4 trace-based traffic 已完成。Phase 1/2、Phase 5 和 trace replay T1--T4 均有自动验收数据；Phase 3 的 ring/naive all-reduce 和 Phase 4 的真正 vector reduction 是明确标注的可选扩展，不属于当前完成声明。

## 6. Reproduction

在仓库根目录构建并运行完整 collective 矩阵：

```bash
LD_LIBRARY_PATH=/path/to/python/lib \
  scons build/Garnet_standalone/gem5.opt -j32 PROTOC=/bin/false
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_collective_matrix.py --jobs 11 --rounds 5
```

运行当前 multicast correctness 和 paired performance runner：

```bash
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_multicast_matrix.py \
    --jobs 32 --rounds 10 --packet-flits 1 4 16 64
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_multicast_performance.py --jobs 32
```

验证并回放仓库中的真实 H100 trace：

```bash
python3 util/lab4_trace/validate_trace.py traces/h100_8gpu_collectives.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_broadcast_replay.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_allreduce_replay.json

LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_trace_replay.py \
    --gem5 build/Garnet_standalone/gem5.opt \
    --source-trace traces/h100_8gpu_collectives.json \
    --replay traces/h100_8gpu_broadcast_replay.json \
    --output /tmp/lab4-t3 --sim-cycles 30000000

LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_allreduce_trace_replay.py \
    --gem5 build/Garnet_standalone/gem5.opt \
    --source-trace traces/h100_8gpu_collectives.json \
    --replay traces/h100_8gpu_allreduce_replay.json \
    --output /tmp/lab4-t4 --sim-cycles 100000000
```

测试工具为每次运行创建独立 `/tmp/lab4-*-matrix-*` 或指定的 output 目录，并保留每项的 `sim.log`、`stats.txt`、`config.ini` 和 `config.json`。performance runner 额外输出 `summary.csv` 和 `summary.json`。HDF5 缺失只会产生 warning；Lab4 不依赖 protobuf tracing，因此构建使用 `PROTOC=/bin/false`。

## 7. Development constraints

- Multicast 已完成；bypass G1--G10 已按逐 gate 验收，trace replay T1--T4 也已完成；
- 每次协议改动都要保留独立正确性测试；
- `lab4_smoke.log` 和 `m5out_lab4_smoke/` 是运行产物，不应作为源码提交；
- AllReduce 性能比较必须包含完整 reduce + broadcast 流程；multicast/bypass 则按各自统一的 logical request 比较；
- 文档状态必须和已验收代码保持一致，不能把规划项误标记为完成。

## 8. Reference files

- `configs/topologies/Mesh_XY.py`：collective tree 元数据构造。
- `configs/example/garnet_synth_traffic.py`：synthetic collective 入口与参数约束。
- `tests/gem5/lab4/run_collective_matrix.py`：并行回归矩阵与精确统计检查。
- `tests/gem5/lab4/run_multicast_matrix.py`：naive/tree、目的集合和 multi-flit correctness matrix。
- `tests/gem5/lab4/run_multicast_performance.py`：paired latency/throughput performance runner。
- `tests/gem5/lab4/run_trace_replay.py`：真实 broadcast trace 的 Mesh/Bypass paired runner。
- `tests/gem5/lab4/run_allreduce_trace_replay.py`：真实 all-reduce scalar-lane paired runner。
- `traces/`：原始 8×H100 trace、两个 replay 文件及 SHA-256 说明。
- `tests/gem5/lab4/README.md`：回归使用说明。
- `multicast.md`：multicast contract、实现阶段与完成状态。
- `bypass.md`：bypass baseline、架构、验收和性能实验规划。

## 9. Current status (2026-08-07)

### 9.1 What is working

- 已完成 Garnet collective plumbing：`collective-root` 配置、Mesh_XY 树元数据、flit 的 `value`/`collective_id`/`CollectiveOp` 字段，以及 Router/NetworkInterface 的 collective 接口。
- 已完成 Router 内部的单轮标量归约和 root 广播路径。2×2、root=0、single-flit、单轮 Stage 1 测试已通过：4 个节点注入、子树合并、root 汇总为 10，并向所有节点广播且仿真正常退出。
- 首次广播失败暴露的 Router 子节点方向映射错误已经修正。输入方向的含义是“从父 Router 指向 child 的方向”，因此 East/West/North/South 必须分别映射为 `(x+1)`, `(x-1)`, `(y+1)`, `(y-1)`。
- collective 注入值已按规范使用 `src_ni + 1`；普通 smoke traffic 仍使用 `src_ni`。
- 多轮执行由每轮全目的端交付完成事件驱动，最终一轮主动退出；不再依赖固定 period 或超时判定成功。
- 2×2、3×3、4×4 的 11 项 all-reduce/multicast 矩阵全部通过，并核对精确协议统计。
- 独立 multicast 已完成 `naive_unicast` 和 `tree_multicast` 两种可运行模式；任意目的 bitmap、local delivery、tree pruning 和 replicated baseline 使用统一完成语义。
- Multicast 已支持 1--64 flit packet、受限 VC/buffer 背压、多个 outstanding round 和 deterministic background traffic，不再强制 single flit。
- 最终验收包括旧 collective 11/11、multicast correctness 208/208、performance paired cases 162/162；构建、Python compile 和结果有限值检查均通过。
- T3 broadcast：30/30 requests、6,720/6,720 source flits；Mesh_XY 与 cost-aware Mesh_Bypass 均为 17,047,500 measurement ticks，p95 为 643,500 ticks。
- T4 all-reduce：15 trace events 展开为 6,720 lanes；53,760 contributions、53,760 Router merges、53,760 deliveries 和 147,840 collective Router flits 全部精确匹配。

### 9.2 Current status and next blocker

Multicast M1--M5、bypass G1--G10 和 trace replay T1--T4 已分别提交验收。当前没有课程计划内阻塞项；后续均属于 vector reduction、完整模型 trace 或 bypass-aware all-reduce 等扩展。Distance-scaled 结果仍不支持宣称 bypass 具有普遍收益。

### 9.3 Build pitfalls and recovery

1. **Protobuf 链接失败**：Lab4 不需要 Protobuf tracing。不能只忽略 linker 报错；构建时使用 `PROTOC=/bin/false`，让 gem5 明确关闭 protobuf 相关生成功能，并确认最终 binary 可运行。
2. **Python ABI 与动态库**：构建和运行必须使用同一套 Python 头文件/库，并把对应 lib 目录加入 `LD_LIBRARY_PATH`。当前 Python 3.13 还要求避免依赖函数内 `exec()` 写回局部变量。
3. **有效构建目标**：当前目标是 `build/Garnet_standalone/gem5.opt`；不要混用其他协议/ISA build 目录。
4. **并行度**：当前机器可使用 `-j32` 构建；回归工具通过 `--jobs` 控制案例级并行度。
5. **非 2 次幂 directory 配置**：gem5 默认 memory interleave 逻辑要求 directory 数量为 2 的幂。3×3 Mesh 仍使用 9 个 Router，但 synthetic Garnet 测试配置 16 个 directory controllers；前 9 个 directory 对应 9 个 Router，多余 directory 由 Mesh_XY 挂到 Router0。collective 的 Router 数量和树语义仍由 `--num-cpus=9 --mesh-rows=3` 决定。

### 9.4 Verification artifacts

回归工具打印当次唯一 artifact 目录。每个 case 的 `sim.log` 用于确认连续 round 和 completion-driven exit，`stats.txt` 用于确认理论通信量与实测计数一致；运行产物不提交到源码仓库。

### 9.5 Remaining minimum-work items

当前计划已完成。可选工作为：AllReduce naive/ring baseline、真正 vector reduction、完整训练 trace，以及 wire/radix-matched bypass capacity baseline。
