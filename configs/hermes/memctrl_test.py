import argparse
import os
import sys

import m5
from m5.objects import *

LINE = 64
NS = 1000  # one tick is 1 ps
READ_BUFFER_SIZE = 16
SIM_TICKS = 20000 * NS

CTRL = "system.mem_ctrl."
HERMES_DRAM_BYTES = CTRL + "requestorReadBytes::tester.hermes"
REGULAR_DRAM_BYTES = CTRL + "requestorReadBytes::tester"
READ_BURSTS = CTRL + "readBursts"
SERVICED_BY_WRQ = CTRL + "servicedByWrQ"
HERMES_REQS = CTRL + "hermesReqs"
HERMES_MERGED = CTRL + "hermesMerged"
HERMES_UNUSED = CTRL + "hermesUnused"
HERMES_DROP_FULL = CTRL + "hermesDropFull"
HERMES_DROP_IN_FLIGHT = CTRL + "hermesDropInFlight"
HERMES_WRQ = CTRL + "hermesServicedByWrQ"
HERMES_OUTCOMES = [
    HERMES_MERGED,
    HERMES_UNUSED,
    HERMES_DROP_FULL,
    HERMES_DROP_IN_FLIGHT,
    HERMES_WRQ,
]
REGULAR_SENT = "system.tester.regularSent"
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
            HERMES_UNUSED: 1,
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
            HERMES_MERGED: 1,
            HERMES_UNUSED: 0,
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
            HERMES_UNUSED: 1,
            HERMES_DROP_IN_FLIGHT: 1,
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
            HERMES_DROP_IN_FLIGHT: 1,
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
            HERMES_UNUSED: READ_BUFFER_SIZE,
            HERMES_DROP_FULL: 4,
        },
    },
    # A Hermes request to a line in the write queue needs no DRAM read
    "write_queue_hit": {
        "ops": [(100 * NS, "write", X), (200 * NS, "hermes", X)],
        "expect": {
            HERMES_DRAM_BYTES: 0,
            SERVICED_BY_WRQ: 1,
            RESPONSES: 1,
            HERMES_WRQ: 1,
            HERMES_UNUSED: 0,
        },
    },
    # A merged read returns the data of a write that already left the write
    # queue. A low threshold of 0 makes the controller drain the write at once
    "merge_after_write": {
        "ctrl": {"write_low_thresh_perc": 0},
        "ops": [
            (100 * NS, "write", X),
            (5000 * NS, "hermes", X),
            # The write left the row open, so the Hermes read is a row hit
            # that ends after 17.5 ns, and the regular read must come earlier
            (5005 * NS, "read", X),
        ],
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: 0,
            READ_BURSTS: 1,
            SERVICED_BY_WRQ: 0,
            RESPONSES: 2,
            HERMES_MERGED: 1,
        },
    },
    # A drain waits for Hermes reads, both queued and already sent to DRAM
    "drain_with_hermes": {
        "ops": [(100 * NS, "hermes", X + i * LINE) for i in range(8)],
        "drain_at": 105 * NS,
        "expect": {
            HERMES_DRAM_BYTES: 8 * LINE,
            READ_BURSTS: 8,
            RESPONSES: 0,
        },
    },
    # A drain also waits for a regular read merged with a Hermes read
    "drain_with_merge": {
        "ops": [(100 * NS, "hermes", X), (120 * NS, "read", X)],
        "drain_at": 125 * NS,
        "expect": {
            HERMES_DRAM_BYTES: LINE,
            REGULAR_DRAM_BYTES: 0,
            READ_BURSTS: 1,
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
parser.add_argument(
    "--misroute",
    choices=["membus", "cache"],
    help="Connect the Hermes port the wrong way, which must end in a panic",
)
args = parser.parse_args()
scenario = SCENARIOS[args.scenario]

system = System()
system.clk_domain = SrcClockDomain(
    clock="1GHz", voltage_domain=VoltageDomain()
)
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

system.mem_ctrl = MemCtrl(**scenario.get("ctrl", {}))
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

if args.misroute == "membus":
    system.tester.hermes_port = system.membus.cpu_side_ports
elif args.misroute == "cache":
    system.cache = Cache(
        size="1kB",
        assoc=2,
        tag_latency=1,
        data_latency=1,
        response_latency=1,
        mshrs=4,
        tgts_per_mshr=4,
    )
    system.tester.hermes_port = system.cache.cpu_side
    system.cache.mem_side = system.membus.cpu_side_ports
else:
    system.tester.hermes_port = system.mem_ctrl.hermes_port

root = Root(full_system=False, system=system)
m5.instantiate()
m5.simulate(scenario.get("drain_at", SIM_TICKS))
# Everything in flight must finish here, or this call never returns
m5.drain()
m5.stats.dump()

stats = read_stats(os.path.join(m5.options.outdir, "stats.txt"))
failed = False
for name, expected in scenario["expect"].items():
    # stats flagged nozero are left out of stats.txt when they are zero
    actual = float(stats.get(name, 0))
    if actual != expected:
        print(f"FAIL {name}: expected {expected}, got {actual}")
        failed = True

# Every regular request gets exactly one response
if float(stats[REGULAR_SENT]) != float(stats[RESPONSES]):
    print(f"FAIL sent {stats[REGULAR_SENT]}, got {stats[RESPONSES]} responses")
    failed = True

# Every Hermes request ends in exactly one outcome
outcomes = sum(float(stats.get(name, 0)) for name in HERMES_OUTCOMES)
if float(stats[HERMES_REQS]) != outcomes:
    print(f"FAIL {stats[HERMES_REQS]} Hermes requests, {outcomes} outcomes")
    failed = True

for smaller, larger in scenario.get("less", []):
    print(f"{smaller} = {stats[smaller]}, {larger} = {stats[larger]}")
    if float(stats[smaller]) >= float(stats[larger]):
        print(f"FAIL {smaller} should be below {larger}")
        failed = True

print(f"{'FAIL' if failed else 'PASS'} {args.scenario}")
sys.exit(1 if failed else 0)
