"""
BVHtoFBX Node - Retarget BVH motion to rigged FBX/VRM characters using Blender
"""

from pathlib import Path
from typing import Dict, Tuple
import subprocess
import tempfile
import shutil
import os

from hmr4d.utils.pylogger import Log


class BVHtoFBX:
    """
    Retarget BVH motion data to a rigged FBX/VRM character using Blender's BVH Retargeter addon.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bvh_data": ("BVH_DATA",),
                "character_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "output_path": ("STRING", {
                    "default": "output/retargeted.fbx",
                    "multiline": False,
                }),
            },
            "optional": {
                "character_type": (["auto", "vrm", "fbx"],),
                "output_format": (["fbx", "vrm"],),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("output_path", "info")
    FUNCTION = "retarget"
    OUTPUT_NODE = True
    CATEGORY = "MotionCapture/BVH"

    def retarget(
        self,
        bvh_data: Dict,
        character_path: str,
        output_path: str,
        character_type: str = "auto",
        output_format: str = "fbx",
    ) -> Tuple[str, str]:
        try:
            Log.info("[BVHtoFBX] Starting BVH retargeting...")

            # Validate inputs
            if not character_path:
                raise ValueError("Character path is empty. Please select a VRM or FBX file.")
                
            character_path = Path(character_path)
            if not character_path.exists():
                raise FileNotFoundError(f"Character file not found: {character_path}")

            bvh_file = bvh_data.get("file_path", "")
            if not bvh_file or not Path(bvh_file).exists():
                raise FileNotFoundError(f"BVH file not found: {bvh_file}")

            # Auto-detect character type
            if character_type == "auto":
                if character_path.suffix.lower() == ".vrm":
                    character_type = "vrm"
                else:
                    character_type = "fbx"

            Log.info(f"[BVHtoFBX] Character type: {character_type}")

            # Get Blender executable
            blender_exe = self._find_blender()
            if not blender_exe:
                raise RuntimeError(
                    "Blender not found. Please install Blender and ensure it's in your PATH."
                )

            Log.info(f"[BVHtoFBX] Using Blender: {blender_exe}")

            # Prepare output directory
            output_path = Path(output_path)
            
            # Security/Convention: If relative path doesn't start with output/, force it to output/
            if not output_path.is_absolute() and not str(output_path).startswith("output/") and not str(output_path).startswith("temp/"):
                output_path = Path("output") / output_path
            
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Ensure output has correct extension
            if output_format == "vrm" and output_path.suffix.lower() != ".vrm":
                output_path = output_path.with_suffix(".vrm")
            elif output_format == "fbx" and output_path.suffix.lower() != ".fbx":
                output_path = output_path.with_suffix(".fbx")

            # Create Blender retargeting script
            blender_script = self._create_blender_script(
                character_input=str(character_path.absolute()),
                bvh_input=str(Path(bvh_file).absolute()),
                output_file=str(output_path.absolute()),
                character_type=character_type,
                output_format=output_format,
            )

            # Write script to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                script_path = Path(f.name)
                f.write(blender_script)

            Log.info(f"[BVHtoFBX] Created Blender script: {script_path}")

            try:
                # Run Blender in background mode
                cmd = [
                    str(blender_exe),
                    "--background",
                    "--python", str(script_path),
                ]

                Log.info(f"[BVHtoFBX] Running Blender command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )

                if result.returncode != 0:
                    error_details = f"Blender Error (Code {result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                    Log.error(f"[BVHtoFBX] {error_details}")
                    raise RuntimeError(error_details)

                Log.info(f"[BVHtoFBX] Blender output:\n{result.stdout}")

            finally:
                # Clean up temporary script
                script_path.unlink(missing_ok=True)

            if not output_path.exists():
                raise RuntimeError(f"Output file not created at: {output_path}\nCheck Blender logs above.")

            # Create info string
            num_frames = bvh_data.get("num_frames", 0)
            fps = bvh_data.get("fps", 30)

            info = (
                f"BVH Retargeting Complete\n"
                f"Character: {character_path.name}\n"
                f"BVH: {Path(bvh_file).name}\n"
                f"Output: {output_path.name}\n"
                f"Frames: {num_frames}\n"
                f"FPS: {fps}\n"
                f"Format: {output_format.upper()}\n"
            )

            Log.info("[BVHtoFBX] Retargeting complete!")
            return (str(output_path.absolute()), info)

        except Exception as e:
            error_msg = f"BVHtoFBX Failed:\n{str(e)}"
            Log.error(error_msg)
            return ("", error_msg)

    def _find_blender(self) -> Path:
        """Find Blender executable."""
        local_blender = Path(__file__).parent.parent / "lib" / "blender"

        if local_blender.exists():
            import platform
            system = platform.system().lower()
            if system == "windows":
                pattern = "**/blender.exe"
            elif system == "darwin":
                pattern = "**/MacOS/blender"
            else:
                pattern = "**/blender"

            executables = list(local_blender.glob(pattern))
            if executables:
                return executables[0]

        import shutil as sh
        system_blender = sh.which("blender")
        if system_blender:
            return Path(system_blender)

        return None

    def _create_blender_script(
        self,
        character_input: str,
        bvh_input: str,
        output_file: str,
        character_type: str,
        output_format: str,
    ) -> str:
        """
        Create Blender Python script for BVH retargeting.
        Includes built-in SMPL to VRM bone mapping.
        """
        # No manual backslash replacement needed if we trust Path.absolute() and python string handling
        # character_input = character_input.replace("\", "/") 

        # Bone Mapping: SMPL (Source) -> VRM/Mixamo (Target)
        bone_map = {
            'Pelvis': 'Hips',
            'L_Hip': 'LeftUpperLeg',
            'R_Hip': 'RightUpperLeg',
            'Spine1': 'Spine',
            'L_Knee': 'LeftLowerLeg',
            'R_Knee': 'RightLowerLeg',
            'Spine2': 'Chest',
            'L_Ankle': 'LeftFoot',
            'R_Ankle': 'RightFoot',
            'Spine3': 'UpperChest',
            'L_Foot': 'LeftToes',
            'R_Foot': 'RightToes',
            'Neck': 'Neck',
            'L_Collar': 'LeftShoulder',
            'R_Collar': 'RightShoulder',
            'Head': 'Head',
            'L_Shoulder': 'LeftUpperArm',
            'R_Shoulder': 'RightUpperArm',
            'L_Elbow': 'LeftLowerArm',
            'R_Elbow': 'RightLowerArm',
            'L_Wrist': 'LeftHand',
            'R_Wrist': 'RightHand',
            'L_Hand': 'LeftHand', 
            'R_Hand': 'RightHand'
        }

        # Use a raw string for the template to minimize escape issues
        script_template = r'''
import bpy
import sys
import traceback

print("[BVHtoFBX] Starting Blender retargeting script")

# Bone Mapping Dictionary - Will be replaced by Python
BONE_MAP = REPLACE_BONE_MAP

try:
    # Clear scene
    bpy.ops.wm.read_homefile(use_empty=True)
    print("[BVHtoFBX] Cleared scene")

    # Import character
    character_path = "REPLACE_CHARACTER_INPUT"
    character_type = "REPLACE_CHARACTER_TYPE"

    if character_type == "vrm":
        print("[BVHtoFBX] Importing VRM character...")
        try:
            bpy.ops.import_scene.vrm(filepath=character_path)
            print("[BVHtoFBX] VRM import successful")
        except AttributeError:
            try:
                bpy.ops.import_model.vrm(filepath=character_path)
                print("[BVHtoFBX] VRM import successful (legacy command)")
            except:
                print("[BVHtoFBX] ERROR: VRM addon not found. Please install VRM Addon for Blender.")
                sys.exit(1)
    else:
        print("[BVHtoFBX] Importing FBX character...")
        bpy.ops.import_scene.fbx(filepath=character_path)
        print("[BVHtoFBX] FBX import successful")

    # Find character armature
    char_armature = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            char_armature = obj
            break

    if not char_armature:
        print("[BVHtoFBX] ERROR: No armature found in character file")
        sys.exit(1)

    print(f"[BVHtoFBX] Found character armature: {char_armature.name}")
    # Print character bone names for debugging
    print(f"[BVHtoFBX] Character Armature Bones: {[b.name for b in char_armature.data.bones]}")

    # Ensure we are in Object Mode
    if bpy.context.object:
        bpy.ops.object.mode_set(mode='OBJECT')

    # Load BVH (Source Motion)
    bvh_path = "REPLACE_BVH_INPUT"
    print(f"[BVHtoFBX] Loading BVH animation: {bvh_path}")
    bpy.ops.import_anim.bvh(filepath=bvh_path)
    
    # Find BVH armature
    bvh_armature = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj != char_armature:
            bvh_armature = obj
            break

    if not bvh_armature:
        print("[BVHtoFBX] ERROR: BVH armature not found after import")
        sys.exit(1)

    print(f"[BVHtoFBX] Found BVH armature: {bvh_armature.name}")
    print(f"[BVHtoFBX] BVH Armature Bones: {[b.name for b in bvh_armature.data.bones]}")

    # --- RETARGETING LOGIC ---
    print("[BVHtoFBX] Starting retargeting...")
    
    bpy.context.view_layer.objects.active = char_armature
    bpy.ops.object.mode_set(mode='POSE')

    # Auto-detect bone naming convention (Standard VRM vs VRoid FBX)
    bone_names = char_armature.pose.bones.keys()
    is_vroid = any("J_Bip_C_Hips" in b for b in bone_names)
    
    if is_vroid:
        print("[BVHtoFBX] Detected VRoid bone naming convention (J_Bip_...)")
        vroid_map = {
            'Hips': 'J_Bip_C_Hips',
            'Spine': 'J_Bip_C_Spine',
            'Chest': 'J_Bip_C_Chest',
            'UpperChest': 'J_Bip_C_UpperChest',
            'Neck': 'J_Bip_C_Neck',
            'Head': 'J_Bip_C_Head',
            'LeftShoulder': 'J_Bip_L_Shoulder',
            'LeftUpperArm': 'J_Bip_L_UpperArm',
            'LeftLowerArm': 'J_Bip_L_LowerArm',
            'LeftHand': 'J_Bip_L_Hand',
            'RightShoulder': 'J_Bip_R_Shoulder',
            'RightUpperArm': 'J_Bip_R_UpperArm',
            'RightLowerArm': 'J_Bip_R_LowerArm',
            'RightHand': 'J_Bip_R_Hand',
            'LeftUpperLeg': 'J_Bip_L_UpperLeg',
            'LeftLowerLeg': 'J_Bip_L_LowerLeg',
            'LeftFoot': 'J_Bip_L_Foot',
            'LeftToes': 'J_Bip_L_ToeBase',
            'RightUpperLeg': 'J_Bip_R_UpperLeg',
            'RightLowerLeg': 'J_Bip_R_LowerLeg',
            'RightFoot': 'J_Bip_R_Foot',
            'RightToes': 'J_Bip_R_ToeBase',
        }
        # Update BONE_MAP with VRoid names if present
        new_map = {}
        for smpl, vrm in BONE_MAP.items():
            if vrm in vroid_map:
                new_map[smpl] = vroid_map[vrm]
            else:
                new_map[smpl] = vrm 
        BONE_MAP = new_map
    
    # Apply constraints
    constraints_applied = 0
    for smpl_bone, vrm_bone in BONE_MAP.items():
        if vrm_bone not in char_armature.pose.bones:
            print(f"[BVHtoFBX] WARNING: Target bone '{vrm_bone}' not found. Skipping.")
            continue
            
        if smpl_bone not in bvh_armature.data.bones:
            print(f"[BVHtoFBX] WARNING: Source bone '{smpl_bone}' not found. Skipping.")
            continue
            
        p_bone = char_armature.pose.bones[vrm_bone]
        
        const = p_bone.constraints.new('COPY_ROTATION')
        const.target = bvh_armature
        const.subtarget = smpl_bone
        const.mix_mode = 'REPLACE'
        const.owner_space = 'WORLD'
        const.target_space = 'WORLD'
        print(f"[BVHtoFBX] Applied COPY_ROTATION: '{smpl_bone}' -> '{vrm_bone}'")
        constraints_applied += 1
        
        if smpl_bone == 'Pelvis':
            const_loc = p_bone.constraints.new('COPY_LOCATION')
            const_loc.target = bvh_armature
            const_loc.subtarget = smpl_bone
            const_loc.owner_space = 'WORLD'
            const_loc.target_space = 'WORLD'
            print(f"[BVHtoFBX] Applied COPY_LOCATION: '{smpl_bone}' -> '{vrm_bone}'")
            constraints_applied += 1
            
    print(f"[BVHtoFBX] Total constraints applied: {constraints_applied}")
    
    if constraints_applied == 0:
        print("[BVHtoFBX] ERROR: No constraints were applied.")
        sys.exit(1)

    # Bake
    print("[BVHtoFBX] Baking animation...")
    action = bvh_armature.animation_data.action
    frame_start = int(action.frame_range[0])
    frame_end = int(action.frame_range[1])
    
    bpy.ops.nla.bake(
        frame_start=frame_start,
        frame_end=frame_end,
        only_selected=True,
        visual_keying=True,
        clear_constraints=True,
        use_current_action=True,
        bake_types={'POSE'}
    )
    print("[BVHtoFBX] Baking complete")
    
    # Delete BVH armature
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(bvh_armature, do_unlink=True)

    # Export
    output_path = "REPLACE_OUTPUT_FILE"
    output_format = "REPLACE_OUTPUT_FORMAT"

    bpy.ops.object.select_all(action='DESELECT')
    char_armature.select_set(True)
    for child in char_armature.children:
        if child.type == 'MESH':
            child.select_set(True)

    if output_format == "vrm":
        print("[BVHtoFBX] Exporting as VRM...")
        try:
            bpy.ops.export_scene.vrm(filepath=output_path, export_fbx_hdr_emb=False) 
            print("[BVHtoFBX] VRM export successful")
        except AttributeError:
            print("[BVHtoFBX] ERROR: VRM export failed. Falling back to FBX.")
            output_path = output_path.replace(".vrm", ".fbx")
            bpy.ops.export_scene.fbx(filepath=output_path, use_selection=True, bake_anim=True, add_leaf_bones=False)
            print("[BVHtoFBX] FBX export successful (fallback)")
    else:
        print("[BVHtoFBX] Exporting as FBX...")
        bpy.ops.export_scene.fbx(
            filepath=output_path,
            use_selection=True,
            bake_anim=True,
            add_leaf_bones=False
        )

    print(f"[BVHtoFBX] Output saved to: {output_path}")
    print("[BVHtoFBX] Retargeting complete!")

except Exception as e:
    print(f"[BVHtoFBX] ERROR: {str(e)}")
    traceback.print_exc()
    sys.exit(1)
'''
        
        # Inject variables into script using simple replace to avoid f-string syntax errors
        script = script_template.replace("REPLACE_BONE_MAP", str(bone_map))
        script = script.replace("REPLACE_CHARACTER_INPUT", character_input)
        script = script.replace("REPLACE_CHARACTER_TYPE", character_type)
        script = script.replace("REPLACE_BVH_INPUT", bvh_input)
        script = script.replace("REPLACE_OUTPUT_FILE", output_file)
        script = script.replace("REPLACE_OUTPUT_FORMAT", output_format)

        return script


NODE_CLASS_MAPPINGS = {
    "BVHtoFBX": BVHtoFBX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BVHtoFBX": "BVH to FBX Retargeter",
}