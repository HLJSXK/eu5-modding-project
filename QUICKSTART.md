# EU5 LAN Multiplayer Quick Start Guide

快速开始使用 Goldberg Emulator 进行 EU5 局域网联机。

## 🚀 快速部署（推荐）

### 1. 克隆项目

```bash
git clone https://github.com/HLJSXK/eu5-modding-project.git
cd eu5-modding-project
```

### 2. 自动部署

**Linux/macOS:**
```bash
python3 tools/deploy_goldberg.py
```

**Windows:**
```cmd
python tools\deploy_goldberg.py
```

脚本会自动：
- 检测 EU5 安装位置
- 备份原始 `steam_api64.dll`
- 部署 Goldberg Emulator
- 复制配置文件

### 3. 启动游戏

直接从 Steam 启动 EU5，即可在局域网列表中看到朋友的房间！

## 🔄 恢复原始文件

当你想恢复正常的 Steam 联机模式时：

```bash
python3 tools/deploy_goldberg.py --restore
```

## 📝 配置 DLC

编辑 `goldberg_emulator/steam_settings/DLC.txt` 文件，添加你拥有的 DLC ID：

```
# EU5 DLC Configuration
2883680
2883681
```

**如何查找 DLC ID：**
1. 访问 [SteamDB](https://steamdb.info/)
2. 搜索 "European Universalis V"
3. 查看 DLC 页面获取 App ID

## 🎮 添加 Mods

将 mod 文件夹放入 `goldberg_emulator/steam_settings/mods/` 目录，然后重新运行部署脚本。

**注意：** 所有玩家必须使用相同的 mods！

## 🌐 虚拟局域网设置

如果你和朋友不在同一个物理网络，需要使用 VPN 工具创建虚拟局域网：

### 推荐工具

1. **n2n** (推荐)
   - 开源、点对点
   - 项目地址: https://github.com/ntop/n2n
   - 需要部署 supernode 服务器

2. **ZeroTier**
   - 易用、免费
   - 官网: https://www.zerotier.com/

3. **Tailscale**
   - 基于 WireGuard
   - 官网: https://tailscale.com/

### n2n 快速配置

**服务器端（Supernode）：**
```bash
supernode -l 7777
```

**客户端（每个玩家）：**
```bash
edge -a 10.0.0.1 -c mynetwork -k mypassword -l supernode_ip:7777
```

## 🐛 常见问题

### 游戏无法启动
- 运行 `deploy_goldberg.py --restore` 恢复原始文件
- 在 Steam 中验证游戏完整性
- 确保使用的是 64 位版本的 Goldberg

### 看不到其他玩家
- 确认所有玩家都在同一网络（物理或虚拟）
- 检查防火墙设置，允许 EU5 通过
- 确保所有玩家都部署了 Goldberg Emulator

### DLC 不工作
- 检查 `DLC.txt` 中的 DLC ID 是否正确
- 确认文件位置：`<EU5安装目录>/binaries/steam_settings/DLC.txt`
- 所有玩家的 DLC 配置应该一致

### Mods 未加载
- 确保 mods 在 `steam_settings/mods/` 文件夹中
- 验证所有玩家有相同的 mods
- 检查 mod 与当前 EU5 版本的兼容性

## 📚 详细文档

- [Goldberg Emulator 完整说明](goldberg_emulator/README.md)
- [工具使用文档](tools/README.md)
- [项目用户指南](docs/Project_User_Guide.md)

## ⚠️ 重要提示

1. **始终备份：** 部署前会自动备份，但建议手动再备份一次
2. **杀毒软件：** 某些杀毒软件可能会误报，需要添加例外
3. **游戏更新：** EU5 更新后需要先恢复原始文件，更新完成后重新部署
4. **版本一致：** 所有玩家必须使用相同版本的 EU5
5. **合法使用：** 仅用于局域网游戏，所有玩家应拥有正版 EU5

## 🎯 下一步

现在你已经完成了基础设置，可以：

1. 配置你的 DLC 列表
2. 添加想要使用的 mods
3. 设置虚拟局域网（如果需要）
4. 邀请朋友一起游戏！

---

**项目地址：** https://github.com/HLJSXK/eu5-modding-project  
**问题反馈：** https://github.com/HLJSXK/eu5-modding-project/issues

祝游戏愉快！🎮
