# Go 工具使用指南

本项目已使用 **Go 语言**重写核心工具，可编译为独立的 exe 文件，无需安装任何运行时环境。

## 📦 预编译版本

如果您不想自己编译，可以直接使用预编译的可执行文件：

### Windows 用户
- `build/eu5-tools-windows-amd64/eu5-sync-ui.exe` - 一键同步 UI（部署 + Mod 同步）

### Linux 用户
- 使用 `go run ./cmd/eu5-deployer` 和 `go run ./cmd/eu5-detector` 运行 CLI

### macOS 用户
- 使用 `go run ./cmd/eu5-deployer` 和 `go run ./cmd/eu5-detector` 运行 CLI

## 🚀 快速使用

### Windows 用户

1. **双击运行部署工具：**
   ```
   build\eu5-tools-windows-amd64\eu5-sync-ui.exe
   ```
   
   工具会自动检测 EU5 安装位置并完成部署。

2. **恢复原始文件：**
   ```cmd
   go run ./cmd/eu5-deployer --restore
   ```

3. **手动指定 EU5 路径：**
   ```cmd
   go run ./cmd/eu5-deployer --eu5-path "D:\Steam\steamapps\common\Europa Universalis V"
   ```

### Linux/macOS 用户

1. **赋予执行权限（首次使用）：**
   ```bash
   # go run 无需赋予执行权限
   ```

2. **运行部署工具：**
   ```bash
   go run ./cmd/eu5-deployer
   ```

3. **恢复原始文件：**
   ```bash
   go run ./cmd/eu5-deployer --restore
   ```

## 🔧 工具说明

### 1. eu5-detector - EU5 检测工具

**功能：** 自动检测 EU5 安装位置

**使用方法：**
```bash
# Windows
go run ./cmd/eu5-detector

# Linux/macOS
go run ./cmd/eu5-detector
```

**输出示例：**
```
Detecting EU5 installation on windows...
Checking Steam library: C:\Program Files (x86)\Steam

✓ Found EU5 installation: D:\Steam\steamapps\common\Europa Universalis V

EU5 Main Folder: D:\Steam\steamapps\common\Europa Universalis V
Binaries Folder: D:\Steam\steamapps\common\Europa Universalis V\binaries

__EU5_PATH__=D:\Steam\steamapps\common\Europa Universalis V
__BINARIES_PATH__=D:\Steam\steamapps\common\Europa Universalis V\binaries
```

### 2. eu5-deployer - Goldberg 部署工具

**功能：** 自动部署 Goldberg Emulator 到 EU5 安装目录

**使用方法：**
```bash
# 自动检测并部署（使用默认显示名称）
go run ./cmd/eu5-deployer

# 自定义显示名称
go run ./cmd/eu5-deployer --account-name "玩家1"

# 指定 EU5 路径
go run ./cmd/eu5-deployer --eu5-path "D:\Steam\steamapps\common\Europa Universalis V"

# 恢复原始文件
go run ./cmd/eu5-deployer --restore
```

**命令行参数：**
- `--eu5-path` - 手动指定 EU5 安装路径
- `--account-name` - 设置显示名称（默认：EU5Player）
- `--restore` - 恢复原始文件

**部署流程：**
1. 配置 Steam 模拟器设置（显示名称）
2. 验证 EU5 安装路径
3. 备份原始 `steam_api64.dll`
4. 复制 Goldberg `steam_api64.dll`
5. 复制 `steam_appid.txt`（EU5 的 App ID: 3450310）
6. 复制 `steam_settings` 文件夹（包含 DLC.txt、账户配置和 mods）

**输出示例：**
```
============================================================
Goldberg Emulator Deployment for EU5
============================================================

Project Root: D:\eu5-modding-project
EU5 Installation: D:\Steam\steamapps\common\Europa Universalis V
Binaries Folder: D:\Steam\steamapps\common\Europa Universalis V\binaries

[Step 0/4] Configuring Steam emulator settings...
✓ Prepared display name: EU5Player

[Step 1/4] Backing up original steam_api64.dll...
✓ Backed up original DLL to: ...\binaries\.goldberg_backup\steam_api64.dll.original

[Step 2/4] Deploying Goldberg steam_api64.dll...
✓ Deployed Goldberg DLL to: ...\binaries\steam_api64.dll

[Step 3/4] Deploying steam_appid.txt...
✓ Deployed steam_appid.txt to: ...\binaries\steam_appid.txt

[Step 4/4] Deploying steam_settings folder...
✓ Removed existing steam_settings
✓ Deployed steam_settings to: ...\binaries\steam_settings
  - DLC.txt: ...\binaries\steam_settings\DLC.txt
   - mods folder cleaned; note written: ...\binaries\steam_settings\mods\README.txt

============================================================
✓ Deployment completed successfully!
============================================================

You can now launch EU5 for LAN multiplayer.
To restore original files, run with --restore flag.
```

