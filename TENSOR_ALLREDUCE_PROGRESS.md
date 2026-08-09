# Tensor All-Reduce 工作汇总（tensor-allreduce 分支）

本文档汇总 `tensor-allreduce` 分支（基线 `main` = `4e00fe4`）上相对
`TENSOR_ALLREDUCE_HANDOFF.md` 的全部实现、验证结果、已知限制和复现命令。
目标：把原有的 scalar 串行 in-network all-reduce 扩展为 backpressure-safe
的 multi-flit tensor all-reduce，并按 H1--H6 门禁逐阶段验收。

## 1. 分支与提交

分支上共 6 个提交（按时间顺序）：

| Commit | 内容 | 关键验证 |
|---|---|---|
| `b1645d5` | H1：tensor replay 契约/compiler/validator | 单测 12/12 |
| `2bf6b2c` | H2：multi-flit tensor 数据通路 | 矩阵 8/8（初版） |
| `72c161d` | H3 backpressure + H4/H5/H6 gates | 矩阵 14/14、backpressure 16/16、H5/H6 首跑 |
| `3a9151e` | H5/H6 补完（wire distance、Mesh_Bypass、§6 计数器） | H5 双设计、H6 双设计 |
| `aa6232a` | 修复 multicast 矩阵 `tree_edges()` 期望公式 | multicast 208/208 |
| `8458ae8` | H3 link-latency 维度 + credit 守恒断言 + §6 统计 + 一键 full-gate runner | backpressure 32/32、full gate 7/7 |

工作区状态：干净（`git status` 无改动）。

## 2. H1 — Tensor replay 契约 / compiler / validator

- 新 schema `lab4.garnet_tensor_allreduce_replay.v1`：一个 logical all-reduce
  event = 一个 request，tensor 按 chunk 切分，1 flit = 1 个 64-bit lane；
  字段含 `collective/chunk/lane/packet_flits/source_rank/release_cycle`。
- 新 compiler `util/lab4_trace/compile_tensor_allreduce_replay.py`
  （`--chunk-bytes` 默认 4096）；新 validator
  `validate_tensor_allreduce_replay()` 拒绝：非整 flit payload、重复 id、
  非单调 release、错误 flit count、错误 participant set、chunk 未精确铺满。
- 契约文档 `util/lab4_trace/tensor_contract.md`。
- 真实 8×H100 测量阶段 15 个 all-reduce events 编译为 **15 个 logical
  requests**（不再是 6,720 个 scalar rounds）：
  107,520 scaled bytes、6,720 flits/rank、53,760 contribution flits、
  30 chunks（1/1024 byte/time scale，16-byte flit）。
- 入库 `traces/h100_8gpu_tensor_allreduce_replay.json`；单元测试 12/12。

## 3. H2 — Multi-flit tensor 数据通路

- `flit`：新增 `lane_id` 元数据，serialize/deserialize 同步携带。
- `Router`：以 `(collective_id, lane_id)` 为 key 的 lane 累加表取代单
  accumulator；多 flit 包只在 TAIL/HEAD_TAIL 释放上游 VC；每个 lane 收齐
  fan-in 后独立向上归约（非根）或向 Local+children 广播（根）。
- `NetworkInterface`：tensor 注入按 `(rank+1)*1000 + lane` 生成多 flit 包；
  弹出按 lane 断言期望值 `1000*N*(N+1)/2 + N*lane`（错误即 fail-fast）。
- `GarnetNetwork`：`collective_tensor` 参数、per-round lane 数、投递按
  (dest, lane) 记录、完成即 `exitSimLoop`。
- 值公式覆盖 "所有 lane 相同" 的测试陷阱：`value(rank,lane)` 同时依赖
  rank 与 lane。

## 4. H3 — Backpressure 与 credit 守恒

- 归约/广播转发改为 per-router pending-forward FIFO：下游 VC 无空闲时排队
  重试（原实现直接 fatal），每周期尽量清空、按 FIFO 停头保持顺序。
- 去掉"单活跃请求"限制（lane 表按 (cid, lane) 天然隔离并发请求），支持
  outstanding 1/2/4/8。
- **credit 守恒显式断言**：tensor 完成时 `assertNoResidualCollectiveState()`
  遍历所有 router，任何残留 lane 累加器或 pending 转发即 fatal。
- 矩阵 32 例：2×2、3×3 × router-latency{1,4} × link-latency{1,4} ×
  outstanding{1,2,4,8}，全部 1 VC + depth-1 buffer。

## 5. H4 — 规模 / 矩形 Mesh / root

- 矩阵扩展到 14 例：2×2（root 0/3 × 1/4/16/64 flits）、3×3、4×4、矩形
  4×2（root 0/3/4）、2×4（root 5）。
- 注意：`--num-dirs` 必须是 2 的幂（gem5 地址交织），矩形规模用 16 dirs。

## 6. H5 — 真实 H100 tensor replay

- `run_tensor_allreduce_trace_replay.py` 在 Mesh_XY 和 Mesh_Bypass 双设计
  上重放 15 个 logical requests，校验精确计数 + per-lane 值 + 错误计数器。
- 实测（两设计一致）：
  - measurement ticks：17,054,500
  - p50/p95/p99：647,500 / 2,567,500 / 2,567,500
  - reduce/broadcast internal-link flits：47,040 / 47,040（= (N-1)×6720）
  - peak lanes = 2、active entries = 0、credit stalls = 0、错误计数器全 0
  - wire-flit distance = 94,080、express flits = 0（收敛树用普通 XY 边）

## 7. H6 — Paired 性能对比（非退化）

