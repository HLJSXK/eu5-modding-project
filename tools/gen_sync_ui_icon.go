package main

import (
	"flag"
	"image"
	"image/color"
	"image/png"
	"math"
	"os"
	"path/filepath"
)

func main() {
	out := flag.String("out", "build/sync-ui-icon.png", "output icon png path")
	flag.Parse()

	if err := os.MkdirAll(filepath.Dir(*out), 0755); err != nil {
		panic(err)
	}

	img := image.NewRGBA(image.Rect(0, 0, 256, 256))

	bg1 := color.RGBA{20, 36, 64, 255}
	bg2 := color.RGBA{14, 22, 40, 255}
	for y := 0; y < 256; y++ {
		t := float64(y) / 255.0
		c := lerp(bg1, bg2, t)
		for x := 0; x < 256; x++ {
			img.SetRGBA(x, y, c)
		}
	}

	// Soft rounded highlight
	for y := 0; y < 256; y++ {
		for x := 0; x < 256; x++ {
			dx := float64(x - 80)
			dy := float64(y - 72)
			d := math.Sqrt(dx*dx + dy*dy)
			if d < 80 {
				a := uint8((80 - d) * 0.8)
				blend(img, x, y, color.RGBA{90, 170, 255, a})
			}
		}
	}

	accent := color.RGBA{122, 235, 255, 255}
	shadow := color.RGBA{0, 0, 0, 100}

	// Two sync arcs + arrow heads.
	drawArc(img, 128, 128, 70, 42, 320, shadow, 2, 2)
	drawArc(img, 128, 128, 70, 42, 320, accent, 0, 0)
	drawTriangle(img, 183, 82, 200, 74, 188, 98, accent)

	drawArc(img, 128, 128, 70, 220, 140, shadow, 2, 2)
	drawArc(img, 128, 128, 70, 220, 140, accent, 0, 0)
	drawTriangle(img, 73, 175, 56, 183, 68, 159, accent)

	f, err := os.Create(*out)
	if err != nil {
		panic(err)
	}
	defer f.Close()

	if err := png.Encode(f, img); err != nil {
		panic(err)
	}
}

func lerp(a, b color.RGBA, t float64) color.RGBA {
	return color.RGBA{
		R: uint8(float64(a.R)*(1-t) + float64(b.R)*t),
		G: uint8(float64(a.G)*(1-t) + float64(b.G)*t),
		B: uint8(float64(a.B)*(1-t) + float64(b.B)*t),
		A: 255,
	}
}

func blend(img *image.RGBA, x, y int, src color.RGBA) {
	if !image.Pt(x, y).In(img.Bounds()) {
		return
	}
	dst := img.RGBAAt(x, y)
	a := float64(src.A) / 255.0
	inva := 1.0 - a
	img.SetRGBA(x, y, color.RGBA{
		R: uint8(float64(src.R)*a + float64(dst.R)*inva),
		G: uint8(float64(src.G)*a + float64(dst.G)*inva),
		B: uint8(float64(src.B)*a + float64(dst.B)*inva),
		A: 255,
	})
}

func drawArc(img *image.RGBA, cx, cy, r int, degStart, degEnd float64, c color.RGBA, offX, offY int) {
	if degEnd < degStart {
		degEnd += 360
	}
	for t := degStart; t <= degEnd; t += 0.5 {
		rad := t * math.Pi / 180.0
		x := cx + int(math.Round(float64(r)*math.Cos(rad))) + offX
		y := cy + int(math.Round(float64(r)*math.Sin(rad))) + offY
		for dy := -3; dy <= 3; dy++ {
			for dx := -3; dx <= 3; dx++ {
				if dx*dx+dy*dy <= 9 {
					blend(img, x+dx, y+dy, c)
				}
			}
		}
	}
}

func drawTriangle(img *image.RGBA, x1, y1, x2, y2, x3, y3 int, c color.RGBA) {
	minX, maxX := min3(x1, x2, x3), max3(x1, x2, x3)
	minY, maxY := min3(y1, y2, y3), max3(y1, y2, y3)
	for y := minY; y <= maxY; y++ {
		for x := minX; x <= maxX; x++ {
			if inTriangle(float64(x), float64(y), float64(x1), float64(y1), float64(x2), float64(y2), float64(x3), float64(y3)) {
				blend(img, x, y, c)
			}
		}
	}
}

func inTriangle(px, py, ax, ay, bx, by, cx, cy float64) bool {
	v0x, v0y := cx-ax, cy-ay
	v1x, v1y := bx-ax, by-ay
	v2x, v2y := px-ax, py-ay

	dot00 := v0x*v0x + v0y*v0y
	dot01 := v0x*v1x + v0y*v1y
	dot02 := v0x*v2x + v0y*v2y
	dot11 := v1x*v1x + v1y*v1y
	dot12 := v1x*v2x + v1y*v2y

	invDenom := 1.0 / (dot00*dot11 - dot01*dot01)
	u := (dot11*dot02 - dot01*dot12) * invDenom
	v := (dot00*dot12 - dot01*dot02) * invDenom
	return u >= 0 && v >= 0 && u+v < 1
}

func min3(a, b, c int) int {
	if a < b {
		if a < c {
			return a
		}
		return c
	}
	if b < c {
		return b
	}
	return c
}

func max3(a, b, c int) int {
	if a > b {
		if a > c {
			return a
		}
		return c
	}
	if b > c {
		return b
	}
	return c
}
