"""
MHRtoBVH Node - Convert MHR 70-keypoint skeleton to BVH format

This node converts motion data from SAM3D Video Inference (MHR_PARAMS) to
BVH (Biovision Hierarchy) format for use with animation tools and retargeting.
"""

import sys
from pathlib import Path
from typing import Dict, Tuple, Optional
import torch
import numpy as np
from scipy.spatial.transform import Rotation as R

# Add lib path
LIB_PATH = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_PATH))

# Add vendor path for logging
VENDOR_PATH = Path(__file__).parent.parent / "vendor"
sys.path.insert(0, str(VENDOR_PATH))

from hmr4d.utils.pylogger import Log
from mhr_skeleton import (
    MHRKeypoints,
    MHR_BVH_JOINT_NAMES,
    MHR_BVH_PARENTS,
    MHR_BVH_OFFSETS,
    MHR_BVH_BODY_JOINT_NAMES,
    MHR_BVH_BODY_PARENTS,
    MHR_TO_BVH_KEYPOINT_MAP,
    get_bvh_joint_order,
    extract_bvh_positions_from_mhr,
    rotation_matrix_from_vectors,
)


class MHRtoBVH:
    """
    Convert MHR motion parameters (70 keypoints) to BVH file format.

    This node performs inverse kinematics to convert position-based keypoints
    to rotation-based skeleton animation suitable for BVH export.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mhr_params": ("MHR_PARAMS",),
                "output_path": ("STRING", {
                    "default": "output/mhr_motion.bvh",
                    "multiline": False,
                }),
                "fps": ("INT", {
                    "default": 30,
                    "min": 1,
                    "max": 120,
                    "step": 1,
                }),
                "scale": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.01,
                    "max": 100.0,
                    "step": 0.01,
                    "round": 0.01,
                }),
            },
            "optional": {
                "include_hands": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Include hand/finger joints in BVH output"
                }),
            }
        }

    RETURN_TYPES = ("BVH_DATA", "STRING", "STRING")
    RETURN_NAMES = ("bvh_data", "file_path", "info")
    FUNCTION = "convert_to_bvh"
    OUTPUT_NODE = True
    CATEGORY = "MotionCapture/MHR"

    def convert_to_bvh(
        self,
        mhr_params: Dict,
        output_path: str,
        fps: int = 30,
        scale: float = 1.0,
        include_hands: bool = True,
    ) -> Tuple[Dict, str, str]:
        """
        Convert MHR parameters to BVH file format.

        Args:
            mhr_params: MHR parameters from SAM3DVideoInference
            output_path: Path to save BVH file
            fps: Frames per second for the animation
            scale: Scale factor for the skeleton
            include_hands: Whether to include hand joints

        Returns:
            Tuple of (bvh_data_dict, file_path, info_string)
        """
        try:
            Log.info("[MHRtoBVH] Converting MHR to BVH format...")

            # Prepare output directory
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Ensure .bvh extension
            if not output_path.suffix == '.bvh':
                output_path = output_path.with_suffix('.bvh')

            # Extract keypoints from MHR params
            keypoints_3d = mhr_params.get("keypoints_3d")
            if keypoints_3d is None:
                raise ValueError("Missing keypoints_3d in MHR params")

            # Convert to numpy
            if isinstance(keypoints_3d, torch.Tensor):
                keypoints_3d = keypoints_3d.cpu().numpy()

            num_frames = keypoints_3d.shape[0]
            Log.info(f"[MHRtoBVH] Processing {num_frames} frames with {keypoints_3d.shape[1]} keypoints")

            # Select skeleton configuration
            if include_hands:
                joint_names = MHR_BVH_JOINT_NAMES
                parent_indices = MHR_BVH_PARENTS
                Log.info(f"[MHRtoBVH] Using full skeleton with hands ({len(joint_names)} joints)")
            else:
                joint_names = MHR_BVH_BODY_JOINT_NAMES
                parent_indices = MHR_BVH_BODY_PARENTS
                Log.info(f"[MHRtoBVH] Using body-only skeleton ({len(joint_names)} joints)")

            num_joints = len(joint_names)
            frame_time = 1.0 / fps

            # Compute rotations via inverse kinematics
            Log.info("[MHRtoBVH] Computing joint rotations via IK...")
            euler_rotations, translations = self._compute_rotations(
                keypoints_3d, joint_names, parent_indices, include_hands
            )

            # Log rotation statistics
            rot_mins = np.min(euler_rotations, axis=(0, 1))
            rot_maxs = np.max(euler_rotations, axis=(0, 1))
            Log.info(f"[MHRtoBVH] Rotation ranges (degrees):")
            Log.info(f"  Z: [{rot_mins[0]:.1f}, {rot_maxs[0]:.1f}]")
            Log.info(f"  X: [{rot_mins[1]:.1f}, {rot_maxs[1]:.1f}]")
            Log.info(f"  Y: [{rot_mins[2]:.1f}, {rot_maxs[2]:.1f}]")

            # Write BVH file
            bvh_content = self._write_bvh(
                euler_rotations,
                translations,
                frame_time,
                scale,
                joint_names,
                parent_indices
            )

            # Save to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(bvh_content)

            # Prepare BVH data structure for next nodes
            bvh_data = {
                "file_path": str(output_path.absolute()),
                "num_frames": num_frames,
                "fps": fps,
                "frame_time": frame_time,
                "scale": scale,
                "rotations": euler_rotations,
                "translations": translations,
                "joint_names": joint_names,
                "num_joints": num_joints,
            }

            info = (
                f"MHRtoBVH Complete\n"
                f"Output: {output_path}\n"
                f"Frames: {num_frames}\n"
                f"FPS: {fps}\n"
                f"Frame time: {frame_time:.4f}s\n"
                f"Scale: {scale}x\n"
                f"Joints: {num_joints}\n"
                f"Include hands: {include_hands}\n"
            )

            Log.info(f"[MHRtoBVH] Converted {num_frames} frames to {output_path}")
            return (bvh_data, str(output_path.absolute()), info)

        except Exception as e:
            error_msg = f"MHRtoBVH failed: {str(e)}"
            Log.error(error_msg)
            import traceback
            traceback.print_exc()
            return ({}, "", error_msg)

    def _compute_rotations(
        self,
        keypoints_3d: np.ndarray,
        joint_names: list,
        parent_indices: list,
        include_hands: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute joint rotations from MHR keypoint positions using inverse kinematics.

        Args:
            keypoints_3d: [F, 70, 3] MHR keypoint positions
            joint_names: List of BVH joint names
            parent_indices: List of parent indices for hierarchy
            include_hands: Whether to include hand joints

        Returns:
            Tuple of (euler_rotations [F, J, 3], translations [F, 3])
        """
        num_frames = keypoints_3d.shape[0]
        num_joints = len(joint_names)

        euler_rotations = np.zeros((num_frames, num_joints, 3))
        translations = np.zeros((num_frames, 3))

        # Rest pose directions (T-pose, Y-up)
        rest_directions = self._compute_rest_directions(joint_names, parent_indices)

        for frame in range(num_frames):
            kp = keypoints_3d[frame]  # [70, 3]

            # Extract BVH joint positions from MHR keypoints
            bvh_positions = extract_bvh_positions_from_mhr(kp, include_hands)

            # Compute root translation (pelvis position)
            translations[frame] = bvh_positions[0]

            # Compute rotations for each joint
            accumulated_rotations = {}

            for joint_idx in range(num_joints):
                parent_idx = parent_indices[joint_idx]

                if parent_idx == -1:
                    # Root joint - compute global rotation from hip/shoulder orientation
                    rot_mat = self._compute_root_rotation(kp)
                    accumulated_rotations[joint_idx] = rot_mat
                else:
                    # Get parent's accumulated rotation
                    parent_rot = accumulated_rotations.get(parent_idx, np.eye(3))

                    # Find children of this joint
                    children = [i for i, p in enumerate(parent_indices) if p == joint_idx]

                    if children:
                        # Compute rotation to align with child
                        child_idx = children[0]  # Use first child for direction
                        child_pos = bvh_positions[child_idx]
                        joint_pos = bvh_positions[joint_idx]

                        # Current bone direction
                        current_dir = child_pos - joint_pos
                        current_length = np.linalg.norm(current_dir)

                        if current_length > 1e-6:
                            current_dir = current_dir / current_length

                            # Transform rest direction by parent rotation
                            rest_dir = rest_directions.get(joint_idx, np.array([0, 1, 0]))
                            transformed_rest = parent_rot @ rest_dir

                            # Compute local rotation
                            local_rot = rotation_matrix_from_vectors(transformed_rest, current_dir)

                            # Accumulate rotation
                            accumulated_rotations[joint_idx] = local_rot @ parent_rot
                        else:
                            accumulated_rotations[joint_idx] = parent_rot
                    else:
                        # Leaf joint - use parent rotation
                        accumulated_rotations[joint_idx] = parent_rot

                # Convert accumulated rotation to local rotation
                if parent_idx == -1:
                    local_rot = accumulated_rotations[joint_idx]
                else:
                    parent_rot = accumulated_rotations.get(parent_idx, np.eye(3))
                    global_rot = accumulated_rotations[joint_idx]
                    local_rot = parent_rot.T @ global_rot

                # Convert to Euler angles (ZXY order for BVH)
                try:
                    rot = R.from_matrix(local_rot)
                    euler_angles = rot.as_euler('ZXY', degrees=True)
                    euler_rotations[frame, joint_idx] = euler_angles
                except Exception:
                    # Fallback to identity
                    euler_rotations[frame, joint_idx] = [0, 0, 0]

        return euler_rotations, translations

    def _compute_root_rotation(self, keypoints: np.ndarray) -> np.ndarray:
        """
        Compute pelvis/root rotation from hip and shoulder positions.

        Args:
            keypoints: [70, 3] MHR keypoint positions

        Returns:
            3x3 rotation matrix
        """
        # Get key positions
        left_hip = keypoints[MHRKeypoints.LEFT_HIP]
        right_hip = keypoints[MHRKeypoints.RIGHT_HIP]
        left_shoulder = keypoints[MHRKeypoints.LEFT_SHOULDER]
        right_shoulder = keypoints[MHRKeypoints.RIGHT_SHOULDER]

        # Compute body axes
        hip_center = (left_hip + right_hip) / 2
        shoulder_center = (left_shoulder + right_shoulder) / 2

        # Up direction (spine)
        up = shoulder_center - hip_center
        up_norm = np.linalg.norm(up)
        if up_norm < 1e-6:
            up = np.array([0, 1, 0])
        else:
            up = up / up_norm

        # Right direction (hip axis)
        right = right_hip - left_hip
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-6:
            right = np.array([1, 0, 0])
        else:
            right = right / right_norm

        # Forward direction (cross product)
        forward = np.cross(right, up)
        forward_norm = np.linalg.norm(forward)
        if forward_norm < 1e-6:
            forward = np.array([0, 0, 1])
        else:
            forward = forward / forward_norm

        # Recompute right to ensure orthogonality
        right = np.cross(up, forward)

        # Build rotation matrix (columns are axes)
        rotation_matrix = np.column_stack([right, up, forward])

        return rotation_matrix

    def _compute_rest_directions(
        self,
        joint_names: list,
        parent_indices: list
    ) -> Dict[int, np.ndarray]:
        """
        Compute rest pose bone directions for each joint.

        Args:
            joint_names: List of joint names
            parent_indices: List of parent indices

        Returns:
            Dict mapping joint index to rest direction
        """
        directions = {}

        for joint_idx, joint_name in enumerate(joint_names):
            # Find children
            children = [i for i, p in enumerate(parent_indices) if p == joint_idx]

            if children:
                # Use first child's offset as direction
                child_idx = children[0]
                child_offset = np.array(MHR_BVH_OFFSETS.get(child_idx, [0, 1, 0]))
                offset_norm = np.linalg.norm(child_offset)
                if offset_norm > 1e-6:
                    directions[joint_idx] = child_offset / offset_norm
                else:
                    directions[joint_idx] = np.array([0, 1, 0])
            else:
                # Leaf joint - use default up
                directions[joint_idx] = np.array([0, 1, 0])

        return directions

    def _write_bvh(
        self,
        rotations: np.ndarray,
        translations: np.ndarray,
        frame_time: float,
        scale: float,
        joint_names: list,
        parent_indices: list
    ) -> str:
        """
        Write BVH file content.

        Args:
            rotations: [F, J, 3] Euler angles in degrees
            translations: [F, 3] root translations
            frame_time: Time per frame in seconds
            scale: Scale factor for skeleton
            joint_names: List of joint names
            parent_indices: List of parent indices

        Returns:
            BVH file content as string
        """
        num_frames = rotations.shape[0]

        # Store for recursive writing
        self._joint_names = joint_names
        self._parent_indices = parent_indices

        # Get depth-first traversal order
        joint_order = get_bvh_joint_order(parent_indices)

        # Build hierarchy section
        lines = ["HIERARCHY"]
        self._write_joint(lines, 0, 0, scale)

        # Write motion section
        lines.append("MOTION")
        lines.append(f"Frames: {num_frames}")
        lines.append(f"Frame Time: {frame_time:.6f}")

        # Write frame data
        for frame in range(num_frames):
            frame_data = []

            for joint_idx in joint_order:
                if joint_idx == 0:
                    # Root: translation + rotation
                    tx, ty, tz = translations[frame] * scale
                    frame_data.extend([f"{tx:.6f}", f"{ty:.6f}", f"{tz:.6f}"])
                    rz, rx, ry = rotations[frame, joint_idx]
                    frame_data.extend([f"{rz:.6f}", f"{rx:.6f}", f"{ry:.6f}"])
                else:
                    # Other joints: rotation only
                    rz, rx, ry = rotations[frame, joint_idx]
                    frame_data.extend([f"{rz:.6f}", f"{rx:.6f}", f"{ry:.6f}"])

            lines.append(" ".join(frame_data))

        return "\n".join(lines)

    def _write_joint(self, lines: list, joint_idx: int, indent_level: int, scale: float):
        """
        Recursively write joint hierarchy in BVH format.

        Args:
            lines: List to append BVH lines to
            joint_idx: Current joint index
            indent_level: Indentation level
            scale: Scale factor for offsets
        """
        indent = "  " * indent_level
        joint_name = self._joint_names[joint_idx]
        offset = MHR_BVH_OFFSETS.get(joint_idx, [0.0, 0.0, 0.0])
        offset_scaled = [o * scale for o in offset]

        # Joint header
        if joint_idx == 0:
            lines.append(f"{indent}ROOT {joint_name}")
        else:
            lines.append(f"{indent}JOINT {joint_name}")

        lines.append(f"{indent}{{")
        lines.append(f"{indent}  OFFSET {offset_scaled[0]:.6f} {offset_scaled[1]:.6f} {offset_scaled[2]:.6f}")

        # Channels
        if joint_idx == 0:
            lines.append(f"{indent}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation")
        else:
            lines.append(f"{indent}  CHANNELS 3 Zrotation Xrotation Yrotation")

        # Find and write children
        children = [i for i, p in enumerate(self._parent_indices) if p == joint_idx]

        if children:
            for child_idx in children:
                self._write_joint(lines, child_idx, indent_level + 1, scale)
        else:
            # End site for leaf joints
            lines.append(f"{indent}  End Site")
            lines.append(f"{indent}  {{")
            lines.append(f"{indent}    OFFSET 0.0 0.0 0.0")
            lines.append(f"{indent}  }}")

        lines.append(f"{indent}}}")


NODE_CLASS_MAPPINGS = {
    "MHRtoBVH": MHRtoBVH,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MHRtoBVH": "MHR to BVH Converter",
}
