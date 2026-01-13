"""
Blender Configuration Management for ComfyUI-MotionCapture

Provides centralized configuration for Blender path detection and version management.
Supports custom paths via YAML configuration file.
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Optional, Tuple
import yaml


# Default Blender version (LTS)
DEFAULT_BLENDER_VERSION = "4.2.3"
DEFAULT_DOWNLOAD_BASE = "https://download.blender.org/release"


class BlenderConfig:
    """
    Centralized Blender configuration and detection.

    Manages:
    - Custom Blender paths from config file
    - Version selection for auto-installation
    - Platform-specific executable detection
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize BlenderConfig.

        Args:
            config_path: Path to blender_config.yaml. If None, searches in project root.
        """
        self.config = {}
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[Path] = None):
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            # Default: project root / blender_config.yaml
            project_root = Path(__file__).parent.parent
            config_path = project_root / "blender_config.yaml"

        if not config_path.exists():
            # No config file - use defaults
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    self.config = data.get('blender', {})
        except yaml.YAMLError as e:
            print(f"[BlenderConfig] Warning: Failed to parse config file: {e}")
            print("[BlenderConfig] Falling back to default configuration")
        except Exception as e:
            print(f"[BlenderConfig] Warning: Failed to load config file: {e}")
            print("[BlenderConfig] Falling back to default configuration")

    def get_custom_path(self) -> Optional[Path]:
        """
        Get custom Blender path from config.

        Returns:
            Path to Blender executable if configured and exists, None otherwise.
        """
        custom_path = self.config.get('custom_path')
        if not custom_path:
            return None

        path = Path(custom_path).expanduser().resolve()

        # Validate path exists and is executable
        if not path.exists():
            print(f"[BlenderConfig] Warning: Custom path does not exist: {path}")
            return None

        if not path.is_file():
            print(f"[BlenderConfig] Warning: Custom path is not a file: {path}")
            return None

        if not os.access(path, os.X_OK):
            print(f"[BlenderConfig] Warning: Custom path is not executable: {path}")
            return None

        print(f"[BlenderConfig] Using custom Blender path: {path}")
        return path

    def get_version(self) -> str:
        """
        Get Blender version for installation.

        Returns:
            Version string (e.g., "4.2.3")
        """
        version = self.config.get('version')
        if version:
            # Validate version format
            if self._validate_version(version):
                print(f"[BlenderConfig] Using configured Blender version: {version}")
                return version
            else:
                print(f"[BlenderConfig] Warning: Invalid version format '{version}', using default")

        return DEFAULT_BLENDER_VERSION

    def _validate_version(self, version: str) -> bool:
        """
        Validate version string format.

        Args:
            version: Version string to validate

        Returns:
            True if version format is valid (X.Y.Z)
        """
        if not isinstance(version, str):
            return False

        parts = version.split('.')
        if len(parts) != 3:
            return False

        try:
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False

    def get_download_base_url(self) -> str:
        """
        Get base URL for Blender downloads.

        Returns:
            Base URL string
        """
        url = self.config.get('download_base_url')
        if url:
            print(f"[BlenderConfig] Using custom download base URL: {url}")
            return url
        return DEFAULT_DOWNLOAD_BASE

    def get_download_url(self, platform_name: str, architecture: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get download URL for specific platform and architecture.

        Args:
            platform_name: Platform name ("linux", "macos", "windows")
            architecture: Architecture ("x64", "arm64")

        Returns:
            Tuple of (download_url, version, filename) or (None, None, None) if not found
        """
        version = self.get_version()
        base_url = self.get_download_base_url()

        # Construct version-specific URL
        major_minor = '.'.join(version.split('.')[:2])  # e.g., "4.2" from "4.2.3"
        version_url = f"{base_url}/Blender{major_minor}"

        # Platform-specific filenames
        urls = {
            ("linux", "x64"): (
                f"{version_url}/blender-{version}-linux-x64.tar.xz",
                version,
                f"blender-{version}-linux-x64.tar.xz"
            ),
            ("macos", "x64"): (
                f"{version_url}/blender-{version}-macos-x64.dmg",
                version,
                f"blender-{version}-macos-x64.dmg"
            ),
            ("macos", "arm64"): (
                f"{version_url}/blender-{version}-macos-arm64.dmg",
                version,
                f"blender-{version}-macos-arm64.dmg"
            ),
            ("windows", "x64"): (
                f"{version_url}/blender-{version}-windows-x64.zip",
                version,
                f"blender-{version}-windows-x64.zip"
            ),
        }

        key = (platform_name, architecture)
        if key in urls:
            url, ver, filename = urls[key]
            print(f"[BlenderConfig] Download URL for {platform_name}-{architecture}: {url}")
            return url, ver, filename

        return None, None, None

    def find_blender_executable(self) -> Optional[Path]:
        """
        Find Blender executable using priority order:
        1. Custom path from config (if set)
        2. Local installation in lib/blender/
        3. System PATH

        Returns:
            Path to Blender executable if found, None otherwise
        """
        # Priority 1: Custom path from config
        custom_path = self.get_custom_path()
        if custom_path:
            return custom_path

        # Priority 2: Local installation
        local_blender = Path(__file__).parent / "blender"
        if local_blender.exists():
            system = platform.system().lower()
            if system == "windows":
                pattern = "**/blender.exe"
            elif system == "darwin":
                pattern = "**/MacOS/blender"
            else:
                pattern = "**/blender"

            executables = list(local_blender.glob(pattern))
            if executables:
                print(f"[BlenderConfig] Found local Blender installation: {executables[0]}")
                return executables[0]

        # Priority 3: System PATH
        system_blender = shutil.which("blender")
        if system_blender:
            print(f"[BlenderConfig] Found Blender in system PATH: {system_blender}")
            return Path(system_blender)

        # Not found
        print("[BlenderConfig] Blender not found in any location")
        return None


def get_blender_executable() -> Path:
    """
    Convenience function to get Blender executable.

    Returns:
        Path to Blender executable

    Raises:
        RuntimeError: If Blender is not found
    """
    config = BlenderConfig()
    blender_exe = config.find_blender_executable()

    if not blender_exe:
        raise RuntimeError(
            "Blender not found. Please either:\n"
            "1. Set custom_path in blender_config.yaml\n"
            "2. Run install.py --install-blender\n"
            "3. Install Blender system-wide"
        )

    return blender_exe
