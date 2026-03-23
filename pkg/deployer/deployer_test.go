package deployer

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestValidateAccountName(t *testing.T) {
	tests := []struct {
		name        string
		accountName string
		wantErr     bool
	}{
		{name: "valid", accountName: "EU5Player", wantErr: false},
		{name: "trimmed valid", accountName: "  EU5Player  ", wantErr: false},
		{name: "empty", accountName: "", wantErr: true},
		{name: "spaces only", accountName: "   ", wantErr: true},
		{name: "too long", accountName: strings.Repeat("a", 33), wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateAccountName(tt.accountName)
			if (err != nil) != tt.wantErr {
				t.Fatalf("ValidateAccountName() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestConfigureSteamSettings_DoesNotMutateSourceTemplate(t *testing.T) {
	tempDir := t.TempDir()
	projectRoot := filepath.Join(tempDir, "project")
	eu5Path := filepath.Join(tempDir, "eu5")

	sourceSettings := filepath.Join(projectRoot, "goldberg_emulator", "steam_settings")
	if err := os.MkdirAll(sourceSettings, 0755); err != nil {
		t.Fatalf("failed to create source settings dir: %v", err)
	}

	sourceAccountFile := filepath.Join(sourceSettings, "force_account_name.txt")
	sourceModsDir := filepath.Join(sourceSettings, "mods")
	if err := os.WriteFile(sourceAccountFile, []byte("DEFAULT_ACCOUNT"), 0644); err != nil {
		t.Fatalf("failed to write source account file: %v", err)
	}
	if err := os.MkdirAll(sourceModsDir, 0755); err != nil {
		t.Fatalf("failed to create source mods dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(sourceModsDir, "old_mod.marker"), []byte("legacy"), 0644); err != nil {
		t.Fatalf("failed to write source legacy mod marker: %v", err)
	}

	binariesPath := filepath.Join(eu5Path, "binaries")
	if err := os.MkdirAll(binariesPath, 0755); err != nil {
		t.Fatalf("failed to create binaries path: %v", err)
	}

	d := NewDeployer(projectRoot, eu5Path)
	if err := d.ConfigureSteamSettings("  CustomName  "); err != nil {
		t.Fatalf("ConfigureSteamSettings() returned error: %v", err)
	}

	accountSourceBytes, err := os.ReadFile(sourceAccountFile)
	if err != nil {
		t.Fatalf("failed to read source account file: %v", err)
	}
	if got := string(accountSourceBytes); got != "DEFAULT_ACCOUNT" {
		t.Fatalf("source account file changed unexpectedly: got %q", got)
	}

	if err := d.DeploySteamSettings(); err != nil {
		t.Fatalf("DeploySteamSettings() returned error: %v", err)
	}

	targetSettings := filepath.Join(binariesPath, "steam_settings")
	targetAccountFile := filepath.Join(targetSettings, "force_account_name.txt")
	targetModsDir := filepath.Join(targetSettings, "mods")

	targetAccountBytes, err := os.ReadFile(targetAccountFile)
	if err != nil {
		t.Fatalf("failed to read target account file: %v", err)
	}
	if got := string(targetAccountBytes); got != "CustomName" {
		t.Fatalf("target account file not updated: got %q", got)
	}

	modEntries, err := os.ReadDir(targetModsDir)
	if err != nil {
		t.Fatalf("failed to read target mods dir: %v", err)
	}
	if len(modEntries) != 1 || modEntries[0].Name() != "README.txt" {
		t.Fatalf("target mods dir should contain only README.txt, got %v entries", len(modEntries))
	}

	noteBytes, err := os.ReadFile(filepath.Join(targetModsDir, "README.txt"))
	if err != nil {
		t.Fatalf("failed to read target mods README.txt: %v", err)
	}
	noteText := string(noteBytes)
	if !strings.Contains(noteText, "Europa Universalis V\\game\\mod") {
		t.Fatalf("target mods note does not point to game/mod: %q", noteText)
	}
}
