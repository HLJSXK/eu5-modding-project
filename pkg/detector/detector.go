package detector

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
)

// EU5Detector handles detection of EU5 installation
type EU5Detector struct {
	System string
}

// NewDetector creates a new EU5Detector
func NewDetector() *EU5Detector {
	return &EU5Detector{
		System: runtime.GOOS,
	}
}

// GetCommonSteamPaths returns common Steam installation paths for the current OS
func (d *EU5Detector) GetCommonSteamPaths() []string {
	switch d.System {
	case "windows":
		return []string{
			`C:\Program Files (x86)\Steam`,
			`C:\Program Files\Steam`,
			`D:\Steam`,
			`E:\Steam`,
			`F:\Steam`,
			`D:\SteamLibrary`,
			`E:\SteamLibrary`,
			`F:\SteamLibrary`,
		}
	case "linux":
		homeDir, _ := os.UserHomeDir()
		return []string{
			filepath.Join(homeDir, ".steam", "steam"),
			filepath.Join(homeDir, ".local", "share", "Steam"),
			"/usr/share/steam",
		}
	case "darwin": // macOS
		homeDir, _ := os.UserHomeDir()
		return []string{
			filepath.Join(homeDir, "Library", "Application Support", "Steam"),
		}
	default:
		return []string{}
	}
}

// ParseLibraryFolders parses Steam's libraryfolders.vdf to find all library locations
func (d *EU5Detector) ParseLibraryFolders(steamPath string) []string {
	libraries := []string{steamPath}

	vdfPath := filepath.Join(steamPath, "steamapps", "libraryfolders.vdf")
	if _, err := os.Stat(vdfPath); os.IsNotExist(err) {
		return libraries
	}

	file, err := os.Open(vdfPath)
	if err != nil {
		return libraries
	}
	defer file.Close()

	// Pattern to match: "path"		"D:\\SteamLibrary"
	pathPattern := regexp.MustCompile(`"path"\s+"([^"]+)"`)

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		matches := pathPattern.FindStringSubmatch(line)
		if len(matches) > 1 {
			// Convert Windows path separators
			libPath := strings.ReplaceAll(matches[1], `\\`, string(filepath.Separator))
			if _, err := os.Stat(libPath); err == nil {
				libraries = append(libraries, libPath)
			}
		}
	}

	return libraries
}

// FindEU5InLibrary searches for EU5 installation in a Steam library folder
func (d *EU5Detector) FindEU5InLibrary(libraryPath string) (string, error) {
	possiblePaths := []string{
		filepath.Join(libraryPath, "steamapps", "common", "Europa Universalis V"),
		filepath.Join(libraryPath, "SteamApps", "common", "Europa Universalis V"),
	}

	for _, path := range possiblePaths {
		if _, err := os.Stat(path); err == nil {
			// Verify it's actually EU5 by checking for binaries folder
			binariesPath := filepath.Join(path, "binaries")
			if _, err := os.Stat(binariesPath); err == nil {
				// Check for steam_api64.dll or EU5 executable
				dllPath := filepath.Join(binariesPath, "steam_api64.dll")
				if _, err := os.Stat(dllPath); err == nil {
					return path, nil
				}
				
				// Check for any eu5*.exe files (Windows)
				if d.System == "windows" {
					matches, _ := filepath.Glob(filepath.Join(binariesPath, "eu5*.exe"))
					if len(matches) > 0 {
						return path, nil
					}
				}
			}
		}
	}

	return "", fmt.Errorf("EU5 not found in library: %s", libraryPath)
}

// Detect attempts to find EU5 installation
func (d *EU5Detector) Detect() (string, error) {
	fmt.Printf("Detecting EU5 installation on %s...\n", d.System)

	steamPaths := d.GetCommonSteamPaths()

	for _, steamPath := range steamPaths {
		if _, err := os.Stat(steamPath); os.IsNotExist(err) {
			continue
		}

		fmt.Printf("Checking Steam library: %s\n", steamPath)

		// Get all library folders from this Steam installation
		libraries := d.ParseLibraryFolders(steamPath)

		// Search each library for EU5
		for _, library := range libraries {
			eu5Path, err := d.FindEU5InLibrary(library)
			if err == nil {
				fmt.Printf("\n✓ Found EU5 installation: %s\n", eu5Path)
				return eu5Path, nil
			}
		}
	}

	return "", fmt.Errorf("EU5 installation not found")
}

// GetBinariesPath returns the binaries folder path
func (d *EU5Detector) GetBinariesPath(eu5Path string) string {
	return filepath.Join(eu5Path, "binaries")
}
