"""Load the fixed prior ``EnvEmptyNoWait2D-RobotPlanarDisk`` with upstream MPD.

Why a shim
----------
``mmd.planners.single_agent.MPD`` builds its world through
``get_dataset(dataset_class='TrajectoryDataset', ...)``, which reads
``data_trajectories/<subdir>/`` -- the 10 000-trajectory dataset the model was
trained on (``train_subset_indices.pt`` holds 9500 of 10000).  That directory is
**not present in this workspace** (only the checkpoint archive is; see
``docs/dsip_reconstruction/checkpoint_manifest.md``), so this module supplies a
*shim* exposing exactly the attributes ``MPD`` reads.

``MPD`` itself is **not modified**: ``mmd.planners.single_agent.mpd.get_dataset``
is patched only while the planner object is being constructed.

Normalization limits -- assumption and why it is safe
-----------------------------------------------------
``LimitsNormalizer`` maps the training data's per-dimension ``[min, max]`` to
``[-1, 1]``.  The training data are collision-free trajectories of a disk of
radius 0.05 inside the env box ``[-1, 1]^2``, so the position range is that box
shrunk by the robot margin: about ``+-0.95``.  A small error here only rescales
the planning frame, and that scale is an explicit adapter parameter anyway (see
``planning_frame.py``).  Velocities are taken as symmetric ``+-1.5``; every hard
condition pins the velocity to zero, and a symmetric range normalizes zero to
exactly zero, so this value affects only the *unnormalized* velocity channel,
which the SUMO interface never uses.

Every run manifest records ``dataset_source: "shim"``.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import torch

from . import upstream_env

ROBOT_RADIUS = 0.05          # RobotPlanarDisk radius, in frame units
POS_LIMIT = 0.95
VEL_LIMIT = 1.5
N_SUPPORT_POINTS = 64


class LimitsNormalizer:
    """Same arithmetic as ``mmd.datasets.normalization.LimitsNormalizer``."""

    def __init__(self, mins, maxs, tensor_args):
        self.mins = torch.as_tensor(mins, **tensor_args)
        self.maxs = torch.as_tensor(maxs, **tensor_args)

    def normalize(self, x):
        return 2.0 * (x - self.mins) / (self.maxs - self.mins) - 1.0

    def unnormalize(self, x, eps=1e-4):
        if x.max() > 1 + eps or x.min() < -1 - eps:
            x = torch.clip(x, -1, 1)
        return (x + 1.0) / 2.0 * (self.maxs - self.mins) + self.mins


class FrameDataset:
    """The subset of ``TrajectoryDataset``'s interface that ``MPD`` uses."""

    def __init__(self, env, robot, task, tensor_args,
                 pos_limit=POS_LIMIT, vel_limit=VEL_LIMIT):
        self.env = env
        self.robot = robot
        self.task = task
        self.tensor_args = tensor_args
        self.n_support_points = N_SUPPORT_POINTS
        self.state_dim = 2 * robot.q_dim          # [x, y, vx, vy]
        self.threshold_start_goal_pos = 0.5
        self.include_velocity = True
        self.normalizer = LimitsNormalizer(
            [-pos_limit, -pos_limit, -vel_limit, -vel_limit],
            [pos_limit, pos_limit, vel_limit, vel_limit],
            tensor_args)

    def normalize_trajectories(self, x):
        return self.normalizer.normalize(x)

    def unnormalize_trajectories(self, x):
        return self.normalizer.unnormalize(x)

    def get_hard_conditions(self, traj, horizon=None, normalize=False):
        # Body copied verbatim from mmd.datasets.trajectories.TrajectoryDataset.
        start_state_pos = self.robot.get_position(traj[0])
        goal_state_pos = self.robot.get_position(traj[-1])
        start_state = torch.cat((start_state_pos,
                                 torch.zeros_like(start_state_pos)), dim=-1)
        goal_state = torch.cat((goal_state_pos,
                                torch.zeros_like(goal_state_pos)), dim=-1)
        if normalize:
            start_state = self.normalizer.normalize(start_state)
            goal_state = self.normalizer.normalize(goal_state)
        if horizon is None:
            horizon = self.n_support_points
        return {0: start_state, horizon - 1: goal_state}



class _Subset:
    """Stand-in for a ``torch.utils.data.Subset``: only ``.dataset`` is read."""

    def __init__(self, dataset):
        self.dataset = dataset


