# SOL Workshop 标签更新入口

工具实现和通用测试已移至 `eu5-modding-base`。完整用法、环境要求、Steam 接口来源和故障处理见[共享指南](../../.eu5-base/docs/guides/Workshop_Tags.md)。本工作区只保留薄入口与 SOL 默认配置。

## SOL 用法

```powershell
$env:EU5_PYTHON = 'C:\Users\Hades\anaconda3\envs\eu5\python.exe'
$env:PYTHONUTF8 = '1'

# 离线预览
& $env:EU5_PYTHON scripts/update_workshop_tags.py --item-id 3815438890

# 只读查询
& $env:EU5_PYTHON scripts/update_workshop_tags.py --item-id 3815438890 --check

# 仅更新标签并读回验证
& $env:EU5_PYTHON scripts/update_workshop_tags.py --item-id 3815438890 --apply
```

`3815438890` 是 SOL 的 1.4 beta 条目；`3698931463` 是旧 1.3 条目。本地入口默认传入本工作区 `src/stable/.metadata/metadata.json` 的绝对路径，因此从其他目录调用也不会读错配置；显式 `--metadata`（包括 `--metadata=...` 写法）会覆盖默认值。

目标分类来自 metadata，当前为 `Balance`、`Trade and Economics`、`User Interface`。`--apply` 是完整替换，将移除原来的 `Advancements`；默认与 `--check` 都不提交更新。共享脚本不包含 SOL 条目 ID 或默认目标。

本地回归入口：`& $env:EU5_PYTHON scripts/test_update_workshop_tags.py`。它运行共享工具测试及本地入口的路径/参数转发检查，不写入 Steam。

## 验证记录

2026-10-24 迁移前实机只读检查成功：条目标题为 `[v1.4 beta] Standard of Living - 生活水平需求`，当前标签为 `Advancements`，登录账号确为所有者。没有执行线上标签更新；真实写入路径尚未验收。

本地 JSON 与 Workshop 分类不一致已被查询确认，但具体上传环节的根因仍无引擎后端证据。
