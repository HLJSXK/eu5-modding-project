//go:build windows

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"

	_ "embed"

	"github.com/HLJSXK/eu5-modding-project/pkg/deployer"
	"github.com/HLJSXK/eu5-modding-project/pkg/detector"
	"github.com/HLJSXK/eu5-modding-project/pkg/modsync"
	"github.com/jchv/go-webview2"
)

//go:embed ui.html
var uiHTML string

type AppConfig struct {
	ManifestURL          string `json:"manifest_url"`
	ProjectRoot          string `json:"project_root"`
	EU5Path              string `json:"eu5_path"`
	ModPath              string `json:"mod_path"`
	AccountName          string `json:"account_name"`
	SteamID              string `json:"steam_id"`
	DeleteManagedMissing bool   `json:"delete_managed_missing"`
}

type SyncManager struct {
	mu      sync.Mutex
	running bool
	done    bool
	runID   int
	lastErr string
	logBuf  bytes.Buffer
	ops     []ModRecord
	fullLog string
	stats   SyncStats
	config  AppConfig
	cfgPath string
}

type ModRecord struct {
	Name   string
	Local  string
	Action string
}

type UIState struct {
	IsDone    bool
	LastError string
	TotalOps  int
	Added     int
	Updated   int
	Deleted   int
	Ops       []ModRecord
	FullLog   string
}

type SyncStats struct {
	Added     int
	Updated   int
	Deleted   int
	KeptLocal int
	Unmanaged int
	NoOp      int
}

type modStatusPayload struct {
	Action     string `json:"action"`
	ModID      string `json:"mod_id"`
	ModName    string `json:"mod_name"`
	LocalState string `json:"local_state"`
	Reason     string `json:"reason"`
}

type workflowWriter struct {
	m       *SyncManager
	partial string
}

func (w *workflowWriter) Write(p []byte) (int, error) {
	w.m.mu.Lock()
	n, err := w.m.logBuf.Write(p)

	w.partial += string(p)
	for {
		idx := strings.IndexByte(w.partial, '\n')
		if idx < 0 {
			break
		}
		line := strings.TrimSpace(w.partial[:idx])
		w.partial = w.partial[idx+1:]
		parseAndAppendOperationLocked(w.m, line)
	}
	w.m.mu.Unlock()
	return n, err
}

func parseAndAppendOperationLocked(m *SyncManager, line string) {
	if line == "" {
		return
	}
	m.fullLog += line + "\n"

	if strings.HasPrefix(line, "[ModStatusJSON] ") {
		content := strings.TrimSpace(line[len("[ModStatusJSON] "):])
		var p modStatusPayload
		if err := json.Unmarshal([]byte(content), &p); err == nil {
			name := strings.TrimSpace(p.ModName)
			if name == "" {
				name = strings.TrimSpace(p.ModID)
			}
			if name == "" {
				name = "(unknown mod)"
			}

			record := ModRecord{
				Action: strings.TrimSpace(p.Action),
				Name:   name,
				Local:  strings.TrimSpace(p.LocalState),
			}
			m.ops = append(m.ops, record)

			switch record.Action {
			case "Added":
				m.stats.Added++
			case "Updated":
				m.stats.Updated++
			case "Deleted":
				m.stats.Deleted++
			}
		}
		return
	}

	// Parse [ModStatus] markers emitted by applyPlan
	// format: [ModStatus] Action|ModName|LocalState|Reason
	if strings.HasPrefix(line, "[ModStatus] ") {
		content := strings.TrimSpace(line[len("[ModStatus] "):])
		parts := strings.SplitN(content, "|", 4)
		if len(parts) >= 3 {
			name := strings.TrimSpace(parts[1])
			if name == "" {
				name = "(unknown mod)"
			}

			record := ModRecord{
				Action: strings.TrimSpace(parts[0]),
				Name:   name,
				Local:  strings.TrimSpace(parts[2]),
			}
			m.ops = append(m.ops, record)

			switch record.Action {
			case "Added":
				m.stats.Added++
			case "Updated":
				m.stats.Updated++
			case "Deleted":
				m.stats.Deleted++
			}
		}
	}
}

