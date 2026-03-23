package main

import (
	"log"

	"github.com/jchv/go-webview2"
)

func main() {
	w := webview2.New(true)
	if w == nil {
		log.Println("Failed to load webview.")
		return
	}
	defer w.Destroy()
	w.SetTitle("Minimal webview example")
	w.SetSize(800, 600, webview2.HintNone)
	w.Navigate("https://en.m.wikipedia.org/wiki/Main_Page")
	w.Run()
}
