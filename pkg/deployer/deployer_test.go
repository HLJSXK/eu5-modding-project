package deployer

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestValidateSteamID(t *testing.T) {
	tests := []struct {
		name    string
		steamID string
		wantErr bool
	}{
		{name: "valid", steamID: "76561197960287930", wantErr: false},
		{name: "wrong length", steamID: "7656119796028793", wantErr: true},
		{name: "non digit", steamID: "7656119796028793A", wantErr: true},
		{name: "wrong prefix", steamID: "12345678901234567", wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateSteamID(tt.steamID)
			if (err != nil) != tt.wantErr {
				t.Fatalf("ValidateSteamID() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

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
	sourceSteamIDFile := filepath.Join(sourceSettings, "force_steamid.txt")
	if err := os.WriteFile(sourceAccountFile, []byte("DEFAULT_ACCOUNT"), 0644); err != nil {
		t.Fatalf("failed to write source account file: %v", err)
	}
	if err := os.WriteFile(sourceSteamIDFile, []byte("76561197960287930"), 0644); err != nil {
		t.Fatalf("failed to write source steamid file: %v", err)
	}

	binariesPath := filepath.Join(eu5Path, "binaries")
	if err := os.MkdirAll(binariesPath, 0755); err != nil {
		t.Fatalf("failed to create binaries path: %v", err)
	}

	d := NewDeployer(projectRoot, eu5Path)
	if err := d.ConfigureSteamSettings("  CustomName  ", "76561197960287931"); err != nil {
		t.Fatalf("ConfigureSteamSettings() returned error: %v", err)
	}

	accountSourceBytes, err := os.ReadFile(sourceAccountFile)
	if err != nil {
		t.Fatalf("failed to read source account file: %v", err)
	}
	if got := string(accountSourceBytes); got != "DEFAULT_ACCOUNT" {
		t.Fatalf("source account file changed unexpectedly: got %q", got)
	}

	steamIDSourceBytes, err := os.ReadFile(sourceSteamIDFile)
	if err != nil {
		t.Fatalf("failed to read source steamid file: %v", err)
	}
	if got := string(steamIDSourceBytes); got != "76561197960287930" {
		t.Fatalf("source steamid file changed unexpectedly: got %q", got)
	}

	if err := d.DeploySteamSettings(); err != nil {
		t.Fatalf("DeploySteamSettings() returned error: %v", err)
	}

	targetSettings := filepath.Join(binariesPath, "steam_settings")
	targetAccountFile := filepath.Join(targetSettings, "force_account_name.txt")
	targetSteamIDFile := filepath.Join(targetSettings, "force_steamid.txt")

	targetAccountBytes, err := os.ReadFile(targetAccountFile)
	if err != nil {
		t.Fatalf("failed to read target account file: %v", err)
	}
	if got := string(targetAccountBytes); got != "CustomName" {
		t.Fatalf("target account file not updated: got %q", got)
	}

	targetSteamIDBytes, err := os.ReadFile(targetSteamIDFile)
	if err != nil {
		t.Fatalf("failed to read target steamid file: %v", err)
	}
	if got := string(targetSteamIDBytes); got != "76561197960287931" {
		t.Fatalf("target steamid file not updated: got %q", got)
	}
}
