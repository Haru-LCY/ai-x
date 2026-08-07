# Tensor All-Reduce 项目接手说明

## 1. 接手目标

这个项目基于 gem5 Garnet，研究 Mesh NoC 上面向分布式 AI 通信的：

- Router 内 in-network reduction；
- tree multicast/broadcast；
- bypass/express links；
- 真实 GPU collective trace replay。

你接手后的主要目标是：**把当前 single-flit、scalar、串行的
in-network all-reduce 扩展为真正的 multi-flit tensor/chunk all-reduce。**

这里的“tensor”不能只表示把一个 tensor 拆成许多互不相关的 scalar
round。目标是让一个 logical all-reduce request 携带多个 flit/lane，Router
能够在 backpressure 下持续归约并广播整个 packet/chunk，同时保留正确的
packet、lane、round 和 credit 状态。

最小完成定义：

1. 一个 logical all-reduce 可以包含 1、4、16、64 个 flit；
2. 每个 flit/lane 在所有 rank 之间执行 element-wise reduction；
3. root 沿 tree 广播完整归约结果；
4. HEAD/BODY/TAIL、VC、credit 和多轮状态不会混淆；
5. 真实 H100 all-reduce trace 不再展开成 6,720 个串行 collective
   rounds，而是保留 15 个 logical events 和各自的 multi-flit payload；
6. timeout、少包、重复、错 lane、错结果或 credit 泄漏必须判失败。

Ring、naive all-reduce 和 bypass-aware all-reduce 是有价值的后续 baseline，
但首要任务是先完成并严格验收 tensor tree all-reduce datapath。

## 2. 当前仓库状态

截至 2026-08-07，课程范围内的 Topic 3 和 Topic 4 已完成：

- Multicast M1--M5 完成；
- Bypass G1--G10 完成；
- 真实 trace replay T1--T4 完成；
- 综合代码提交：`2fb5abde72`；
- 综合文档提交：`bb361a34d1`。

### 2.1 当前 scalar all-reduce

现有 Router 执行真实的 reduce-then-broadcast：

```text
rank contributions
       │
       ▼
child Routers -> partial sums -> root -> tree broadcast -> every rank
```

每个 rank 注入确定值 `rank + 1`。8-rank 测试中，每个目的 NI 都断言最终
结果为：

```text
1 + 2 + ... + 8 = 36
```

但当前 Router reduction path 强制每个 collective packet 是单个
`HEAD_TAIL` flit，并且每个 Router 只有一组活动状态：

```text
active
collective_id
accum
count
```

所以它目前是正确的 scalar reduction，不是 vector/tensor reduction。

### 2.2 当前真实 H100 all-reduce replay

原始输入是实际执行的 8×NVIDIA H100 80GB HBM3 NCCL collective
microbenchmark：

- CUDA 12.8；
- PyTorch 2.8.0+cu128；
- NCCL 2.27.3；
- 48 个事件；
- measurement 阶段包含 15 个 all-reduce 和 15 个 broadcast；
- tensor 大小为 1、4、16 MiB；
- 它不是完整模型训练 trace。

当前 all-reduce compiler 使用 `1/1024` byte scale 和 `1/1024` time
scale，将 15 个事件展开为：

- 6,720 个独立 scalar lanes；
- 53,760 个 rank contribution flits；
- 53,760 个 Router reduce merges；
- 53,760 个最终 rank deliveries；
- 147,840 个 collective Router flits。

输入快照哈希：

```text
c65857924f2a4be0958124a480d60e4f402df5684e5a9b04b7e44427d4933afd  h100_8gpu_collectives.json
7745c3f0f2b282c42e062998159e5d1ef21e9af032ac96f394c3e133d5b2a87f  h100_8gpu_broadcast_replay.json
ebd8386732b93e38c9be462fa48e66d16f46a29e42a9b457e5db5ba76dcbadad  h100_8gpu_allreduce_replay.json
```

Mesh_XY 和 Mesh_Bypass 都精确完成 6,720 lanes：

| metric | Mesh_XY | Mesh_Bypass |
|---|---:|---:|
| measurement ticks | 80,638,000 | 80,638,000 |
| p95 lane ticks | 10,000 | 10,000 |
| wire-flit distance | 94,080 | 94,080 |
| express flits | 0 | 0 |

