# H100 trace replay

<p class="lede">Same collective work; different request granularity.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:335px"><img src="/tensor_allreduce_pipeline.png" alt="Pipeline from the measured H100 collective schedule through scalar and tensor replay lowerings to router reduction" /></div>
  <div class="cap">Trace-based traffic pattern: real NCCL collective events from 8×H100 become an operation-level Garnet replay; the figure shows the shared work and the two request representations.</div>

</div>

<div class="stack">

  <table class="tbl">
    <thead><tr><th>Lowering</th><th class="r">Request shape</th><th class="r">Scaled window</th></tr></thead>
    <tbody>
      <tr><td>Scalar</td><td class="num">many one-flit rounds</td><td class="num">80.638 M ticks</td></tr>
      <tr class="pick"><td>Tensor</td><td class="num">one multi-flit request/event</td><td class="num">17.055 M ticks</td></tr>
    </tbody>
  </table>

  <div class="metric vi">
    <span class="v">4.728×</span>
    <span class="k">shorter scaled replay window</span>
    <span class="n">same payload and tree work</span>
  </div>

</div>

</div>

</div>

<div class="take vi"><span class="lab">Takeaway</span>Tensor does not send fewer bytes; it preserves one collective event as one multi-flit request, removing scalar request serialization.</div>

<!--
先看左边流程图。8 个 distributed processes 分别绑定一张 H100，真实执行 NCCL 的 collective traffic；每轮对 1、4、16 MiB 的 tensor 依次执行 all-reduce 和 root-0 broadcast。我们保留的是 all-reduce event 的大小和相对 release 顺序，形成了 trace-based traffic pattern。

然后把这个 operation-level schedule 放进 Garnet replay。payload 和时间会做缩放，所以结果是 simulation ticks，不能解释成 native H100 或 NVLink 的时间。

最后看右边表格。scalar 把一个 event 拆成很多 one-flit rounds；tensor 保留成一个 multi-flit request。两边搬运的 payload 和 tree work 相同，但 tensor 消除了 request serialization，所以 scaled replay window 缩短了 4.728 倍。
-->
