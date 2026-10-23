# 生活水平 · 四节横栏 + 四个 tooltip —— 新版设计

2026-10-23 更新。已生成至 stable / standalone；本文件描述当前四节界面，离线渲染不替代游戏内验收。
位置与几何沿用当前实现：左面板 9 个按钮下方，`{0 130}`，`570 × 36`，GlorpUI 兼容文件按 36 下推仍然成立。

```powershell
$env:PYTHONUTF8='1'
& C:/Users/Hades/anaconda3/envs/eu5/python.exe ai_gui_assessment/prototypes/living_standard_4sections/build.py
```

生成物（勿手改）：`sol_lshud4.gui`（行根 `sol_lshud4_root` + 4 个 tooltip 模板）、`sol_lshud4_l_simp_chinese.yml`（仅新增键）。
其余文案沿用已发布的 `SOL_LSHUD_*`、`SOL_C_*`、`SOL_ESTATE_*`、`SOL_SUB_*` 键。

## 1. 横栏四节（左→右，各自一个热区和 tooltip）

| 节 | 宽 | 内容 | tooltip |
|---|---|---|---|
| 1 | 172 | 等级徽章（低/中/高）· **18.0** · 箭头 · 同比 % | `SOL_LSHUD4_tooltip_1` |
| 2 | 112 | SOL 金币图标 · **−11.2%**（全国原始 α−1，按符号着色）| `SOL_LSHUD4_tooltip_2` |
| 3 | 168 | 第一名支出商品图标 · 商品名 + 占比 · 第 2、3 名小图标（渐淡）| `SOL_LSHUD4_tooltip_3` |
| 4 | 104 | 原版强国排名旗标 · **12 / 87** | `SOL_LSHUD4_tooltip_4` |

节间为 1px 金色竖线。各节**不带文字标签**（2026-10-18 用户决定），只靠图标与数值区分，含义由各自 tooltip 标题说明。
节内分组：组内间距 1–2px、组间 12px。第 1 节为〔生活水平〕〔箭头 + 同比%〕两组；第 3 节为〔第一商品图标 + 名称 + 占比〕〔第 2、3 商品小图标〕两组。未结算 / 排行未出时分别显示「等待首次计算」「待更新」。

## 2. 四个 tooltip

1. **生活水平**：英雄区（徽章、等级、生活水平大数字、同比色块）；副标题用大白话说明生活水平的含义（不列公式，2026-10-24 起去掉底部注释段）；
   表格 `阶层 | 人口(千) | 生活水平 | 同比`，首行「全国」金框，五阶层斑马纹，空阶层隐藏，无去年数据时同比列显示「—」。
2. **购买力**（520×445）：**原 situation 面板的购买力区块原样迁移**——由 `gen_sol_ls_gui.balance_sections()`
   以 `Player.MakeScope` / `gls_sol` 直接生成（全国总行 + 共享刻度 + 五阶层行 + 资金/基准），外加一行口径说明。
3. **主要支出与替代组**（520×723）：前 5 支出商品（图标、名称、相对第一名的长度条、月度金额、占比，第一名金条）；
   下方为**原面板商品区原样迁移**（`goods_block()`：替代状态摘要、图例、必需/日用/奢侈三档 20 个替代组卡片）。
4. **全球排名**（480×416）：全国排名梯（第 1 名、⋯、本国上下各一，本国金框金条）；
   各阶层排名表 `阶层 | 生活水平 | 世界排名 n/m | 百分位条 | 世界最高（国家 + 数值）`。

迁移完成后 situation 面板中的全部内容（购买力 + 商品组）都已在 tooltip 2、3 中，面板可以下线。

## 3. 后端需新增的变量（GUI 已按此绑定）

已有且沿用：`sol_ls_sol` / `sol_ls_sol_<e>`、`sol_ls_tier`、`sol_ls_rank`、`sol_ls_percentile`、`sol_ls_above/below_*`、`sol_ls_top_*`、`sol_ls_pop_all/<e>`，以及面板的 `gls_*_display` / `sol_substitute_*` 脚本值。

同比公开缓存为 `sol_ls_sol_prev*`、`sol_ls_sol_yoy*`、`sol_ls_sol_yoy_class*`；同月历史为 `sol_ls_sol_sample_<m>_*`，与旧收入样本完全隔离。首次计算门控为 `IsSet('sol_ls_sol')`。国家级收入与 PCI 汇总已删除，地点净收入仍供求解器使用。