这证明真实 trace、Router reduction 和结果校验可以工作，但由于 lanes 被
串行化，**不能把这个结果称为 tensor implementation 或 tensor throughput。**

### 2.3 当前 multicast 和 bypass

Multicast 已支持真正 multi-flit packet、1--64 flits、destination bitmap、
Router replication、多 outstanding、backpressure 和严格 credit handling。
这些代码是 tensor all-reduce packet-state 设计的重要参考。

Bypass 已支持 diagonal/stride express links、optimistic/distance-scaled
wire model、route oracle 和成本统计。当前 all-reduce convergence tree 只用
普通 XY parent/child edges，因此 Mesh_Bypass 的 all-reduce express flits 为
0。不要把当前持平结果描述成 bypass all-reduce 加速。

## 3. 重要文件

### Tensor datapath 入口

- `src/mem/ruby/network/garnet/flit.hh`
  - 当前每个 flit 有 `value`、`collective_id`、`CollectiveOp`；
  - tensor 需要明确 lane/chunk/packet metadata 的表示方式。
- `src/mem/ruby/network/garnet/NetworkInterface.cc`
  - collective flit 创建、贡献值设置和最终结果断言；
  - 当前 all-reduce 使用单 flit；multicast 已有动态 packet flit 数逻辑。
- `src/mem/ruby/network/garnet/Router.cc`
  - `handleCollectiveFlit()` 中存在 scalar `HEAD_TAIL` 限制；
  - 当前只有一组 `accum/count/active`；
  - multicast 的 multi-flit branch state 和 atomic credit 检查可作为参考。
- `src/mem/ruby/network/garnet/Router.hh`
  - Router collective 与 multicast 状态定义。
- `src/mem/ruby/network/garnet/GarnetNetwork.{hh,cc,py}`
  - collective round completion、delivery、统计和全局配置。

### Workload 和 trace

- `configs/example/garnet_synth_traffic.py`
  - collective 参数解析和 replay consumer；
- `src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.{py,hh,cc}`
  - release cycle、round 注入与 traffic generation；
- `util/lab4_trace/compile_allreduce_replay.py`
  - 当前把 event 编译成 scalar lanes；tensor 版本需要保留 event/chunk packet；
- `util/lab4_trace/validate_replay.py`
  - replay schema 和精确 flit arithmetic 验证；
- `traces/h100_8gpu_collectives.json`
  - 原始 H100 trace；
- `traces/h100_8gpu_allreduce_replay.json`
  - 当前 scalar-lane replay。

### Regression 和报告

- `tests/gem5/lab4/run_collective_matrix.py`
  - scalar all-reduce 非退化回归；
- `tests/gem5/lab4/run_multicast_matrix.py`
  - multi-flit/backpressure 测试结构参考；
- `tests/gem5/lab4/run_allreduce_trace_replay.py`
  - 当前真实 trace paired gate；
- `topic4_trace_replay_t4.md`
  - T4 语义、计数与限制；
- `report/multicast_report.pdf`
  - 当前 Topic 3/4 综合报告；
- `report/data/trace_replay_summary.csv`
  - T3/T4 已验收结果快照。

## 4. 推荐 tensor 语义

在改代码前先提交一份短 contract，至少固定以下字段：

```text
collective_id       # logical all-reduce request
chunk_id            # 一个 tensor 中的 packet/chunk
lane_id             # chunk 内 element/flit index
packet_flits        # HEAD/BODY/TAIL 总 flit 数
source_rank
reduction_op        # 第一版固定 SUM
release_cycle
```

推荐第一版把一个 flit 看作一个 64-bit reduction lane。对于每个
`(collective_id, chunk_id, lane_id)`，Router 必须等待本地贡献和所有 child
贡献，得到 partial sum 后再向 parent 发送。root 对该 lane 完成后广播；NI
按 lane id 校验结果并在收到完整 tensor/chunk 后完成 logical request。

不建议仅移除 `HEAD_TAIL` assert，然后让多个 flit共享当前单个 `accum`。
那会把相邻 lanes 的值混在一起。状态至少需要按 lane 或流水位置区分，且
必须定义在多个 packet/round overlap 时如何索引和释放。

