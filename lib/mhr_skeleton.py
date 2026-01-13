"""
MHR Skeleton Definition and Utilities

MHR (Meta Human Representation) is a 70-keypoint skeleton format from SAM3D Body.
This module provides skeleton definitions for converting MHR to BVH/FBX formats.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional


# ============================================================
# MHR70 KEYPOINT DEFINITIONS
# ============================================================

# MHR 70 keypoint names (from SAM3D Body)
MHR_KEYPOINT_NAMES = [
    # Face/Head (0-4)
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    # Upper body (5-8)
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    # Lower body (9-14)
    "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    # Feet (15-20)
    "left_big_toe", "left_small_toe", "left_heel",
    "right_big_toe", "right_small_toe", "right_heel",
    # Right hand (21-41)
    "right_thumb_tip", "right_thumb_first", "right_thumb_second", "right_thumb_third",
    "right_index_tip", "right_index_first", "right_index_second", "right_index_third",
    "right_middle_tip", "right_middle_first", "right_middle_second", "right_middle_third",
    "right_ring_tip", "right_ring_first", "right_ring_second", "right_ring_third",
    "right_pinky_tip", "right_pinky_first", "right_pinky_second", "right_pinky_third",
    "right_wrist",
    # Left hand (42-62)
    "left_thumb_tip", "left_thumb_first", "left_thumb_second", "left_thumb_third",
    "left_index_tip", "left_index_first", "left_index_second", "left_index_third",
    "left_middle_tip", "left_middle_first", "left_middle_second", "left_middle_third",
    "left_ring_tip", "left_ring_first", "left_ring_second", "left_ring_third",
    "left_pinky_tip", "left_pinky_first", "left_pinky_second", "left_pinky_third",
    "left_wrist",
    # Extra anatomical points (63-69)
    "left_olecranon", "right_olecranon",
    "left_cubital_fossa", "right_cubital_fossa",
    "left_acromion", "right_acromion",
    "neck",
]


class MHRKeypoints:
    """MHR keypoint index constants for easy reference."""
    # Face/Head
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4

    # Upper body
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8

    # Lower body
    LEFT_HIP = 9
    RIGHT_HIP = 10
    LEFT_KNEE = 11
    RIGHT_KNEE = 12
    LEFT_ANKLE = 13
    RIGHT_ANKLE = 14

    # Feet
    LEFT_BIG_TOE = 15
    LEFT_SMALL_TOE = 16
    LEFT_HEEL = 17
    RIGHT_BIG_TOE = 18
    RIGHT_SMALL_TOE = 19
    RIGHT_HEEL = 20

    # Wrists
    RIGHT_WRIST = 41
    LEFT_WRIST = 62

    # Extra points
    LEFT_OLECRANON = 63
    RIGHT_OLECRANON = 64
    LEFT_CUBITAL_FOSSA = 65
    RIGHT_CUBITAL_FOSSA = 66
    LEFT_ACROMION = 67
    RIGHT_ACROMION = 68
    NECK = 69


# ============================================================
# BVH SKELETON DEFINITION FOR MHR
# ============================================================

# BVH joint names for MHR skeleton (hierarchical)
# We create a standard skeleton that matches common animation rigs
MHR_BVH_JOINT_NAMES = [
    # Core body (0-15)
    'Pelvis',       # 0 - derived from hip midpoint
    'Spine',        # 1 - interpolated
    'Spine1',       # 2 - interpolated
    'Spine2',       # 3 - interpolated
    'Neck',         # 4 - MHR keypoint 69
    'Head',         # 5 - MHR keypoint 0 (nose)
    'L_Hip',        # 6 - MHR keypoint 9
    'R_Hip',        # 7 - MHR keypoint 10
    'L_Knee',       # 8 - MHR keypoint 11
    'R_Knee',       # 9 - MHR keypoint 12
    'L_Ankle',      # 10 - MHR keypoint 13
    'R_Ankle',      # 11 - MHR keypoint 14
    'L_Foot',       # 12 - MHR keypoint 15 (big toe)
    'R_Foot',       # 13 - MHR keypoint 18 (big toe)
    'L_Collar',     # 14 - MHR keypoint 67 (acromion)
    'R_Collar',     # 15 - MHR keypoint 68 (acromion)
    # Arms (16-21)
    'L_Shoulder',   # 16 - MHR keypoint 5
    'R_Shoulder',   # 17 - MHR keypoint 6
    'L_Elbow',      # 18 - MHR keypoint 7
    'R_Elbow',      # 19 - MHR keypoint 8
    'L_Wrist',      # 20 - MHR keypoint 62
    'R_Wrist',      # 21 - MHR keypoint 41
    # Left hand fingers (22-36)
    'L_Thumb1', 'L_Thumb2', 'L_Thumb3',      # 22-24
    'L_Index1', 'L_Index2', 'L_Index3',      # 25-27
    'L_Middle1', 'L_Middle2', 'L_Middle3',   # 28-30
    'L_Ring1', 'L_Ring2', 'L_Ring3',         # 31-33
    'L_Pinky1', 'L_Pinky2', 'L_Pinky3',      # 34-36
    # Right hand fingers (37-51)
    'R_Thumb1', 'R_Thumb2', 'R_Thumb3',      # 37-39
    'R_Index1', 'R_Index2', 'R_Index3',      # 40-42
    'R_Middle1', 'R_Middle2', 'R_Middle3',   # 43-45
    'R_Ring1', 'R_Ring2', 'R_Ring3',         # 46-48
    'R_Pinky1', 'R_Pinky2', 'R_Pinky3',      # 49-51
]

# Parent indices for BVH hierarchy (depth-first traversal)
MHR_BVH_PARENTS = [
    -1,  # 0: Pelvis (root)
    0,   # 1: Spine -> Pelvis
    1,   # 2: Spine1 -> Spine
    2,   # 3: Spine2 -> Spine1
    3,   # 4: Neck -> Spine2
    4,   # 5: Head -> Neck
    0,   # 6: L_Hip -> Pelvis
    0,   # 7: R_Hip -> Pelvis
    6,   # 8: L_Knee -> L_Hip
    7,   # 9: R_Knee -> R_Hip
    8,   # 10: L_Ankle -> L_Knee
    9,   # 11: R_Ankle -> R_Knee
    10,  # 12: L_Foot -> L_Ankle
    11,  # 13: R_Foot -> R_Ankle
    3,   # 14: L_Collar -> Spine2
    3,   # 15: R_Collar -> Spine2
    14,  # 16: L_Shoulder -> L_Collar
    15,  # 17: R_Shoulder -> R_Collar
    16,  # 18: L_Elbow -> L_Shoulder
    17,  # 19: R_Elbow -> R_Shoulder
    18,  # 20: L_Wrist -> L_Elbow
    19,  # 21: R_Wrist -> R_Elbow
    # Left hand
    20,  # 22: L_Thumb1 -> L_Wrist
    22,  # 23: L_Thumb2 -> L_Thumb1
    23,  # 24: L_Thumb3 -> L_Thumb2
    20,  # 25: L_Index1 -> L_Wrist
    25,  # 26: L_Index2 -> L_Index1
    26,  # 27: L_Index3 -> L_Index2
    20,  # 28: L_Middle1 -> L_Wrist
    28,  # 29: L_Middle2 -> L_Middle1
    29,  # 30: L_Middle3 -> L_Middle2
    20,  # 31: L_Ring1 -> L_Wrist
    31,  # 32: L_Ring2 -> L_Ring1
    32,  # 33: L_Ring3 -> L_Ring2
    20,  # 34: L_Pinky1 -> L_Wrist
    34,  # 35: L_Pinky2 -> L_Pinky1
    35,  # 36: L_Pinky3 -> L_Pinky2
    # Right hand
    21,  # 37: R_Thumb1 -> R_Wrist
    37,  # 38: R_Thumb2 -> R_Thumb1
    38,  # 39: R_Thumb3 -> R_Thumb2
    21,  # 40: R_Index1 -> R_Wrist
    40,  # 41: R_Index2 -> R_Index1
    41,  # 42: R_Index3 -> R_Index2
    21,  # 43: R_Middle1 -> R_Wrist
    43,  # 44: R_Middle2 -> R_Middle1
    44,  # 45: R_Middle3 -> R_Middle2
    21,  # 46: R_Ring1 -> R_Wrist
    46,  # 47: R_Ring2 -> R_Ring1
    47,  # 48: R_Ring3 -> R_Ring2
    21,  # 49: R_Pinky1 -> R_Wrist
    49,  # 50: R_Pinky2 -> R_Pinky1
    50,  # 51: R_Pinky3 -> R_Pinky2
]

# Mapping from BVH joint index to MHR keypoint index (for position-based joints)
# None means the position needs to be interpolated
MHR_TO_BVH_KEYPOINT_MAP = {
    0: None,                         # Pelvis - midpoint of hips
    1: None,                         # Spine - interpolated
    2: None,                         # Spine1 - interpolated
    3: None,                         # Spine2 - interpolated
    4: MHRKeypoints.NECK,            # Neck
    5: MHRKeypoints.NOSE,            # Head
    6: MHRKeypoints.LEFT_HIP,        # L_Hip
    7: MHRKeypoints.RIGHT_HIP,       # R_Hip
    8: MHRKeypoints.LEFT_KNEE,       # L_Knee
    9: MHRKeypoints.RIGHT_KNEE,      # R_Knee
    10: MHRKeypoints.LEFT_ANKLE,     # L_Ankle
    11: MHRKeypoints.RIGHT_ANKLE,    # R_Ankle
    12: MHRKeypoints.LEFT_BIG_TOE,   # L_Foot
    13: MHRKeypoints.RIGHT_BIG_TOE,  # R_Foot
    14: MHRKeypoints.LEFT_ACROMION,  # L_Collar
    15: MHRKeypoints.RIGHT_ACROMION, # R_Collar
    16: MHRKeypoints.LEFT_SHOULDER,  # L_Shoulder
    17: MHRKeypoints.RIGHT_SHOULDER, # R_Shoulder
    18: MHRKeypoints.LEFT_ELBOW,     # L_Elbow
    19: MHRKeypoints.RIGHT_ELBOW,    # R_Elbow
    20: MHRKeypoints.LEFT_WRIST,     # L_Wrist
    21: MHRKeypoints.RIGHT_WRIST,    # R_Wrist
    # Left hand (MHR indices: 45=third, 44=second, 43=first for thumb, etc.)
    22: 45,  # L_Thumb1 - left_thumb_third_joint
    23: 44,  # L_Thumb2 - left_thumb_second
    24: 43,  # L_Thumb3 - left_thumb_first
    25: 49,  # L_Index1 - left_index_third_joint
    26: 48,  # L_Index2 - left_index_second
    27: 47,  # L_Index3 - left_index_first
    28: 53,  # L_Middle1 - left_middle_third_joint
    29: 52,  # L_Middle2 - left_middle_second
    30: 51,  # L_Middle3 - left_middle_first
    31: 57,  # L_Ring1 - left_ring_third_joint
    32: 56,  # L_Ring2 - left_ring_second
    33: 55,  # L_Ring3 - left_ring_first
    34: 61,  # L_Pinky1 - left_pinky_third_joint
    35: 60,  # L_Pinky2 - left_pinky_second
    36: 59,  # L_Pinky3 - left_pinky_first
    # Right hand (MHR indices: 24=third, 23=second, 22=first for thumb, etc.)
    37: 24,  # R_Thumb1 - right_thumb_third_joint
    38: 23,  # R_Thumb2 - right_thumb_second
    39: 22,  # R_Thumb3 - right_thumb_first
    40: 28,  # R_Index1 - right_index_third_joint
    41: 27,  # R_Index2 - right_index_second
    42: 26,  # R_Index3 - right_index_first
    43: 32,  # R_Middle1 - right_middle_third_joint
    44: 31,  # R_Middle2 - right_middle_second
    45: 30,  # R_Middle3 - right_middle_first
    46: 36,  # R_Ring1 - right_ring_third_joint
    47: 35,  # R_Ring2 - right_ring_second
    48: 34,  # R_Ring3 - right_ring_first
    49: 40,  # R_Pinky1 - right_pinky_third_joint
    50: 39,  # R_Pinky2 - right_pinky_second
    51: 38,  # R_Pinky3 - right_pinky_first
}

# T-pose offsets for BVH skeleton (in meters, Y-up coordinate system)
MHR_BVH_OFFSETS = {
    0: [0.0, 0.0, 0.0],           # Pelvis (root)
    1: [0.0, 0.1, 0.0],           # Spine
    2: [0.0, 0.15, 0.0],          # Spine1
    3: [0.0, 0.15, 0.0],          # Spine2
    4: [0.0, 0.1, 0.0],           # Neck
    5: [0.0, 0.15, 0.0],          # Head
    6: [0.1, 0.0, 0.0],           # L_Hip
    7: [-0.1, 0.0, 0.0],          # R_Hip
    8: [0.0, -0.4, 0.0],          # L_Knee
    9: [0.0, -0.4, 0.0],          # R_Knee
    10: [0.0, -0.4, 0.0],         # L_Ankle
    11: [0.0, -0.4, 0.0],         # R_Ankle
    12: [0.0, -0.05, 0.1],        # L_Foot
    13: [0.0, -0.05, 0.1],        # R_Foot
    14: [0.1, 0.0, 0.0],          # L_Collar
    15: [-0.1, 0.0, 0.0],         # R_Collar
    16: [0.1, 0.0, 0.0],          # L_Shoulder
    17: [-0.1, 0.0, 0.0],         # R_Shoulder
    18: [0.25, 0.0, 0.0],         # L_Elbow
    19: [-0.25, 0.0, 0.0],        # R_Elbow
    20: [0.25, 0.0, 0.0],         # L_Wrist
    21: [-0.25, 0.0, 0.0],        # R_Wrist
    # Left hand fingers
    22: [0.04, 0.0, 0.02],        # L_Thumb1
    23: [0.03, 0.0, 0.0],         # L_Thumb2
    24: [0.025, 0.0, 0.0],        # L_Thumb3
    25: [0.08, 0.0, 0.01],        # L_Index1
    26: [0.035, 0.0, 0.0],        # L_Index2
    27: [0.025, 0.0, 0.0],        # L_Index3
    28: [0.08, 0.0, 0.0],         # L_Middle1
    29: [0.04, 0.0, 0.0],         # L_Middle2
    30: [0.03, 0.0, 0.0],         # L_Middle3
    31: [0.075, 0.0, -0.01],      # L_Ring1
    32: [0.035, 0.0, 0.0],        # L_Ring2
    33: [0.025, 0.0, 0.0],        # L_Ring3
    34: [0.065, 0.0, -0.02],      # L_Pinky1
    35: [0.025, 0.0, 0.0],        # L_Pinky2
    36: [0.02, 0.0, 0.0],         # L_Pinky3
    # Right hand fingers (mirrored)
    37: [-0.04, 0.0, 0.02],       # R_Thumb1
    38: [-0.03, 0.0, 0.0],        # R_Thumb2
    39: [-0.025, 0.0, 0.0],       # R_Thumb3
    40: [-0.08, 0.0, 0.01],       # R_Index1
    41: [-0.035, 0.0, 0.0],       # R_Index2
    42: [-0.025, 0.0, 0.0],       # R_Index3
    43: [-0.08, 0.0, 0.0],        # R_Middle1
    44: [-0.04, 0.0, 0.0],        # R_Middle2
    45: [-0.03, 0.0, 0.0],        # R_Middle3
    46: [-0.075, 0.0, -0.01],     # R_Ring1
    47: [-0.035, 0.0, 0.0],       # R_Ring2
    48: [-0.025, 0.0, 0.0],       # R_Ring3
    49: [-0.065, 0.0, -0.02],     # R_Pinky1
    50: [-0.025, 0.0, 0.0],       # R_Pinky2
    51: [-0.02, 0.0, 0.0],        # R_Pinky3
}


# ============================================================
# BODY-ONLY SKELETON (without hands, 22 joints)
# ============================================================

MHR_BVH_BODY_JOINT_NAMES = MHR_BVH_JOINT_NAMES[:22]
MHR_BVH_BODY_PARENTS = MHR_BVH_PARENTS[:22]


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_bvh_joint_order(parent_indices: List[int]) -> List[int]:
    """
    Get depth-first traversal order of joints for BVH format.
    BVH requires motion data in hierarchy order.

    Args:
        parent_indices: List of parent indices for each joint

    Returns:
        List of joint indices in depth-first order
    """
    joint_order = []

    def traverse(joint_idx: int):
        joint_order.append(joint_idx)
        children = [i for i, parent in enumerate(parent_indices) if parent == joint_idx]
        for child_idx in children:
            traverse(child_idx)

    traverse(0)  # Start from root
    return joint_order


def compute_bone_direction(
    parent_pos: np.ndarray,
    joint_pos: np.ndarray,
    child_pos: np.ndarray
) -> np.ndarray:
    """
    Compute normalized bone direction from joint to child.

    Args:
        parent_pos: Parent joint position [3]
        joint_pos: Current joint position [3]
        child_pos: Child joint position [3]

    Returns:
        Normalized direction vector [3]
    """
    direction = child_pos - joint_pos
    norm = np.linalg.norm(direction)
    if norm < 1e-8:
        return np.array([0.0, 1.0, 0.0])  # Default up direction
    return direction / norm


def rotation_matrix_from_vectors(vec_from: np.ndarray, vec_to: np.ndarray) -> np.ndarray:
    """
    Compute rotation matrix that rotates vec_from to vec_to.
    Uses Rodrigues' rotation formula.

    Args:
        vec_from: Source direction vector (normalized)
        vec_to: Target direction vector (normalized)

    Returns:
        3x3 rotation matrix
    """
    # Normalize inputs
    vec_from = vec_from / (np.linalg.norm(vec_from) + 1e-8)
    vec_to = vec_to / (np.linalg.norm(vec_to) + 1e-8)

    # Compute rotation axis and angle
    cross = np.cross(vec_from, vec_to)
    dot = np.dot(vec_from, vec_to)

    # Handle parallel vectors
    if np.linalg.norm(cross) < 1e-8:
        if dot > 0:
            return np.eye(3)  # Same direction
        else:
            # Opposite direction - rotate 180 degrees around any perpendicular axis
            perp = np.array([1, 0, 0]) if abs(vec_from[0]) < 0.9 else np.array([0, 1, 0])
            axis = np.cross(vec_from, perp)
            axis = axis / np.linalg.norm(axis)
            return -np.eye(3) + 2 * np.outer(axis, axis)

    # Rodrigues' formula
    axis = cross / np.linalg.norm(cross)
    angle = np.arccos(np.clip(dot, -1, 1))

    K = np.array([
        [0, -axis[2], axis[1]],
        [axis[2], 0, -axis[0]],
        [-axis[1], axis[0], 0]
    ])

    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
    return R


def extract_bvh_positions_from_mhr(
    mhr_keypoints: np.ndarray,
    include_hands: bool = True
) -> np.ndarray:
    """
    Extract BVH joint positions from MHR 70-keypoint data.
    Interpolates positions for joints not directly mapped to keypoints.

    Args:
        mhr_keypoints: [70, 3] MHR keypoint positions
        include_hands: Whether to include hand joints

    Returns:
        [num_joints, 3] BVH joint positions
    """
    num_joints = len(MHR_BVH_JOINT_NAMES) if include_hands else len(MHR_BVH_BODY_JOINT_NAMES)
    positions = np.zeros((num_joints, 3))

    # Compute pelvis as midpoint of hips
    left_hip = mhr_keypoints[MHRKeypoints.LEFT_HIP]
    right_hip = mhr_keypoints[MHRKeypoints.RIGHT_HIP]
    pelvis = (left_hip + right_hip) / 2
    positions[0] = pelvis

    # Compute spine interpolation
    neck = mhr_keypoints[MHRKeypoints.NECK]
    spine_dir = neck - pelvis
    positions[1] = pelvis + spine_dir * 0.25  # Spine
    positions[2] = pelvis + spine_dir * 0.5   # Spine1
    positions[3] = pelvis + spine_dir * 0.75  # Spine2

    # Direct mappings for body joints
    for bvh_idx in range(4, num_joints):
        mhr_idx = MHR_TO_BVH_KEYPOINT_MAP.get(bvh_idx)
        if mhr_idx is not None and mhr_idx < len(mhr_keypoints):
            positions[bvh_idx] = mhr_keypoints[mhr_idx]

    return positions
