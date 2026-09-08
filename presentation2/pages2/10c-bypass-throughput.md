# Throughput

<p class="lede">Throughput tells the same story: long paths gain the most.</p>

<div class="body">

<figure class="result-figure">
  <img src="/bypass_throughput_improvement_by_traffic_pattern.png" alt="Packet-averaged throughput improvement by traffic pattern for diagonal and stride-2 adaptive bypass" />
  <figcaption>Distance-scaled diagonal and stride-2 · positive improvement means bypass delivers more packets per unit time.</figcaption>
</figure>

</div>

<!--
（Throughput 的分布更明显。8×8 bit-complement 下 stride-2 的提升最大，diagonal 的收益相对小；hotspot 仍然比较保守。这个顺序和前一页的 latency 是一致的：长路径、能多次使用 shortcut 的 traffic 更占优势。）
-->
