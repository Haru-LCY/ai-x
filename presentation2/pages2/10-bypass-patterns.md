# Traffic patterns

<p class="lede">Four destination maps set the stress on each route.</p>

<div class="body">

<div class="pattern-grid">

  <div>
    <div class="fig pattern-map"><img src="/bypass_traffic_pattern_structure.png" alt="Spatial source-to-destination structure of the uniform random, transpose, bit-complement, and hotspot traffic patterns" /></div>
    <div class="cap">Arrow: source → destination · node size: incoming traffic.</div>
  </div>

  <div class="steps am" style="align-content:center">
    <div class="row"><em>1</em><div><b>Uniform random</b><span>Demand spreads across many source-destination pairs, so the gain remains moderate.</span></div></div>
    <div class="row"><em>2</em><div><b>Transpose</b><span>Symmetric diagonal flows can favor the alternative placement on 4×4.</span></div></div>
    <div class="row"><em>3</em><div><b>Bit complement</b><span>Long cross-mesh paths give stride hops more chances to skip loaded routers.</span></div></div>
    <div class="row"><em>4</em><div><b>Hotspot</b><span>A few concentrated sinks create pressure; conservative admission limits the downside.</span></div></div>
  </div>

</div>

</div>

<div class="take am"><span class="lab">Why separate</span>Pooling these patterns would hide the difference between geometric gain and hotspot risk.</div>

<!--
Timing 20 s. 这四张小图说明后面为什么要按 traffic pattern 分开看。Uniform random 的需求比较分散；transpose 集中在对角方向；bit complement 有很多跨 mesh 的长路径；hotspot 则把大量 incoming traffic 压到少数节点。尤其最后一格解释了为什么 routing 里需要 hotspot 和 pressure guard。
-->
