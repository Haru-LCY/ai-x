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
    choices = [ordinary_edge_cost + best_stride_step(xy_next, destination)]
    for legal_bypass in outgoing[current]:
        bypass_cost = wire_latency(legal_bypass) + router_latency
        suffix_cost = best_stride_step(legal_bypass.dst, destination)
        choices += [bypass_cost + suffix_cost]
    return min(choices)  # exact tie: ordinary XY</code></pre>

  <div class="route-order">
    <div><b>Diagonal</b><span>X* → diagonal* → Y*</span></div>
    <div><b>Stride-2</b><span>aligned +2 X hops → aligned +2 Y hops</span></div>
  </div>
</div>

</div>

</div>

<div class="take am"><span class="lab">Safety</span>Before any run, all oracle routes are unioned into a channel-dependency graph; a complete topological order is required, and a cyclic placement is rejected at construction time.</div>

<!--
对于 routing 部分，我们先考虑一个一般的问题：mesh 上摆了任意一组保持单调 XY 的 express link，怎么为每对 source/destination 选出 latency 最小的走法？我们可以用递归做离线的计算。在这里 latency 由普通 XY 边、Router latency，加上后面的最优 suffix 组成；对于 bypass 增加的快速通道（express link），我们考虑他的 link latency 是按照曼哈顿距离放大的，比如 diagonal 的话因为是斜边，曼哈顿距离是2，所以 link latency 是2。很显然在这里，这样一个离线计算得出的表最终的 routing 方法可以看出对于 diagonal，先走 X 到能对角的地方，然后再走对角线，最后再走 y；stride 2呢就是在原本 dimension order routing 的基础上，多走 bypass express link。
-->
