# Lab4 Project — Mesh In-Network All-Reduce

## 1. Introduction

本项目基于 gem5 Garnet，研究 Mesh NoC 中面向分布式 AI 通信的 in-network collective communication。核心设计是让 Mesh Router 参与 AllReduce：各 node 注入局部贡献，Router 沿 XY 路由诱导的 convergence tree 进行部分归约，root 再沿树广播全局结果。

项目采用分阶段路线：先用 single-flit scalar AllReduce 验证协议正确性和 credit 稳定性，再扩展到 tensor chunks、独立 multicast 和 bypass/express links，最后用统一 baseline 评估通信量、完成周期和延迟。

项目可定位为 Topic 4（与 interconnection 相关的其他项目），同时 multicast 和 bypass 扩展也覆盖 Topic 3 的 microarchitecture 方向。当前代码库是 `/volume/haru/cxiao03/work/gem5-lab4` 的 `lab4` 分支。`Lab4_project/` 是配套的设计规范、计划和验收文档，不是 gem5 主代码库。

## 2. Project highlights

项目的研究叙事是：现代分布式 AI 训练受到 collective communication 开销限制；one-to-many traffic 产生重复复制，远距离节点之间的多跳传输增加 latency 和拥塞。因此项目研究 Router-level reduction、tree multicast/broadcast 和 bypass link 如何共同优化 Mesh NoC 上的 AI-style collectives。

当前已实现或正在推进的主要亮点：

- **Deterministic convergence tree**：根据 `Mesh_XY` 的 XY 路由和 `--collective-root`，预计算每个 Router 的 parent、children 和 expected fan-in。
- **In-network reduction**：Router 对 scalar collective flit 做累加，非 root 只向 parent 发送一个 merged flit。
- **Tree broadcast**：root 得到全局 sum 后沿同一棵树传播，使每个 node 收到相同结果。
- **Independent multicast mode**：新增 `--lab4-multicast`，root-only injection，并沿树复制 flit；2×2 和 3×3 多轮回归已通过。
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
- Garnet flit：增加并传递 `value`、`collective_id`、`is_reduce`。
- Router：实现串行 scalar reduction state (`accum/count/active`)、merged flit 上行和 tree broadcast。
- NetworkInterface：注入 deterministic contribution，eject 时校验最终结果。
- Traffic generator：支持 `--collective-rounds`；新增 `--lab4-multicast` root-only tree multicast workload。
- 正确性验证：2×2 100 轮、3×3 多 root 单轮、3×3 root=4 100 轮、4×4 多 root 单轮均有成功记录。
- 设计文档：`Lab4_project/BASELINE_SPEC.md`、`Lab4_project/todo.md`、`Lab4_project/scalar.md`。

### 4.2 Current work

- 完成 multicast 改动后的新 binary 编译和 2×2/3×3 多轮回归测试；
- 补齐 3×3/4×4 多 root 的更大轮次 scalar 验收；
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

Scalar 阶段的详细逐项验收见 `Lab4_project/scalar.md`。目前 Phase 1 已完成，Phase 2 已基本完成，Phase 3 尚未完成；Phase 4--6 尚未作为完成项声明。

## 6. Reproduction

工作区根目录为 `/volume/haru/cxiao03/work`。

快速校验收敛树：

```bash
cd /volume/haru/cxiao03/work
python3 Lab4_project/test_tree.py
python3 Lab4_project/spanning_tree.py
```

推荐使用项目脚本构建：

```bash
cd /volume/haru/cxiao03/work
auto_env=/volume/haru/cxiao03/work/env-gem5
./build_lab4.sh
```

脚本使用 `Garnet_standalone`、`NULL ISA` 和 `-j4`。当前环境没有 `protoc` 和 HDF5 时会有 warning；历史日志中还出现过 protobuf/Abseil 链接失败，所以验收时必须检查实际 binary 是否存在并可运行。

已有 smoke 产物：

- `lab4_smoke.log`：普通 Garnet traffic，可正常结束；
- `m5out_lab4_smoke/`：`config.ini`、`config.json`、`stats.txt`。

这个 smoke 只证明普通 traffic 的 flit payload 没有被破坏，不证明 all-reduce 已经完成。

## 7. Development constraints

- 只有 scalar correctness 和稳定性验收通过后，才进入 tensor、multicast 性能、bypass 或其他 stretch；
- 每次协议改动都要保留独立正确性测试；
- `lab4_smoke.log` 和 `m5out_lab4_smoke/` 是运行产物，不应作为源码提交；
- 性能比较必须包含完整 reduce + broadcast 流程；
- 现有源码改动与 README 文档提交分开管理，避免把未验收实现误标记为完成。

