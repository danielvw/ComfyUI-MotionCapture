"""
CompareSMPLtoBVH Node - Side-by-side comparison of SMPL and BVH animations

Displays SMPL mesh and BVH skeleton side-by-side with synchronized playback
and camera controls for easy comparison.
"""

import sys
from pathlib import Path
from typing import Dict, Tuple
import time
import torch
import numpy as np

from hmr4d.utils.pylogger import Log


class CompareSMPLtoBVH:
    """
    Side-by-side comparison viewer for SMPL and BVH animations.
    Synchronized playback and camera for easy comparison.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "smpl_params": ("SMPL_PARAMS",),
                "bvh_data": ("BVH_DATA",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("info",)
    FUNCTION = "compare_animations"
    OUTPUT_NODE = True
    CATEGORY = "MotionCapture/Comparison"

    def compare_animations(
        self,
        smpl_params: Dict,
        bvh_data: Dict,
    ) -> Tuple[str]:
        """
        Display SMPL and BVH animations side-by-side.

        Args:
            smpl_params: SMPL parameters from GVHMR or LoadSMPL
            bvh_data: BVH data from SMPLtoBVH

        Returns:
            Tuple of (info_string,)
        """
        try:
            Log.info("[CompareSMPLtoBVH] Loading animations for comparison...")

            # Generate SMPL mesh and save to file
            Log.info("[CompareSMPLtoBVH] Generating SMPL mesh...")

            # Import SMPL model
            VENDOR_PATH = Path(__file__).parent.parent / "vendor"
            sys.path.insert(0, str(VENDOR_PATH))
            from hmr4d.utils.body_model.smplx_lite import SmplxLite

            # Extract SMPL parameters
            params = smpl_params['global']
            body_pose = params['body_pose']  # (F, 63)
            betas = params['betas']  # (F, 10)
            global_orient = params['global_orient']  # (F, 3)
            transl = params.get('transl', None)  # (F, 3) or None

            num_frames = body_pose.shape[0]
            smpl_frames = num_frames

            # Initialize SMPL model
            smpl_model = SmplxLite(gender="neutral", num_betas=10)
            smpl_model.eval()
            device = body_pose.device
            smpl_model = smpl_model.to(device)

            # Generate mesh for each frame
            Log.info(f"[CompareSMPLtoBVH] Generating {num_frames} frames...")
            vertices_list = []
            with torch.no_grad():
                for frame_idx in range(num_frames):
                    bp = body_pose[frame_idx:frame_idx+1]
                    b = betas[frame_idx:frame_idx+1]
                    go = global_orient[frame_idx:frame_idx+1]
                    t = transl[frame_idx:frame_idx+1] if transl is not None else None

                    verts = smpl_model.forward(
                        body_pose=bp,
                        betas=b,
                        global_orient=go,
                        transl=t,
                        rotation_type="aa"
                    )
                    vertices_list.append(verts[0].cpu().numpy())

            vertices_array = np.stack(vertices_list, axis=0)  # (F, V, 3)
            faces = smpl_model.faces.astype(np.int32)  # (Nf, 3)

            # Save mesh to .npz file
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            mesh_filename = f"smpl_mesh_{timestamp}.npz"
            mesh_filepath = output_dir / mesh_filename

            np.savez_compressed(
                mesh_filepath,
                vertices=vertices_array,
                faces=faces,
                fps=30,
                num_frames=num_frames
            )

            Log.info(f"[CompareSMPLtoBVH] Saved mesh to {mesh_filepath} ({vertices_array.nbytes / 1024 / 1024:.1f} MB uncompressed)")

            # Read BVH file content
            bvh_file_path = bvh_data.get("file_path", "")
            if not bvh_file_path or not Path(bvh_file_path).exists():
                raise ValueError(f"BVH file not found: {bvh_file_path}")

            with open(bvh_file_path, 'r') as f:
                bvh_content = f.read()

            # Store data for web viewer (file paths instead of data)
            self.smpl_mesh_file = str(mesh_filepath)
            self.bvh_content = bvh_content
            self.bvh_info = {
                "num_frames": bvh_data.get("num_frames", 0),
                "fps": bvh_data.get("fps", 30),
                "file_path": bvh_file_path,
            }

            bvh_frames = bvh_data.get("num_frames", 0)

            info = (
                f"SMPL vs BVH Comparison\n"
                f"SMPL Frames: {smpl_frames}\n"
                f"BVH Frames: {bvh_frames}\n"
                f"BVH File: {Path(bvh_file_path).name}\n"
                f"Synchronized playback and camera\n"
            )

            Log.info(f"[CompareSMPLtoBVH] Ready for comparison - SMPL: {smpl_frames} frames, BVH: {bvh_frames} frames")

            # Return data in ComfyUI OUTPUT_NODE format
            # The "ui" dict is sent to the frontend JavaScript
            # Send file path instead of mesh data to avoid large JSON
            return {
                "ui": {
                    "smpl_mesh_file": [self.smpl_mesh_file],
                    "bvh_content": [self.bvh_content],
                    "bvh_info": [self.bvh_info]
                },
                "result": (info,)
            }

        except Exception as e:
            error_msg = f"CompareSMPLtoBVH failed: {str(e)}"
            Log.error(error_msg)
            import traceback
            traceback.print_exc()
            return {
                "ui": {
                    "smpl_mesh_file": [""],
                    "bvh_content": [""],
                    "bvh_info": [{}]
                },
                "result": (error_msg,)
            }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Always update when input changes
        return float("nan")


NODE_CLASS_MAPPINGS = {
    "CompareSMPLtoBVH": CompareSMPLtoBVH,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CompareSMPLtoBVH": "Compare SMPL vs BVH",
}
