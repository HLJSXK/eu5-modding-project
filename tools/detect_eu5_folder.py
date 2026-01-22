#!/usr/bin/env python3
"""
EU5 Installation Folder Detection Script
Searches common Steam library locations for European Universalis 5 installation.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Optional, List


class EU5Detector:
    """Detects EU5 installation folder across different platforms."""
    
    # Common Steam library folder locations
    COMMON_STEAM_PATHS = {
        'Windows': [
            r'C:\Program Files (x86)\Steam',
            r'C:\Program Files\Steam',
            r'D:\Steam',
            r'E:\Steam',
            r'D:\SteamLibrary',
            r'E:\SteamLibrary',
        ],
        'Linux': [
            '~/.steam/steam',
            '~/.local/share/Steam',
            '/usr/share/steam',
        ],
        'Darwin': [  # macOS
            '~/Library/Application Support/Steam',
        ]
    }
    
    # EU5 folder name in Steam library
    EU5_FOLDER_NAME = 'Europa Universalis V'
    
    def __init__(self):
        self.system = platform.system()
        
    def expand_path(self, path: str) -> Path:
        """Expand user home directory and convert to Path object."""
        return Path(os.path.expanduser(path))
    
    def get_steam_library_folders(self, steam_path: Path) -> List[Path]:
        """
        Parse Steam's libraryfolders.vdf to find all library locations.
        
        Args:
            steam_path: Path to Steam installation directory
            
        Returns:
            List of library folder paths
        """
        libraries = [steam_path]
        
        # Check for libraryfolders.vdf
        vdf_path = steam_path / 'steamapps' / 'libraryfolders.vdf'
        
        if not vdf_path.exists():
            return libraries
        
        try:
            with open(vdf_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Simple parsing for library paths
            # Format: "path"		"D:\\SteamLibrary"
            import re
            pattern = r'"path"\s+"([^"]+)"'
            matches = re.findall(pattern, content)
            
            for match in matches:
                # Convert Windows path separators
                lib_path = Path(match.replace('\\\\', os.sep))
                if lib_path.exists():
                    libraries.append(lib_path)
                    
        except Exception as e:
            print(f"Warning: Failed to parse libraryfolders.vdf: {e}")
            
        return libraries
    
    def find_eu5_in_library(self, library_path: Path) -> Optional[Path]:
        """
        Search for EU5 installation in a Steam library folder.
        
        Args:
            library_path: Path to Steam library folder
            
        Returns:
            Path to EU5 installation if found, None otherwise
        """
        # Check common locations
        possible_paths = [
            library_path / 'steamapps' / 'common' / self.EU5_FOLDER_NAME,
            library_path / 'SteamApps' / 'common' / self.EU5_FOLDER_NAME,
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_dir():
                # Verify it's actually EU5 by checking for key files
                binaries_path = path / 'binaries'
                if binaries_path.exists():
                    # Look for EU5 executable or steam_api64.dll
                    if (binaries_path / 'steam_api64.dll').exists() or \
                       list(binaries_path.glob('eu5*.exe')):
                        return path
                        
        return None
    
    def detect(self) -> Optional[Path]:
        """
        Detect EU5 installation folder.
        
        Returns:
            Path to EU5 installation folder if found, None otherwise
        """
        print(f"Detecting EU5 installation on {self.system}...")
        
        # Get platform-specific Steam paths
        steam_paths = self.COMMON_STEAM_PATHS.get(self.system, [])
        
        for steam_path_str in steam_paths:
            steam_path = self.expand_path(steam_path_str)
            
            if not steam_path.exists():
                continue
                
            print(f"Checking Steam library: {steam_path}")
            
            # Get all library folders from this Steam installation
            libraries = self.get_steam_library_folders(steam_path)
            
            # Search each library for EU5
            for library in libraries:
                eu5_path = self.find_eu5_in_library(library)
                if eu5_path:
                    print(f"\n✓ Found EU5 installation: {eu5_path}")
                    return eu5_path
                    
        return None
    
    def get_binaries_path(self, eu5_path: Path) -> Path:
        """Get the binaries folder path."""
        return eu5_path / 'binaries'


def main():
    """Main entry point."""
    detector = EU5Detector()
    
    eu5_path = detector.detect()
    
    if eu5_path:
        binaries_path = detector.get_binaries_path(eu5_path)
        print(f"\nEU5 Main Folder: {eu5_path}")
        print(f"Binaries Folder: {binaries_path}")
        
        # Output machine-readable format for scripting
        print(f"\n__EU5_PATH__={eu5_path}")
        print(f"__BINARIES_PATH__={binaries_path}")
        
        return 0
    else:
        print("\n✗ EU5 installation not found.")
        print("\nSearched locations:")
        for path in detector.COMMON_STEAM_PATHS.get(detector.system, []):
            print(f"  - {path}")
        print("\nPlease ensure European Universalis V is installed via Steam.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
