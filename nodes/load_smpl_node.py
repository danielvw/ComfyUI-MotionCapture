"""
LoadSMPL Node - Load SMPL motion data from disk
"""

import os
from pathlib import Path
from typing import Dict, Tuple, List
import torch
import numpy as np
import folder_paths

from hmr4d.utils.pylogger import Log


class LoadSMPL:
    """
    Load SMPL motion parameters from .npz file.
    """

    @staticmethod
    def get_npz_files_from_input() -> List[str]:
        """Get all NPZ files from input directory recursively."""
        try:
            input_dir = folder_paths.get_input_directory()
            npz_files = []

            for root, dirs, files in os.walk(input_dir):
                for file in files:
                    if file.lower().endswith('.npz'):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, input_dir)
                        npz_files.append(rel_path)

            return sorted(npz_files)
        except Exception as e:
            Log.error(f"[LoadSMPL] Error scanning input directory: {e}")
            return []

    @staticmethod
    def get_npz_files_from_output() -> List[str]:
        """Get all NPZ files from output directory recursively."""
        try:
            output_dir = folder_paths.get_output_directory()
            npz_files = []

            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file.lower().endswith('.npz'):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, output_dir)
                        npz_files.append(rel_path)

            return sorted(npz_files)
        except Exception as e:
            Log.error(f"[LoadSMPL] Error scanning output directory: {e}")
            return []

    @classmethod
    def INPUT_TYPES(cls):
        # Get files from both directories
        input_files = cls.get_npz_files_from_input()
        output_files = cls.get_npz_files_from_output()

        # Combine and prefix with folder name for clarity
        all_files = []
        if output_files:
            all_files.extend([f"output/{f}" for f in output_files])
        if input_files:
            all_files.extend([f"input/{f}" for f in input_files])

        # Fallback if no files found
        if not all_files:
            all_files = ["[No NPZ files found]"]

        return {
            "required": {
                "npz_file": (all_files,),
            },
        }

    RETURN_TYPES = ("SMPL_PARAMS", "STRING")
    RETURN_NAMES = ("smpl_params", "info")
    FUNCTION = "load_smpl"
    CATEGORY = "MotionCapture/SMPL"

    def load_smpl(
        self,
        npz_file: str,
    ) -> Tuple[Dict, str]:
        """
        Load SMPL parameters from NPZ file.

        Args:
            npz_file: File path in format "output/file.npz" or "input/file.npz"

        Returns:
            Tuple of (smpl_params, info_string)
        """
        try:
            Log.info("[LoadSMPL] Loading SMPL motion data...")

            # Check for placeholder
            if npz_file == "[No NPZ files found]":
                raise ValueError("No NPZ files found in input or output directories")

            # Parse folder from path
            if npz_file.startswith("output/"):
                base_dir = folder_paths.get_output_directory()
                npz_file = npz_file[7:]  # Remove "output/" prefix
            elif npz_file.startswith("input/"):
                base_dir = folder_paths.get_input_directory()
                npz_file = npz_file[6:]  # Remove "input/" prefix
            else:
                # Fallback to output if no prefix
                base_dir = folder_paths.get_output_directory()

            # Construct full path
            file_path = os.path.join(base_dir, npz_file)
            file_path = Path(os.path.abspath(file_path))

            # Validate input
            if not file_path.exists():
                raise FileNotFoundError(f"SMPL file not found: {file_path}")

            # Load NPZ file
            data = np.load(file_path)

            # Convert to torch tensors
            global_params = {}
            for key in data.files:
                global_params[key] = torch.from_numpy(data[key])

            # Create SMPL_PARAMS structure (matching GVHMRInference output)
            smpl_params = {
                "global": global_params,
                "incam": global_params,  # Use same for both (global coordinates)
            }

            # Get info
            num_frames = global_params.get("body_pose", torch.tensor([])).shape[0] if "body_pose" in global_params else 0
            file_size_kb = file_path.stat().st_size / 1024

            info = (
                f"LoadSMPL Complete\n"
                f"Input: {file_path}\n"
                f"Frames: {num_frames}\n"
                f"File size: {file_size_kb:.1f} KB\n"
                f"Parameters: {', '.join(global_params.keys())}\n"
            )

            Log.info(f"[LoadSMPL] Loaded {num_frames} frames from {file_path}")
            return (smpl_params, info)

        except Exception as e:
            error_msg = f"LoadSMPL failed: {str(e)}"
            Log.error(error_msg)
            import traceback
            traceback.print_exc()
            return ({}, error_msg)


NODE_CLASS_MAPPINGS = {
    "LoadSMPL": LoadSMPL,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadSMPL": "Load SMPL Motion",
}
