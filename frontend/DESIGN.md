# DESIGN.md — DeepSeek-AuditMind 设计系统

> 本文件是前端改版的**唯一权威**。任何组件改写都必须符合这里的方向、调色板、
> 字阶与禁令。与旧代码冲突时，以本文件为准。

---

## 1. 方向（Named Direction）

**「暗房 · 亮底稿」** — *The dark room, the lit workpaper.*

审计员在暗房里工作。屏幕上大部分是一间安静的、连续的暗场；**证据是唯一被照亮的东西**。
这不是"深色主题"，这是把产品的核心隐喻直接变成界面：在昏暗里，结论必须被点亮。

三个必须能"命名"的设计决策（改版前后对比时用得上）：

1. **面由色阶分层，不由描边分层。** 整个应用没有一根装饰性 1px 描边。层级靠
   `field → field-raised → field-raised2 → field-raised3` 逐级提亮。描边只允许出现在
   **真实数据表格**和**表单输入框**上。
2. **结论落在纸上。** 关键结论（研判结论、底稿、导出凭证）独占一个亮面
   (`--paper`)，与暗场形成极端对比。全屏只允许**存在一个**这样的亮面。
3. **一个重音，信号红。** `--seal: #D92B21`。它只出现在**最主要的
   一个动作**上。状态色（红/橙/黄/绿）只出现在**数据标记**上，绝不作为面板底色或装饰。
   （初版取的是印章朱红 `#C6402E`，因撞上 tasteskill 明令禁止的「奶黄底 + 陶土红」一组而换掉，
   详见 §3 末尾。）

**场景**：finance（信任、精确、数字密度）+ ai-product（智能体在思考、在穿透）。
**不是**：游戏化大屏、霓虹赛博、加密货币仪表盘。

---

## 2. 叙事（Storyline — 五个节拍）

界面按审计工作的真实节奏组织，而不是按功能菜单组织：

| 节拍 | 含义 | 对应视图 |
|---|---|---|
| **1 清点** | 打开案件：我们手上有什么 | 审计指挥舱 |
| **2 穿透** | 智能体在跑，证据被逐条追下去 | 三单勾稽穿透 / 资金体外拓扑 / 思维链演播 |
| **3 定谳** | 结论落纸，带着支撑它的那个数字 | 指挥舱结论区 / 各视图结论 |
| **4 存证** | 底稿、凭证、可导出的东西 | 底稿与成果导出 |
| **5 对战** | 28 案例同台打分 | 28案例竞技场 |

每个视图都必须能回答：**我现在在哪个节拍？**

---

## 3. 调色板

```css
--field:        #0E0F12   /* 房间。页面底色 */
--field-sunken: #0A0B0D   /* 比房间更深：凹陷区 */
--field-raised: #17191D   /* 面板，比房间亮一级 —— 不需要描边 */
--field-raised-2:#1F2227  /* 悬停 / 选中 / 行条纹 */
--field-raised-3:#2A2C31  /* 按下 / 激活 */

--paper:        #EFEFEF   /* 被照亮的底稿。中性纸白，不是奶黄 */
--paper-deep:   #E2E2E2   /* 纸上的次级块 */
--ink:          #14151A   /* 纸上的字 */
--ink-muted:    #5A5C63   /* 纸上的次级字 */

--fg:           #ECEDEF   /* 暗场上的正文 */
--fg-muted:     #A3A7AE   /* 暗场上的次级字（标签、说明） */
--fg-faint:     #7D8188   /* 暗场上的三级字（时间戳、角标） */

--seal:         #D92B21   /* 唯一重音。信号红 */
--seal-deep:    #B01F18   /* 重音悬停 / 按下 */
--seal-soft:    #E8736A   /* 小字号红字专用（暗场对比度 ≥4.5:1） */
--risk-critical:#D92B21
--risk-high:    #D97B4A
--risk-medium:  #C9A03F
--risk-clear:   #5C9070
```

Tailwind 语义类：`bg-field` `bg-field-raised{,-2,-3}` `bg-paper` `text-ink`
`text-ink-muted` `text-fg` `text-fg-muted` `text-fg-faint` `bg-seal` `text-seal`
`text-seal-soft` `hover:bg-seal-deep` `text-risk-{critical,high,medium,clear}`。

