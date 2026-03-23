package deployer

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

const modsFolderNotice = "This folder is no longer used for EU5 mods.\nPlease place your mods in: Europa Universalis V\\game\\mod\n"

// Deployer handles Goldberg Emulator deployment
type Deployer struct {
	ProjectRoot  string
	EU5Path      string
	BinariesPath string
	BackupDir    string
	out          io.Writer // all output goes here (stdout, or stdout+logfile)

	configuredAccountName string
	hasCustomSettings     bool
}

// NewDeployer creates a new Deployer that writes to stdout
func NewDeployer(projectRoot, eu5Path string) *Deployer {
	return NewDeployerWithWriter(projectRoot, eu5Path, os.Stdout)
}

// NewDeployerWithWriter creates a new Deployer that writes to w
func NewDeployerWithWriter(projectRoot, eu5Path string, w io.Writer) *Deployer {
	binariesPath := filepath.Join(eu5Path, "binaries")
	backupDir := filepath.Join(binariesPath, ".goldberg_backup")

	return &Deployer{
		ProjectRoot:  projectRoot,
		EU5Path:      eu5Path,
		BinariesPath: binariesPath,
		BackupDir:    backupDir,
		out:          w,
	}
}

// logf is a convenience helper that writes to the deployer's output writer
func (d *Deployer) logf(format string, args ...interface{}) {
	fmt.Fprintf(d.out, format, args...)
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
		d.logf("⚠ Warning: Original steam_api64.dll not found\n")
		return nil
	}

	// Create backup directory if it doesn't exist
	if err := os.MkdirAll(d.BackupDir, 0755); err != nil {
		return fmt.Errorf("failed to create backup directory: %w", err)
	}

	backupDLL := filepath.Join(d.BackupDir, "steam_api64.dll.original")

	// Skip if backup already exists
	if _, err := os.Stat(backupDLL); err == nil {
		d.logf("✓ Backup already exists: %s\n", backupDLL)
		return nil
	}

	// Copy file
	if err := copyFile(originalDLL, backupDLL); err != nil {
		return fmt.Errorf("failed to backup original DLL: %w", err)
	}

	d.logf("✓ Backed up original DLL to: %s\n", backupDLL)
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

	d.logf("✓ Deployed Goldberg DLL to: %s\n", targetDLL)
	return nil
}

// DeployAppID deploys steam_appid.txt to binaries folder
func (d *Deployer) DeployAppID() error {
	sourceAppID := filepath.Join(d.ProjectRoot, "goldberg_emulator", "steam_appid.txt")
	targetAppID := filepath.Join(d.BinariesPath, "steam_appid.txt")

	if _, err := os.Stat(sourceAppID); os.IsNotExist(err) {
		return fmt.Errorf("steam_appid.txt not found: %s", sourceAppID)
	}

	if err := copyFile(sourceAppID, targetAppID); err != nil {
		return fmt.Errorf("failed to deploy steam_appid.txt: %w", err)
	}

	d.logf("✓ Deployed steam_appid.txt to: %s\n", targetAppID)
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
		d.logf("✓ Removed existing steam_settings\n")
	}

	// Copy steam_settings folder
	if err := copyDir(sourceSettings, targetSettings); err != nil {
		return fmt.Errorf("failed to deploy steam_settings: %w", err)
	}

	if d.hasCustomSettings {
		accountNameFile := filepath.Join(targetSettings, "force_account_name.txt")
		if err := os.WriteFile(accountNameFile, []byte(d.configuredAccountName), 0644); err != nil {
			return fmt.Errorf("failed to write deployed account name: %w", err)
		}

		d.logf("  - Applied custom display name to deployed steam_settings\n")
	}

	modsDir := filepath.Join(targetSettings, "mods")
	if err := d.ensureDeprecatedModsFolder(modsDir); err != nil {
		return err
	}

	d.logf("✓ Deployed steam_settings to: %s\n", targetSettings)

	// List deployed contents
	dlcFile := filepath.Join(targetSettings, "DLC.txt")
	modsNote := filepath.Join(modsDir, "README.txt")

	if _, err := os.Stat(dlcFile); err == nil {
		d.logf("  - DLC.txt: %s\n", dlcFile)
	}

	if _, err := os.Stat(modsNote); err == nil {
		d.logf("  - mods folder cleaned; note written: %s\n", modsNote)
	}

	return nil
}

