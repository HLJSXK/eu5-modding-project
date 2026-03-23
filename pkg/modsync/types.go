package modsync

import (
	"encoding/json"
	"io"
	"path/filepath"
	"strings"
	"time"

	"github.com/HLJSXK/eu5-modding-project/pkg/detector"
)

const (
	stateFileName = ".eu5-modsync-state.json"
)

type SnapshotManifest struct {
	SchemaVersion string        `json:"schema_version"`
	SnapshotID    string        `json:"snapshot_id"`
	GeneratedAt   string        `json:"generated_at_utc"`
	HostName      string        `json:"host_name"`
	GameModRel    string        `json:"game_mod_rel_path"`
	Mods          []SnapshotMod `json:"mods"`
}

type SnapshotMod struct {
	ModID       string `json:"mod_id"`
	DisplayName string `json:"display_name"`
	PackageURL  string `json:"package_url"`
	PackageSHA  string `json:"package_sha256"`
	PackageSize int64  `json:"package_size"`
	ContentHash string `json:"content_hash"`
	FileCount   int    `json:"file_count"`
}

func (m SnapshotMod) MarshalJSON() ([]byte, error) {
	type outSnapshotMod struct {
		ModID       string `json:"mod_id"`
		ID          string `json:"id"`
		DisplayName string `json:"display_name"`
		Name        string `json:"name"`
		ModName     string `json:"mod_name"`
		PackageURL  string `json:"package_url"`
		PackageSHA  string `json:"package_sha256"`
		PackageSize int64  `json:"package_size"`
		ContentHash string `json:"content_hash"`
		FileCount   int    `json:"file_count"`
	}

	modID := strings.TrimSpace(m.ModID)
	name := strings.TrimSpace(m.DisplayName)

	return json.Marshal(outSnapshotMod{
		ModID:       modID,
		ID:          modID,
		DisplayName: name,
		Name:        name,
		ModName:     name,
		PackageURL:  m.PackageURL,
		PackageSHA:  m.PackageSHA,
		PackageSize: m.PackageSize,
		ContentHash: m.ContentHash,
		FileCount:   m.FileCount,
	})
}

func (m *SnapshotMod) UnmarshalJSON(data []byte) error {
	type rawSnapshotMod struct {
		ModID       string `json:"mod_id"`
		ID          string `json:"id"`
		DisplayName string `json:"display_name"`
		Name        string `json:"name"`
		ModName     string `json:"mod_name"`
		PackageURL  string `json:"package_url"`
		PackageSHA  string `json:"package_sha256"`
		PackageSize int64  `json:"package_size"`
		ContentHash string `json:"content_hash"`
		FileCount   int    `json:"file_count"`
	}

	var r rawSnapshotMod
	if err := json.Unmarshal(data, &r); err != nil {
		return err
	}

	m.ModID = strings.TrimSpace(r.ModID)
	if m.ModID == "" {
		m.ModID = strings.TrimSpace(r.ID)
	}

	m.DisplayName = strings.TrimSpace(r.DisplayName)
	if m.DisplayName == "" {
		m.DisplayName = strings.TrimSpace(r.Name)
	}
	if m.DisplayName == "" {
		m.DisplayName = strings.TrimSpace(r.ModName)
	}

	m.PackageURL = r.PackageURL
	m.PackageSHA = r.PackageSHA
	m.PackageSize = r.PackageSize
	m.ContentHash = r.ContentHash
	m.FileCount = r.FileCount

	return nil
}

type SyncState struct {
	SchemaVersion string                    `json:"schema_version"`
	LastSnapshot  string                    `json:"last_snapshot_id"`
	LastSyncTime  string                    `json:"last_sync_time_utc"`
	ManagedMods   map[string]ManagedModInfo `json:"managed_mods"`
}

type ManagedModInfo struct {
	LastAppliedSnapshotID  string `json:"last_applied_snapshot_id"`
	LastAppliedContentHash string `json:"last_applied_content_hash"`
	LastAppliedPackageSHA  string `json:"last_applied_package_sha256"`
}

type ActionType string

const (
	ActionAdded     ActionType = "Added"
	ActionUpdated   ActionType = "Updated"
	ActionDeleted   ActionType = "Deleted"
	ActionKeptLocal ActionType = "KeptLocal"
	ActionUnmanaged ActionType = "UnmanagedLocal"
	ActionNoOp      ActionType = "NoOp"
	ActionFailed    ActionType = "Failed"
)

type PlanItem struct {
	Action     ActionType
	ModID      string
	ModName    string // e.g. "European Expanded", otherwise ModID
	LocalState string // e.g. "Missing", "Exist", "Out of date", "Modified", "Unmanaged"
	Reason     string
}

type SyncReport struct {
	SnapshotID string
	Items      []PlanItem
}

type SyncOptions struct {
	ManifestURL          string
	ModPath              string
	DryRun               bool
	DeleteManagedMissing bool
	Out                  io.Writer
}

type PublishOptions struct {
	ModPath   string
	OutDir    string
	BaseURL   string
	UploadCmd string
	Out       io.Writer

	COSSecretID  string
	COSSecretKey string
	COSBucket    string
	COSRegion    string
	COSPrefix    string
}

func nowUTC() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func statePath(modPath string) string {
	return filepath.Join(modPath, stateFileName)
}

func ResolveDefaultModPath() (string, error) {
	d := detector.NewDetector()
	eu5Path, err := d.DetectWithWriter(io.Discard)
	if err != nil {
		return "", err
	}
	return filepath.Join(eu5Path, "game", "mod"), nil
}