**对比度已核算**：正文 `#ECEDEF` on `#0E0F12` ≈ 15:1；次级 `#A3A7AE` ≈ 7.4:1；
三级 `#7D8188` ≈ 4.6:1 —— 三级**只用于非必要信息**。`--ink-muted` on `--paper` ≈ 6.6:1。
`--seal` `#D92B21` on `#0E0F12` 只有 **3.1:1**，只够做大字和色块；**小字号红字
（股票代码一类）必须用 `text-seal-soft`**（≈6.4:1）。

> **为什么改过一版**：初版取的是"印章朱红 `#C6402E` + 暖奶纸 `#F2EFE8`"。
> 真实渲染检查把这一对判为 `[palette-terracotta]` / `[palette-claude]` ——
> **奶黄底 + 陶土红**正是 tasteskill 明令禁止的那一组（"reads as an assistant
> brand, not yours"）。暖奶纸也不是审计底稿的真实颜色：真实底稿是中性纸白。
> 于是改成**中性纸白 `#EFEFEF` + 信号红 `#D92B21`**（取自 skill 的
> `library/palettes.json`：`Signal red` 的 accent、`Black and crimson` 的 field）。
> 方向没变（暗房里唯一被照亮的是底稿），只是把这组撞车的色值换掉。

> ⚠️ **遗留色阶已被收敛**：`slate/gray/zinc/neutral/stone → graphite`，
> `cyan/blue/sky/indigo/violet/purple/fuchsia/pink → seal`，
> `emerald/green/teal/lime → moss`，`amber/yellow → ochre`。
> 也就是说旧的 `text-cyan-400` 现在渲染成朱红。**不要**新写这些类名，
> 它们只是迁移期的安全网。

---

## 4. 字阶（Typography）

**一个字体族**：`IBM Plex Sans SC`（拉丁 + 中文同一族，OFL 开源，自托管）。
**等宽只用于字面代码**：`IBM Plex Mono`，仅 `<pre>` / `<code>` / CoT 原文载荷。

| 类 | 尺寸 | 行高 | 用途 |
|---|---|---|---|
| `text-label` | 13px | 1.3 | 标签、表头、角标。**这是下限** |
| `text-small` | 14px | 1.45 | 次级说明、表格单元格 |
| `text-body` | 16px | 1.5 | **正文**。说明段落、结论句 |
| `text-title` | 22px | 1.2 | 面板标题、结论 |
| `text-display` | 40px | 1.05 | 全屏唯一的那个数字 / 那个结论 |

**规则**
- 小于 13px 的文字**一律删除或提升**。旧版 9/10/11px 是主要"廉价感"来源。
- 数字一律 `tabular-nums`（body 已全局开启），靠字体特性对齐，**不靠等宽字体**。
- 每个视图**只能有一个** `text-display`。其余用 `text-title`。
- 标题 `text-wrap: balance`，段落 `text-wrap: pretty`（body 已设）。

---

## 5. 布局与间距

- **4px 基准**；间距取 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 56。
- **圆角一律 0**。Tailwind 的 `rounded-*` 已被配置压平（最大 2px），
  但新代码写 `rounded-none` 或干脆不写。
- **阴影在静止状态一律为 0**。只有真实浮层可用 `shadow-overlay`。
- 面板内边距：`px-5 pt-5 pb-4`（头部）/ `px-5 pb-5`（内容）。或直接用 `<Panel>`。
- 响应式：**默认是窄屏**，用 `sm:` / `lg:` / `xl:` 向上增强。
  `md:` 是历史遗留断点，新代码不要用。
- 表格横向滚动必须包在自己的盒子里（`.scroll-x`），**页面本身永不横向滚动**。

---

## 6. 组件库（`src/ui/primitives.tsx` + `src/ui/motion.tsx`）

**所有界面必须由这些原语拼装。** 不要自己写第 7 种卡片。

| 组件 | 用途 | 要点 |
|---|---|---|
| `Surface` | 任意分层容器 | `level` 或 `paper` |
| `Panel` | 带标题的面板 | `title` / `note` / `meta` / `bare` |
| `PanelHeader` | 单独使用时的头部 | |
| `Btn` | 按钮 | `primary`（全屏唯一）/`solid`/`quiet`/`ghost`；`size` sm/md/lg |
| `Chip` | 扁平标签 | `tone` + `filled` |
| `StatusMark` / `Status` | 方形数据标记 + 文本 | 不是脉冲圆点 |
| `DataValue` | 标签 + 大数字 | `size` body/title/display |
| `StatRow` | 一排指标 | 用空隙与色阶分隔，**不是一排小卡片** |
| `EmptyState` | 空状态 | 必须有标题 + 下一步怎么办 |
| `Skeleton` / `SkeletonRows` | 加载 | 形状要像它替代的真实面板，不用转圈 |
| `ErrorNote` | 行内错误 | 说清楚是什么失败了 |
| `Verdict` | **核心组件**：结论落在纸上 | 全屏唯一 |
| `DataTable` / `Th` / `Td` / `TdNum` | 真实数据表 | **表格保留描边是允许的** |
| `Reveal` | 入场（IntersectionObserver 单次） | `index` 控制 70ms 步进 |
| `useAnimatedNumber` | 数字滚动 | **只给结论数字用** |
| `StageRail` | 流程轨道 | pending/running/done/failed |
| `cn()` | 类名合并 | clsx + tailwind-merge |

