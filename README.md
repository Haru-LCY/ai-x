# Lab4 Project — Mesh In-Network All-Reduce

## 1. Introduction

本项目基于 gem5 Garnet，研究 Mesh NoC 中面向分布式 AI 通信的 in-network collective communication。核心设计是让 Mesh Router 参与 AllReduce：各 node 注入局部贡献，Router 沿 XY 路由诱导的 convergence tree 进行部分归约，root 再沿树广播全局结果。

项目采用分阶段路线：先用 single-flit scalar AllReduce 验证协议正确性和 credit 稳定性，再扩展到 tensor chunks、独立 multicast 和 bypass/express links，最后用统一 baseline 评估通信量、完成周期和延迟。

项目可定位为 Topic 4（与 interconnection 相关的其他项目），同时 multicast 和 bypass 扩展也覆盖 Topic 3 的 microarchitecture 方向。本仓库同时包含 gem5 实现、运行配置和 `tests/gem5/lab4/` 下的 collective 回归工具。

## 2. Project highlights

项目的研究叙事是：现代分布式 AI 训练受到 collective communication 开销限制；one-to-many traffic 产生重复复制，远距离节点之间的多跳传输增加 latency 和拥塞。因此项目研究 Router-level reduction、tree multicast/broadcast 和 bypass link 如何共同优化 Mesh NoC 上的 AI-style collectives。

当前已实现或正在推进的主要亮点：

- **Deterministic convergence tree**：根据 `Mesh_XY` 的 XY 路由和 `--collective-root`，预计算每个 Router 的 parent、children 和 expected fan-in。
- **In-network reduction**：Router 对 scalar collective flit 做累加，非 root 只向 parent 发送一个 merged flit。
- **Tree broadcast**：root 得到全局 sum 后沿同一棵树传播，使每个 node 收到相同结果。
- **Independent multicast mode**：新增 `--lab4-multicast`，root-only injection，并沿树复制 flit；2×2、3×3 和 4×4 多轮回归已通过。
- **Fair evaluation plan**：最终比较 naive unicast、ring 和 tree，并统计完整 reduce + broadcast 流程，而不是只比较单个阶段。

当前 scalar AllReduce 已完成主要功能正确性和规模/root 扩展，但 baseline 和性能论证尚未完成；不能把单轮正确性等同于最终性能结论。

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
- Traffic generator：支持 completion-driven 多轮串行化；新增 `--lab4-multicast` root-only tree multicast workload。
- Scalar 约束：配置层只允许 vnet 0/1，NI 与 Router 强制单个 `HEAD_TAIL` flit。
- 统计与回归：记录完成轮数、交付数、源/Router flit、reduce merge 和完成延迟；11 项 2×2/3×3/4×4 矩阵已通过。

### 4.2 Current work

- 实现 naive unicast AllReduce 和 ring baseline；
- 统一三种方案的输入、退出条件和性能统计。

### 4.3 Not yet claimed

当前尚未声称完成 tensor-level distributed training、完整 PyTorch/LLM 训练、bypass 性能收益或三种 baseline 的最终对比。

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

实现并评估独立 multicast，以及 bypass/express links。Multicast 解决重复 one-to-many traffic，bypass 解决远距离多跳 traffic。每个扩展都必须有 baseline、正确性测试和定量结果。

### Phase 6 — Final evaluation and report

完成实验矩阵、架构图、算法伪代码、理论通信量、实测结果、失败场景、限制说明和可复现实验命令，最终报告与代码状态保持一致。

### Current acceptance boundary

目前 Phase 1 和 single-flit scalar 的多规模回归已经完成，Phase 3 的公平 baseline 尚未完成；Phase 4--6 尚未作为完成项声明。

## 6. Reproduction

在仓库根目录构建并运行完整 collective 矩阵：

```bash
LD_LIBRARY_PATH=/path/to/python/lib \
  scons build/Garnet_standalone/gem5.opt -j32 PROTOC=/bin/false
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_collective_matrix.py --jobs 11 --rounds 5
```

测试工具为每次运行创建独立 `/tmp/lab4-collective-matrix-*` 目录，并保留每项的 `sim.log`、`stats.txt`、`config.ini` 和 `config.json`。HDF5 缺失只会产生 warning；Lab4 不依赖 protobuf tracing，因此构建使用 `PROTOC=/bin/false`。

