package modsync

import (
	"archive/zip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

func RunPublish(opts PublishOptions) error {
	if opts.Out == nil {
		opts.Out = os.Stdout
	}
	if opts.OutDir == "" {
		opts.OutDir = filepath.Join(os.TempDir(), "eu5-modsync-publish")
	}

	if err := os.MkdirAll(opts.OutDir, 0755); err != nil {
		return fmt.Errorf("failed to create host out dir: %w", err)
	}

	fmt.Fprintf(opts.Out, "Publish started\n")
	fmt.Fprintf(opts.Out, "Source mod path: %s\n", opts.ModPath)
	fmt.Fprintf(opts.Out, "Output directory: %s\n", opts.OutDir)

	effectiveBaseURL := strings.TrimSpace(opts.BaseURL)
	if effectiveBaseURL == "" && opts.COSBucket != "" && opts.COSRegion != "" {
		effectiveBaseURL = buildCOSPublicBaseURL(opts.COSBucket, opts.COSRegion, opts.COSPrefix)
	}

	packagesDir := filepath.Join(opts.OutDir, "packages")
	if err := os.RemoveAll(packagesDir); err != nil {
		return fmt.Errorf("failed to clean packages dir: %w", err)
	}
	if err := os.MkdirAll(packagesDir, 0755); err != nil {
		return fmt.Errorf("failed to create packages dir: %w", err)
	}

	manifest, err := buildSnapshot(opts.ModPath, packagesDir, effectiveBaseURL)
	if err != nil {
		return err
	}

	manifestPath := filepath.Join(opts.OutDir, "snapshot.json")
	manifestBytes, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal snapshot manifest: %w", err)
	}
	if err := os.WriteFile(manifestPath, manifestBytes, 0644); err != nil {
		return fmt.Errorf("failed to write snapshot manifest: %w", err)
	}

	fmt.Fprintf(opts.Out, "Publish snapshot prepared: %s\n", manifestPath)
	fmt.Fprintf(opts.Out, "Packages directory: %s\n", packagesDir)
	fmt.Fprintf(opts.Out, "Snapshot ID: %s\n", manifest.SnapshotID)
	fmt.Fprintf(opts.Out, "Mods in snapshot: %d\n", len(manifest.Mods))
	for _, mod := range manifest.Mods {
		fmt.Fprintf(opts.Out, "  - %s: %d files, package %d bytes\n", mod.ModID, mod.FileCount, mod.PackageSize)
	}
	if effectiveBaseURL != "" {
		fmt.Fprintf(opts.Out, "Base URL for clients: %s\n", strings.TrimRight(effectiveBaseURL, "/"))
	}

	if opts.COSBucket != "" || opts.COSRegion != "" {
		if opts.COSSecretID == "" || opts.COSSecretKey == "" || opts.COSBucket == "" || opts.COSRegion == "" {
			return fmt.Errorf("COS upload requires --cos-secret-id, --cos-secret-key, --cos-bucket, and --cos-region")
		}
		fmt.Fprintf(opts.Out, "Uploading publish output to COS...\n")
		if err := uploadPublishOutputToCOS(opts, manifestPath, packagesDir); err != nil {
			return err
		}
		fmt.Fprintf(opts.Out, "Uploaded to COS bucket: %s (%s)\n", opts.COSBucket, opts.COSRegion)
		fmt.Fprintf(opts.Out, "Manifest URL: %s/snapshot.json\n", strings.TrimRight(buildCOSPublicBaseURL(opts.COSBucket, opts.COSRegion, opts.COSPrefix), "/"))
	}

	if opts.UploadCmd != "" {
		fmt.Fprintf(opts.Out, "Running upload command...\n")
		cmd := exec.Command("cmd", "/c", opts.UploadCmd)
		cmd.Env = append(os.Environ(),
			"MODSYNC_OUT_DIR="+opts.OutDir,
			"MODSYNC_SNAPSHOT_FILE="+manifestPath,
			"MODSYNC_PACKAGES_DIR="+packagesDir,
		)
		cmd.Stdout = opts.Out
		cmd.Stderr = opts.Out
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("upload command failed: %w", err)
		}
	}

	fmt.Fprintf(opts.Out, "Publish finished successfully\n")

	return nil
}