- 同一 trace/scale/root/topology 下，标量 scalar-lane replay vs tensor：
  - scalar measurement ticks = 80,638,000（与 H0 基线完全一致，无回归）
  - tensor measurement ticks = 17,054,500
  - **measurement speedup = 4.73×**（Mesh_XY 与 Mesh_Bypass 一致）
  - source flits 与 router flits 两者相同（53,760 / 147,840）
- p95 粒度不同（标量按 lane、tensor 按 request），paired 输出只报绝对值并
  注明不可直接比较；主指标为 measurement ticks。

## 8. 额外修复：multicast 矩阵

- `run_multicast_matrix.py` 的 `tree_edges()` 期望公式回溯顺序错误（先 X 后
  Y），与真实 X-first XY 剪枝树不一致，导致 12 个 tree_multicast case 的
  router-flit 期望值差 ±1。数据通路本身正确（投递/轮次/internal 计数自洽）。
- 修复为"回溯先 Y 后 X"（提交 `aa6232a`）后 **208/208 全部通过**。

## 9. §6 统计对照

| 要求 | 实现状态 |
|---|---|
| logical requests started/completed | ✓ `collective_rounds_completed` / `collective_tensor_requests_completed` |
| contribution flits / Router lane merges | ✓ `collective_source_flits` / `collective_reduce_merges` |
| chunks / flits per request | ✓ H5 summary 输出 min/max（runner 侧） |
| reduce 与 broadcast internal-link flits | ✓ `collective_reduce/broadcast_internal_link_flits` |
| ordinary / express flits | ✓ `express_internal_link_flits` + wire distance |
| p50/p95/p99 request completion | ✓ `collective_tensor_p50/p95/p99_completion_ticks` |
| active / peak accumulator entries | ✓ `collective_tensor_active_entries`（完成时 0）/ `peak_lanes` |
| VC/credit/switch stalls | ✓ `collective_credit_stalls`、`collective_outvc_stalls`；switch stalls 对 collective 路径不适用（不走 SA），报告中注明 |
| duplicate/unexpected/wrong-lane/wrong-value/incomplete counters | ✓ 前四者 C++ 计数 + fail-fast；incomplete 由 runner 的 `incomplete_requests` 列检测 |

## 10. 复现命令

```bash
# 构建（容器内，/gem5 = 本仓库）
scons build/Garnet_standalone/gem5.opt -j4 PROTOC=/bin/false

# 一键全部 gate（7 个）
python3 tests/gem5/lab4/run_lab4_full_gate.py \
  --gem5 build/Garnet_standalone/gem5.opt --jobs 4

# 单个 gate
python3 tests/gem5/lab4/test_ai_trace_tools.py -v          # H1 单测 12/12
python3 tests/gem5/lab4/run_tensor_allreduce_matrix.py --gem5 build/Garnet_standalone/gem5.opt --jobs 4
python3 tests/gem5/lab4/run_tensor_allreduce_backpressure.py --gem5 build/Garnet_standalone/gem5.opt --jobs 4
python3 tests/gem5/lab4/run_tensor_allreduce_trace_replay.py --gem5 build/Garnet_standalone/gem5.opt
python3 tests/gem5/lab4/run_tensor_allreduce_paired.py --gem5 build/Garnet_standalone/gem5.opt
python3 tests/gem5/lab4/run_collective_matrix.py --rounds 3 --jobs 4   # 回归 11/11
python3 tests/gem5/lab4/run_multicast_matrix.py --jobs 4 --rounds 5 --packet-flits 1 4 16 64
python3 tests/gem5/lab4/run_trace_replay.py --gem5 build/Garnet_standalone/gem5.opt \
  --source-trace traces/h100_8gpu_collectives.json \
  --replay traces/h100_8gpu_broadcast_replay.json \
  --output /tmp/bcast --sim-cycles 50000000
```

注意：宿主提交时 pre-commit 包装器因环境缺模块被跳过；提交前已单独运行
gem5 style checker（`util/git-pre-commit.py`）并通过。

## 11. 已知限制与尚未完成

- **H2/H3/H4 runner 尚无 provenance 元数据**（git revision / 输入 hash）：
  只有 H5 runner 记录；计划中列为待办第 4 项。
- **最终 H1--H6 提交报告**：本文档是工作汇总，handoff 要求的正式报告
  （含 map entry 数、bounded 实现计划、完整统计表）仍需按提交格式产出。
- **bypass 对 all-reduce 的 express 使用为 0**：收敛树用普通 XY 边，
  `express_flits=0` 是有意策略（handoff 列为后续 baseline）。
- **p95 粒度**：标量按 lane、tensor 按 request，不可直接比较（已注明）。
- **仿真缩放**：1/1024 byte/time scale 的 Garnet 仿真，不代表 H100/NVLink
  实测性能（handoff §10 措辞约束已遵守）。
- **Router lane 表为 `std::map`**：本实现按活跃请求的 lane 数为界（实测
  peak=2）；若后续做多 chunk/更大 tensor，需要 bounded table 化
  （handoff §4 要求报告中给出 entry 数与 bounded 计划）。

## 12. 关键文件

- 契约/格式：`TENSOR_ALLREDUCE_HANDOFF.md`、`util/lab4_trace/tensor_contract.md`
- 数据通路：`src/mem/ruby/network/garnet/{flit,Router,NetworkInterface,GarnetNetwork}.{hh,cc}`
- 流量/配置：`src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.{hh,cc,py}`、
  `configs/example/garnet_synth_traffic.py`
- 测试：`tests/gem5/lab4/run_{tensor_allreduce_matrix,tensor_allreduce_backpressure,
  tensor_allreduce_trace_replay,tensor_allreduce_paired,lab4_full_gate,multicast_matrix,
  collective_matrix,trace_replay}.py`
- 数据：`traces/h100_8gpu_tensor_allreduce_replay.json`