可选实现路线：

1. **保守版本**：同一时刻只允许一个 tensor request，但允许它的多个 lanes
   streaming through tree；Router 按 lane 建立 accumulator table。
2. **增强版本**：支持多个 outstanding tensor requests，状态 key 为
   `(collective_id, chunk_id, lane_id)`，并设置有限容量和 backpressure。

先完成保守版本的正确性和 credit gate，再增加并发。不要用无限 map 掩盖
硬件状态成本；如果第一版使用 map，报告中必须给出 entry 数和后续 bounded
implementation 计划。

## 5. 分阶段实施与验收

每一阶段必须保存命令、Git revision、输入 hash、raw stats 和实验目录。
到达 `sim-cycles` 上限不算成功。

### H0 — 固定基线

在改代码前复现：

```bash
python3 tests/gem5/lab4/test_ai_trace_tools.py

LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_collective_matrix.py --rounds 3 --jobs 4

LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_allreduce_trace_replay.py \
    --gem5 build/Garnet_standalone/gem5.opt \
    --source-trace traces/h100_8gpu_collectives.json \
    --replay traces/h100_8gpu_allreduce_replay.json \
    --output /tmp/tensor-h0 --sim-cycles 100000000
```

Gate：5 个 trace-tool unit tests、11 个 legacy collective cases 和当前
6,720-lane replay 全部通过。

### H1 — Tensor contract 和 compiler

- 新 schema 必须区分 logical events、chunks 和 packet flits；
- 独立 validator 检查 ID、release、payload、chunk/lane arithmetic；
- 15 个 H100 all-reduce events 在 1/1024 byte scale 下应保留：
  - 107,520 scaled bytes；
  - 6,720 flits per rank；
  - 53,760 total contribution flits；
  - 15 logical requests，而不是 6,720 logical rounds。

Gate：unit tests 包含非整 flit payload、重复 ID、非单调 release、错误 flit
count 和错误 participant set 的 reject cases。

### H2 — 2×2 multi-flit correctness

覆盖 root 0 和 root 3，packet size 1、4、16、64 flits。为避免“所有 lane
碰巧相同”掩盖 lane mixing，贡献值必须同时依赖 rank 和 lane，例如：

```text
value(rank, lane) = (rank + 1) * 1000 + lane
expected(lane) = 1000 * N * (N + 1) / 2 + N * lane
```

Gate：每个 rank 每个 lane 的值精确匹配；source flits、Router flits、merge、
delivery 和 internal-link traversal 与手算一致；最后一个 tail 完成后所有
temporary state 为空。

### H3 — Backpressure 和 packet-state 稳定性

- 至少覆盖 1 VC、低 buffer、Router/link latency 1 和 4；
- 连续至少 100 个 tensor requests；
- HEAD/BODY/TAIL 不丢失、不重复、不乱序；
- retry 不重复注入已成功的 packet prefix；
- credit 最终守恒；
- 可以先限制一个 outstanding request，再增加 2、4、8 outstanding。

Gate：所有 case completion-driven exit，零 duplicate/wrong-lane/wrong-value，
无 residual accumulator/branch/VC state。

### H4 — 规模、矩形 Mesh 和 root

覆盖：

- 2×2、3×3、4×4；
- 8-rank 4×2 rectangular Mesh；
- corner、edge、center root；
- 1、4、16、64 flits。

Gate：legacy 11-case regression 仍全部通过，新 tensor matrix 全绿。

### H5 — 真实 H100 tensor replay

使用相同的 source trace、rank map、1/1024 byte/time scale 和 16-byte flit。
最终 workload 必须是 15 logical all-reduce events，而不是 6,720 scalar
collective rounds。

必须精确满足：

| invariant | expected |
|---|---:|
| logical events | 15 |
| scaled tensor bytes per rank | 107,520 |
| tensor flits per rank | 6,720 |
| total rank contribution flits | 53,760 |
| Router lane merges | 53,760 |
| final lane deliveries | 53,760 |

如果仍使用同一 XY reduce/broadcast tree，理论 collective Router flits 应为：

