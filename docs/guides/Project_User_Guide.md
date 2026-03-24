# EU5 模组项目简明指南

**版本:** 2.0
**更新日期:** 2026年3月24日

## 1. 项目定位

本仓库现在仅保留 EU5 模组开发内容：

- 模组源码
- 模组设计文档
- 模组参考资料

联机部署工具和同步工具已迁移到独立仓库：

- https://github.com/HLJSXK/eu5-online-tools

## 2. 模组结构

### `src/stable/`

- 当前主维护分支
- 用于多人平衡和稳定玩法

### `src/develop/`

- 动态任务方向的开发分支
- 用于实验复杂系统和新机制

## 3. 如何开始

1. 阅读 `src/README.md`
2. 选择 `stable` 或 `develop` 作为起点
3. 参考 `docs/technical/EU5_Mod_Framework_Guide.md`
4. 启用 EU5 调试模式进行本地测试

## 4. 文档入口

- `docs/technical/EU5_Modding_Knowledge_Base.md`
- `docs/technical/EU5_Mod_Framework_Guide.md`
- `docs/design/Dynamic_Missions_Design.md`
- `docs/task_summaries/`

## 5. 维护原则

- 本仓库不再包含联机部署脚本和可执行工具
- 所有变更以模组玩法、结构、兼容性为中心
- 参考资料保持可追溯，不直接作为发布内容