func (d *Deployer) ensureDeprecatedModsFolder(modsDir string) error {
	if err := os.MkdirAll(modsDir, 0755); err != nil {
		return fmt.Errorf("failed to create mods folder: %w", err)
	}

	entries, err := os.ReadDir(modsDir)
	if err != nil {
		return fmt.Errorf("failed to read mods folder: %w", err)
	}

	removed := 0
	for _, entry := range entries {
		entryPath := filepath.Join(modsDir, entry.Name())
		if err := os.RemoveAll(entryPath); err != nil {
			return fmt.Errorf("failed to clean mods folder entry %s: %w", entryPath, err)
		}
		removed++
	}

	if removed > 0 {
		d.logf("  - Cleaned deprecated steam_settings/mods folder (%d items removed)\n", removed)
	}

	notePath := filepath.Join(modsDir, "README.txt")
	if err := os.WriteFile(notePath, []byte(modsFolderNotice), 0644); err != nil {
		return fmt.Errorf("failed to write mods folder note: %w", err)
	}

	return nil
}

// Deploy executes full deployment process
func (d *Deployer) Deploy() error {
	d.logf("============================================================\n")
	d.logf("Goldberg Emulator Deployment for EU5\n")
	d.logf("============================================================\n")
	d.logf("\nProject Root: %s\n", d.ProjectRoot)
	d.logf("EU5 Installation: %s\n", d.EU5Path)
	d.logf("Binaries Folder: %s\n", d.BinariesPath)
	d.logf("\n")

	// Validate paths
	if err := d.ValidatePaths(); err != nil {
		return err
	}

	// Step 1: Backup original DLL
	d.logf("\n[Step 1/4] Backing up original steam_api64.dll...\n")
	if err := d.BackupOriginalDLL(); err != nil {
		return err
	}

	// Step 2: Deploy Goldberg DLL
	d.logf("\n[Step 2/4] Deploying Goldberg steam_api64.dll...\n")
	if err := d.DeployDLL(); err != nil {
		return err
	}

	// Step 3: Deploy steam_appid.txt
	d.logf("\n[Step 3/4] Deploying steam_appid.txt...\n")
	if err := d.DeployAppID(); err != nil {
		return err
	}

	// Step 4: Deploy steam_settings
	d.logf("\n[Step 4/4] Deploying steam_settings folder...\n")
	if err := d.DeploySteamSettings(); err != nil {
		return err
	}

	d.logf("\n============================================================\n")
	d.logf("✓ Deployment completed successfully!\n")
	d.logf("============================================================\n")
	d.logf("\nYou can now launch EU5 for LAN multiplayer.\n")
	d.logf("To restore original files, run with --restore flag.\n")

	return nil
}

// Restore restores original steam_api64.dll from backup
func (d *Deployer) Restore() error {
	d.logf("============================================================\n")
	d.logf("Restoring Original Files\n")
	d.logf("============================================================\n")

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
	d.logf("✓ Restored original steam_api64.dll\n")

	// Remove steam_settings
	if _, err := os.Stat(targetSettings); err == nil {
		if err := os.RemoveAll(targetSettings); err != nil {
			return fmt.Errorf("failed to remove steam_settings: %w", err)
		}
		d.logf("✓ Removed steam_settings folder\n")
	}

	// Remove steam_appid.txt
	targetAppID := filepath.Join(d.BinariesPath, "steam_appid.txt")
	if _, err := os.Stat(targetAppID); err == nil {
		if err := os.Remove(targetAppID); err != nil {
			return fmt.Errorf("failed to remove steam_appid.txt: %w", err)
		}
		d.logf("✓ Removed steam_appid.txt\n")
	}

	d.logf("\n✓ Restoration completed successfully!\n")
	return nil
}

// ConfigureSteamSettings configures display name in steam_settings folder.
func (d *Deployer) ConfigureSteamSettings(accountName string) error {
	accountName = strings.TrimSpace(accountName)

	if err := ValidateAccountName(accountName); err != nil {
		return fmt.Errorf("invalid account name: %w", err)
	}

	d.configuredAccountName = accountName
	d.hasCustomSettings = true

	d.logf("✓ Prepared display name: %s\n", accountName)

	return nil
}

// ValidateAccountName validates the account name
func ValidateAccountName(accountName string) error {
	accountName = strings.TrimSpace(accountName)

	if accountName == "" {
		return fmt.Errorf("account name cannot be empty")
	}

	if len(accountName) > 32 {
		return fmt.Errorf("account name too long (max 32 characters)")
	}

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
	srcInfo, err := os.Stat(src)
	if err != nil {
		return err
	}

	if err := os.MkdirAll(dst, srcInfo.Mode()); err != nil {
		return err
	}

	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		srcPath := filepath.Join(src, entry.Name())
		dstPath := filepath.Join(dst, entry.Name())

		if entry.IsDir() {
			if err := copyDir(srcPath, dstPath); err != nil {
				return err
			}
		} else {
			if err := copyFile(srcPath, dstPath); err != nil {
				return err
			}
		}
	}

	return nil
}