## 7. Development constraints

- 只有 scalar correctness 和稳定性验收通过后，才进入 tensor、multicast 性能、bypass 或其他 stretch；
- 每次协议改动都要保留独立正确性测试；
- `lab4_smoke.log` 和 `m5out_lab4_smoke/` 是运行产物，不应作为源码提交；
- 性能比较必须包含完整 reduce + broadcast 流程；
- 现有源码改动与 README 文档提交分开管理，避免把未验收实现误标记为完成。

## 8. Reference files

- `configs/topologies/Mesh_XY.py`：collective tree 元数据构造。
- `configs/example/garnet_synth_traffic.py`：synthetic collective 入口与参数约束。
- `tests/gem5/lab4/run_collective_matrix.py`：并行回归矩阵与精确统计检查。
- `tests/gem5/lab4/README.md`：回归使用说明。

## 9. Current status (2026-08-07)

### 9.1 What is working

- 已完成 Garnet collective plumbing：`collective-root` 配置、Mesh_XY 树元数据、flit 的 `value`/`collective_id`/`CollectiveOp` 字段，以及 Router/NetworkInterface 的 collective 接口。
- 已完成 Router 内部的单轮标量归约和 root 广播路径。2×2、root=0、single-flit、单轮 Stage 1 测试已通过：4 个节点注入、子树合并、root 汇总为 10，并向所有节点广播且仿真正常退出。
- 首次广播失败暴露的 Router 子节点方向映射错误已经修正。输入方向的含义是“从父 Router 指向 child 的方向”，因此 East/West/North/South 必须分别映射为 `(x+1)`, `(x-1)`, `(y+1)`, `(y-1)`。
- collective 注入值已按规范使用 `src_ni + 1`；普通 smoke traffic 仍使用 `src_ni`。
- 多轮执行由每轮全目的端交付完成事件驱动，最终一轮主动退出；不再依赖固定 period 或超时判定成功。
- 2×2、3×3、4×4 的 11 项 all-reduce/multicast 矩阵全部通过，并核对精确协议统计。

### 9.2 Current status and next blocker

Phase 1 和 scalar 多规模矩阵已通过。当前下一步是实现 naive/ring/tree 的公平 baseline，并基于现有 completion、flit、hop 和 latency 统计完成对比。

### 9.3 Build pitfalls and recovery

1. **Protobuf 链接失败**：Lab4 不需要 Protobuf tracing。不能只忽略 linker 报错；构建时使用 `PROTOC=/bin/false`，让 gem5 明确关闭 protobuf 相关生成功能，并确认最终 binary 可运行。
2. **Python ABI 与动态库**：构建和运行必须使用同一套 Python 头文件/库，并把对应 lib 目录加入 `LD_LIBRARY_PATH`。当前 Python 3.13 还要求避免依赖函数内 `exec()` 写回局部变量。
3. **有效构建目标**：当前目标是 `build/Garnet_standalone/gem5.opt`；不要混用其他协议/ISA build 目录。
4. **并行度**：当前机器可使用 `-j32` 构建；回归工具通过 `--jobs` 控制案例级并行度。
5. **非 2 次幂 directory 配置**：gem5 默认 memory interleave 逻辑要求 directory 数量为 2 的幂。3×3 Mesh 仍使用 9 个 Router，但 synthetic Garnet 测试配置 16 个 directory controllers；前 9 个 directory 对应 9 个 Router，多余 directory 由 Mesh_XY 挂到 Router0。collective 的 Router 数量和树语义仍由 `--num-cpus=9 --mesh-rows=3` 决定。

### 9.4 Verification artifacts

回归工具打印当次唯一 artifact 目录。每个 case 的 `sim.log` 用于确认连续 round 和 completion-driven exit，`stats.txt` 用于确认理论通信量与实测计数一致；运行产物不提交到源码仓库。

### 9.5 Remaining minimum-work items

1. 实现 naive/ring/tree 的统一 baseline；
2. 使用一致输入和退出条件完成性能对比；
3. 再进入 tensor chunks、multicast 性能和 bypass。
