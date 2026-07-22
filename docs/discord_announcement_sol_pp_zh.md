# SOL × Prosper or Perish 兼容补丁

Standard of Living 与 Prosper or Perish 现在可以通过专用兼容补丁共同使用。

**兼容补丁 Workshop 直链：**
https://steamcommunity.com/sharedfiles/filedetails/?id=3769565170

这是兼容补丁，不能独立运行。使用时必须同时启用 SOL、PP 与 Community Mod Framework。

## 整合后的玩法

- **整体经济由 Prosper or Perish 主导。** PP 的食物系统、人口增长与迁移、食物储备、建筑、生产方式、乡村容量、道路和共同地点平衡均完整保留。
- **保留 SOL 核心系统。** 基于收入的动态人口需求、生活水平局势与地图、地点 UI 继续生效。
- **SOL 会正确处理 PP 商品。** 军粮会进入 SOL 的计算与面板，同时保持 PP 的木材人口需求为零。
- **保留少量 Compact SOL 平衡内容。** 包括经过筛选的建设、税收、外交、厌战、殖民与非冲突价格规则。

## 为什么必须使用兼容补丁

SOL 与 PP 都会修改人口需求、商品、食物与气候平衡、RGO 与地点数值、道路、时代递增和战争修正。只加载两个主模组时，部分改动会互相覆盖，另一些则会重复叠加。

兼容补丁会把这些重叠内容整理为一套由 PP 主导的明确规则，不再让加载顺序偶然决定结果；同时补上 SOL 对军粮的计算，并防止 SOL 重新加入木材人口需求。

## 所需模组与加载顺序

1. [Community Mod Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=3692202776)
2. [Prosper or Perish](https://steamcommunity.com/sharedfiles/filedetails/?id=3613232232)
3. [Standard of Living](https://steamcommunity.com/sharedfiles/filedetails/?id=3698931463)
4. [SOL-PP 兼容补丁](https://steamcommunity.com/sharedfiles/filedetails/?id=3769565170)

**兼容补丁必须同时放在 PP 与 SOL 的下方。**

推荐开启新档。SOL 或 PP 大版本更新后，请先确认兼容补丁已经跟进，再开始长期游戏。
