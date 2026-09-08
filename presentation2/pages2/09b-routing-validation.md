# Safety validation

<p class="lede">The route union and runtime paths are checked before the performance plots.</p>

<div class="body">

<div>

  <table class="tbl routing-table">
    <thead><tr><th>Suite</th><th class="r">Cases</th><th>Coverage and acceptance check</th></tr></thead>
    <tbody>
      <tr>
        <td>Route / dependency</td>
        <td class="num">5</td>
        <td>2×2 none and diagonal, 3×3 diagonal, 4×4 stride, and a fixed-link placement; rebuild the oracle independently, reject loops, and require a complete topological order.</td>
      </tr>
      <tr>
        <td>Single-flit traversal</td>
        <td class="num">8</td>
        <td>Plain, diagonal forward/reverse/no-shortcut, stride short/reverse/multi-hop, and fixed-span paths; measured hops and ordinary/express flit counters must equal the oracle.</td>
      </tr>
      <tr>
        <td>Multi-flit / backpressure</td>
        <td class="num">14</td>
        <td>1/2/4/8/16/64-flit default and restricted routes, plus bit-complement and opposing-direction contention; require completion, exact counts, and the expected stall observation.</td>
      </tr>
    </tbody>
  </table>

</div>

</div>

<div class="validation-footer">
  <div><b>Construction rule</b><span>A cyclic channel-dependency graph rejects the placement before any performance run.</span></div>
  <div><b>Adaptive-guard pilot</b><span>The aggressive policy had a higher mean but four regressions above 5%; the retained conservative guard had none.</span></div>
</div>

<!--
Timing 25 s. 安全验证放在算法后面。构造阶段会展开所有 source-destination 路径，把连续 channel pair 加进 dependency graph，并要求完整 topological order；有 cycle 就直接拒绝这个 placement。功能上有三组 suite：5 个 route/dependency case，8 个 single-flit traversal case，14 个 multi-flit 和 backpressure case。页面底部的 pilot 说明为什么保留 conservative guard：激进版本平均值更高，但有四个超过 5% 的 regression。
-->