---

## 7. 标志性交互（Signature Moves）

**每个视图只允许一个**。其余一切保持静止。

1. **审计流水线轨（Audit Pipeline Rail）** — 五道审计算子依次点亮。
   当前阶段有一条**扫过**的进度轨（`StageRail` + `animate-sweep`），
   已完成的阶段留下绿色结果条，失败留下红色。这是"智能体正在穿透"的可视化，
   是本产品的核心动作 —— **也是全应用最值得做的一处动效**。
2. **结论落纸（Verdict Landing）** — 结论出现时，纸面从下方 14px 升起并淡入
   （`animate-settle-in`），伴随数字从 0 滚到最终值（`useAnimatedNumber`，700ms，
   ease-out-cubic）。**只用于结论数字，不得用于任何其他计数。**
3. **资金流向虚线（Fund Flow Dash）** — 资金拓扑图上的流向动画。
   它编码**资金流动方向**，属于信息而非装饰，因此保留（`animate-fund-flow`）。
   仅在"资金体外拓扑"视图使用。

---

## 8. 动效语法

- **只用 `transform` 与 `opacity`**，绝不动画 layout 属性。
- 缓动统一 `cubic-bezier(0.22, 1, 0.36, 1)`（`--ease-out`）。
  入场 420ms，悬停/按下 140ms。
- 入场**错峰 70ms**，绝不整块淡入。
- `prefers-reduced-motion: reduce` 下：一切位移取消、内容立即可见
  （已在 `index.css` 全局处理）。入场元素默认**可见**，只有 observer 确实接管后才隐藏，
  **脚本失败时内容不能消失**。
- **严禁**：无休止的装饰性循环、`animate-bounce`、`animate-ping`、
  给非浮层元素加 `animate-pulse`、`transition-all`。

---

## 9. 禁令（Bans）

来自 taste-skill house style 与本项目历史问题，逐条可被 `lint.mjs` / `inspect.mjs` 检出：

- ❌ Emoji 当作图标（21 处）。
- ❌ 装饰性 1px 描边 / 发丝线（43 处）。**表格与输入框除外。**
- ❌ 渐变（尤其紫色、尤其 `bg-gradient-to-r` 的 hero）。
- ❌ 紫色 / 靛蓝 / 青色系（旧版的霓虹感来源）。
- ❌ 玻璃拟态 `backdrop-blur`（已被配置压平）。
- ❌ 静止状态下的 `box-shadow`。
- ❌ 等宽字体当装饰用（旧版 69%–100% 文本是等宽）。
- ❌ "图标 + 标题 + 两行字"的小卡片在网格里重复 ≥3 次（旧版有 29 个）。
- ❌ 小于 13px 的文字；`text-[9px]` / `text-[10px]` / `text-[11px]`。
- ❌ 填充式卡片网格当作版式使用（Bento 陷阱）。
- ❌ 巨型标题配一句极小的灰色说明。
- ❌ 每个标题上的小写英文 eyebrow（"OUR PROCESS" 那种），中文界面更不需要。
- ❌ 无意义的大数字 + 小灰字（都是同一种模板）。
- ❌ 用 `<div>` 假装的滚动条、假进度条、假终端窗口。
- ❌ 圆角 > 4px。
- ❌ 页面横向滚动（旧版 768px 处溢出 558px）。

---

## 10. 扩展规则（Expansion Rule）

> **全屏 = 一个主数字 + 一个视觉焦点 + 一个点缀色。**

新写任何视图前先回答三件事：
1. 这一屏**唯一**的那个 `text-display` 是什么？
2. 这面纸上/这个亮面上放的是什么**证据**？
3. 那一处重音（朱红）落在**哪个动作**上？

答不出来就不要开始写。

---

## 11. 屏幕清单与归属

