# SOL 商品替代组实验室

项目根目录下的零依赖 Web 项目，用中文交互展示 v1.1 商品替代组与国家级 `global_<good>_pop_demand` 恢复候选。它是机制说明与离线模型，未修改游戏 `src/`，不代表功能或引擎组合语义已通过游戏验收。

直接双击 `index.html` 即可使用全部功能。也可在本目录启动本地服务器：

```powershell
cd C:\Users\Hades\Documents\code\eu5-modding-project\substitution-lab
npm.cmd start
```

访问 **http://127.0.0.1:4173**。无需 `npm install`，无 CDN、网络字体、框架或外部资源。按 Ctrl+C 停止。端口冲突时在启动前设置 `$env:PORT=4174`。

页面提供十章：历史与迁移全景、六档价格边界实验、20 组完整网络与 A/B 方案、旧阶层收入曲线、双市场国家聚合误差、使用当前真实净消费量的 56 商品 × 七人口类型国家篮子、modifier 叠加假设、SOL 求解器与生命周期、离线验收及兼容范围、源码与术语，以及把 `q`、`p_ref`、`B`、`D`、`E′`、`M`、`size`、守恒和国家级精度损失逐项翻译成人话的符号指南。支持 CSV / JSON 导出、逐商品完整历史偏好源码、带行号源码弹窗、打印为 PDF、手机布局和键盘导航。

## 资料与模型口径

- 历史版本固定为 `origin/v1.1` 对应提交 `9670e1414d8e2ce5c692672adc588f485baf167c`，不是几个 v1.1.x tag 的混合。
- 20 组、56 历史商品、67 条成员关系和 11 个跨组平均来自实际 weight/demand 脚本。组成员与 N 通过生成器提取，不用早期十组草案覆盖。
- 新方案 A 复算当期 / 中性倍率之比（默认 V=1，旧 group_scale=1），不保证金额守恒。B 为新增组预算守恒方案，重叠基线先按成员数均分。
- 商品组实验的金额为教学输入，默认每商品 50。关闭供给时有效 B=0；缺接口但仍有供给时冻结原额。接口勾选只模拟假设覆盖，不改变真实接口。
- 新版有效集合、供给过滤和接口冻结是候选规则，不是旧版行为。目录选“v1.1”仅改变商品集合，实验仍计算新版 A/B；旧真实曲线另章展示。
- 国家聚合使用地点系数重算前、按商品默认价换算的中性参考金额，epsilon 用金额单位分支回退，不抬高正分母。当前 SOL 的 `min(市场价,默认价)` 是后续 raw spending 代理，不进入替代基线。聚合页的 D 可独立输入，专门隔离观察压缩误差。
- Engel 图用固定历史提交的真实 α、P 和 offset；不是完整 POP scope 或引擎模拟。时代系数用历史实际值。
- `size=M-1`、外部 offset 换算及商品/global/local 组合均作为隔离条件或假设展示，必须进游戏验证；网页不替引擎决定叠加、截断和滚动更新周期。
- 端到端国家篮子使用当前核心净单位消费量与默认价，人口为教学输入，市场 A 价格沿用组实验、B 可选中性/同价/反向。逐人口类型计算 A/B 后按国家金额聚合，仍不模拟收入求解器或外部修正。组实验的任意 B 不用于此真实基线实验。两个实验都不模拟完整 PP / M&T / JTG 基线；JTG 26 新商品尚无确定替代组，保持中性。

主要参考：

- [修订实施规格](../docs/technical/SOL_Substitute_Groups_Global_Modifier_Implementation.md)
- [审计报告](../docs/technical/SOL_Substitute_Groups_Global_Modifier_Audit.md)
- 历史源码（通过 `git show 9670e141:<path>` 读取）与当前原版/官方接口。

## 维护与验证

```powershell
# 将固定历史源码和当前工作树资料重新生成至 data.js
npm.cmd run snapshot

# 运行独立的数学与数据一致性测试
npm.cmd test
```

`data.js` 为自动生成的离线快照，不手动编辑。历史提交保持固定；当前工作树来源记录生成时的 HEAD，文档与参考文件内容取当时工作树，未跟踪内容也可能进入快照。源码弹窗明确标记工作树版本。

文件职责：`index.html` 为机制说明，`styles.css` 为响应式样式，`app.js` 管交互与导出，`engine.js` 管独立数学模型，`scripts/build-data.cjs` 提取源码/曲线/目录，`server.cjs` 为本目录静态服务器，`tests/engine.test.cjs` 验证边界和不变量。

可选真实浏览器测试位于 `tests/browser-smoke.cjs`，需要 Node 22+、本地 Chromium 的 CDP 端口和运行中的页面。设置 `$env:CDP_URL='http://127.0.0.1:9227'`，然后执行 `node tests/browser-smoke.cjs`。`SOL_TEST_URL` 可指定 HTTP 或 `file:///.../index.html`；`SOL_SCREENSHOTS` 可指定截图输出目录。这不是运行网页的依赖。

服务器仅监听 `127.0.0.1`，不读取项目目录之外的 URL 路径。网页无需服务器，也不调用 Git 或外部服务。修改商品组模型时应同步测试与页面文字；刷新资料后重新检查目录数目、交互和源码行号。
