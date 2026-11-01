"""FCFS baseline for the DSIP revision -- SHADOW MODE only.

This package computes FCFS scheduling decisions and logs events but never
commands a vehicle.  No ``setSpeed`` / ``slowDown`` / ``setStop`` / ``moveTo``
call exists anywhere in the package.

Modules
-------
conflicts  provisional movement-level conflict model for one intersection
tracker    per-step vehicle state tracking (approach / inside / exit / gone)
queue      frozen-priority FCFS request queue
shadow     shadow decision engine + CSV writers
runner     TraCI loop that connects the three parts (read-only)
test_logic dependency-free self check of the pure logic
"""

__all__ = ["conflicts", "tracker", "queue", "shadow", "runner"]
