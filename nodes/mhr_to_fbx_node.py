"""
MHRToFBX Node - High-level node to export MHR motion data to animated FBX

This node combines MHRtoBVH and BVHtoFBX into a single convenient workflow
for exporting SAM3D motion capture data to rigged FBX characters.
"""

import sys
from pathlib import Path
from typing import Dict, Tuple
import tempfile

# Add vendor path for logging
VENDOR_PATH = Path(__file__).parent.parent / "vendor"
sys.path.insert(0, str(VENDOR_PATH))

from hmr4d.utils.pylogger import Log

from .mhr_to_bvh_node import MHRtoBVH
from .bvh_retarget_node import BVHtoFBX


class MHRToFBX:
    """
    High-level node to export MHR motion data to animated FBX.

    This node combines the MHR to BVH conversion with BVH to FBX retargeting
    in a single step. It takes MHR parameters from SAM3D Video Inference
    and produces an animated FBX file with the motion applied to a target character.

    Pipeline: MHR_PARAMS -> BVH -> Blender Retarget -> FBX
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mhr_params": ("MHR_PARAMS",),
                "character_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Path to target FBX/VRM character file"
                }),
                "output_path": ("STRING", {
                    "default": "output/mhr_animated.fbx",
                    "multiline": False,
                }),
            },
            "optional": {
                "fps": ("INT", {
                    "default": 30,
                    "min": 1,
                    "max": 120,
                    "step": 1,
                }),
                "include_hands": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Include hand/finger animation"
                }),
                "character_type": (["auto", "vrm", "fbx"], {
                    "default": "auto",
                    "tooltip": "Character file type (auto-detect recommended)"
                }),
                "output_format": (["fbx", "vrm"], {
                    "default": "fbx",
                    "tooltip": "Output file format"
                }),
                "scale": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.01,
                    "max": 100.0,
                    "step": 0.01,
                    "tooltip": "Scale factor for skeleton (1.0 = meters)"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("fbx_path", "frame_count", "info")
    FUNCTION = "export_to_fbx"
    OUTPUT_NODE = True
    CATEGORY = "MotionCapture/MHR"

    def export_to_fbx(
        self,
        mhr_params: Dict,
        character_path: str,
        output_path: str,
        fps: int = 30,
        include_hands: bool = True,
        character_type: str = "auto",
        output_format: str = "fbx",
        scale: float = 1.0,
    ) -> Tuple[str, int, str]:
        """
        Export MHR motion data to animated FBX.

        Args:
            mhr_params: MHR parameters from SAM3DVideoInference
            character_path: Path to target FBX/VRM character
            output_path: Output FBX/VRM file path
            fps: Frames per second
            include_hands: Include hand animation
            character_type: Character type (auto/vrm/fbx)
            output_format: Output format (fbx/vrm)
            scale: Scale factor for skeleton

        Returns:
            Tuple of (fbx_path, frame_count, info_string)
        """
        try:
            Log.info("[MHRToFBX] Starting MHR to FBX export pipeline...")

            # Validate inputs
            if not character_path:
                raise ValueError("Character path is empty. Please select a VRM or FBX file.")

            character_path_obj = Path(character_path)
            if not character_path_obj.exists():
                raise FileNotFoundError(f"Character file not found: {character_path}")

            # Get frame count
            num_frames = mhr_params.get("num_frames", 0)
            if num_frames == 0:
                keypoints = mhr_params.get("keypoints_3d")
                if keypoints is not None:
                    num_frames = keypoints.shape[0]

            Log.info(f"[MHRToFBX] Processing {num_frames} frames")
            Log.info(f"[MHRToFBX] Target character: {character_path_obj.name}")
            Log.info(f"[MHRToFBX] Include hands: {include_hands}")

            # Step 1: Convert MHR to BVH
            Log.info("[MHRToFBX] Step 1: Converting MHR to BVH...")

            # Create temporary BVH file
            temp_dir = tempfile.mkdtemp(prefix="mhr_to_fbx_")
            bvh_path = Path(temp_dir) / "mhr_motion.bvh"

            mhr_to_bvh = MHRtoBVH()
            bvh_data, bvh_file_path, bvh_info = mhr_to_bvh.convert_to_bvh(
                mhr_params=mhr_params,
                output_path=str(bvh_path),
                fps=fps,
                scale=scale,
                include_hands=include_hands,
            )

            if not bvh_file_path or not Path(bvh_file_path).exists():
                raise RuntimeError(f"BVH conversion failed: {bvh_info}")

            Log.info(f"[MHRToFBX] BVH created: {bvh_file_path}")

            # Step 2: Retarget BVH to FBX
            Log.info("[MHRToFBX] Step 2: Retargeting BVH to FBX character...")

            bvh_to_fbx = BVHtoFBX()
            fbx_path, retarget_info = bvh_to_fbx.retarget(
                bvh_data=bvh_data,
                character_path=character_path,
                output_path=output_path,
                character_type=character_type,
                output_format=output_format,
            )

            if not fbx_path:
                raise RuntimeError(f"FBX retargeting failed: {retarget_info}")

            Log.info(f"[MHRToFBX] FBX created: {fbx_path}")

            # Clean up temporary BVH file
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as cleanup_error:
                Log.warn(f"[MHRToFBX] Failed to clean up temp dir: {cleanup_error}")

            # Build info string
            info = (
                f"MHR to FBX Export Complete\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Input: SAM3D MHR ({num_frames} frames)\n"
                f"Character: {character_path_obj.name}\n"
                f"Output: {Path(fbx_path).name}\n"
                f"FPS: {fps}\n"
                f"Include hands: {include_hands}\n"
                f"Format: {output_format.upper()}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Pipeline: MHR → BVH → Blender → FBX\n"
            )

            Log.info("[MHRToFBX] Export complete!")
            return (fbx_path, num_frames, info)

        except Exception as e:
            error_msg = f"MHRToFBX failed: {str(e)}"
            Log.error(error_msg)
            import traceback
            traceback.print_exc()
            return ("", 0, error_msg)


NODE_CLASS_MAPPINGS = {
    "MHRToFBX": MHRToFBX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MHRToFBX": "MHR to FBX Export",
}
