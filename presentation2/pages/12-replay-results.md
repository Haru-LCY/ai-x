# Replay results

<p class="lede">A scheduling win, not fewer bytes.</p>

<div class="body">

<div class="metrics">
  <div class="metric vi">
    <span class="v">4.728×</span>
    <span class="k">shorter replay window</span>
    <span class="n">80,638,000 → 17,054,500 ticks</span>
  </div>
  <div class="metric vi">
    <span class="v">53,760</span>
    <span class="k">source flits in both arms</span>
    <span class="n">same rank-lane deliveries</span>
  </div>
  <div class="metric vi">
    <span class="v">147,840</span>
    <span class="k">Router-forwarded flits</span>
    <span class="n">identical in both representations</span>
  </div>
</div>

<table class="tbl">
  <thead><tr><th>Replay view</th><th class="r">Trace events</th><th class="r">Logical requests</th><th class="r">Source flits</th><th class="r">Window</th></tr></thead>
  <tbody>
    <tr><td>Broadcast</td><td class="num">15</td><td class="num">30</td><td class="num">6,720</td><td class="num">17,047,500</td></tr>
    <tr><td>Scalar all-reduce</td><td class="num">15</td><td class="num">6,720</td><td class="num">53,760</td><td class="num">80,638,000</td></tr>
    <tr class="pick"><td>Tensor all-reduce</td><td class="num">15</td><td class="num">15</td><td class="num">53,760</td><td class="num">17,054,500</td></tr>
  </tbody>
</table>

</div>

<div class="take vi"><span class="lab">Boundary</span>The win comes from replacing 6,720 independently admitted scalar rounds with 15 event-level requests. Mesh XY and the bypass arm are identical here because selected routes follow ordinary XY and express flits are zero.</div>

<!--
Timing 40 s. Tensor replay reduces the window from 80.638 million to 17.0545 million ticks, 4.728 times. Source and Router-forwarded flit counts are identical, so this is a request-representation and scheduling result, not an H100 hardware speedup.
-->
