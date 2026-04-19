# EU5 自动测试与智能体工作流指南

**版本:** 1.0  
**更新日期:** 2026-04-19

---

## 概述

本指南解决以下核心问题：

| 问题 | 方案 |
|------|------|
| EU5 加载缓慢，无法快速验证脚本 | 静态分析器（无需启动游戏）|
| AI coding agent 频繁引入语法错误 | 已知错误模式数据库 + CI 自动拦截 |
| 重复更新文档的人力消耗 | 知识库自动更新工具 |
| Agent 错误无法系统积累 | Documented Violations 表 + 自动扫描 |

---

## 1. 静态验证器（无需加载游戏）

### 工具位置

```
tools/validator/eu5_validator.py
tools/validator/known_patterns.py
```

### 快速使用

```bash
# 从仓库根目录运行，扫描 src/ 目录
python tools/validator/eu5_validator.py

# JSON 输出（适合 CI / 编辑器集成）
python tools/validator/eu5_validator.py --json

# 严格模式（warning 也视为 error）
python tools/validator/eu5_validator.py --strict
```

### 检查内容

| 文件类型 | 检查项目 |
|---------|---------|
| `.yml`（本地化） | UTF-8-BOM 编码、非 ASCII 引号（"" 等） |
| `.txt`（脚本） | 已知错误模式、`auto_modifier` 键名、花括号平衡 |

### 已知错误模式

| 模式 | 原因 |
|------|------|
| `location_rank:village` | 无效枚举值，应为 `rural_settlement`/`town`/`city` |
| `mean_time_to_happen` | EU4 语法，EU5 通过 `on_actions` 触发事件 |
| 中文/全角引号（`""`） | PDX YAML 解析器只接受 ASCII `"` |
| 全角等号 `＝` | 常见粘贴污染 |

### 添加新规则

编辑 `tools/validator/known_patterns.py`，向 `BAD_PATTERNS` 列表追加：

```python
(
    "描述新规则",
    re.compile(r"你的正则表达式"),
),
```

---

## 2. CI 自动验证（GitHub Actions）

文件：`.github/workflows/validate.yml`

### 触发条件

- `src/` 或 `tools/validator/` 下有文件变更时，自动在 PR 和 push 上运行。

### 工作流程

```
push / PR
    │
    ▼
validate job
    ├── python eu5_validator.py --json  →  上传 JSON 报告到 Artifacts
    └── python eu5_validator.py         →  有 error 则失败（exit 1）
```

### 查看报告

1. GitHub → Actions → 对应 workflow run
2. 下载 **validation-report** artifact
3. 用任意 JSON 查看器打开 `validation_report.json`

---

## 3. 知识库自动更新工具

### 工具位置

```
tools/doc_updater/update_knowledge.py
```

### 使用场景

当 AI agent 引入错误语法，你修正后运行此工具，它会：

1. 扫描 `src/` 中含 `TODO`/`FIXME` + 语法关键词的注释
2. 扫描近期 git 提交（如 "fix modifier", "wrong enum"）
3. 交互式询问：将候选项添加为 Documented Violations

```bash
# 交互式模式
python tools/doc_updater/update_knowledge.py

# 仅打印候选项（不写入）
python tools/doc_updater/update_knowledge.py --dry-run

# 扫描最近 60 天
python tools/doc_updater/update_knowledge.py --git-days 60
```

### 自动更新的位置

工具追加到 `docs/guides/AI_Tool_Workflow_Prompt.md` 的 **Documented Violations** 表，
格式为 `| 日期 | 违规 | 根本原因 | 正确行为 |`。

---

## 4. AI Coding Agent 路由建议

### 推荐工作流

```
编写需求
    │
    ▼
AI Agent 生成草稿
    │
    ▼
运行验证器 (python tools/validator/eu5_validator.py)
    │
    ├── 有 error → 将报告粘贴给 Agent，要求修正
    │               Agent 须遵循 3-Step Resolution Rule
    │
    └── 无 error → 提交 PR → CI 再次验证 → 合并
```

### Agent 错误后的处理流程

1. 记录错误类型（哪个 Category 被违反）
2. 运行 `python tools/doc_updater/update_knowledge.py`，将新错误记录到 Violations 表
3. 更新 `CLAUDE.md` 中的 **Mandatory Reference Categories**（如有新类别）
4. 提交文档更新 → 下次 Agent 初始化时自动获得最新规则

### 支持的 Agent 工具

| 工具 | 集成方式 |
|------|---------|
| **Claude / GitHub Copilot** | 读取 `CLAUDE.md` 中的规则；验证器输出直接粘贴到对话 |
| **VS Code + CwTools** | CwTools 提供实时错误高亮；验证器补充 EU5 特定检查 |
| **OpenClaw / 类似工具** | 将验证器作为 pre-commit hook 或 CI step 集成 |

---

## 5. 快速参考：推荐日常流程

```
每次开发会话:
1. git pull
2. 编辑 src/ 中的脚本
3. python tools/validator/eu5_validator.py  ← 秒级反馈，无需启动游戏
4. 修正 error/warning
5. git commit & push  →  GitHub Actions 自动验证
6. 如发现新的 Agent 错误模式，运行 doc_updater 记录
```

---

## 6. 路线图（待实现）

- [ ] **CwTools 集成**: 将 `known_patterns.py` 转化为 CwTools rule 文件，实现编辑器实时检查
- [ ] **auto_modifier 修饰符名称验证**: 从 `reference_game_files/` 提取完整修饰符名称列表
- [ ] **scope 类型检查**: 静态分析触发器/效果的 scope 类型兼容性
- [ ] **本地化键完整性检查**: 验证脚本中引用的所有 loc key 都在 `.yml` 中定义
- [ ] **AI-assisted violation detection**: 使用 LLM 自动识别新的错误模式并提 PR