| 新变量 | 作用域 | 含义 |
|---|---|---|
| `sol_ls_spend_1 … 5` | 国家，**goods 作用域变量** | 按月度总价排序的前 5 消费商品 |
| `sol_ls_spend_<n>_gold` / `_share` | 国家 | 该商品月度消费总价 / 占全国消费比例 |
| `sol_ls_spend_total` | 国家 | 全国月度消费总价 |
| `sol_ls_rank_<e>` / `sol_ls_percentile_<e>` | 国家 | 阶层生活水平在世界同阶层中的排名 / 百分位 |
| `sol_ls_rank_count_<e>` | 全局 | 有该阶层人口的国家数 |
| `sol_ls_top_1_<e>` / `sol_ls_top_sol_<e>` | 全局 | 该阶层生活水平世界第一的国家 / 数值（千人均年流动资金＋生活水平修正） |

商品支出可在现有 `gls_country_consumes_*` 累计遍历里顺带求和（每商品数量 × 市场价），不新增地块遍历；
阶层排名在现有 1 月 1 日排行里对每个阶层各做一次 `ordered_country`（只读缓存）。

第一格、等级、全国与阶层排名统一读取人口加权的 SOL 数值，保留一位小数；第二格继续读取购买力。SOL = 固定值之和 + max(0, 1 + 百分比之和) × 千人均年流动资金，结果最低为0。顶栏第一格数字后也加专用小屋 `@sol_living_standard!`（2026-10-24 用户要求；数字与同比间距 12→8 以容纳图标）。悬浮窗1的大数字、表格和排名数值同样使用该图标。标题只显示等级，避免重复大数字。

## 4. 渲染结果（`ai_gui_assessment/images/living_standard_4sections_20261018/`）

| 文件 | 内容 |
|---|---|
| `row_left.png` / `hud.png` | 横栏在 HUD 中 |
| `hover1.png` … `hover4.png` | 各节悬停时 tooltip 的位置示意 |
| `tooltip{1-4}_normal.png` | 四个 tooltip（中 / 增长）|
| `tooltip{1-4}_{high_bigup,low_bigdown,rank_pending,pending}.png` | 其他数据状态 |
| `row_states.png` | 五种状态的横栏 |
| `glorp_row_left.png` | 与 GlorpUI 统计栏共存（使用已发布的兼容文件）|

渲染器：所有状态 0 个未解析原型绑定、0 张缺失贴图。

## 5. 待确认

1. **goods 作用域变量**：`set_variable` 能否存 `goods:wheat`、GUI 的 `GetVariable(...).GetGoods`（`data_types_script.txt:1896`）
   与 `GetGoodsIcon(...)`（原版 `attribute_columns/goods.gui:22`）组合能否实机工作。若不行，退回按商品逐一可见性开关。
2. tooltip 3 高 723px（含 20 组商品）：1080p/100% 可容纳，高 UI 缩放会贴底。
3. 四个独立 tooltip 热区在实机上的切换手感；横栏其余空白区域透明不吞鼠标。
4. 简中和英文均由生成器提供；新增小屋单位图标的基线对齐仍待游戏内截图验收。

## 6. 等级图标（自绘，2026-10-18）

用户否决了沿用现有图标的全部方案，要求自制（按图标规则属第 3 级“从头制作”，理由即用户明确要求）。
`make_tier_icons.py` 用 Pillow 程序化绘制三枚同构徽章，128px DXT5 + mipmap（`texture_density = 2` → 64 单位），
输出到本目录 `gfx/interface/sol_lshud_proto/tier_{low,mid,high}.dds`；不依赖外部图片或生成服务。

三个信号同向递进，任一尺寸至少两个可辨：
| | 低 | 中 | 高 |
|---|---|---|---|
| 外圈金属 | 铁灰 | 青铜 | 黄金 |
| 碗 | 空碗、带裂纹、碗底几粒碎屑 | 一条面包 | 两条面包 + 水果 + 葡萄 + 金币，瓷碗金蓝边，背后放射光 |
| 下缘宝石 | 1 颗亮 | 2 颗亮 | 3 颗亮 |

徽章自带外框，所以 `TIER_SETS["custom"]` 以 `ring = none` 直接绘制，不再叠加底盘与文化金环；未结算时仍显示 SOL 徽记。
`build.py` 只使用该套；淘汰的候选方案（现行、金属环、爵位盾徽、枯苗→金币）及其渲染已删除。
预览：`images/living_standard_4sections_20261018/tier_icons/custom/`（`tier_sizes.png` 为 20/28/40/58/128px 可读性检查，`in_context.png` 为横栏与 tooltip 中的效果）。
