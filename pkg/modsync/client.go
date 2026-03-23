package modsync

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func RunSync(opts SyncOptions) error {
	if opts.Out == nil {
		opts.Out = os.Stdout
	}
	if opts.ManifestURL == "" {
		return fmt.Errorf("--manifest-url is required")
	}
	if opts.ModPath == "" {
		return fmt.Errorf("--mod-path is required")
	}
	if err := os.MkdirAll(opts.ModPath, 0755); err != nil {
		return fmt.Errorf("failed to create mod path: %w", err)
	}

	fmt.Fprintf(opts.Out, "Sync started\n")
	fmt.Fprintf(opts.Out, "Manifest URL: %s\n", opts.ManifestURL)
	fmt.Fprintf(opts.Out, "Target mod path: %s\n", opts.ModPath)
	fmt.Fprintf(opts.Out, "Delete managed missing: %t\n", opts.DeleteManagedMissing)

	manifest, manifestBaseURL, err := fetchManifest(opts.ManifestURL)
	if err != nil {
		return err
	}
	fmt.Fprintf(opts.Out, "Loaded snapshot: %s (%d mods)\n", manifest.SnapshotID, len(manifest.Mods))

	state, err := loadState(opts.ModPath)
	if err != nil {
		return err
	}

	plan, err := buildPlan(opts.ModPath, manifest, state, opts.DeleteManagedMissing)
	if err != nil {
		return err
	}

	report := &SyncReport{SnapshotID: manifest.SnapshotID, Items: plan}
	printReport(opts.Out, report)

	if opts.DryRun {
		fmt.Fprintf(opts.Out, "Dry run enabled, no changes were applied.\n")
		return nil
	}

	fmt.Fprintf(opts.Out, "Applying sync plan...\n")

	if err := applyPlan(opts, manifestBaseURL, manifest, state, plan); err != nil {
		return err
	}

	state.LastSnapshot = manifest.SnapshotID
	state.LastSyncTime = nowUTC()
	if err := saveState(opts.ModPath, state); err != nil {
		return err
	}

	fmt.Fprintf(opts.Out, "Sync completed. State updated at %s\n", statePath(opts.ModPath))
	return nil
}

func fetchManifest(manifestURL string) (*SnapshotManifest, string, error) {
	req, err := http.NewRequest(http.MethodGet, manifestURL, nil)
	if err != nil {
		return nil, "", err
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, "", fmt.Errorf("failed to fetch manifest: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, "", fmt.Errorf("failed to fetch manifest, status %d: %s", resp.StatusCode, string(body))
	}

	var manifest SnapshotManifest
	if err := json.NewDecoder(resp.Body).Decode(&manifest); err != nil {
		return nil, "", fmt.Errorf("failed to decode manifest: %w", err)
	}

	baseURL, err := manifestBaseURL(manifestURL)
	if err != nil {
		return nil, "", err
	}

	return &manifest, baseURL, nil
}

func manifestBaseURL(manifestURL string) (string, error) {
	u, err := url.Parse(manifestURL)
	if err != nil {
		return "", fmt.Errorf("invalid manifest URL: %w", err)
	}
	if u.Scheme == "" || u.Host == "" {
		return "", fmt.Errorf("manifest URL must be absolute")
	}
	base := *u
	base.Path = filepath.ToSlash(filepath.Dir(u.Path))
	base.RawQuery = ""
	base.Fragment = ""
	return strings.TrimRight(base.String(), "/"), nil
}

func loadState(modPath string) (*SyncState, error) {
	path := statePath(modPath)
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return &SyncState{SchemaVersion: "1.0", ManagedMods: map[string]ManagedModInfo{}}, nil
	}

	b, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read state file: %w", err)
	}

	var s SyncState
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, fmt.Errorf("failed to decode state file: %w", err)
	}
	if s.ManagedMods == nil {
		s.ManagedMods = map[string]ManagedModInfo{}
	}

	return &s, nil
}

func saveState(modPath string, state *SyncState) error {
	b, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(statePath(modPath), b, 0644); err != nil {
		return fmt.Errorf("failed to write state file: %w", err)
	}
	return nil
}

func scanLocalModHashes(modPath string) (map[string]string, error) {
	entries, err := os.ReadDir(modPath)
	if err != nil {
		return nil, err
	}
	result := make(map[string]string)
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		if shouldIgnoreLocalModDir(e.Name()) {
			continue
		}
		hash, _, err := computeDirectoryHash(filepath.Join(modPath, e.Name()))
		if err != nil {
			return nil, err
		}
		result[e.Name()] = hash
	}
	return result, nil
}