def build_frame_dataset(tensor_args):
    """Instantiate env/robot/task the way ``TrajectoryDataset`` would."""
    from torch_robotics.environments import EnvEmptyNoWait2DExtraObjects
    from torch_robotics.robots import RobotPlanarDisk
    from torch_robotics.tasks.tasks import PlanningTask

    env = EnvEmptyNoWait2DExtraObjects(tensor_args=tensor_args)
    robot = RobotPlanarDisk(tensor_args=tensor_args)
    task = PlanningTask(env=env, robot=robot, obstacle_cutoff_margin=0.05,
                        tensor_args=tensor_args)
    return FrameDataset(env, robot, task, tensor_args)


@contextmanager
def _patched_dataset(frame_dataset):
    """Temporarily replace ``get_dataset`` in ``mpd``'s module namespace."""
    import mmd.planners.single_agent.mpd as mpd_module

    original = mpd_module.get_dataset

    def fake_get_dataset(**kwargs):
        return _Subset(frame_dataset), None, None, None

    mpd_module.get_dataset = fake_get_dataset
    try:
        yield
    finally:
        mpd_module.get_dataset = original


_DATASET_CACHE = {}
_STATE_DICT_CACHE = {}


def cached_frame_dataset(tensor_args):
    """One env/robot/task per device: the SDF precompute is the expensive part."""
    key = (str(tensor_args["device"]), str(tensor_args["dtype"]))
    if key not in _DATASET_CACHE:
        _DATASET_CACHE[key] = build_frame_dataset(tensor_args)
    return _DATASET_CACHE[key]


@contextmanager
def _patched_torch_load():
    """Memoise checkpoint loads: every planner would otherwise re-read the file."""
    original = torch.load

    def fake_load(f, *a, **k):
        key = str(f)
        if key.endswith(".pth"):
            if key not in _STATE_DICT_CACHE:
                _STATE_DICT_CACHE[key] = original(f, *a, **k)
            return _STATE_DICT_CACHE[key]
        return original(f, *a, **k)

    torch.load = fake_load
    try:
        yield
    finally:
        torch.load = original


def build_mpd(start_state_pos, goal_state_pos, device="cuda", seed=0,
              model_id=upstream_env.MODEL_ID,
              trained_models_dir=upstream_env.TRAINED_MODELS_DIR,
              shim=True, torch_compile=None):
    """Construct an upstream ``MPD`` planner bound to one start/goal pair."""
    if torch_compile is None:
        torch_compile = os.environ.get("DSIP_TORCH_COMPILE", "1") != "0"
    from mmd.config import MMDParams as params
    from mmd.planners.single_agent import MPD

    tensor_args = {"device": torch.device(device), "dtype": torch.float32}
    kwargs = dict(
        model_id=model_id,
        planner_alg="mmd",
        start_state_pos=start_state_pos,
        goal_state_pos=goal_state_pos,
        use_guide_on_extra_objects_only=params.use_guide_on_extra_objects_only,
        n_samples=params.n_samples,
        n_local_inference_noising_steps=params.n_local_inference_noising_steps,
        n_local_inference_denoising_steps=params.n_local_inference_denoising_steps,
        start_guide_steps_fraction=params.start_guide_steps_fraction,
        n_guide_steps=params.n_guide_steps,
        n_diffusion_steps_without_noise=params.n_diffusion_steps_without_noise,
        weight_grad_cost_collision=params.weight_grad_cost_collision,
        weight_grad_cost_smoothness=params.weight_grad_cost_smoothness,
        weight_grad_cost_constraints=params.weight_grad_cost_constraints,
        weight_grad_cost_soft_constraints=params.weight_grad_cost_soft_constraints,
        factor_num_interpolated_points_for_collision=(
            params.factor_num_interpolated_points_for_collision),
        trajectory_duration=params.trajectory_duration,
        device=device,
        debug=params.debug,
        seed=seed,
        results_dir=params.results_dir,
        trained_models_dir=trained_models_dir,
    )
    original_compile = None
    if not torch_compile:
        # torch.compile is upstream's default; disabled only for debugging.
        original_compile = torch.compile
        torch.compile = lambda fn, *a, **k: fn
    try:
        if shim:
            with _patched_torch_load(), _patched_dataset(
                    cached_frame_dataset(tensor_args)):
                planner = MPD(**kwargs)
        else:
            planner = MPD(**kwargs)
    finally:
        if original_compile is not None:
            torch.compile = original_compile
    return planner