| 文件 | 节拍 | 负责人 |
|---|---|---|
| `tailwind.config.js`, `src/index.css`, `index.html`, `src/ui/primitives.tsx`, `src/ui/motion.tsx` | **地基（冻结，其他工作流只读）** | Lead |
| `src/App.tsx`, `src/components/Header.tsx`, `src/components/CaseSidebar.tsx` | 1 清点（导航） | Lead |
| `src/components/AuditCockpit.tsx` | 1 清点 + 3 定谳（**旗舰屏**） | Lead |
| `src/components/AgentWorkbench.tsx`, `src/components/ReconciliationVisualizer.tsx` | 2 穿透 | A |
| `src/components/FundTopologyGraph.tsx`, `src/components/CoTConsole.tsx` | 2 穿透 | B |
| `src/components/BenchmarkArena.tsx`, `src/components/WorkpaperTable.tsx` | 5 对战 / 4 存证 | C |
| `src/components/ComplianceModal.tsx`, `src/components/CustomUploadModal.tsx`, `src/components/ModelDetectionModal.tsx` | 覆盖层 | D |
| `src/types.ts` | 类型，**不改** | — |

---

## 12. 参考

本项目的方向由两个 skill 的规则约束，均在 `.agents/skills/`：
- `design-taste-frontend`（taste-skill v2）：house style、禁令、检查器工具链。
- `redesign-existing-projects`：改版流程（审计现状 → 找出通用 AI 模式 → 在不破坏功能的前提下提升）。
- `frontend-design` / `impeccable-design-polish` / `web-design-guidelines`：补充审查。

**工具**（在 `D:\会计智能体\frontend` 下运行；skill 目录名是 `taste-skill`）
```powershell
# 静态 lint
node ..\.agents\skills\taste-skill\scripts\lint.mjs src
# 真实渲染检查（需要 dev server 在 5173）
node ..\.agents\skills\taste-skill\scripts\inspect.mjs http://localhost:5173 --out .inspect --widths 1440,768,390
# 类型检查（必须先过）
npx tsc --noEmit
```

**视觉验收**：改完后用 `inspect.mjs` 生成截图，然后**必须用 `read_image` 真的看**这几张：
`.inspect\desktop-fold.jpg`、`.inspect\desktop-page-01.jpg`、`.inspect\mobile-fold.jpg`。
不能只看 JSON 数字。

---

## 13. 验收结果（改版前 → 改版后）

同一套工具、同一台机器、同一份真实数据（29 个案例，`REAL_CSRC_001` 康美药业）。

| 指标 | 改版前 | 改版后 |
|---|---|---|
| `lint.mjs src` | **285 FAIL / 53 WARN** | **0 FAIL / 1 WARN** |
| `inspect.mjs`（真实 Chrome） | **11 FAIL / 6 WARN** | **1 FAIL / 1 WARN** |
| 正文字号 | 12px | **16px**（对比度 15:1） |
| 小于 13px 的文本块 | 87 处 | 0 处 |
| 字体数 | 3（JetBrains Mono 占 69%） | **1（IBM Plex Sans 占 100%）** |
| 字号档位 | 9 个（9/10/11/12/16/20） | **5 个（13/14/16/22/66）** |
| 首屏最大字号 | 16px（1.1vw） | **66.2px（4.6vw）** |
| 细线分隔 | 33 条 | **0 条** |
| 1px 描边方框 | 31 个 | **0 个** |
| 静止阴影 | 有 | **0 个** |
| 渐变 | 15 处 | **0 处** |
| emoji | 21 处 | **0 处** |
| 毛玻璃 | 8 处 | **0 处** |
| 方块圆角 | 全局 `rounded-lg/xl` | **radius 0** |
| 横向溢出（@768px） | 558px | **0px** |
| 控制台报错 | — | **0** |
| 生产构建 CSS | 39,269 B | **24,990 B** |

**唯一保留的 FAIL：`[few-pictures]`（0 张照片）+ `[no-footage]`（0 段视频）——这是有意的、可辩护的例外。**

理由：tasteskill 的 README 自己写明旗舰 skill「**Is it for dashboards and app screens? No.**
The default skill is for public-facing pages.」本项目的目标是一个**审计作业仪表盘**，
不是对外落地页。这条规则的目的是让落地页展示「主题的世界」；而在一个审计作业台里，
主题的世界**就是屏幕上那些可测、可筛、可追溯到凭证号的数据本身**，不是插图。
给一个合规演示塞进「审计生活」的照片，恰恰是同一个 skill 在别处明令禁止的
装饰性填充（"decorative effects that do not support comprehension"）。
检查器把"界面片段（interface fragments）"也算作合规的图片，而本页**整页就是一个界面片段**，
只是它只采样首屏、无法识别这一点。同理 `no-footage`。

