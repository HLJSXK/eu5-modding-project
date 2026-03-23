//go:build !windows

package main

import "fmt"

func main() {
	fmt.Println("eu5-sync-ui is only supported on Windows.")
}