## 🛠️ 自己编译（开发者）

如果您想自己编译工具：

### 前置要求
- Go 1.25 或更高版本
- Git

### 编译步骤

**Windows:**
```cmd
git clone https://github.com/HLJSXK/eu5-modding-project.git
cd eu5-modding-project
build.bat
```

**Linux/macOS:**
```bash
git clone https://github.com/HLJSXK/eu5-modding-project.git
cd eu5-modding-project
chmod +x build.sh
./build.sh
```

编译完成后，可执行文件会生成在 `build/` 目录中。

### 当前构建脚本说明

当前 `build.bat` / `build.sh` 主要用于打包 Windows Sync UI 工具包：
- `build/eu5-tools-windows-amd64/`
- `build/eu5-tools-windows-amd64.zip`

如需单独构建 CLI，请使用 `go build ./cmd/...`。

## 📁 项目结构

```
eu5-modding-project/
├── cmd/                        # 可执行文件源码
│   ├── eu5-detector/          # 检测工具
│   ├── eu5-deployer/          # 部署工具
│   ├── eu5-modsync/           # 发布/同步工具
│   └── eu5-sync-ui/           # Windows UI
├── pkg/                        # 共享包
│   ├── detector/              # 检测逻辑
│   ├── deployer/              # 部署逻辑
│   └── modsync/               # 同步逻辑
├── goldberg_emulator/         # Goldberg 文件
│   ├── steam_api64.dll
│   └── steam_settings/
├── build/                      # 编译输出（.gitignore）
│   ├── eu5-sync-ui-windows-amd64.exe
│   ├── eu5-tools-windows-amd64/
│   └── ...
├── build.sh                    # Linux/macOS 构建脚本
├── build.bat                   # Windows 构建脚本
├── go.mod                      # Go 模块定义
└── docs/guides/Tools_Guide.md # 本文件
```

## ⚠️ 重要提示

1. **运行位置：** 工具需要在项目目录中运行，或确保 `goldberg_emulator` 文件夹与可执行文件在同一目录
2. **管理员权限：** 某些系统可能需要管理员权限来修改游戏文件
3. **杀毒软件：** 部分杀毒软件可能误报，请添加例外
4. **备份安全：** 工具会自动备份原始文件到 `.goldberg_backup` 文件夹

## 🐛 故障排除

### 工具无法运行
- **Windows:** 右键点击 → "以管理员身份运行"
- **Linux/macOS:** 确保已赋予执行权限：`chmod +x <文件名>`

### 找不到 goldberg_emulator 文件夹
- 确保在项目根目录运行工具
- 或将 `goldberg_emulator` 文件夹复制到可执行文件同一目录

### 无法检测到 EU5
- 手动指定路径：`--eu5-path "完整路径"`
- 确保 EU5 已通过 Steam 正确安装

### 部署失败
- 检查是否有足够的磁盘空间
- 确保没有其他程序正在使用 EU5 文件
- 尝试以管理员权限运行

## 📝 与 Python 版本的对比

| 特性 | Python 版本 | Go 版本 |
|------|------------|---------|
| 运行时依赖 | 需要 Python 3.11+ | 无需任何依赖 |
| 文件大小 | ~10KB (脚本) | ~1.8MB (单文件) |
| 启动速度 | 较慢 | 极快 |
| 跨平台 | 需要 Python 环境 | 单个可执行文件 |
| 分发难度 | 需要说明环境配置 | 直接发送 exe |
| 适合人群 | 开发者 | 所有用户 |

## 🎯 推荐使用方式

**对于普通用户（您的朋友）：**
- 直接使用 `build/` 目录中的预编译 exe 文件
- 双击运行，无需任何配置

**对于开发者：**
- 可以查看和修改 `cmd/` 和 `pkg/` 中的源代码
- 使用 `build.sh` 或 `build.bat` 重新编译

## 📚 相关文档

- [快速开始指南](QUICKSTART.md)
- [Goldberg Emulator 说明](goldberg_emulator/README.md)
- [项目主文档](README.md)

---

**最后更新：** 2026年3月24日  
**Go 版本：** 1.25.0  
**工具版本：** 1.0.0
