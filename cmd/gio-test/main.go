package main

import (
	"log"

	"gioui.org/app"
	"gioui.org/op"
	"gioui.org/widget/material"
)

func main() {
	go func() {
		w := new(app.Window)
		err := run(w)
		if err != nil {
			log.Fatal(err)
		}
	}()
	app.Main()
}

func run(w *app.Window) error {
	th := material.NewTheme()
	var ops op.Ops
	for {
		switch e := w.Event().(type) {
		case app.DestroyEvent:
			return e.Err
		case app.FrameEvent:
			// gtx := app.NewContext(&ops, e)
			// Draw
			e.Frame(&ops)
		}
	}
}
