package main

import (
	"log"

	"github.com/zserge/lorca"
)

func main() {
	ui, err := lorca.New("data:text/html,<html><body><h1>Hello World</h1></body></html>", "", 480, 320, "--incognito")
	if err != nil {
		log.Fatal(err)
	}
	defer ui.Close()
	<-ui.Done()
}
