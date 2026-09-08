# Multicast implementation

<p class="lede">The router builds the tree in two phases, then we validate every delivery.</p>

<div class="body">

<div class="grid2 rev">

<div class="steps cy" style="align-content:start">

  <div class="row"><em>1</em><div><b>Head computes the pruned tree</b><span>The bitmap selects child branches; branches with no destination never receive a flit.</span></div></div>
  <div class="row"><em>2</em><div><b>Branch state commits atomically</b><span>The Router allocates all required output VCs together; body and tail flits reuse those VCs.</span></div></div>
  <div class="row"><em>3</em><div><b>Tail releases the reservation</b><span>Per-round expected and received delivery sets must match exactly before the case is accepted.</span></div></div>

</div>

<div class="stack">

  <div class="metric">
    <span class="v">240 / 240</span>
    <span class="k">functional executions pass</span>
    <span class="n">120 mode-matched comparisons · 2×2–8×8 · two implementations · four packet sizes</span>
  </div>

  <div class="metric cy">
    <span class="v">324 + 108</span>
    <span class="k">paired performance cases</span>
    <span class="n">324 common cross-topology pairs · 108 additional 8×8 scale-out pairs</span>
  </div>

  <div class="card">
    <span class="mark">DOMAIN BOUND</span>
    <h3>64 routers per bitmap</h3>
    <p>The compact mask covers the largest evaluated 8×8 network exactly.</p>
  </div>

</div>

</div>

</div>

<div class="take cy"><span class="lab">Validated properties</span>Payload values, destination sets, flit ordering, and completion under backpressure.</div>

<!--
Backup note, 30 s. 这一页是 multicast 的实现细节。Head flit 先根据 bitmap 计算 pruned tree；然后 Router 把所有需要的 output VCs 一起分配，body 和 tail 复用这组 branch state；tail 到达后释放 reservation。右侧的 240 / 240 是 functional executions 全部通过，性能实验则包括 324 组 common pairs 和 108 组 8×8 scale-out pairs。主讲时如果时间紧，可以只用上一页的示意图说明这个 two-phase allocation。
-->