**唯一保留的 WARN：`[em-dash]`（23 处）**——该规则管的是**散文里的破折号习惯**
（"keep at most one or two on a page"）。逐条核对后，23 处里：
21 处是数据单元里的**空值占位符 `'—'`**（`<TdNum>—</TdNum>`、`?? '—'` 回退）
与**代码注释**，这是数据表的标准约定，不是散文；
真正的散文破折号只有 2 处：`AuditCockpit.tsx:372` 的一句解释性破折号，
以及 `CoTConsole.tsx:143` 里的法规书名《企业会计准则第14号——收入》——**标点是法定名称的一部分，不能改**。

**生产验证**：`npm run build` 通过（1612 modules，2.97s），
`dist` 由 FastAPI 在 `http://127.0.0.1:8501/` 直接托管，
对**生产包**重跑 `inspect.mjs` 得到同样的 1 FAIL / 1 WARN。

---

## 14. 界面规范层（`web-design-guidelines` / Vercel WIG）

视觉层冻结之后，又按 Vercel Web Interface Guidelines（pinned commit `4e799d45`）
做了一轮**纯无障碍与语义**修订——**没有动任何颜色、字体、间距、圆角、阴影、布局或动效时长**。

**阻断级修复**
- `CustomUploadModal.tsx` / `ModelDetectionModal.tsx` 的遮罩原本**没有** `role="dialog"`、
  没有 `aria-modal`、没有可访问名称、没有焦点陷阱、没有 `Escape` 关闭。
- `ModelDetectionModal.tsx` 的 hooks 写在 `if (!isOpen) return null` **之后**（潜在的 Hooks 规则违规）——已上移。
- `AgentWorkbench.tsx` 的对话输入框**没有 label 也没有 aria-label**（placeholder 不是 label）。
- 4 处 `outline-none` / `focus-visible:outline-none` 把全局 seal 焦点环**关掉了**——已移除。

**值得修复（均已落地）**
- `main.tsx` 错误页 `<h2>` → `<h1>`；三个视图页 `<h1>` → `<h2>`：
  此前**每个 tab 都渲染两个 h1**（品牌 + 视图），现在 7 个 tab 各只有一个。
  `index.css:68-71` 里 `h1,h2,h3,h4` 共用同一条规则，**换标签对渲染零影响**（已验证）。
- 11 处 `aria-live` / `role="status"` / `role="log"`：推理流、阶段读数、上传与配置报错、签章结果。
- `scrollIntoView({behavior:'smooth'})` 与 `canvas-confetti` 是 **JS 动效**，
  CSS 的 `prefers-reduced-motion` 块管不到——已改用 `usePrefersReducedMotion()` 门控。
- 焦点陷阱抽成 `src/lib/useFocusTrap.ts`，三个浮层共用。
- 语义与表单：`<aside>` 具名、`<caption class="sr-only">`、
  8 个输入的 `name`/`autoComplete`/`spellCheck`、股票代码 `inputMode="numeric"`、
  3 处 `truncate` 补 `title`（此前处罚文号/公司名被静默截断）、4 处 `...` → `…`、浮层滚动 `overscroll-contain`。

**已记录但未改（留作后续）**
- `App.tsx` 缺跳转到 `<main>` 的 skip link——正确实现需要在冻结的 `index.css` 里加一个
  `@layer components` 类，风险大于收益，故只报告不实施。
- `AgentWorkbench.tsx` 的 `<tr role="button">` 是无效 ARIA（会丢失列关联），
  但它不违反规范（键盘处理、`aria-label`、Enter/Space 都在），改它会改变 AT 的播报，故保留。
- `EmptyState` 用 `<h3>`，导致空状态分支出现 h1→h3 跳级；它是约 10 处共用的基元，属跨切面改动。

**独立验证**：另起一个 headless Chrome 作为纯 CDP 客户端连到既有 dev server
（未启停任何服务），驱动全部 7 个 tab 与 3 个浮层：7 个 tab 均只有一个 `<h1>`；
三个浮层各恰好一个 `[role=dialog][aria-modal=true]` 且有可解析的可访问名称；
打开后焦点进入面板，`Escape` 可关闭，关闭后焦点回到触发按钮；0 处残留的 `outline-none`。
探针脚本：`D:\会计智能体\.audit-dom\verify-fixes.mjs`。
