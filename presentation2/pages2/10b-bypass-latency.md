# Latency

<p class="lede">Which traffic patterns actually benefit from the shortcuts?</p>

<div class="body">

<figure class="result-figure">
  <img src="/bypass_latency_speedup_by_traffic_pattern.png" alt="Packet-averaged latency speedup by traffic pattern for diagonal and stride-2 adaptive bypass" />
  <figcaption>Distance-scaled diagonal and stride-2 · higher than 1× means bypass finishes before Mesh XY.</figcaption>
</figure>

</div>

<!--
（可以讲 4x4 的 transpose 对于 diagonal 效果很好，这也说明了transpose 这种全是对角的天然适合 diagonal bypass。）
-->
