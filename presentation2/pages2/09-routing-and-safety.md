# Bypass routing

<p class="lede">An offline table picks each shortcut; at runtime we only decide whether to take it.</p>

<div class="body">

<div class="grid2 rev">

<div class="steps am" style="align-content:start">

  <div class="row"><em>1</em><div><b>Build the table offline</b><span>For every current router and destination, compare ordinary XY with each legal express edge over the complete remaining path.</span></div></div>
  <div class="row"><em>2</em><div><b>Prefer XY on ties</b><span>Ordinary cost is link latency plus Router latency; express cost is distance-scaled wire latency plus one Router traversal and the best suffix.</span></div></div>
  <div class="row"><em>3</em><div><b>Look up, then admit</b><span>Each Router reads the precomputed entry. Ordered Vnets keep it; unordered traffic selects that express hop or monotonic XY from local credits, landing pressure, and hotspot state.</span></div></div>
  <div class="row"><em>4</em><div><b>Apply packet-aware rules</b><span>Diagonal 1-flit packets, plus 4-flit packets on 4×4, use at most one express hop. Packets above 32 flits require an idle landing lookahead.</span></div></div>

</div>

<div class="routing-algorithm">
  <pre><code>best_stride_step(current, destination):
    if current == destination:
        return 0
    choices = [ordinary_edge_cost + best_stride_step(xy_next, destination)]
    for legal_bypass in outgoing[current]:
        bypass_cost = wire_latency(legal_bypass) + router_latency
        suffix_cost = best_stride_step(legal_bypass.dst, destination)
        choices += [bypass_cost + suffix_cost]
    return min(choices)  # exact tie: ordinary XY</code></pre>

  <div class="route-order">
    <div><b>Diagonal static table</b><span>X* → diagonal* → Y*</span></div>
    <div><b>Stride-2 static table</b><span>aligned +2 X hops → aligned +2 Y hops</span></div>
  </div>
</div>

</div>

</div>

<div class="take am"><span class="lab">Safety</span>Before any run, static routes must form an acyclic channel-dependency graph. Diagonal also audits the complete express-or-XY runtime choice union; stride choices remain monotonic X-before-Y DOR.</div>

<!--
对于 routing 部分，首先在仿真前用递归为每个 current router 和 destination 建一张静态表。普通 XY 和合法 express edge 都按完整 suffix 的 cycle cost 比较；相同 cost 时保留 XY。运行时不会重新计算 cost，而是每到一个 Router 查询这张表。Ordered Vnet 直接采用表项；unordered Vnet 在表中的 express hop 和单调 XY 之间，根据本地 credit、landing pressure 和 hotspot state 做准入。静态表中 diagonal 是 X、diagonal、Y 三阶段，stride-2 保持 X-before-Y DOR。实际准入还有 packet-aware 规则：1-flit diagonal，以及 4×4 上的 4-flit diagonal，最多使用一个 express hop；超过 32 flit 的包还要求 landing lookahead 空闲。

（安全检查：静态表中的所有路径先合成 channel-dependency graph，并要求完整拓扑序。Diagonal 还会把运行时 express-or-XY 的全部选择合并后再做一次 DAG 审计；stride 的两个选择都保持单调的 X-before-Y DOR。）
-->
