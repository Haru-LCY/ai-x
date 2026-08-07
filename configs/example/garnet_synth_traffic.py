# Copyright (c) 2016 Georgia Institute of Technology
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Tushar Krishna

import m5
from m5.objects import *
from m5.defines import buildEnv
from m5.util import addToPath
import os, argparse, sys
import math

addToPath("../")

from common import Options
from ruby import Ruby

# Get paths we might need.  It's expected this file is in m5/configs/example.
config_path = os.path.dirname(os.path.abspath(__file__))
config_root = os.path.dirname(config_path)
m5_root = os.path.dirname(config_root)

parser = argparse.ArgumentParser()
Options.addNoISAOptions(parser)

parser.add_argument(
    "--synthetic",
    default="uniform_random",
    choices=[
        "uniform_random",
        "tornado",
        "bit_complement",
        "bit_reverse",
        "bit_rotation",
        "neighbor",
        "shuffle",
        "transpose",
    ],
)

parser.add_argument(
    "-i",
    "--injectionrate",
    type=float,
    default=0.1,
    metavar="I",
    help="Injection rate in packets per cycle per node. \
                        Takes decimal value between 0 to 1 (eg. 0.225). \
                        Number of digits after 0 depends upon --precision.",
)

parser.add_argument(
    "--precision",
    type=int,
    default=3,
    help="Number of digits of precision after decimal point\
                        for injection rate",
)

parser.add_argument(
    "--sim-cycles", type=int, default=1000, help="Number of simulation cycles"
)

parser.add_argument(
    "--collective-rounds",
    "--multicast-rounds",
    dest="collective_rounds",
    type=int,
    default=1,
    help="number of serialized Lab4 all-reduce rounds",
)

parser.add_argument(
    "--lab4-multicast",
    action="store_true",
    help="run the Lab4 tree multicast validation workload",
)

parser.add_argument(
    "--multicast-mode",
    choices=["naive_unicast", "tree_multicast"],
    help="multicast implementation to run",
)

parser.add_argument(
    "--multicast-destinations",
    default="all",
    help="all, a comma-separated Router list, or random:K",
)

parser.add_argument(
    "--multicast-source",
    type=int,
    default=None,
    help="source Router (defaults to --collective-root)",
)

parser.add_argument(
    "--multicast-packet-flits",
    type=int,
    default=1,
    help="multicast packet size in flits",
)

parser.add_argument(
    "--multicast-seed",
    type=int,
    default=1,
    help="seed used to construct deterministic destination sets",
)

parser.add_argument(
    "--multicast-workload",
    choices=["latency", "throughput"],
    default="latency",
)
parser.add_argument("--multicast-injection-rate", type=float, default=1.0)
parser.add_argument("--multicast-max-outstanding", type=int, default=1)
parser.add_argument("--multicast-warmup-rounds", type=int, default=0)
parser.add_argument("--multicast-measurement-rounds", type=int, default=0)
parser.add_argument("--multicast-cooldown-rounds", type=int, default=0)
parser.add_argument(
    "--multicast-background-traffic",
    choices=["none", "uniform_random"],
    default="none",
)
parser.add_argument("--multicast-background-rate", type=float, default=0.0)

parser.add_argument(
    "--num-packets-max",
    type=int,
    default=-1,
    help="Stop injecting after --num-packets-max.\
                        Set to -1 to disable.",
)

parser.add_argument(
    "--single-sender-id",
    type=int,
    default=-1,
    help="Only inject from this sender.\
                        Set to -1 to disable.",
)

parser.add_argument(
    "--single-dest-id",
    type=int,
    default=-1,
    help="Only send to this destination.\
                        Set to -1 to disable.",
)
parser.add_argument(
    "--source-destinations",
    default="",
    help="comma-separated per-source destinations, for example 0:8,4:0",
)

parser.add_argument(
    "--inj-vnet",
    type=int,
    default=-1,
    choices=[-1, 0, 1, 2],
    help="Only inject in this vnet (0, 1 or 2).\
                        0 and 1 are 1-flit, 2 is 5-flit.\
                        Set to -1 to inject randomly in all vnets.",
)

