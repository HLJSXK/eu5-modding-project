package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/HLJSXK/eu5-modding-project/pkg/modsync"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	sub := os.Args[1]
	switch sub {
	case "publish":
		runPublish(os.Args[2:])
	case "sync":
		runSync(os.Args[2:])
	default:
		fmt.Printf("Unknown subcommand: %s\n", sub)
		printUsage()
		os.Exit(1)
	}
}

func runPublish(args []string) {
	fs := flag.NewFlagSet("publish", flag.ExitOnError)
	modPath := fs.String("mod-path", "", "Path to EU5 game mod directory")
	outDir := fs.String("out", ".modsync_publish", "Publish output directory")
	baseURL := fs.String("base-url", "", "Public base URL where snapshot.json and packages/ are hosted")
	uploadCmd := fs.String("upload-cmd", "", "Optional upload command (runs via cmd /c) with MODSYNC_* env vars")
	cosSecretID := fs.String("cos-secret-id", "", "Tencent COS SecretId (or env TENCENT_SECRET_ID)")
	cosSecretKey := fs.String("cos-secret-key", "", "Tencent COS SecretKey (or env TENCENT_SECRET_KEY)")
	cosBucket := fs.String("cos-bucket", "", "Tencent COS bucket name (e.g. mybucket-1250000000)")
	cosRegion := fs.String("cos-region", "", "Tencent COS region (e.g. ap-shanghai)")
	cosPrefix := fs.String("cos-prefix", "modsync", "COS object prefix")
	fs.Parse(args)

	if *cosSecretID == "" {
		*cosSecretID = os.Getenv("TENCENT_SECRET_ID")
	}
	if *cosSecretKey == "" {
		*cosSecretKey = os.Getenv("TENCENT_SECRET_KEY")
	}

	if *modPath == "" {
		defaultPath, err := modsync.ResolveDefaultModPath()
		if err == nil {
			*modPath = defaultPath
		}
	}

	if *modPath == "" {
		fmt.Println("Error: --mod-path is required")
		os.Exit(1)
	}

	err := modsync.RunPublish(modsync.PublishOptions{
		ModPath:      *modPath,
		OutDir:       *outDir,
		BaseURL:      *baseURL,
		UploadCmd:    *uploadCmd,
		Out:          os.Stdout,
		COSSecretID:  *cosSecretID,
		COSSecretKey: *cosSecretKey,
		COSBucket:    *cosBucket,
		COSRegion:    *cosRegion,
		COSPrefix:    *cosPrefix,
	})
	if err != nil {
		fmt.Printf("Publish error: %v\n", err)
		os.Exit(1)
	}
}

func runSync(args []string) {
	fs := flag.NewFlagSet("sync", flag.ExitOnError)
	manifestURL := fs.String("manifest-url", "", "Manifest URL, e.g. https://cdn.example.com/modsync/snapshot.json")
	modPath := fs.String("mod-path", "", "Path to EU5 game mod directory")
	dryRun := fs.Bool("dry-run", false, "Preview actions without changing files")
	deleteManaged := fs.Bool("delete-managed-missing", true, "Delete managed local mods that are missing in remote snapshot")
	fs.Parse(args)

	if *modPath == "" {
		defaultPath, err := modsync.ResolveDefaultModPath()
		if err == nil {
			*modPath = defaultPath
		}
	}

	err := modsync.RunSync(modsync.SyncOptions{
		ManifestURL:          *manifestURL,
		ModPath:              *modPath,
		DryRun:               *dryRun,
		DeleteManagedMissing: *deleteManaged,
		Out:                  os.Stdout,
	})
	if err != nil {
		fmt.Printf("Sync error: %v\n", err)
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("eu5-modsync - async publish/sync tool for EU5 mods")
	fmt.Println("")
	fmt.Println("Usage:")
	fmt.Println("  eu5-modsync publish --mod-path \"C:/.../Europa Universalis V/game/mod\" --out .modsync_publish --base-url \"https://cdn.example.com/modsync\"")
	fmt.Println("  eu5-modsync publish --mod-path \"C:/.../game/mod\" --cos-bucket mybucket-1250000000 --cos-region ap-shanghai --cos-prefix modsync")
	fmt.Println("  eu5-modsync sync --manifest-url \"https://cdn.example.com/modsync/snapshot.json\" --mod-path \"C:/.../Europa Universalis V/game/mod\"")
}
