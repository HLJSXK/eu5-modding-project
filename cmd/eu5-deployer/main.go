package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/HLJSXK/eu5-modding-project/pkg/deployer"
	"github.com/HLJSXK/eu5-modding-project/pkg/detector"
)

// setupLogger creates a log file next to the executable and returns a writer
// that mirrors all output to both stdout and the log file.
// It returns the log file handle (caller must close it) and the tee writer.
func setupLogger(exeDir string) (*os.File, io.Writer) {
	logPath := filepath.Join(exeDir, "eu5-deployer.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		// If we can't create the log file, just use stdout
		fmt.Printf("Warning: Could not create log file at %s: %v\n", logPath, err)
		return nil, os.Stdout
	}
	// Write a session header so multiple runs are easy to distinguish
	fmt.Fprintf(logFile, "\n========================================\n")
	fmt.Fprintf(logFile, "Session started: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(logFile, "========================================\n")

	tee := io.MultiWriter(os.Stdout, logFile)
	return logFile, tee
}

// logf writes a formatted message to the tee writer (stdout + log file).
func logf(w io.Writer, format string, args ...interface{}) {
	fmt.Fprintf(w, format, args...)
}

func main() {
	// Parse command line flags
	projectRootFlag := flag.String("project-root", "", "Path to project root (directory containing goldberg_emulator)")
	eu5PathFlag := flag.String("eu5-path", "", "Path to EU5 installation directory")
	restoreFlag := flag.Bool("restore", false, "Restore original files from backup")
	accountNameFlag := flag.String("account-name", "EU5Player", "Steam account name to use in emulator")
	steamIDFlag := flag.String("steam-id", "76561197960287930", "Steam ID to use in emulator (17 digits)")
	flag.Parse()

	// Resolve executable path (use os.Executable for the real path, not a symlink)
	exePath, err := os.Executable()
	if err != nil {
		fmt.Printf("Error: Failed to get executable path: %v\n", err)
		os.Exit(1)
	}
	exeDir := filepath.Dir(exePath)

	// Set up logging – all subsequent output goes through `out`
	logFile, out := setupLogger(exeDir)
	if logFile != nil {
		defer logFile.Close()
	}

	logf(out, "Executable path : %s\n", exePath)
	logf(out, "Working directory: %s\n", func() string { d, _ := os.Getwd(); return d }())

	// ----------------------------------------------------------------
	// Locate project root (where goldberg_emulator/ lives)
	// ----------------------------------------------------------------
	projectRoot, err := resolveProjectRoot(*projectRootFlag, exeDir, out)
	if err != nil {
		logf(out, "\nError: %v\n", err)
		logf(out, "\nTips:\n")
		logf(out, "  - If running via go run, set --project-root to your repository root\n")
		logf(out, "  - Example: %s --project-root \"%s\"\n", filepath.Base(exePath), func() string { d, _ := os.Getwd(); return d }())
		logf(out, "Log saved to: %s\n", filepath.Join(exeDir, "eu5-deployer.log"))
		pause()
		os.Exit(1)
	}
	logf(out, "Project root    : %s\n", projectRoot)

	// ----------------------------------------------------------------
	// Locate EU5 installation
	// ----------------------------------------------------------------
	var eu5Path string
	if *eu5PathFlag != "" {
		eu5Path = *eu5PathFlag
		logf(out, "EU5 path (manual): %s\n", eu5Path)
	} else {
		logf(out, "\nNo EU5 path specified, attempting auto-detection...\n")
		d := detector.NewDetector()
		detectedPath, err := d.DetectWithWriter(out)
		if err != nil {
			logf(out, "\n✗ Could not auto-detect EU5 installation.\n")
			logf(out, "Error detail: %v\n", err)
			logf(out, "\nPlease specify path with --eu5-path flag:\n")
			logf(out, "  %s --eu5-path \"C:\\Path\\To\\Europa Universalis V\"\n", filepath.Base(exePath))
			logf(out, "\nLog saved to: %s\n", filepath.Join(exeDir, "eu5-deployer.log"))
			pause()
			os.Exit(1)
		}
		eu5Path = detectedPath
	}

	// ----------------------------------------------------------------
	// Create deployer and execute
	// ----------------------------------------------------------------
	d := deployer.NewDeployerWithWriter(projectRoot, eu5Path, out)

	var actionErr error
	if *restoreFlag {
		actionErr = d.Restore()
	} else {
		logf(out, "\n[Step 0/4] Configuring Steam emulator settings...\n")
		if err := d.ConfigureSteamSettings(*accountNameFlag, *steamIDFlag); err != nil {
			logf(out, "\n✗ Error configuring Steam settings: %v\n", err)
			logf(out, "Log saved to: %s\n", filepath.Join(exeDir, "eu5-deployer.log"))
			pause()
			os.Exit(1)
		}
		actionErr = d.Deploy()
	}

	if actionErr != nil {
		logf(out, "\n✗ Error: %v\n", actionErr)
		logf(out, "Log saved to: %s\n", filepath.Join(exeDir, "eu5-deployer.log"))
		pause()
		os.Exit(1)
	}

	logf(out, "\nLog saved to: %s\n", filepath.Join(exeDir, "eu5-deployer.log"))
	pause()
}

// resolveProjectRoot finds the directory containing goldberg_emulator.
// It supports explicit --project-root and several fallbacks for go run and built binaries.
func resolveProjectRoot(projectRootFlag, exeDir string, out io.Writer) (string, error) {
	if projectRootFlag != "" {
		absPath, err := filepath.Abs(projectRootFlag)
		if err != nil {
			return "", fmt.Errorf("invalid --project-root path: %w", err)
		}
		if hasGoldbergDir(absPath) {
			logf(out, "Using project root from flag: %s\n", absPath)
			return absPath, nil
		}
		return "", fmt.Errorf("--project-root does not contain goldberg_emulator: %s", absPath)
	}

	if root, ok := findRootUpward(exeDir, 4); ok {
		logf(out, "Resolved project root from executable location: %s\n", root)
		return root, nil
	}

	if cwd, err := os.Getwd(); err == nil {
		if root, ok := findRootUpward(cwd, 8); ok {
			logf(out, "Resolved project root from working directory: %s\n", root)
			return root, nil
		}
	}

	if _, currentFile, _, ok := runtime.Caller(0); ok {
		sourceDir := filepath.Dir(currentFile)
		if root, ok := findRootUpward(sourceDir, 8); ok {
			logf(out, "Resolved project root from source file location: %s\n", root)
			return root, nil
		}
	}

	return "", fmt.Errorf("cannot find goldberg_emulator folder")
}

func findRootUpward(start string, maxDepth int) (string, bool) {
	cur := start
	for i := 0; i <= maxDepth; i++ {
		if hasGoldbergDir(cur) {
			return cur, true
		}
		parent := filepath.Dir(cur)
		if parent == cur {
			break
		}
		cur = parent
	}
	return "", false
}

func hasGoldbergDir(root string) bool {
	if root == "" {
		return false
	}
	path := filepath.Join(root, "goldberg_emulator")
	stat, err := os.Stat(path)
	if err != nil {
		return false
	}
	return stat.IsDir()
}

// pause keeps the console window open when the program is double-clicked on Windows.
// It reads a single byte from stdin so the user can see the output before the window closes.
func pause() {
	fmt.Print("\nPress Enter to exit...")
	buf := make([]byte, 1)
	os.Stdin.Read(buf) //nolint:errcheck
}