#
# Add the ruby specific and protocol specific options
#
Ruby.define_options(parser)

args = parser.parse_args()

source_destinations = {}
if args.source_destinations:
    if args.single_sender_id >= 0 or args.single_dest_id >= 0:
        parser.error("--source-destinations conflicts with single sender/dest")
    try:
        for entry in args.source_destinations.split(","):
            source, destination = (int(item) for item in entry.split(":"))
            if source in source_destinations:
                parser.error("duplicate source in --source-destinations")
            source_destinations[source] = destination
    except ValueError:
        parser.error("--source-destinations requires SRC:DST pairs")
    if any(
        source < 0 or source >= args.num_cpus
        or destination < 0 or destination >= args.num_cpus
        for source, destination in source_destinations.items()
    ):
        parser.error("source/destination mapping lies outside the Mesh")

if args.lab4_multicast:
    if args.multicast_mode not in (None, "tree_multicast"):
        parser.error("--lab4-multicast conflicts with --multicast-mode")
    args.multicast_mode = "tree_multicast"

multicast_requested = args.multicast_mode is not None
if multicast_requested:
    if args.lab4_all_reduce:
        parser.error("multicast and --lab4-all-reduce are mutually exclusive")
    if args.multicast_source is None:
        args.multicast_source = args.collective_root
    if not 0 <= args.multicast_source < args.num_cpus:
        parser.error("--multicast-source must name an existing Router")
    args.collective_root = args.multicast_source
    args.lab4_multicast = args.multicast_mode == "tree_multicast"

    if args.multicast_destinations == "all":
        multicast_destinations = list(range(args.num_cpus))
    elif args.multicast_destinations.startswith("random:"):
        import random

        try:
            group_size = int(args.multicast_destinations.split(":", 1)[1])
        except ValueError:
            parser.error("random multicast destinations require random:K")
        if not 1 <= group_size <= args.num_cpus:
            parser.error("random multicast group size must be within the Mesh")
        multicast_destinations = sorted(
            random.Random(args.multicast_seed).sample(
                range(args.num_cpus), group_size
            )
        )
    else:
        try:
            multicast_destinations = sorted(
                {int(item) for item in args.multicast_destinations.split(",")}
            )
        except ValueError:
            parser.error("multicast destinations must be Router integers")
        if not multicast_destinations:
            parser.error("multicast destination set must not be empty")
        if multicast_destinations[0] < 0 or multicast_destinations[-1] >= args.num_cpus:
            parser.error("multicast destination lies outside the Mesh")
else:
    multicast_destinations = []

collective_requested = args.lab4_all_reduce or multicast_requested
if collective_requested and source_destinations:
    parser.error("--source-destinations conflicts with collective traffic")
if collective_requested:
    if args.collective_rounds < 1:
        parser.error("--collective-rounds must be positive")
    if args.multicast_packet_flits < 1:
        parser.error("--multicast-packet-flits must be positive")
    if not 0 < args.multicast_injection_rate <= 1:
        parser.error("--multicast-injection-rate must be in (0, 1]")
    if args.multicast_max_outstanding < 1:
        parser.error("--multicast-max-outstanding must be positive")
    phase_rounds = (
        args.multicast_warmup_rounds
        + args.multicast_measurement_rounds
        + args.multicast_cooldown_rounds
    )
    if min(
        args.multicast_warmup_rounds,
        args.multicast_measurement_rounds,
        args.multicast_cooldown_rounds,
    ) < 0:
        parser.error("multicast phase round counts must be non-negative")
    if phase_rounds:
        if args.multicast_measurement_rounds < 1:
            parser.error("phased workload requires measurement rounds")
        args.collective_rounds = phase_rounds
    if not 0 <= args.multicast_background_rate <= 1:
        parser.error("--multicast-background-rate must be in [0, 1]")
    if (args.multicast_background_traffic == "uniform_random" and
            args.multicast_background_rate == 0):
        parser.error("uniform background requires a positive background rate")
    # M1 scalar collectives operate on one HEAD_TAIL flit.
    if args.inj_vnet == -1:
        args.inj_vnet = 0
    elif args.inj_vnet not in (0, 1):
        parser.error(
            "Lab4 scalar collectives require a single-flit vnet "
            "(--inj-vnet=0 or --inj-vnet=1)"
        )

