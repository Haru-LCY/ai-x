# Scalar vs tensor replay

<p class="lede">Same H100-derived work; different request granularity.</p>

<div class="body">

<div class="metrics">
  <div class="metric vi">
    <span class="v">4.728×</span>
    <span class="k">shorter replay window</span>
    <span class="n">80,638,000 → 17,054,500 ticks</span>
  </div>
  <div class="metric vi">
    <span class="v">53,760</span>
    <span class="k">source contribution flits in both all-reduce arms</span>
    <span class="n">8 ranks × 6,720 lanes/rank</span>
  </div>
  <div class="metric vi">
    <span class="v">147,840</span>
    <span class="k">collective Router flits in both arms</span>
    <span class="n">(3 × 8 − 2) × 6,720</span>
  </div>
</div>

<table class="tbl">
  <thead><tr><th>Replay arm</th><th class="r">Source events</th><th class="r">Simulator work units</th><th class="r">Source flits</th><th class="r">Window</th></tr></thead>
  <tbody>
    <tr><td>Broadcast</td><td class="num">15 measured</td><td class="num">30 chunk requests</td><td class="num">6,720</td><td class="num">17,047,500</td></tr>
    <tr><td>Scalar all-reduce</td><td class="num">15 measured</td><td class="num">6,720 one-flit rounds</td><td class="num">53,760</td><td class="num">80,638,000</td></tr>
    <tr class="pick"><td>Tensor all-reduce</td><td class="num">15 measured</td><td class="num">15 multi-flit requests</td><td class="num">53,760</td><td class="num">17,054,500</td></tr>
  </tbody>
</table>

</div>

<div class="take vi"><span class="lab">One-event example</span>A scaled 4-MiB event has 256 lanes per rank: scalar admits 256 one-flit rounds, while tensor admits one 256-flit request. Both inject 2,048 source flits across eight ranks; the 4.728× result is a scaled Garnet scheduling result, not an H100/NVLink speedup.</div>

<!--
Timing 40 s. 这一页只比较同一份 H100-derived measurement trace 的两种 all-reduce lowering。先看数量：15 个 measured events 在 scalar arm 中被展开为 6,720 个 one-flit rounds；在 tensor arm 中保留为 15 个 multi-flit requests。

但这不是少传了 bytes。每个 rank 都有 6,720 个 lane，八个 rank 一共注入 53,760 个 source contribution flits；两种表示在 Router 中产生的 collective flits 也都是 147,840。真正改变的是 request granularity 和 admission/scheduling。

可以用一个 4-MiB event 解释：缩放后是 4 KiB，也就是每个 rank 的 256 个 lane。scalar 要做 256 次 one-flit round；tensor 是一个带 256 个 flit 的 event-level request。于是整个 replay window 从 80.638 million ticks 降到 17.0545 million ticks，得到 4.728×。这是 Garnet scaled replay 的调度收益，不是 native H100 或 NVLink 的 speedup。Mesh XY 和 bypass arm 在这里相同，是因为这些 selected routes 实际走 ordinary XY，express flits 为 0。
-->