func shouldIgnoreLocalModDir(name string) bool {
	if name == ".modsync_tmp" {
		return true
	}
	if strings.HasPrefix(name, ".modsync_") {
		return true
	}
	return false
}

func buildPlan(modPath string, manifest *SnapshotManifest, state *SyncState, deleteManagedMissing bool) ([]PlanItem, error) {
	localHashes, err := scanLocalModHashes(modPath)
	if err != nil {
		return nil, fmt.Errorf("failed to scan local mods: %w", err)
	}

	remote := make(map[string]SnapshotMod)
	for _, m := range manifest.Mods {
		remote[m.ModID] = m
	}

	var plan []PlanItem
	var remoteIDs []string
	for id := range remote {
		remoteIDs = append(remoteIDs, id)
	}
	sort.Strings(remoteIDs)

	for _, id := range remoteIDs {
		rm := remote[id]
		localHash, hasLocal := localHashes[id]
		managed, hasManaged := state.ManagedMods[id]

		modName := rm.DisplayName
		if modName == "" {
			modName = id
		}

		switch {
		case !hasLocal:
			plan = append(plan, PlanItem{Action: ActionAdded, ModID: id, ModName: modName, LocalState: "Missing", Reason: "missing locally"})
		case localHash == rm.ContentHash:
			plan = append(plan, PlanItem{Action: ActionNoOp, ModID: id, ModName: modName, LocalState: "Exist", Reason: "already up to date"})
		case hasManaged && managed.LastAppliedContentHash == localHash:
			plan = append(plan, PlanItem{Action: ActionUpdated, ModID: id, ModName: modName, LocalState: "Out of date", Reason: "remote changed since last applied"})
		default:
			plan = append(plan, PlanItem{Action: ActionKeptLocal, ModID: id, ModName: modName, LocalState: "Modified", Reason: "local mod diverged from managed state"})
		}
	}

	var localIDs []string
	for id := range localHashes {
		if _, ok := remote[id]; !ok {
			localIDs = append(localIDs, id)
		}
	}
	sort.Strings(localIDs)

	for _, id := range localIDs {
		_, managed := state.ManagedMods[id]

		// For local-only mods, we might not have a clean "Name" unless we read metadata.
		// For simplicity, just use the directory ID as the Name.
		modName := id

		if managed {
			if deleteManagedMissing {
				plan = append(plan, PlanItem{Action: ActionDeleted, ModID: id, ModName: modName, LocalState: "Deprecated", Reason: "removed from remote snapshot"})
			} else {
				plan = append(plan, PlanItem{Action: ActionKeptLocal, ModID: id, ModName: modName, LocalState: "Deprecated", Reason: "managed mod missing remotely; delete disabled"})
			}
			continue
		}
		plan = append(plan, PlanItem{Action: ActionUnmanaged, ModID: id, ModName: modName, LocalState: "Unmanaged", Reason: "local unmanaged mod"})
	}

	return plan, nil
}

func applyPlan(opts SyncOptions, manifestBase string, manifest *SnapshotManifest, state *SyncState, plan []PlanItem) error {
	remote := make(map[string]SnapshotMod)
	for _, m := range manifest.Mods {
		remote[m.ModID] = m
	}

	for _, item := range plan {
		// Emit structured UI log for intercepting
		fmt.Fprintf(opts.Out, "[ModStatus] %s|%s|%s|%s\n", item.Action, item.ModName, item.LocalState, item.Reason)

		switch item.Action {
		case ActionAdded, ActionUpdated:
			fmt.Fprintf(opts.Out, "[System_%s] %s - %s\n", item.Action, item.ModID, item.Reason)
			rm := remote[item.ModID]
			if err := applyRemoteMod(opts.Out, opts.ModPath, manifestBase, rm); err != nil {
				return fmt.Errorf("failed to apply mod %s: %w", item.ModID, err)
			}
			state.ManagedMods[item.ModID] = ManagedModInfo{
				LastAppliedSnapshotID:  manifest.SnapshotID,
				LastAppliedContentHash: rm.ContentHash,
				LastAppliedPackageSHA:  rm.PackageSHA,
			}
		case ActionDeleted:
			fmt.Fprintf(opts.Out, "[System_%s] %s - %s\n", item.Action, item.ModID, item.Reason)
			if err := os.RemoveAll(filepath.Join(opts.ModPath, item.ModID)); err != nil {
				return fmt.Errorf("failed to delete mod %s: %w", item.ModID, err)
			}
			delete(state.ManagedMods, item.ModID)
		case ActionNoOp:
			fmt.Fprintf(opts.Out, "[System_%s] %s - %s\n", item.Action, item.ModID, item.Reason)
			rm, ok := remote[item.ModID]
			if ok {
				state.ManagedMods[item.ModID] = ManagedModInfo{
					LastAppliedSnapshotID:  manifest.SnapshotID,
					LastAppliedContentHash: rm.ContentHash,
					LastAppliedPackageSHA:  rm.PackageSHA,
				}
			}
		case ActionKeptLocal, ActionUnmanaged:
			fmt.Fprintf(opts.Out, "[System_%s] %s - %s\n", item.Action, item.ModID, item.Reason)
		}
	}

	return nil
}

