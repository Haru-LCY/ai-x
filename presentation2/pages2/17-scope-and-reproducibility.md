# Scope and reproducibility

<p class="lede">Claims, limits, and revision provenance.</p>

<div class="body">

<div class="bounds">
  <div><b>Resource boundary</b><span>Bypass is workload-matched and added-resource, not iso-area, iso-power, or iso-wire; physical area and power are outside Garnet.</span></div>
  <div><b>Topology separation</b><span>Multicast common-fanout and 8×8 scale-out groups stay separate; fanout 32 and 64 are never pooled into the cross-topology mean.</span></div>
  <div><b>Trace scaling</b><span>H100 payload and release times are scaled by 1/1024; the reported window is Garnet simulation ticks, not native NVLink time.</span></div>
  <div><b>Neutral topology arm</b><span>The tensor trace's selected routes use ordinary XY, so Mesh XY and the bypass arm produce identical replay results.</span></div>
  <div><b>Revisions</b><span>Multicast/tensor: 77fcf26d57. Bypass evaluation: 1e8764cde7; pressure-aware source hash: ea4c3c9b0f.</span></div>
</div>

</div>

<div class="take"><span class="lab">Rebuild</span><code>plot_multicast.py</code> and <code>generate_architecture_figures.py</code> rebuild figures; <code>run_lab4_full_gate.py</code> runs the functional, backpressure, and trace suites.</div>

<!--
Backup. Use this slide for questions about resource fairness, scale-out pooling, trace scaling, or revisions.
-->
