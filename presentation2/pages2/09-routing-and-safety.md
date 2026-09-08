# Bypass routing

<p class="lede">A static oracle chooses the shortcut; runtime adaptation only accepts or escapes it.</p>

<div class="body">

<div class="grid2 rev">

<div class="steps am" style="align-content:start">

  <div class="row"><em>1</em><div><b>Price the whole suffix</b><span>At every current router and destination, compare ordinary XY with each legal express edge over the complete remaining path.</span></div></div>
  <div class="row"><em>2</em><div><b>Prefer XY on ties</b><span>Ordinary cost is link latency plus Router latency; express cost is distance-scaled wire latency plus one Router traversal and the best suffix.</span></div></div>
  <div class="row"><em>3</em><div><b>Keep the phase order</b><span>Stride-2 repeats aligned +2 hops within X, then within Y. Diagonal uses X*, diagonal*, then Y*.</span></div></div>
  <div class="row"><em>4</em><div><b>Admit adaptively, within two choices</b><span>Ordered Vnets follow the table. Unordered traffic selects express or monotonic XY using local credits, landing pressure, and hotspot state.</span></div></div>

</div>

<div class="routing-algorithm">
  <pre><code>best_stride_step(current, destination):
  if current == destination:
    return 0
  choices = [ordinary_edge_cost
             + best_stride_step(xy_next, dest)]
  for legal_express in outgoing[current]:
    choices += [wire_latency(express)
                + router_latency
                + best_stride_step(express.dst, dest)]
  return min(choices)   # exact tie: ordinary XY</code></pre>

  <div class="route-order">
    <div><b>Diagonal</b><span>X* → diagonal* → Y*</span></div>
    <div><b>Stride-2</b><span>aligned +2 X hops → aligned +2 Y hops</span></div>
  </div>
</div>

</div>

</div>

<div class="take am"><span class="lab">What “adaptive” means</span>It is pressure-aware admission between an oracle-selected express hop and monotonic XY—not unrestricted adaptive routing. Both choices preserve the audited DOR phase.</div>

<!--
Timing 35 s. Bypass routing 的核心是这张离线表。对每个 current router 和 destination，动态规划不是只看下一跳，而是把剩余路径一起计价：普通 XY 边、Router latency，加上后面的最优 suffix；express link 则用按 Manhattan span 放大的 wire latency，再加一次 Router traversal 和它的 suffix。完全打平时选普通 XY。两个拓扑的差别在 phase order：diagonal 是 X、diagonal、Y；stride-2 是在 X 里重复加二，再在 Y 里重复加二。这里的 adaptive 不是任意选邻居：ordered Vnet 查表；unordered Vnet 只在 oracle 选出的 express hop 和 monotonic XY 之间二选一，依据是本地 credit、landing output 压力和 hotspot 状态。
-->
