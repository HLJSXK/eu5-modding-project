package deployer

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// Deployer handles Goldberg Emulator deployment
type Deployer struct {
	ProjectRoot  string
	EU5Path      string
	BinariesPath string
	BackupDir    string
}

// NewDeployer creates a new Deployer
func NewDeployer(projectRoot, eu5Path string) *Deployer {
	binariesPath := filepath.Join(eu5Path, "binaries")
	backupDir := filepath.Join(binariesPath, ".goldberg_backup")

	return &Deployer{
		ProjectRoot:  projectRoot,
		EU5Path:      eu5Path,
		BinariesPath: binariesPath,
		BackupDir:    backupDir,
	}
}

// ValidatePaths validates that all required paths exist
func (d *Deployer) ValidatePaths() error {
	if _, err := os.Stat(d.EU5Path); os.IsNotExist(err) {
		return fmt.Errorf("EU5 installation not found: %s", d.EU5Path)
	}

	if _, err := os.Stat(d.BinariesPath); os.IsNotExist(err) {
		return fmt.Errorf("binaries folder not found: %s", d.BinariesPath)
	}

	goldbergSource := filepath.Join(d.ProjectRoot, "goldberg_emulator")
	if _, err := os.Stat(goldbergSource); os.IsNotExist(err) {
		return fmt.Errorf("goldberg_emulator source not found: %s", goldbergSource)
	}

	return nil
}

// BackupOriginalDLL backs up the original steam_api64.dll
func (d *Deployer) BackupOriginalDLL() error {
	originalDLL := filepath.Join(d.BinariesPath, "steam_api64.dll")

	if _, err := os.Stat(originalDLL); os.IsNotExist(err) {
		fmt.Println("⚠ Warning: Original steam_api64.dll not found")
		return nil
	}

	// Create backup directory if it doesn't exist
	if err := os.MkdirAll(d.BackupDir, 0755); err != nil {
		return fmt.Errorf("failed to create backup directory: %w", err)
	}

	backupDLL := filepath.Join(d.BackupDir, "steam_api64.dll.original")

	// Skip if backup already exists
	if _, err := os.Stat(backupDLL); err == nil {
		fmt.Printf("✓ Backup already exists: %s\n", backupDLL)
		return nil
	}

	// Copy file
	if err := copyFile(originalDLL, backupDLL); err != nil {
		return fmt.Errorf("failed to backup original DLL: %w", err)
	}

	fmt.Printf("✓ Backed up original DLL to: %s\n", backupDLL)
	return nil
}

// DeployDLL deploys Goldberg steam_api64.dll to binaries folder
func (d *Deployer) DeployDLL() error {
	sourceDLL := filepath.Join(d.ProjectRoot, "goldberg_emulator", "steam_api64.dll")
	targetDLL := filepath.Join(d.BinariesPath, "steam_api64.dll")

	if _, err := os.Stat(sourceDLL); os.IsNotExist(err) {
		return fmt.Errorf("Goldberg DLL not found: %s", sourceDLL)
	}

	if err := copyFile(sourceDLL, targetDLL); err != nil {
		return fmt.Errorf("failed to deploy DLL: %w", err)
	}

	fmt.Printf("✓ Deployed Goldberg DLL to: %s\n", targetDLL)
	return nil
}

// DeploySteamSettings deploys steam_settings folder to binaries folder
func (d *Deployer) DeploySteamSettings() error {
	sourceSettings := filepath.Join(d.ProjectRoot, "goldberg_emulator", "steam_settings")
	targetSettings := filepath.Join(d.BinariesPath, "steam_settings")

	if _, err := os.Stat(sourceSettings); os.IsNotExist(err) {
		return fmt.Errorf("steam_settings folder not found: %s", sourceSettings)
	}

	// Remove existing steam_settings if it exists
	if _, err := os.Stat(targetSettings); err == nil {
		if err := os.RemoveAll(targetSettings); err != nil {
			return fmt.Errorf("failed to remove existing steam_settings: %w", err)
		}
		fmt.Println("✓ Removed existing steam_settings")
	}

	// Copy steam_settings folder
	if err := copyDir(sourceSettings, targetSettings); err != nil {
		return fmt.Errorf("failed to deploy steam_settings: %w", err)
	}

	fmt.Printf("✓ Deployed steam_settings to: %s\n", targetSettings)

	// List deployed contents
	dlcFile := filepath.Join(targetSettings, "DLC.txt")
	modsDir := filepath.Join(targetSettings, "mods")

	if _, err := os.Stat(dlcFile); err == nil {
		fmt.Printf("  - DLC.txt: %s\n", dlcFile)
	}

	if stat, err := os.Stat(modsDir); err == nil && stat.IsDir() {
		entries, _ := os.ReadDir(modsDir)
		fmt.Printf("  - mods folder: %d items\n", len(entries))
	}

	return nil
}