cpus = []
for i in range(args.num_cpus):
    is_multicast_source = multicast_requested and i == args.multicast_source
    is_collective_tester = args.lab4_all_reduce or is_multicast_source
    background_tester = (
        multicast_requested
        and not is_multicast_source
        and args.multicast_background_traffic == "uniform_random"
    )
    cpus.append(GarnetSyntheticTraffic(
        num_packets_max=(
            args.num_packets_max
            if not source_destinations or i in source_destinations
            else 0
        ),
        single_sender=args.single_sender_id,
        single_dest=source_destinations.get(i, args.single_dest_id),
        sim_cycles=args.sim_cycles,
        traffic_type=args.synthetic,
        inj_rate=(args.multicast_background_rate if background_tester else
                  (args.injectionrate if not multicast_requested else 0.0)),
        inj_vnet=(0 if background_tester else args.inj_vnet),
        precision=args.precision,
        num_dest=args.num_dirs,
        collective_mode=is_collective_tester,
        collective_multicast=multicast_requested,
        collective_root=args.collective_root,
        collective_rounds=args.collective_rounds,
        multicast_mode=args.multicast_mode or "none",
        multicast_destinations=multicast_destinations,
        multicast_injection_gap=max(
            1, math.ceil(1.0 / args.multicast_injection_rate)
        ),
        random_seed=args.multicast_seed,
    ))

# create the desired simulated system
system = System(cpu=cpus, mem_ranges=[AddrRange(args.mem_size)])


# Create a top-level voltage domain and clock domain
system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)

system.clk_domain = SrcClockDomain(
    clock=args.sys_clock, voltage_domain=system.voltage_domain
)

Ruby.create_system(args, False, system)
if collective_requested:
    system.ruby.network.collective_mode = True
    system.ruby.network.collective_multicast = multicast_requested
    system.ruby.network.collective_rounds = args.collective_rounds
    system.ruby.network.multicast_mode = args.multicast_mode or "none"
    system.ruby.network.multicast_source = (
        args.multicast_source if multicast_requested else args.collective_root
    )
    system.ruby.network.multicast_destinations = multicast_destinations
    system.ruby.network.multicast_packet_flits = args.multicast_packet_flits
    system.ruby.network.collective_vnet = args.inj_vnet
    system.ruby.network.multicast_workload = args.multicast_workload
    system.ruby.network.multicast_max_outstanding = (
        1 if args.multicast_workload == "latency"
        else args.multicast_max_outstanding
    )
    system.ruby.network.multicast_warmup_rounds = args.multicast_warmup_rounds
    system.ruby.network.multicast_measurement_rounds = (
        args.multicast_measurement_rounds or args.collective_rounds
    )
    system.ruby.network.multicast_cooldown_rounds = args.multicast_cooldown_rounds
    for cpu in cpus:
        cpu.collective_network = system.ruby.network

# Create a seperate clock domain for Ruby
system.ruby.clk_domain = SrcClockDomain(
    clock=args.ruby_clock, voltage_domain=system.voltage_domain
)

i = 0
for ruby_port in system.ruby._cpu_ports:
    #
    # Tie the cpu test ports to the ruby cpu port
    #
    cpus[i].test = ruby_port.in_ports
    i += 1

# -----------------------
# run simulation
# -----------------------

root = Root(full_system=False, system=system)
root.system.mem_mode = "timing"

# Not much point in this being higher than the L1 latency
m5.ticks.setGlobalFrequency("1ps")

# instantiate configuration
m5.instantiate()

# simulate until program terminates
exit_event = m5.simulate(args.abs_max_tick)

print("Exiting @ tick", m5.curTick(), "because", exit_event.getCause())
