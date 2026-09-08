# Packet length shapes multicast speedup

<p class="lede">The tree saves the same link work, but packet length changes latency.</p>

<div class="body scaleout-body" style="grid-template-rows:auto 1fr;gap:8px">

<div class="metrics scaleout-metrics">
  <div class="metric cy">
    <span class="v">1 flit</span>
    <span class="k">short-packet profile</span>
    <span class="n">Fanout 64 mean: 7.36× latency speedup</span>
  </div>
  <div class="metric cy">
    <span class="v">4 flits</span>
    <span class="k">peak latency speedup</span>
    <span class="n">Fanout 64 mean: 46.15× speedup</span>
  </div>
  <div class="metric cy">
    <span class="v">16 flits</span>
    <span class="k">long-packet profile</span>
    <span class="n">Fanout 64 mean: 32.20×, below 4 flits</span>
  </div>
  <div class="metric cy">
    <span class="v">−62.41% / −75.39%</span>
    <span class="k">link flits, all packet sizes</span>
    <span class="n">Fanout 32 / 64 in the 8×8 scale-out</span>
  </div>
</div>

<div>

  <div class="fig" style="height:320px"><img src="/latency_speedup_by_group.png" alt="Multicast latency speedup by topology, fanout, and packet size" /></div>
  <div class="cap">Bars show arithmetic-mean latency speedup by packet length; error bars show the observed min–max. The right panel adds 8×8 fanouts 32 and 64.</div>

</div>

</div>

<div class="take take-focus cy">Packet length changes the latency profile. Structural link savings stay tied to fanout, while long packets expose branch occupancy.</div>

<!--
这一页我们重点看 packet length。右图把 1、4、16-flit packet 分开：在 8×8 的 fanout 32/64 scale-out 中，4 flits 的平均 latency speedup 最高，为 22.95× 和 46.15×；16 flits 为 16.02× 和 32.20×，1 flit 最低，为 4.19× 和 7.36×。

每个 fanout 下，link-flit reduction 对 packet size 不敏感，因为 baseline 和 tree 都按相同比例搬运 payload；fanout 32 和 64 分别都是 62.41% 和 75.39%。所以，packet size 改变的是 latency profile，而不是 tree 节省的 link work。

这种变化来自 packet length 对共享收益和占用成本的不同影响。1-flit packet 可共享的绝对传输量很小。4-flit packet 增加了可共享的连续 flits，同时还没有明显拉长 branch 和 VC 的占用，因此 speedup 最大。16-flit packet 虽然继续共享路径，但更长的占用时间和 atomic fanout 等待会抵消部分收益。这个占用效应也反映在 throughput 上，fanout 64 下从 1-flit 的约 +2,168% 降到 16-flit 的约 +1,651%。
-->
