from m5.params import *
from m5.proxy import *

from m5.objects.ClockedObject import ClockedObject


class HermesTester(ClockedObject):
    type = "HermesTester"
    cxx_header = "cpu/testers/hermes/hermes_tester.hh"
    cxx_class = "gem5::HermesTester"

    # The script of requests to replay, one entry per index in all three
    # vectors, sorted by tick. A type is "read", "write" or "hermes".
    op_ticks = VectorParam.Tick([], "Tick at which each request is sent")
    op_types = VectorParam.String([], "Type of each request")
    op_addrs = VectorParam.Addr([], "Address of each request")

    port = RequestPort("Port for regular reads and writes")
    hermes_port = RequestPort("Port for Hermes requests")
    system = Param.System(Parent.any, "System this tester is part of")
