#!/usr/bin/env python3
"""
Goldberg Emulator Deployment Script for EU5
Deploys Goldberg Emulator files to EU5 installation directory.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional
import argparse


class GoldbergDeployer:
    """Handles deployment of Goldberg Emulator to EU5 installation."""
    
    def __init__(self, project_root: Path, eu5_path: Path):
        """
        Initialize deployer.
        
        Args:
            project_root: Path to the project root directory
            eu5_path: Path to EU5 installation directory
        """
        self.project_root = project_root
        self.eu5_path = eu5_path
        self.binaries_path = eu5_path / 'binaries'
        self.goldberg_source = project_root / 'goldberg_emulator'
        
        # Backup paths
        self.backup_dir = self.binaries_path / '.goldberg_backup'
        
    def validate_paths(self) -> bool:
        """Validate that all required paths exist."""
        if not self.eu5_path.exists():
            print(f"✗ EU5 installation not found: {self.eu5_path}")
            return False
            
        if not self.binaries_path.exists():
            print(f"✗ Binaries folder not found: {self.binaries_path}")
            return False
            
        if not self.goldberg_source.exists():
            print(f"✗ Goldberg emulator source not found: {self.goldberg_source}")
            return False
            
        return True
    
    def backup_original_dll(self) -> bool:
        """
        Backup the original steam_api64.dll if it exists.
        
        Returns:
            True if backup successful or not needed, False on error
        """
        original_dll = self.binaries_path / 'steam_api64.dll'
        
        if not original_dll.exists():
            print("⚠ Warning: Original steam_api64.dll not found")
            return True
            
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)
        
        backup_dll = self.backup_dir / 'steam_api64.dll.original'
        
        # Skip if backup already exists
        if backup_dll.exists():
            print(f"✓ Backup already exists: {backup_dll}")
            return True
            
        try:
            shutil.copy2(original_dll, backup_dll)
            print(f"✓ Backed up original DLL to: {backup_dll}")
            return True
        except Exception as e:
            print(f"✗ Failed to backup original DLL: {e}")
            return False
    
    def deploy_dll(self) -> bool:
        """
        Deploy Goldberg steam_api64.dll to binaries folder.
        
        Returns:
            True if deployment successful, False otherwise
        """
        source_dll = self.goldberg_source / 'steam_api64.dll'
        target_dll = self.binaries_path / 'steam_api64.dll'
        
        if not source_dll.exists():
            print(f"✗ Goldberg DLL not found: {source_dll}")
            return False
            
        try:
            shutil.copy2(source_dll, target_dll)
            print(f"✓ Deployed Goldberg DLL to: {target_dll}")
            return True
        except Exception as e:
            print(f"✗ Failed to deploy DLL: {e}")
            return False
    
    def deploy_steam_settings(self) -> bool:
        """
        Deploy steam_settings folder to binaries folder.
        
        Returns:
            True if deployment successful, False otherwise
        """
        source_settings = self.goldberg_source / 'steam_settings'
        target_settings = self.binaries_path / 'steam_settings'
        
        if not source_settings.exists():
            print(f"✗ steam_settings folder not found: {source_settings}")
            return False
            
        try:
            # Remove existing steam_settings if it exists
            if target_settings.exists():
                shutil.rmtree(target_settings)
                print(f"✓ Removed existing steam_settings")
                
            # Copy steam_settings folder
            shutil.copytree(source_settings, target_settings)
            print(f"✓ Deployed steam_settings to: {target_settings}")
            
            # List deployed contents
            dlc_file = target_settings / 'DLC.txt'
            mods_dir = target_settings / 'mods'
            
            if dlc_file.exists():
                print(f"  - DLC.txt: {dlc_file}")
            if mods_dir.exists():
                mod_count = len(list(mods_dir.iterdir()))
                print(f"  - mods folder: {mod_count} items")
                
            return True
        except Exception as e:
            print(f"✗ Failed to deploy steam_settings: {e}")
            return False
    
    def deploy(self) -> bool:
        """
        Execute full deployment process.
        
        Returns:
            True if all steps successful, False otherwise
        """
        print("=" * 60)
        print("Goldberg Emulator Deployment for EU5")
        print("=" * 60)
        print(f"\nProject Root: {self.project_root}")
        print(f"EU5 Installation: {self.eu5_path}")
        print(f"Binaries Folder: {self.binaries_path}")
        print()
        
        # Validate paths
        if not self.validate_paths():
            return False
            
        # Step 1: Backup original DLL
        print("\n[Step 1/3] Backing up original steam_api64.dll...")
        if not self.backup_original_dll():
            return False
            
        # Step 2: Deploy Goldberg DLL
        print("\n[Step 2/3] Deploying Goldberg steam_api64.dll...")
        if not self.deploy_dll():
            return False
            
        # Step 3: Deploy steam_settings
        print("\n[Step 3/3] Deploying steam_settings folder...")
        if not self.deploy_steam_settings():
            return False
            
        print("\n" + "=" * 60)
        print("✓ Deployment completed successfully!")
        print("=" * 60)
        print("\nYou can now launch EU5 for LAN multiplayer.")
        print("To restore original files, run with --restore flag.")
        
        return True
    
    def restore(self) -> bool:
        """
        Restore original steam_api64.dll from backup.
        
        Returns:
            True if restoration successful, False otherwise
        """
        print("=" * 60)
        print("Restoring Original Files")
        print("=" * 60)
        
        backup_dll = self.backup_dir / 'steam_api64.dll.original'
        target_dll = self.binaries_path / 'steam_api64.dll'
        target_settings = self.binaries_path / 'steam_settings'
        
        if not backup_dll.exists():
            print(f"✗ Backup not found: {backup_dll}")
            return False
            
        try:
            # Restore DLL
            shutil.copy2(backup_dll, target_dll)
            print(f"✓ Restored original steam_api64.dll")
            
            # Remove steam_settings
            if target_settings.exists():
                shutil.rmtree(target_settings)
                print(f"✓ Removed steam_settings folder")
                
            print("\n✓ Restoration completed successfully!")
            return True
        except Exception as e:
            print(f"✗ Failed to restore: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy Goldberg Emulator to EU5 installation'
    )
    parser.add_argument(
        '--eu5-path',
        type=str,
        help='Path to EU5 installation directory'
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='Restore original files from backup'
    )
    
    args = parser.parse_args()
    
    # Get project root (parent of tools folder)
    project_root = Path(__file__).parent.parent
    
    # Get EU5 path
    if args.eu5_path:
        eu5_path = Path(args.eu5_path)
    else:
        # Try to auto-detect
        print("No EU5 path specified, attempting auto-detection...")
        try:
            from detect_eu5_folder import EU5Detector
            detector = EU5Detector()
            eu5_path = detector.detect()
            if not eu5_path:
                print("\n✗ Could not auto-detect EU5 installation.")
                print("Please specify path with --eu5-path argument.")
                return 1
        except ImportError:
            print("✗ Could not import EU5 detector.")
            print("Please specify path with --eu5-path argument.")
            return 1
    
    # Create deployer
    deployer = GoldbergDeployer(project_root, eu5_path)
    
    # Execute action
    if args.restore:
        success = deployer.restore()
    else:
        success = deployer.deploy()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
