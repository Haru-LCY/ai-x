# Comparisons

<p class="lede">What exactly was compared?</p>

<div class="body">

<table class="tbl">
  <thead><tr><th>Study</th><th>New mechanism</th><th>Matched baseline</th><th>Primary evidence</th></tr></thead>
  <tbody>
    <tr><td>Tree multicast</td><td>One bitmap packet, replicated at pruned-tree branches</td><td>Replicated unicast on the same Mesh</td><td>Internal-link flits, latency, logical throughput</td></tr>
    <tr><td>Express bypass</td><td>Stride-2 links, multi-hop DOR table, runtime admission</td><td>Plain Mesh XY with fewer resources</td><td>Latency, throughput, traversals, cost proxies</td></tr>
    <tr><td>Tensor replay</td><td>15 event-level multi-flit requests</td><td>6,720 scalar-lane rounds</td><td>Replay window and identical flit counts</td></tr>
  </tbody>
</table>

<div class="formulas">
  <span>S_L = L_base / L_new</span>
  <span>R_F = 1 − F_new / F_base</span>
  <span>I_Q = Q_new / Q_base − 1</span>
</div>

</div>

<!--
Backup. This table records the exact paired comparison behind each headline number.
-->