func buildSnapshot(modPath, packagesDir, baseURL string) (*SnapshotManifest, error) {
	entries, err := os.ReadDir(modPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read mod path %s: %w", modPath, err)
	}

	hostName, _ := os.Hostname()
	manifest := &SnapshotManifest{
		SchemaVersion: "1.0",
		SnapshotID:    fmt.Sprintf("snapshot-%d", os.Getpid()),
		GeneratedAt:   nowUTC(),
		HostName:      hostName,
		GameModRel:    "game/mod",
		Mods:          make([]SnapshotMod, 0),
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		if shouldIgnoreLocalModDir(entry.Name()) {
			continue
		}
		modID := entry.Name()
		modDir := filepath.Join(modPath, modID)
		modName := modID
		metaPath := filepath.Join(modDir, ".metadata", "metadata.json")
		if b, err := os.ReadFile(metaPath); err == nil {
			if name := extractModNameFromMetadataBytes(b); strings.TrimSpace(name) != "" {
				modName = strings.TrimSpace(name)
			}
		}

		contentHash, fileCount, err := computeDirectoryHash(modDir)
		if err != nil {
			return nil, fmt.Errorf("failed to hash mod %s: %w", modID, err)
		}

		packageName := modID + ".zip"
		packagePath := filepath.Join(packagesDir, packageName)
		if err := zipDirectoryWithTopLevel(modDir, modID, packagePath); err != nil {
			return nil, fmt.Errorf("failed to package mod %s: %w", modID, err)
		}

		pkgSHA, pkgSize, err := fileSHA256AndSize(packagePath)
		if err != nil {
			return nil, fmt.Errorf("failed to hash package %s: %w", packagePath, err)
		}

		manifest.Mods = append(manifest.Mods, SnapshotMod{
			ModID:       modID,
			DisplayName: modName,
			PackageURL:  buildPackageURL(baseURL, packageName),
			PackageSHA:  pkgSHA,
			PackageSize: pkgSize,
			ContentHash: contentHash,
			FileCount:   fileCount,
		})
	}

	sort.Slice(manifest.Mods, func(i, j int) bool {
		return manifest.Mods[i].ModID < manifest.Mods[j].ModID
	})

	snapshotSeed := manifest.GeneratedAt
	for _, mod := range manifest.Mods {
		snapshotSeed += mod.ModID + mod.ContentHash + mod.PackageSHA
	}
	sum := sha256.Sum256([]byte(snapshotSeed))
	manifest.SnapshotID = "snapshot-" + hex.EncodeToString(sum[:8])

	return manifest, nil
}

func buildPackageURL(baseURL, packageName string) string {
	rel := "packages/" + url.PathEscape(packageName)
	if strings.TrimSpace(baseURL) == "" {
		return rel
	}
	return strings.TrimRight(baseURL, "/") + "/" + rel
}

func zipDirectoryWithTopLevel(srcDir, topLevelName, dstZip string) error {
	f, err := os.Create(dstZip)
	if err != nil {
		return err
	}
	defer f.Close()

	zw := zip.NewWriter(f)
	defer zw.Close()

	return filepath.Walk(srcDir, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		rel, err := filepath.Rel(srcDir, path)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}

		zipPath := filepath.ToSlash(filepath.Join(topLevelName, rel))
		if info.IsDir() {
			_, err := zw.Create(zipPath + "/")
			return err
		}

		header, err := zip.FileInfoHeader(info)
		if err != nil {
			return err
		}
		header.Name = zipPath
		header.Method = zip.Deflate

		w, err := zw.CreateHeader(header)
		if err != nil {
			return err
		}

		r, err := os.Open(path)
		if err != nil {
			return err
		}
		defer r.Close()

		_, err = io.Copy(w, r)
		return err
	})
}

func computeDirectoryHash(dir string) (string, int, error) {
	var files []string
	err := filepath.Walk(dir, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if info.IsDir() {
			return nil
		}
		files = append(files, path)
		return nil
	})
	if err != nil {
		return "", 0, err
	}

	sort.Strings(files)
	h := sha256.New()
	for _, f := range files {
		rel, err := filepath.Rel(dir, f)
		if err != nil {
			return "", 0, err
		}
		st, err := os.Stat(f)
		if err != nil {
			return "", 0, err
		}
		fh, _, err := fileSHA256AndSize(f)
		if err != nil {
			return "", 0, err
		}
		line := fmt.Sprintf("%s|%d|%s\n", filepath.ToSlash(rel), st.Size(), fh)
		if _, err := h.Write([]byte(line)); err != nil {
			return "", 0, err
		}
	}

	return hex.EncodeToString(h.Sum(nil)), len(files), nil
}

func fileSHA256AndSize(path string) (string, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()

	h := sha256.New()
	n, err := io.Copy(h, f)
	if err != nil {
		return "", 0, err
	}

	return hex.EncodeToString(h.Sum(nil)), n, nil
}

func joinURL(baseURL, maybeRelative string) string {
	if strings.HasPrefix(maybeRelative, "http://") || strings.HasPrefix(maybeRelative, "https://") {
		return maybeRelative
	}
	base := strings.TrimRight(baseURL, "/")
	rel := strings.TrimLeft(maybeRelative, "/")
	return base + "/" + rel
}
