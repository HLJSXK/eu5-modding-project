package main

import (
	"fmt"
	"os"

	"github.com/HLJSXK/eu5-modding-project/pkg/detector"
)

func main() {
	d := detector.NewDetector()

	eu5Path, err := d.Detect()
	if err != nil {
		fmt.Println("\n✗ EU5 installation not found.")
		fmt.Println("\nSearched locations:")
		for _, path := range d.GetCommonSteamPaths() {
			fmt.Printf("  - %s\n", path)
		}
		fmt.Println("\nPlease ensure European Universalis V is installed via Steam.")
		os.Exit(1)
	}

	binariesPath := d.GetBinariesPath(eu5Path)
	fmt.Printf("\nEU5 Main Folder: %s\n", eu5Path)
	fmt.Printf("Binaries Folder: %s\n", binariesPath)

	// Output machine-readable format for scripting
	fmt.Printf("\n__EU5_PATH__=%s\n", eu5Path)
	fmt.Printf("__BINARIES_PATH__=%s\n", binariesPath)
}
