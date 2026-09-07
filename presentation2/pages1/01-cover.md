---
class: title-slide
---

<div class="titlewrap single">

<div>

<!-- <div class="sec">Lab 4 · Topic 3 + Topic 4 · gem5 Garnet</div> -->

# Collective-Aware Router<br>Microarchitecture in gem5 Garnet

<p class="sub">Multicast, express-link bypass, and tensor all-reduce evaluated against matched baselines.</p>

<div class="who"><b>Chunyu Liu</b><i></i><b>Boyan Pu</b></div>

<!-- <div class="tags">
  <span class="tag cy">Tree multicast</span>
  <span class="tag am">Pressure-aware bypass</span>
  <span class="tag vi">H100 tensor replay</span>
</div> -->

</div>

</div>

<!--
Timing 20 s. 大家好，我们是 Chunyu Liu 和 Boyan Pu。今天介绍三个和 collective communication 相关的机制：router-side multicast、pressure-aware express-link bypass，以及 trace-driven tensor all-reduce。它们的共同点是把 collective 的结构保留在 network 内部，减少重复工作，同时保持正确性。
-->
