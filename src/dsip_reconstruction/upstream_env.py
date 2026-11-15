"""Import the in-workspace MMD checkout, and refuse anything outside it.

The ``mmd`` conda environment has *editable installs that point outside this
workspace* (an older clone in ``~/Downloads``).  AGENTS.md section 0 forbids
reading or using that tree, so this module puts the in-workspace checkout at the
front of ``sys.path`` and then asserts that every import really resolved here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
MMD = ROOT / "third_party" / "_local" / "mmd"

_SUBDIRS = [
    MMD,
    MMD / "deps" / "torch_robotics",
    MMD / "deps" / "motion_planning_baselines",
    MMD / "deps" / "experiment_launcher",
]

TRAINED_MODELS_DIR = str(ROOT / "third_party" / "_local" / "_assets"
                         / "data_trained_models") + "/"
MODEL_ID = "EnvEmptyNoWait2D-RobotPlanarDisk"


def ensure() -> None:
    """Prepend the in-workspace paths; must be called before importing mmd."""
    if not MMD.is_dir():
        raise RuntimeError("upstream MMD checkout missing: %s" % MMD)
    for path in reversed(_SUBDIRS):
        p = str(path)
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)


def assert_inside() -> dict:
    """Raise unless mmd/torch_robotics/mp_baselines resolve inside the workspace."""
    import mmd
    import mp_baselines
    import torch_robotics

    resolved = {"mmd": mmd.__file__,
                "torch_robotics": torch_robotics.__file__,
                "mp_baselines": mp_baselines.__file__}
    root = str(ROOT.resolve())
    bad = {k: v for k, v in resolved.items()
           if not str(Path(v).resolve()).startswith(root + "/")}
    if bad:
        raise RuntimeError(
            "imports resolved outside the workspace (AGENTS.md section 0): %s"
            % bad)
    return resolved
