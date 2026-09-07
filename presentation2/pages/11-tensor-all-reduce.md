# Tensor all-reduce

<p class="lede">Preserve all-reduce as tensor events.</p>

<div class="body">

<div class="grid2">

<div>

  <div class="fig" style="height:335px"><img src="/tensor_allreduce_pipeline.png" alt="Pipeline from traced all-reduce events through scalar and tensor lowerings to router reduction" /></div>
  <div class="cap">The manipulated variable is request representation; lane arithmetic, routes, release schedule, and counted network work stay fixed.</div>

</div>

<div class="stack">

  <div class="card vi">
    <span class="mark">TRACE SOURCE</span>
    <h3>8× H100 NCCL microbenchmark</h3>
    <p>PyTorch 2.8.0+cu128, CUDA 12.8, NCCL 2.27.3. The compiler keeps 15 broadcasts and 15 all-reduces: five repetitions each at 1, 4, and 16 MiB.</p>
  </div>

  <div class="card vi">
    <span class="mark">REPLAY SCALE</span>
    <h3>16-byte flits, 1/1024 scaling</h3>
    <p>Payload bytes and relative release times are scaled to a tractable Garnet replay. Results are simulation ticks, not native H100 timings.</p>
  </div>

  <div class="card vi">
    <span class="mark">TENSOR PATH</span>
    <h3>Lane-wise accumulation</h3>
    <p>Each flit carries a collective and lane ID. Routers accumulate the key, then forward or broadcast completed lanes; full outputs wait under backpressure.</p>
  </div>

</div>

</div>

</div>

<div class="take vi"><span class="lab">Controlled comparison</span>Scalar lowering repeats one-flit rounds; tensor lowering creates one multi-flit request per event and rank.</div>

<!--
Timing 35 s. Topic 4 uses a measured eight-H100 NCCL trace. After scaling, scalar lowering serializes lanes into independent rounds, while tensor lowering keeps one multi-flit request per event. Routers accumulate by collective and lane ID and preserve backpressure.
-->