func main() {
	// Prepare logs
	log.SetFlags(log.LstdFlags | log.Lshortfile)

	exePath, err := os.Executable()
	if err != nil {
		log.Fatalf("Failed to get executable path: %v", err)
	}
	exeDir := filepath.Dir(exePath)
	cfgPath := filepath.Join(exeDir, "eu5-sync-ui-config.json")
	cfg := defaultConfig()
	loadConfig(cfgPath, &cfg)

	mgr := &SyncManager{
		config:  cfg,
		cfgPath: cfgPath,
	}

	// Create Webview2 UI
	w := webview2.New(false)
	if w == nil {
		log.Fatalf("无法加载 WebView2，请确保系统已安装 Microsoft Edge WebView2 运行时")
	}
	defer w.Destroy()

	w.SetTitle("EU5 Sync")
	w.SetSize(900, 700, webview2.HintNone)

	// Bind Go functions to JS
	w.Bind("goLoadConfig", func() AppConfig {
		mgr.mu.Lock()
		defer mgr.mu.Unlock()
		return mgr.config
	})

	w.Bind("goSaveConfig", func(c AppConfig) string {
		mgr.mu.Lock()
		mgr.config = c
		mgr.mu.Unlock()

		err := saveConfig(mgr.cfgPath, c)
		if err != nil {
			return err.Error()
		}
		return ""
	})

	w.Bind("goStartSync", func() {
		mgr.mu.Lock()
		if mgr.running {
			mgr.mu.Unlock()
			return
		}
		mgr.running = true
		mgr.done = false
		mgr.lastErr = ""
		mgr.ops = nil
		mgr.fullLog = ""
		mgr.stats = SyncStats{}
		mgr.logBuf.Reset()
		mgr.runID++
		mgr.mu.Unlock()

		go func() {
			err := runSyncWorkflow(mgr)
			mgr.mu.Lock()
			mgr.running = false
			mgr.done = true
			if err != nil {
				mgr.lastErr = err.Error()
				// manually inject error row
				op := ModRecord{
					Action: "Error",
					Name:   "Sync Workflow",
					Local:  err.Error(),
				}
				mgr.ops = append(mgr.ops, op)
			}
			mgr.mu.Unlock()
		}()
	})

	w.Bind("goGetStatus", func() UIState {
		mgr.mu.Lock()
		defer mgr.mu.Unlock()

		return UIState{
			IsDone:    mgr.done,
			LastError: mgr.lastErr,
			TotalOps:  len(mgr.ops),
			Added:     mgr.stats.Added,
			Updated:   mgr.stats.Updated,
			Deleted:   mgr.stats.Deleted,
			Ops:       mgr.ops,
			FullLog:   mgr.fullLog,
		}
	})

	w.SetHtml(uiHTML)
	w.Run()
}

func defaultConfig() AppConfig {
	return AppConfig{
		ManifestURL:          "https://eu5-1300742092.cos.ap-guangzhou.myqcloud.com/modsync/snapshot.json",
		AccountName:          "EU5Player",
		SteamID:              "76561197960287930",
		DeleteManagedMissing: true,
	}
}

func loadConfig(path string, cfg *AppConfig) {
	b, err := os.ReadFile(path)
	if err != nil {
		return
	}
	_ = json.Unmarshal(b, cfg)
}

func saveConfig(path string, cfg AppConfig) error {
	b, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0644)
}

func runSyncWorkflow(m *SyncManager) error {
	m.mu.Lock()
	cfg := m.config
	m.mu.Unlock()

	w := &workflowWriter{m: m}

	// 1. Setup paths
	fmt.Fprintln(w, "=== 准备工作 ===")
	workspaceDir := cfg.ProjectRoot
	if workspaceDir == "" {
		wd, err := os.Getwd()
		if err != nil {
			return fmt.Errorf("无法获取当前目录: %v", err)
		}
		workspaceDir = wd
	}
	absWorkspace, _ := filepath.Abs(workspaceDir)
	fmt.Fprintf(w, "工作目录: %s\n", absWorkspace)

	gbl := filepath.Join(absWorkspace, "goldberg_emulator")
	if _, err := os.Stat(gbl); err != nil {
		fmt.Fprintf(w, "本地未找到金山发布包(goldberg), 尝试检测...\n")
	}

	gameDir := cfg.EU5Path
	if gameDir == "" {
		fmt.Fprintln(w, "尝试自动检测 EU5 游戏路径...")
		d := detector.NewDetector()
		found, err := d.DetectWithWriter(w)
		if err != nil || found == "" {
			return fmt.Errorf("未能自动找到 EU5，请在设置中手动指定: %v", err)
		}
		gameDir = found
	}
	fmt.Fprintf(w, "采用 EU5 路径: %s\n", gameDir)

	modDir := cfg.ModPath
	if modDir == "" {
		md, err := modsync.ResolveDefaultModPath()
		if err != nil || md == "" {
			return fmt.Errorf("未能获取默认 Mod 路径，请在设置中手动指定")
		}
		modDir = md
	}
	fmt.Fprintf(w, "采用 Mod 路径: %s\n", modDir)

	// 2. Deploy Goldberg
	fmt.Fprintln(w, "=== 部署 Goldberg 模拟器 ===")
	dep := deployer.NewDeployerWithWriter(absWorkspace, gameDir, w)
	if err := dep.Deploy(); err != nil {
		return fmt.Errorf("部署 Goldberg 失败: %w", err)
	}
	if cfg.AccountName != "" || cfg.SteamID != "" {
		if err := dep.ConfigureSteamSettings(cfg.AccountName, cfg.SteamID); err != nil {
			return fmt.Errorf("配置联机账户信息失败: %w", err)
		}
	}
	fmt.Fprintln(w, "[Info] Deploy: Goldberg 部署完成！账户已配置。")

	// 3. Mod Sync
	fmt.Fprintln(w, "=== 执行 Mod 同步 ===")
	sOpt := modsync.SyncOptions{
		ManifestURL:          cfg.ManifestURL,
		ModPath:              modDir,
		DeleteManagedMissing: cfg.DeleteManagedMissing,
		Out:                  w,
	}

	if err := modsync.RunSync(sOpt); err != nil {
		return fmt.Errorf("Mod同步失败: %w", err)
	}

	fmt.Fprintln(w, "=== 全部完成 ===")
	return nil
}