## 8. Reference files

- `Lab4_project/BASELINE_SPEC.md`：保底版协议和硬性验收项；
- `Lab4_project/todo.md`：阶段化任务清单；
- `Lab4_project/spanning_tree.py`：树构造、打印和验证；
- `Lab4_project/test_tree.py`：快速回归检查。

## 9. Current status (2026-08-07)

### 9.1 What is working

- 已完成 Garnet collective plumbing：`collective-root` 配置、Mesh_XY 树元数据、flit 的 `value`/`collective_id`/`is_reduce` 字段，以及 Router/NetworkInterface 的 collective 接口。
- 已完成 Router 内部的单轮标量归约和 root 广播路径。2×2、root=0、single-flit、单轮 Stage 1 测试已通过：4 个节点注入、子树合并、root 汇总为 10，并向所有节点广播且仿真正常退出。
- 首次广播失败暴露的 Router 子节点方向映射错误已经修正。输入方向的含义是“从父 Router 指向 child 的方向”，因此 East/West/North/South 必须分别映射为 `(x+1)`, `(x-1)`, `(y+1)`, `(y-1)`。
- collective 注入值已按规范使用 `src_ni + 1`；普通 smoke traffic 仍使用 `src_ni`。

### 9.2 Current status and next blocker

Phase 1 已通过，Phase 2 已基本完成：已增加 `--collective-rounds`，完成 2×2 root=0 的 100 轮测试、3×3 root=0/4/8 单轮测试、3×3 root=4 的 100 轮测试，以及 4×4 多 root 单轮测试。当前下一步是补齐多轮矩阵并建立公平 baseline。

### 9.3 Build pitfalls and recovery

1. **Protobuf 链接失败**：Lab4 不需要 Protobuf tracing。不能只忽略 linker 报错；构建时使用 `PROTOC=/bin/false`，让 gem5 明确关闭 protobuf 相关生成功能，并确认最终 binary 可运行。
2. **混用 Python 版本导致 pybind 链接失败**：系统 Python 头文件/库与 gem5 虚拟环境不一致时，会出现 Python 3.12 头文件和 Python 3.10 库混用。必须统一使用 `/volume/haru/cxiao03/work/env-gem5/bin/python3`、对应的 `python3-config`，并设置 `LD_LIBRARY_PATH=/volume/haru/cxiao03/work/env-gem5/lib`。
3. **旧 build 目录混杂**：曾有不同配置生成物共存，造成 ABI/链接结果不可靠。旧目录已保存在 `build/NULL_mixed_backup_20260806`，当前有效目标是 `build/NULL/gem5.opt`。
4. **远端 CPU 配额**：容器虽然报告 128 个 CPU，但 cgroup 实际只分配约 1 个 CPU；因此全量 gem5 编译使用 `-j4` 仍会被限流，耗时可达几十分钟。编译过程使用 `nohup` 后台运行，SSH 断开不会中断。
5. **非 2 次幂 directory 配置**：gem5 默认 memory interleave 逻辑要求 directory 数量为 2 的幂。3×3 Mesh 仍使用 9 个 Router，但 synthetic Garnet 测试配置 16 个 directory controllers；前 9 个 directory 对应 9 个 Router，多余 directory 由 Mesh_XY 挂到 Router0。collective 的 Router 数量和树语义仍由 `--num-cpus=9 --mesh-rows=3` 决定。

### 9.4 Verification artifacts

- `build_lab4_routerfix.log`：方向修复后的成功编译日志。
- `lab4_collective_2x2_fix.log`：方向修复后的测试日志；其中 `TEST_RC=134` 记录了旧注入值导致的 `6 != 10` 断言失败。
- `lab4_collective_2x2_valuefix.log`：修正注入值后的 Stage 1 成功日志，`TEST_RC=0`。
- `lab4_collective_2x2_100.log`：2×2、root=0、100 轮串行稳定性测试，`TEST_RC=0`。
- `lab4_scalar_3x3_dirs16_summary.log`：3×3、root=0/4/8 单轮测试，全部 `RC=0`。
- `lab4_scalar_3x3_r4_100_verify`：3×3、root=4、100 轮稳定性测试，`RC=0`。
- `lab4_smoke.log` 和 `m5out_lab4_smoke/`：普通 Garnet smoke，证明基础 traffic 仍可运行，但不等于 all-reduce 已验收。

### 9.5 Remaining minimum-work items

1. 补齐 3×3/4×4 多 root 的更大轮次 scalar 验收；
2. 实现 naive/ring/tree 的统一 baseline 统计；
3. 再进入 tensor chunks、multicast 性能和 bypass。
