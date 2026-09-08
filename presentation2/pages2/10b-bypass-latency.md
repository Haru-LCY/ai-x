# Latency

<p class="lede">Packet-averaged speedup by traffic pattern under distance-scaled wires.</p>

<div class="body">

<figure class="result-figure">
  <img src="/bypass_latency_speedup_by_traffic_pattern.png" alt="Packet-averaged latency speedup by traffic pattern for diagonal and stride-2 adaptive bypass" />
  <figcaption>Distance-scaled diagonal and stride-2 · higher than 1× means bypass finishes before Mesh XY.</figcaption>
</figure>

</div>

<!--
Timing 20 s. 这页只看 latency，两个 bypass arm 都是 distance-scaled。每组柱子都是 packet-averaged paired ratio，高于 1 才表示 bypass 更快。重点看两点：8×8 的 transpose 和 bit-complement 给 stride-2 的空间更大；hotspot 基本贴近 1，说明压力 guard 没有为了平均值去冒尾部风险。
-->
