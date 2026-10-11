# 03 · SOL 三个界面的结构解剖（对应三张图）

## 图 1：情势面板 `global_living_standard`

文件：`src/stable/in_game/gui/panels/situation/global_living_standard.gui`（254 行）+ SOL 复制并修改的 `panels/situation/common.gui`（1.4 模板，696 行）。

```
situation_panel (type, common.gui)  -> lateralview (shared/windows.gui:1155), 宽 570
├─ panel_header: window_header_alt  [情势图标 30×30][名称 #header_titles]
├─ panel_content
│  ├─ 45px 副标题 widget (左/中/右 block 默认 visible=no)  -> SOL: 空
│  ├─ 220px 插画 widget
│  │   ├─ situation_panel_image   -> SOL 覆盖: columbian_exchange.dds + 深蓝渐变
│  │   └─ situation_start_date    -> 原版: 「开始日期」旗帜
│  └─ MAIN vbox (bg_secondary_inner_alt)
│     ├─ situation_tab_buttons: header_secondary_tabs -> 只有「明细」
│     └─ breakdown vbox (Vars 'situation_tab' 默认)
│        ├─ situation_subheader_content       -> SOL: {} 删除
│        └─ scrollarea > vbox(margin 10, spacing 10)
│           ├─ Outcome situation_card_expandable  -> SOL: 按 key 隐藏 (common.gui:268)
│           ├─ situation_panel_main_content       -> SOL: situation_card_common
│           │    header_size {-1 0}; header_decor_templates {}; icon {}; text_full {}
│           │    common_bottom_content: vbox(spacing 8, margin {8 6})
│           │      说明 text_multi(max_width 470)
│           │      #T 小节 ×4 + 表格 hbox(130 + 5×68) + 商品网格 6×10 (34×30)
│           ├─ 进度条 vbox  (原版 visible = no)
│           └─ situation_panel_main_actions -> 原版 situations_actions
│                (GetActionGroups 非空时: dynamicgridbox of situation_card_actions)
└─ [SOL] 0×0 widget: state trigger_on_create -> PushMapModeOverride('sol_living_standard')
```

数据：全部是 `Player.MakeScope.ScriptValue('gls_*_display')`；商品红叉来自 `GetVariableFromGlobalVariableMap('gls_country_consumes_<good>', Player.MakeScope)`。

关键设计决定（以及 AI 曾经犯过的错）：
- 1.4 的 Outcome 外层卡没有专属 blockoverride，所以必须复制整份 `common.gui`；之后游戏更新这份文件时要手动同步。
- 地图模式不能写在情势定义里（不存在 `map_mode = tag` 字段），只能靠 widget 生命周期。`_show` 对创建时即可见的 widget 不触发，这正是早期 bug 的原因。
- 情势定义中的 `is_data_map = yes` / `map_color` / `tooltip` / `legend_key` 驱动的是情势自带的数据地图，和自定义 mapmode `sol_living_standard` 是两套机制。

## 图 2：地点窗口（人口页签）

文件：`src/stable/in_game/gui/location_window.gui`（9197 行，**自动生成**：Glorp UI 04.10.26 快照 + 1.4 迁移 + SOL 按钮）；`gui/vanilla/cmfg_location_window_vanilla_types.gui`（Glorp 提取的原版类型）；`SOL_glorp_location_support.gui`（`zoom_to_button` 类型）。

```
lateralview name=location_window
├─ lateralview_topbuttons_extra: Glorp 改名按钮
├─ panel_header: window_header_alt [rank icon][GetRankAndName][pin] + zoom_to_button
└─ panel_content vbox
   ├─ 45px: [省份 subheader_unified_icon / 省会 uber 按钮][所有者旗帜][省份食物 mirror]
   ├─ 73px location_card (bg_market_card)  ~70 个 blockoverride
   ├─ 220px 场景: ecs_scene_viewer_widget + IO/Periphora + 队列按钮列 + 40px 底部条件栏
   ├─ header_secondary_tabs: 基础设施 | 商品 | 军事 | 人口   (LocationView.Vars 'tab')
   └─ vbox (bg_foreign_country 背景)
      ├─ infrastructure scroll_list
      ├─ goods
      ├─ military
      └─ DEMOGRAPHY vbox (visible = HasValue('tab','demography'))
         ├─ 45px hbox: [人口增长] expand [满意度饼 navigational_button_alt]
         │              [SOL navigational_button_alt -> tooltipwidget StandardofLiving_tooltip] expand [迁徙吸引力]
         ├─ demography_chart 人口  (左: 晋升/类型饼/政治饼/降级; 右: LocationView.GetPops)
         ├─ demography_chart 文化
         └─ demography_chart 宗教
```

- SOL 的唯一改动是插入这个按钮，以及把 `Location.GetTotalIncome` 换成 `local_sol_total_income`。按钮没有 `visible` 条件，也没有点击动作。
- 这份文件同时引用了 Construction Manager 的 `cm_*` 类型。只启用 SOL 时，这些类型缺失会在 error.log 报 `is not a valid widget/type/property`，属于预期内的“可选依赖”报错。
- Standalone 版用原版窗口生成，按钮同样插在人口页签（`src/sol_standalone/.../location_window.gui:9568`）。

## 图 3：地点 SOL tooltip

文件：`src/stable/in_game/gui/SOL_economy_local.gui`（`template StandardofLiving_tooltip`）。

```
ContextualTooltipType (main_menu_cooltip_types.gui:1721)
├─ ContextualTooltipHeader
│    title_icon  -> SOL 天平 (tooltip_title_icon_size)
│    title_text  -> datacontext [Location], text LOCATION_SOL_GUI_TITLE
│    concept_link -> 默认 visible = HasTooltipMetaGameConcept -> 隐藏
└─ TooltipContentSection (margin 10)
   └─ tooltip_content: vbox(spacing 8)
      TooltipTextBlock 总览 (LOCATION_SOL_GUI_SUMMARY: GDP × 控制力 = 税基)
      TooltipTextBlock #T 阶层收入计算 + vbox 表: 150 + 5×72
         图标头 / 人数 / 力量 / 压迫行 / 税率 / 阶层收入 / 建筑维护费 / 总阶层收入
      TooltipTextBlock #T 存款压力 + 表: 图标头 / 存款 / ≈存款目标 / 总存款目标 / 总存款 / 存款压力修正
      TooltipTextBlock #T 人群消费系数 + 表: 流动资金 / 基础总支出 / 原始系数 / 最终校正系数
      TooltipTextBlock #T 本地人群消费商品 + 6×10 网格 (三态: 正常 / 红↓降价 / 红✕不消费)
```

- `TooltipTextBlock` 本身带一层 `bg_listbase_template` 深蓝半透明底条，最小宽 400。SOL 把它当作小节标题条使用。
- 数据 key：`local_*` script value 以及 `sol_market_consumes_*` / `sol_market_price_suppressed_*` 这两个按 `Location.GetMarket.MakeScope` 取值的 map。
- PP / JTG 兼容子模组用 `zz_SOL_economy_local.gui` 重新生成同名模板（57 / 82 个商品）。这依赖“同名 template 由后加载者覆盖”的行为，项目内没有直接验证 [疑]。