// Deploy executes full deployment process
func (d *Deployer) Deploy() error {
	fmt.Println("============================================================")
	fmt.Println("Goldberg Emulator Deployment for EU5")
	fmt.Println("============================================================")
	fmt.Printf("\nProject Root: %s\n", d.ProjectRoot)
	fmt.Printf("EU5 Installation: %s\n", d.EU5Path)
	fmt.Printf("Binaries Folder: %s\n", d.BinariesPath)
	fmt.Println()

	// Validate paths
	if err := d.ValidatePaths(); err != nil {
		return err
	}

	// Step 1: Backup original DLL
	fmt.Println("\n[Step 1/3] Backing up original steam_api64.dll...")
	if err := d.BackupOriginalDLL(); err != nil {
		return err
	}

	// Step 2: Deploy Goldberg DLL
	fmt.Println("\n[Step 2/3] Deploying Goldberg steam_api64.dll...")
	if err := d.DeployDLL(); err != nil {
		return err
	}

	// Step 3: Deploy steam_settings
	fmt.Println("\n[Step 3/3] Deploying steam_settings folder...")
	if err := d.DeploySteamSettings(); err != nil {
		return err
	}

	fmt.Println("\n============================================================")
	fmt.Println("✓ Deployment completed successfully!")
	fmt.Println("============================================================")
	fmt.Println("\nYou can now launch EU5 for LAN multiplayer.")
	fmt.Println("To restore original files, run with --restore flag.")

	return nil
}

// Restore restores original steam_api64.dll from backup
func (d *Deployer) Restore() error {
	fmt.Println("============================================================")
	fmt.Println("Restoring Original Files")
	fmt.Println("============================================================")

	backupDLL := filepath.Join(d.BackupDir, "steam_api64.dll.original")
	targetDLL := filepath.Join(d.BinariesPath, "steam_api64.dll")
	targetSettings := filepath.Join(d.BinariesPath, "steam_settings")

	if _, err := os.Stat(backupDLL); os.IsNotExist(err) {
		return fmt.Errorf("backup not found: %s", backupDLL)
	}

	// Restore DLL
	if err := copyFile(backupDLL, targetDLL); err != nil {
		return fmt.Errorf("failed to restore DLL: %w", err)
	}
	fmt.Println("✓ Restored original steam_api64.dll")

	// Remove steam_settings
	if _, err := os.Stat(targetSettings); err == nil {
		if err := os.RemoveAll(targetSettings); err != nil {
			return fmt.Errorf("failed to remove steam_settings: %w", err)
		}
		fmt.Println("✓ Removed steam_settings folder")
	}

	fmt.Println("\n✓ Restoration completed successfully!")
	return nil
}

// copyFile copies a file from src to dst
func copyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	if _, err := io.Copy(destFile, sourceFile); err != nil {
		return err
	}

	// Copy file permissions
	sourceInfo, err := os.Stat(src)
	if err != nil {
		return err
	}
	return os.Chmod(dst, sourceInfo.Mode())
}

// copyDir recursively copies a directory
func copyDir(src, dst string) error {
	// Get source directory info
	srcInfo, err := os.Stat(src)
	if err != nil {
		return err
	}

	// Create destination directory
	if err := os.MkdirAll(dst, srcInfo.Mode()); err != nil {
		return err
	}

	// Read source directory
	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		srcPath := filepath.Join(src, entry.Name())
		dstPath := filepath.Join(dst, entry.Name())

		if entry.IsDir() {
			// Recursively copy subdirectory
			if err := copyDir(srcPath, dstPath); err != nil {
				return err
			}
		} else {
			// Copy file
			if err := copyFile(srcPath, dstPath); err != nil {
				return err
			}
		}
	}

	return nil
}
