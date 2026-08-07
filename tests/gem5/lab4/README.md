# Lab4 collective regression

`run_collective_matrix.py` validates scalar all-reduce and multicast on 2x2,
3x3, and 4x4 `Mesh_XY` networks. The matrix covers corner and interior roots,
uses completion-driven multi-round execution, and checks exact collective
statistics rather than accepting a timeout-based exit.

Build and run from the repository root:

```sh
LD_LIBRARY_PATH=/path/to/python/lib \
  scons build/Garnet_standalone/gem5.opt -j32 PROTOC=/bin/false
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_collective_matrix.py --jobs 4 --rounds 5
```

The runner creates a unique directory under `/tmp` and prints its path. Each
case retains `sim.log`, `stats.txt`, and the standard gem5 configuration files.
It fails if any round misses or duplicates a destination, if completion is not
the exit cause, or if source, Router-generated, delivery, and reduction counts
do not match the tree protocol.