```text
(3 * N - 2) * tensor_flits_per_rank
= (3 * 8 - 2) * 6720
= 147,840
```

Gate：Mesh_XY 完整结束、每 lane 结果正确、15/15 logical events complete，
并输出 request completion、p50/p95/p99、wire distance 和 peak Router tensor
state。仅 source flit 数正确但 logical events 未完成仍算失败。

### H6 — Paired performance 和非退化

至少比较：

1. 当前 serialized scalar-lane lowering；
2. 新 tensor streaming tree all-reduce。

保持 source trace、scale、root、topology、release cycles 和完成条件一致。
同时补跑：

- legacy collective 11/11；
- multicast correctness 关键 packet sizes；
- T3 broadcast replay 30/30 requests、6,720 flits；
- Mesh_XY 与 Mesh_Bypass tensor replay。

报告绝对值和 speedup，但不能只因 streaming 比串行 baseline 快就宣称真实
GPU 加速。它仍然是 Garnet 上的缩放 trace simulation。

## 6. 必须新增或保留的统计

至少包括：

- logical tensor requests started/completed；
- chunks/flits per request；
- contribution flits；
- Router lane merges；
- reduce and broadcast internal-link flits；
- ordinary/express flits；
- physical wire-flit distance；
- p50/p95/p99 logical request completion；
- active/peak accumulator entries；
- VC/credit/switch stalls；
- duplicate、unexpected、wrong-lane、wrong-value、incomplete counters。

统计名称应逐步从历史遗留的 `multicast_*` 泛化为 `collective_*` 或
`tensor_allreduce_*`，但必须保留兼容或同步更新所有 runner，不能静默改变
已有 CSV/JSON 字段语义。

## 7. 不允许的捷径

- 不得把 6,720 个串行 scalar rounds 重新命名为 tensor hardware；
- 不得只修改 packet size 而让所有 flit共享一个 accumulator；
- 不得只看 simulation exit code，不核对精确计数和最终值；
- 不得把 timeout 当作性能结果；
- 不得只测试所有 lane 相同的 payload；
- 不得用无限 accumulator map 而不报告状态成本；
- 不得把 optimistic bypass link 当硬件收益；
- 不得把 H100 microbenchmark 描述为完整 AI model trace；
- 不得把缩放 Garnet ticks 描述为 H100/NVLink 实测性能。

## 8. 构建和常见问题

当前有效目标：

```bash
LD_LIBRARY_PATH=/path/to/python/lib \
  scons build/Garnet_standalone/gem5.opt -j4
```

注意：

- 构建与运行必须使用兼容的 Python 动态库；
- 最终 `gem5.opt` 必须用 `file` 确认是有效 ELF；
- 参数或 SimObject Python 文件变化会触发较大的代码生成/链接；
- 8-rank topology 使用 `--num-cpus=8 --num-dirs=8 --mesh-rows=4`；
- 不要重新引入 `sqrt(num_destinations)` 计算 collective Mesh 宽度，当前代码
  已修正为使用 network column count；
- worktree 可能包含他人的实验文件，提交前使用精确 `git add`，不要执行
  `git reset --hard` 或覆盖无关改动。

## 9. 推荐提交顺序

建议每个 gate 单独提交：

```text
H1  trace schema/compiler/validator
H2  tensor flit metadata and 2x2 correctness
H3  backpressure-safe Router/NI packet state
H4  scale/root/rectangular regression
H5  real-H100 tensor replay
H6  paired performance and final report
```

每个提交说明中写明：运行命令、通过 case 数、理论计数、实测计数、artifact
目录和已知限制。性能数字必须来自对应提交的可复现实验，不能只引用旧
`/tmp` 文件。

## 10. 交付结果应该如何表述

如果 H1--H6 全部通过，可以表述为：

> Implemented a backpressure-safe multi-flit tensor all-reduce datapath in
> gem5 Garnet. Routers perform lane-wise in-network reduction and broadcast,
> and the committed eight-H100 collective trace completes as 15 logical
> tensor requests with exact flit, merge, delivery, and value validation.

在实现真正 bounded、并行 vector datapath，或完成电路面积/频率模型之前，
不要表述为“完成了 H100 tensor core/NVSwitch 硬件”或“证明 AI 训练加速”。