func applyRemoteMod(logOut io.Writer, modPath, manifestBase string, mod SnapshotMod) error {
	url := resolvePackageURL(manifestBase, mod.PackageURL)
	if logOut != nil {
		fmt.Fprintf(logOut, "  downloading %s\n", url)
	}
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("download failed with status %d: %s", resp.StatusCode, string(body))
	}

	tmpDir := filepath.Join(modPath, ".modsync_tmp")
	if err := os.MkdirAll(tmpDir, 0755); err != nil {
		return err
	}
	tmpZip := filepath.Join(tmpDir, mod.ModID+".zip")

	tmpFile, err := os.Create(tmpZip)
	if err != nil {
		return err
	}
	if _, err := io.Copy(tmpFile, resp.Body); err != nil {
		tmpFile.Close()
		return err
	}
	tmpFile.Close()

	sha, _, err := fileSHA256AndSize(tmpZip)
	if err != nil {
		return err
	}
	if !strings.EqualFold(sha, mod.PackageSHA) {
		return fmt.Errorf("package checksum mismatch for %s", mod.ModID)
	}
	if logOut != nil {
		fmt.Fprintf(logOut, "  checksum verified for %s\n", mod.ModID)
	}

	stagingRoot := filepath.Join(tmpDir, "staging", mod.ModID)
	if err := os.RemoveAll(stagingRoot); err != nil {
		return err
	}
	if err := os.MkdirAll(stagingRoot, 0755); err != nil {
		return err
	}
	if err := unzipTo(tmpZip, stagingRoot); err != nil {
		return err
	}

	stagedDir := filepath.Join(stagingRoot, mod.ModID)
	if _, err := os.Stat(stagedDir); os.IsNotExist(err) {
		stagedDir = stagingRoot
	}

	targetModDir := filepath.Join(modPath, mod.ModID)
	if err := os.RemoveAll(targetModDir); err != nil {
		return err
	}
	if err := os.Rename(stagedDir, targetModDir); err != nil {
		return err
	}
	if logOut != nil {
		fmt.Fprintf(logOut, "  installed to %s\n", targetModDir)
	}

	return nil
}

func resolvePackageURL(manifestBase, packageURL string) string {
	if strings.HasPrefix(packageURL, "http://") || strings.HasPrefix(packageURL, "https://") {
		return packageURL
	}
	return joinURL(manifestBase, packageURL)
}

func unzipTo(zipPath, dst string) error {
	zr, err := zip.OpenReader(zipPath)
	if err != nil {
		return err
	}
	defer zr.Close()

	for _, f := range zr.File {
		cleanName := filepath.Clean(f.Name)
		if strings.HasPrefix(cleanName, "..") {
			return fmt.Errorf("invalid zip path: %s", f.Name)
		}

		targetPath := filepath.Join(dst, cleanName)
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(targetPath, 0755); err != nil {
				return err
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(targetPath), 0755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		out, err := os.Create(targetPath)
		if err != nil {
			rc.Close()
			return err
		}
		if _, err := io.Copy(out, rc); err != nil {
			out.Close()
			rc.Close()
			return err
		}
		out.Close()
		rc.Close()
	}

	return nil
}

func printReport(w io.Writer, report *SyncReport) {
	fmt.Fprintf(w, "\nSync plan for snapshot: %s\n", report.SnapshotID)
	counts := map[ActionType]int{}
	for _, item := range report.Items {
		counts[item.Action]++
		fmt.Fprintf(w, "- %-14s %-30s %s\n", item.Action, item.ModID, item.Reason)
	}

	fmt.Fprintln(w, "\nSummary:")
	fmt.Fprintf(w, "  Added: %d\n", counts[ActionAdded])
	fmt.Fprintf(w, "  Updated: %d\n", counts[ActionUpdated])
	fmt.Fprintf(w, "  Deleted: %d\n", counts[ActionDeleted])
	fmt.Fprintf(w, "  KeptLocal: %d\n", counts[ActionKeptLocal])
	fmt.Fprintf(w, "  UnmanagedLocal: %d\n", counts[ActionUnmanaged])
	fmt.Fprintf(w, "  NoOp: %d\n", counts[ActionNoOp])
}
