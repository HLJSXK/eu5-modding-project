package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/HLJSXK/eu5-modding-project/pkg/deployer"
	"github.com/HLJSXK/eu5-modding-project/pkg/detector"
)

func main() {
	// Parse command line flags
	eu5PathFlag := flag.String("eu5-path", "", "Path to EU5 installation directory")
	restoreFlag := flag.Bool("restore", false, "Restore original files from backup")
	flag.Parse()

	// Get project root (executable directory or parent of cmd)
	exePath, err := os.Executable()
	if err != nil {
		fmt.Printf("Error: Failed to get executable path: %v\n", err)
		os.Exit(1)
	}

	// Assume executable is in project root or in a subdirectory
	projectRoot := filepath.Dir(exePath)
	
	// Check if we're in a build output directory, if so go up
	if filepath.Base(projectRoot) == "bin" || filepath.Base(projectRoot) == "build" {
		projectRoot = filepath.Dir(projectRoot)
	}

	// If goldberg_emulator doesn't exist in current dir, try parent
	goldbergPath := filepath.Join(projectRoot, "goldberg_emulator")
	if _, err := os.Stat(goldbergPath); os.IsNotExist(err) {
		// Try parent directory
		projectRoot = filepath.Dir(projectRoot)
		goldbergPath = filepath.Join(projectRoot, "goldberg_emulator")
		if _, err := os.Stat(goldbergPath); os.IsNotExist(err) {
			fmt.Println("Error: Cannot find goldberg_emulator folder.")
			fmt.Printf("Searched in: %s\n", projectRoot)
			fmt.Println("\nPlease run this tool from the project directory or")
			fmt.Println("ensure goldberg_emulator folder is in the same directory as the executable.")
			os.Exit(1)
		}
	}

	// Get EU5 path
	var eu5Path string
	if *eu5PathFlag != "" {
		eu5Path = *eu5PathFlag
	} else {
		// Try to auto-detect
		fmt.Println("No EU5 path specified, attempting auto-detection...")
		d := detector.NewDetector()
		detectedPath, err := d.Detect()
		if err != nil {
			fmt.Println("\n✗ Could not auto-detect EU5 installation.")
			fmt.Println("Please specify path with --eu5-path flag.")
			fmt.Printf("\nUsage: %s --eu5-path \"C:\\Path\\To\\Europa Universalis V\"\n", filepath.Base(exePath))
			os.Exit(1)
		}
		eu5Path = detectedPath
	}

	// Create deployer
	d := deployer.NewDeployer(projectRoot, eu5Path)

	// Execute action
	var actionErr error
	if *restoreFlag {
		actionErr = d.Restore()
	} else {
		actionErr = d.Deploy()
	}

	if actionErr != nil {
		fmt.Printf("\n✗ Error: %v\n", actionErr)
		os.Exit(1)
	}
}
