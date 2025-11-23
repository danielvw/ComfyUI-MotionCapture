"""
Blender Addon Installer - Automate installation of VRM and BVH Retargeter addons
Robustly installs addons by extracting them directly to the Blender addons directory.
"""

import sys
import os
from pathlib import Path
import urllib.request
import zipfile
import shutil
import platform

# Standard print logging
def log_info(msg): print(f"[INFO] {msg}")
def log_error(msg): print(f"[ERROR] {msg}")

# Addon download URLs
VRM_ADDON_URL = "https://github.com/saturday06/VRM-Addon-for-Blender/releases/download/2_20_88/VRM_Addon_for_Blender-2_20_88.zip"
BVH_RETARGETER_URL = "https://github.com/Diffeomorphic/retarget-bvh/archive/refs/heads/master.zip"

def get_local_blender_path():
    """Find the local portable Blender installation."""
    # This script is in lib/blender_addon_installer.py
    # Blender is in lib/blender/...
    base_dir = Path(__file__).parent.absolute()
    blender_dir = base_dir / "blender"
    
    if not blender_dir.exists():
        return None
        
    # Find the executable
    system = platform.system().lower()
    pattern = "**/blender"
    if system == "windows":
        pattern = "**/blender.exe"
    elif system == "darwin":
        pattern = "**/MacOS/blender"
        
    executables = list(blender_dir.glob(pattern))
    if executables:
        return executables[0]
        
    return None

def get_addons_dir(blender_executable):
    """
    Get the addons directory relative to the Blender executable.
    For portable Blender 4.2: ./4.2/scripts/addons/
    """
    blender_root = blender_executable.parent
    
    # Look for version number folder (e.g., 4.2)
    # It might be directly in root or one level up depending on OS
    # Linux: blender-4.2.3-linux-x64/4.2/scripts/addons
    
    # Search for 'scripts/addons'
    addons_candidates = list(blender_root.glob("**/scripts/addons"))
    
    if addons_candidates:
        return addons_candidates[0]
        
    # Fallback: Look for version folder
    for item in blender_root.iterdir():
        if item.is_dir() and item.name[0].isdigit() and (item / "scripts" / "addons").exists():
            return item / "scripts" / "addons"
            
    return None

def download_file(url, dest_path):
    log_info(f"Downloading from {url}")
    urllib.request.urlretrieve(url, dest_path)
    log_info(f"Downloaded to {dest_path}")

def install_addon_by_unzip(url, addon_name, addons_dir):
    """Download and unzip an addon directly to the addons directory."""
    temp_zip = addons_dir / f"temp_{addon_name}.zip"
    
    try:
        download_file(url, temp_zip)
        
        log_info(f"Extracting {addon_name} to {addons_dir}...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(addons_dir)
            
        log_info(f"{addon_name} installed successfully.")
        return True
    except Exception as e:
        log_error(f"Failed to install {addon_name}: {e}")
        return False
    finally:
        if temp_zip.exists():
            temp_zip.unlink()

def install_all_addons():
    log_info("Starting Blender Addon Installation...")
    
    # 1. Find Blender
    blender_exe = get_local_blender_path()
    if not blender_exe:
        log_error("Local Blender installation not found in lib/blender/")
        log_error("Please run: python install.py --install-blender first.")
        return False
        
    log_info(f"Found Blender: {blender_exe}")
    
    # 2. Find Addons Dir
    addons_dir = get_addons_dir(blender_exe)
    if not addons_dir:
        log_error("Could not locate 'scripts/addons' directory in Blender installation.")
        return False
        
    log_info(f"Target Addons Directory: {addons_dir}")
    addons_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Install VRM Addon
    # Check if already exists (heuristic: check for folder name)
    vrm_installed = False
    for item in addons_dir.iterdir():
        if item.is_dir() and "VRM_Addon" in item.name:
            vrm_installed = True
            log_info(f"VRM Addon appears to be installed at: {item.name}")
            break
            
    if not vrm_installed:
        if not install_addon_by_unzip(VRM_ADDON_URL, "VRM_Addon", addons_dir):
            return False
            
    # 4. Install BVH Retargeter (Optional now, but good to have)
    bvh_installed = False
    if (addons_dir / "retarget_bvh").exists() or (addons_dir / "retarget-bvh-master").exists():
        bvh_installed = True
        log_info("BVH Retargeter appears to be installed.")
        
    if not bvh_installed:
        # Note: BVH Retargeter extracts as "retarget-bvh-master", often needs rename to "retarget_bvh"
        # But Blender loads it fine usually.
        install_addon_by_unzip(BVH_RETARGETER_URL, "BVH_Retargeter", addons_dir)
        
    log_info("Addon installation process finished.")
    return True

if __name__ == "__main__":
    install_all_addons()