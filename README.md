# DeepSeek-AuditMind: 复杂业财融合与数智舞弊穿透智能体

> **2026年北京市大学生数智会计创新应用竞赛 决赛参赛作品**  
> 主办单位：北京市教育委员会 | 承办单位：中央财经大学会计学院  
> 参赛团队：**矛与盾团队** | 核心架构：**Cordis 微内核驱动 + DeepSeek 大模型认知协同**  
> 团队开源仓库：[https://github.com/zhutmg00-eng/accounting-agent-0438](https://github.com/zhutmg00-eng/accounting-agent-0438)

---

## 🎯 参赛主线与系统定位 (Core Mission)

本项目紧扣竞赛核心主赛道——**「注册会计师审计、数智审计与舞弊穿透 (AuditMind)」**，严格遵循《中国注册会计师审计准则第1141号——财务报表审计中与舞弊相关的责任》(CSA 1141) 与《企业会计准则》(CAS 14、CAS 1、CAS 36)，针对资本市场“跨期时序倒挂”、“伪造单据与虚增存款”及“体外资金自循环”等新型高隐蔽舞弊，打造从异构业财数据解析到穿透式审计底稿生成的完整工程闭环：

```
[企业财务总账 / Excel记账凭证 / 增值税发票清单 / 银行流水明细]
                           │
                           ▼
[确定性审计算子矩阵] ──► 借贷试算平衡、三单时序倒挂比对、Beneish M-Score 8因子操纵指数
                           │ (注入只读客观事实切片，100% 精确数学运算，根除大模型计算幻觉)
                           ▼
[DeepSeek 准则研判] ──► 对齐 CAS 14(新收入)、CAS 1(存货)、CAS 36(关联方)、CSA 1141 准则深度定性
                           │
                           ▼
[机构级数智全景审计舱] ─► 彭博风格暗曜石工作台（经典案例直达、7分钟答辩看点、SVG交互式资金拓扑回路）
                           │
                           ▼
[结构化合规底稿一键导出] ─► Excel 标准工作底稿 (.xlsx，含审定表、调整分录及CPA终审签章)、PDF穿透分析报告、全量JSON
```

---

## 🏆 决赛核心要求与六大评审维度对齐 (Official Scoring Pillars)

根据决赛通知与专家评审规程，团队针对六大独立打分维度进行了系统性深度优化与落地：

| 评审维度 | 权重要求 | 本项目工程落地与创新支撑 | 对应模块/文件 |
| :--- | :--- | :--- | :--- |
| **① 专业深度** | 准则对齐与核心算子 | 严格对齐 CAS 14 收入五步法、CAS 1 存货、CAS 36 关联方及 CSA 1141 舞弊审计准则；原生构建 **Beneish M-Score 8 因子刚性测算引擎**（DSRI/GMI/AQI/SGI/DEPI/SGAI/LVGI/TATA）与三单时序倒挂引擎。 | `src/plugins/audit_fraud_plugin/tools.py`<br>`src/core/schemas.py` |
| **② 技术创新** | 架构设计与模型应用 | 首创“**确定性算子 + 大语言模型准则推理**”双飞轮零幻觉架构；原生适配 **DeepSeek-V4.1-Flash**（427 tok/s 吞吐）与 **DeepSeek-V4-Pro**（1.6T MoE 深度思维链），支持模型实时自适应探测与在线/离线平滑切换。 | `src/core/llm_adapter.py`<br>`src/core/harness.py`<br>`frontend/src/components/AgentWorkbench.tsx` |
| **③ 落地可行** | 真实数据与开箱即用 | 支持现场直接上传并解析真实企业 **Excel 记账凭证表**、**CSV 增值税发票清单**、**CSV 银行流水**；具备字段级严格校验与 400 友好拦截；配套 Windows 单端口一键启动脚本（`run.bat`）。 | `src/data_loader/file_importer.py`<br>`src/api/server.py`<br>`run.bat` |
| **④ 效果评估** | 严谨基准与真实案例库 | 基于证监会 (CSRC) 行政处罚决定书，收录涵盖康美药业、康得新、辅仁药业、獐子岛等 **28 例真实重大舞弊与合规对照案例**；构建字段级与金额误差率（$\le 1\%$）严谨评测卡，合规对照组实现**零误报率**。 | `data/cases/real_cases_database.json`<br>`src/benchmark/benchmark_runner.py`<br>`tests/` (48项单测100%通过) |
| **⑤ 文档与展示** | 结构化交付与答辩设计 | 一键生成符合中注协规范的 **标准 Excel 工作底稿 (.xlsx)**（带审定表、调整分录汇总与证据追溯链）及 **PDF 穿透分析报告**；界面采用机构级金融终端风格，内置 7 分钟答辩看点映射面板。 | `src/exporters/excel_exporter.py`<br>`src/exporters/pdf_exporter.py`<br>`frontend/src/components/WorkpaperTable.tsx` |
| **⑥ 伦理与合规** | 隐私保护与人机伦理 | 内置 **DataSanitizer 数据脱敏防护盾**（银行卡/税号/身份证号国家标准级动态脱敏）；推行 **注册会计师终局法定负责制**（CPA Digital Sign-off），生成防伪核验 SHA-256 哈希，彻底杜绝算法独裁；全台严格脱敏，恪守现场匿名红线。 | `src/core/compliance.py`<br>`frontend/src/components/ComplianceModal.tsx`<br>`tests/test_compliance_and_ethics.py` |

---

## 🚀 机构级前端与界面重塑 (Anti-AI-Slop Refinement)

针对传统 AI 生成原型存在的“浮夸霓虹、玩具 Emoji 堆砌、卡片过度嵌套”等廉价感，系统全面吸收了 GitHub 高星反 AI 模板规范（`enterprise-frontend-design`、`ux-skill` 以及彭博/FactSet 机构终端标准），完成专业金融级重塑：

1. **暗曜石金融终端底色 (Obsidian Slate Palette)**：
   - 彻底摒弃 Web3 风格的刺眼荧光青与大面积紫蓝渐变，采用沉稳内敛的 `#0B0F19` 深邃基底与 `#111827` 容器面板，辅以克制的 1px 微分界线；
   - 状态标识遵循严肃法理语义：警示采用正统法理深红，合规采用稳健暗翠绿，主动作采用纯净标准蓝。
2. **去 Emoji 化与证券代码直通车 (Securities Code Presets)**：
   - 剔除所有卡通表情，重构为证券级代码药丸标识：
     - `[600518] 康美药业`（虚增货币 300 亿 / 伪造银行存单）
     - `[002450] 康得新`（虚增存款 122 亿 / 联动池闭环）
     - `[600781] 辅仁药业`（非经营性占用 / 违规担保）
     - `[002069] 獐子岛`（底播存货异常核销 / 异常灭失）
     - `[600660] 福耀玻璃`（真实资本市场合规对照 · 零误报）
3. **原生矢量 SVG 交互式资金拓扑网络 (SVG Topology Matrix)**：
   - 采用自适应矢量 SVG 替代脆弱的 Canvas，**彻底根治 Canvas 在分辨率变化或标签切换时宽度坍缩为 0 的行业通病**；
   - 动态虚线流动回路清晰勾勒资金划出、虚假账户、实控人过桥、虚假购销至资金回流的自闭环；
   - 正下方常驻**五步资金链路穿透明细表**，支持远距离投影仪汇报时评委一目了然。
4. **注会实务工作备忘录排版 (Audit Memorandum)**：
   - 发现项按实务规范自动编制编号（`RF-01`, `RF-02`），分层严谨列示【客观事实证据】、【依据准则条款】及【建议审计程序】，并配备一键复制证据链工具。

---

## ⚡ 极速启动与运行指南

### 方式一：Windows 一键双击极速启动（比赛现场推荐）
直接双击根目录下的 **`run.bat`**，系统将自动自检依赖、单端口（8501）全量托管 FastAPI 后端与 React 18 SPA，并在默认浏览器直接打开：
👉 `http://localhost:8501`

### 方式二：命令行启动
```bash
# 1. 克隆项目与同步环境
git clone https://github.com/zhutmg00-eng/accounting-agent-0438.git
cd accounting-agent-0438
uv sync   # 或 pip install -e .

# 2. 启动单端口整合服务 (FastAPI + SPA 统一托管)
uv run python main.py

# 3. 运行自动化评测基准套件 (28 案例全量评分卡)
uv run python src/benchmark/benchmark_runner.py

# 4. 运行全量自动化测试套件 (48 项全测试 100% 绿灯通过)
uv run pytest -v
```

---

## 📂 核心代码目录结构

```
accounting-agent-0438/
├── .github/workflows/ci.yml       # GitHub Actions 云端自动化持续集成 (CI)
├── run.bat                        # Windows 现场一键双击极速启动脚本
├── main.py                        # 统一托管启动器 (FastAPI 单端口 8501 托管 SPA)
├── pyproject.toml                 # 现代工程依赖与配置锁
├── data/
│   ├── templates/                 # 供现场导入下载的标准 Excel/CSV 账套模板
│   └── cases/                     # 28 例中国证监会真实处罚案例与合规对照数据集
│       └── custom_cases/          # 自定义上传案例持久化存储目录
├── frontend/                      # 机构级数智全景审计指挥舱 (React 18 + Tailwind)
│   ├── src/
│   │   ├── components/            # UI 核心组件 (指挥舱、勾稽飞轮、SVG拓扑、底稿台、伦理模态框)
│   │   │   ├── AuditCockpit.tsx   # 审计指挥大屏、经典案例直通车与 7 分钟看点面板
│   │   │   ├── FundTopologyGraph.tsx # 原生矢量 SVG 交互式资金体外循环拓扑矩阵
│   │   │   ├── WorkpaperTable.tsx # 审计工作底稿、审定表与 CPA 终审数字签章展台
│   │   │   ├── ComplianceModal.tsx# 数智会计伦理、合规与数据安全白皮书模态框
│   │   │   └── ...
│   │   └── types.ts               # 前端强类型 TypeScript 定义
│   └── dist/                      # 生产环境编译构建静态产物
├── src/
│   ├── config.py                  # DeepSeek 模型与环境配置
│   ├── api/
│   │   └── server.py              # FastAPI 高性能后端、防缓存中间件、SSE 流与 REST 接口
│   ├── core/                      # 智能体核心引擎与微内核
│   │   ├── compliance.py          # 【伦理与合规】DataSanitizer 脱敏盾与 CPA 签章存证引擎
│   │   ├── schemas.py             # 强类型数据模型、三层证据链与 Beneish 结构
│   │   ├── llm_adapter.py         # DeepSeek-V4.1/V4 Pro 三模自适应与无泄漏准则推理
│   │   └── harness.py             # 审计算子流水线调度与评测执行引擎
│   ├── data_loader/               # 真实文件导入与字段级校验器
│   ├── plugins/                   # 业务算子插件中心
│   │   ├── audit_fraud_plugin/    # 【主赛道】数智审计与舞弊穿透算子矩阵
│   │   └── cost_analysis_plugin/  # 【扩展】管理会计决策算子
│   ├── exporters/                 # 规范化底稿导出器 (Excel .xlsx / PDF / JSON)
│   └── benchmark/                 # 28 例证监会真实案例评测基座与评分卡
└── tests/                         # 自动化测试用例套件 (48/48 100% 绿灯通过)
    ├── test_compliance_and_ethics.py # 伦理合规、敏感数据脱敏与 CPA 签章测试
    ├── test_upload_closed_loop.py    # Excel/CSV 文件解析与审计闭环测试
    ├── test_benchmark_isolation.py   # 基准隔离与变异事实敏感性检验
    ├── test_agent_and_deepseek.py    # DeepSeek 模型识别与 Agent 交互测试
    └── ...
```

---

## 🔒 伦理、合规与赛纪匿名性承诺

1. **严格遵守大赛现场匿名红线**：项目前端大屏、导出底稿模板、系统标题及代码注释已全面脱敏，**100% 无任何参赛院校名称或学院标识**，仅展示团队代号“矛与盾”与成员姓名，坚决捍卫大赛纪律。
2. **数据安全与隐私合规**：所有导入数据均受 `DataSanitizer` 脱敏防护盾保护，符合《中华人民共和国数据安全法》与《中华人民共和国个人信息保护法》；分析过程在内存临时会话执行，绝不反哺公共模型语料。
3. **算法透明与 CPA 终局负责**：坚守《中国注册会计师职业道德守则》，AI 仅作为实质性程序辅助工具，最终审计结论与法律责任由执业注会终局签署把关，严禁算法独裁。
