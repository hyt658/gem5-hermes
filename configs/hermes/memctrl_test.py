import argparse
import os
import sys

import m5
from m5.objects import *

LINE = 64
NS = 1000  # one tick is 1 ps
READ_BUFFER_SIZE = 16

CTRL = "system.mem_ctrl."
HERMES_DRAM_BYTES = CTRL + "requestorReadBytes::tester.hermes"
REGULAR_DRAM_BYTES = CTRL + "requestorReadBytes::tester"
READ_BURSTS = CTRL + "readBursts"
SERVICED_BY_WRQ = CTRL + "servicedByWrQ"
RESPONSES = "system.tester.regularResponses"
READ_LATENCY = "system.tester.readLatency"

X = 0x10000
Y = 0x20000

SCENARIOS = {
    # A Hermes request reads DRAM and nothing comes back
    "hermes_only": {
        "ops": [(100 * NS, "hermes", X)],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: 0,
            READ_BURSTS: 1,
            RESPONSES: 0,
        },
    },
    # The regular path is unchanged
    "regular_only": {
        "ops": [(100 * NS, "read", X)],
        "expect": {
            HERMES_DRAM_BYTES: 0,
            REGULAR_DRAM_BYTES: LINE,
            READ_BURSTS: 1,
            RESPONSES: 1,
        },
    },
    # The regular read takes over the Hermes read that already went to DRAM
    "hermes_and_regular": {
        "ops": [(100 * NS, "hermes", X), (120 * NS, "read", X)],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: 0,
            READ_BURSTS: 1,
            RESPONSES: 1,
        },
    },
    # The regular read takes over a Hermes read still waiting in the read queue
    "merge_in_read_queue": {
        "ops": [(100 * NS, "hermes", X + i * LINE) for i in range(8)]
        + [(101 * NS, "read", X + 7 * LINE)],
        "expect": {
            HERMES_DRAM_BYTES: 8 * LINE,
            REGULAR_DRAM_BYTES: 0,
            READ_BURSTS: 8,
            RESPONSES: 1,
        },
    },
    # A merged read is faster than a read of a different, equally idle bank
    "merge_latency": {
        "ops": [
            (100 * NS, "read", Y),
            (5000 * NS, "hermes", X),
            (5020 * NS, "read", X),
        ],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: LINE,
            READ_BURSTS: 2,
            RESPONSES: 2,
        },
        "less": [(READ_LATENCY + "::1", READ_LATENCY + "::0")],
    },
    # A second Hermes request to the same line is dropped
    "two_hermes": {
        "ops": [(100 * NS, "hermes", X), (110 * NS, "hermes", X)],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: 0,
            READ_BURSTS: 1,
            RESPONSES: 0,
        },
    },
    # A Hermes request that arrives after the regular read is dropped
    "regular_then_hermes": {
        "ops": [(100 * NS, "read", X), (110 * NS, "hermes", X)],
        "expect": {
            HERMES_DRAM_BYTES: 0,
            REGULAR_DRAM_BYTES: LINE,
            READ_BURSTS: 1,
            RESPONSES: 1,
        },
    },
    # The Hermes read finished and was dropped, so the regular read reads DRAM
    "hermes_finished": {
        "ops": [(100 * NS, "hermes", X), (5000 * NS, "read", X)],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: LINE,
            READ_BURSTS: 2,
            RESPONSES: 1,
        },
    },
    # The write queue wins over an in-flight Hermes read of the same line
    "write_before_merge": {
        "ops": [
            (100 * NS, "hermes", X),
            (105 * NS, "write", X),
            (120 * NS, "read", X),
        ],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: 0,
            SERVICED_BY_WRQ: 1,
            RESPONSES: 2,
        },
    },
    # Hermes requests beyond the queue size are dropped without a retry, and
    # a regular read still completes afterwards
    "queue_full": {
        "ops": [
            (100 * NS, "hermes", X + i * LINE)
            for i in range(READ_BUFFER_SIZE + 4)
        ]
        + [(2000 * NS, "read", Y)],
        "expect": {
            HERMES_DRAM_BYTES: READ_BUFFER_SIZE * LINE,
            REGULAR_DRAM_BYTES: LINE,
            READ_BURSTS: READ_BUFFER_SIZE + 1,
            RESPONSES: 1,
        },
    },
    # A Hermes request to a line in the write queue needs no DRAM read
    "write_queue_hit": {
        "ops": [(100 * NS, "write", X), (200 * NS, "hermes", X)],
        "expect": {
            HERMES_DRAM_BYTES: 0,
            SERVICED_BY_WRQ: 1,
            RESPONSES: 1,
        },
    },
}


def read_stats(path):
    stats = {}
    with open(path) as f:
        for line in f:
            fields = line.split()
            if len(fields) >= 2:
                stats[fields[0]] = fields[1]
    return stats


parser = argparse.ArgumentParser()
parser.add_argument("scenario", choices=SCENARIOS.keys())
args = parser.parse_args()
scenario = SCENARIOS[args.scenario]

system = System()
system.clk_domain = SrcClockDomain(
    clock="1GHz", voltage_domain=VoltageDomain()
)
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR4_2400_8x8(
    range=system.mem_ranges[0], read_buffer_size=READ_BUFFER_SIZE
)

system.tester = HermesTester(
    op_ticks=[op[0] for op in scenario["ops"]],
    op_types=[op[1] for op in scenario["ops"]],
    op_addrs=[op[2] for op in scenario["ops"]],
)

system.membus = IOXBar()
system.tester.port = system.membus.cpu_side_ports
system.system_port = system.membus.cpu_side_ports
system.membus.mem_side_ports = system.mem_ctrl.port

system.tester.hermes_port = system.mem_ctrl.hermes_port

root = Root(full_system=False, system=system)
m5.instantiate()
m5.simulate(20000 * NS)
m5.stats.dump()

stats = read_stats(os.path.join(m5.options.outdir, "stats.txt"))
failed = False
for name, expected in scenario["expect"].items():
    # stats flagged nozero are left out of stats.txt when they are zero
    actual = float(stats.get(name, 0))
    if actual != expected:
        print(f"FAIL {name}: expected {expected}, got {actual}")
        failed = True

for smaller, larger in scenario.get("less", []):
    print(f"{smaller} = {stats[smaller]}, {larger} = {stats[larger]}")
    if float(stats[smaller]) >= float(stats[larger]):
        print(f"FAIL {smaller} should be below {larger}")
        failed = True

print(f"{'FAIL' if failed else 'PASS'} {args.scenario}")
sys.exit(1 if failed else 0)
