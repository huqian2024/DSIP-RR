"""DSIP reconstruction adapters (new code, not the historical DSIP implementation).

The upstream MMD checkout stays pristine in ``third_party/_local/mmd``.  Everything
here is an *adapter*: it loads the fixed prior, feeds traffic demand into the
upstream xECBS coordinator, and drives SUMO.  No CBS/SIPP/denoising logic is
re-implemented.
"""
