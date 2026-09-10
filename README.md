# DeepSeek-AuditMind: 数智业财融合与舞弊穿透智能体基座 (Agent Harness)

> **2026年北京市大学生数智会计创新应用竞赛 参赛作品**  
> 主办单位：北京市教育委员会 | 承办单位：中央财经大学会计学院

---

## 📖 项目简介与设计理念

本项目针对 **2026年北京市大学生数智会计创新应用竞赛** 打造，深度融合 **大语言模型（DeepSeek-V3 / DeepSeek-R1）推理能力** 与 **会计/审计专业实务准则**。

架构全面依托 **DeepSeek Harness** 的 **“一切皆插件 (Everything is a Plugin)”** 设计范式：
- **核心推理引擎**：统一适配 DeepSeek API（支持 `deepseek-chat` 与 `deepseek-reasoner`），兼顾国产主流模型与离线高精度规则引擎；
- **插件体系 (Plugin-Based Architecture)**：通过统一的插件规范解耦领域知识，已内置 **数智审计与舞弊穿透插件 (AuditMind)** 与 **管理会计本量利决策插件 (CostAgent)**；
- **确定性校验卫士 (Deterministic Verification Guard)**：引入 Beneish M-Score、借贷平衡校验、三单勾稽比对等纯数学算子，彻底根除大模型在财务场景下的“数字幻觉”；
- **标准化输出与评测基座 (Benchmark Harness)**：支持一键导出 **标准审计工作底稿 (.xlsx)**、**审计穿透报告 (.pdf)** 与 **结构化数据 (.json)**，并内置 4 大实战案例基准评测体系。

---

## 🏆 满足竞赛硬性要求对照

| 竞赛通知硬性要求 | 本项目实现与落地保障 | 对应模块/文件 |
| :--- | :--- | :--- |
| **1. 核心模型**：必须使用至少一个大语言模型（建议国产大模型） | 原生集成 **DeepSeek-V3 / DeepSeek-R1**，支持国内标准 OpenAI 兼容接口，并支持离线确定性评测模式 | `src/core/llm_adapter.py` |
| **2. 输出格式**：必须输出结构化结果（JSON/表格/PDF），严禁纯自然语言闲聊 | 严格基于 Pydantic 结构化输出，自动生成 **Excel 标准审计底稿**、**PDF 审计报告** 与 **JSON 数据包** | `src/exporters/` & `src/core/schemas.py` |
| **3. 演示原型**：必须提供可演示原型，现场可实时处理样例数据 | 打造 **Streamlit 现代化 Web 演示大屏** 与 **Rich CLI 命令行交互终端**，评委现场可实时上传数据或一键运行案例 | `src/ui/app.py` & `src/ui/cli.py` |
| **4. 专业深度**：围绕注会审计、内部审计、管理会计等场景 | 深度融入《中国注册会计师审计准则》(CSA 1141等)、《企业会计准则》(CAS 14新收入准则五步法、CAS 1存货、CAS 36关联方)及 Beneish M-Score 模型 | `src/plugins/audit_fraud_plugin/` |

---

## 🧱 核心系统架构

```
会计智能体/
├── pyproject.toml              # 项目依赖与 Python 3.12 虚拟环境配置
├── .env.example                # 环境变量配置模板 (DeepSeek API Key 等)
├── README.md                   # 项目完整技术文档与使用说明
├── src/
│   ├── config.py               # 全局设置与路径配置 (全部数据与输出均在 D 盘)
│   ├── core/                   # 智能体核心框架
│   │   ├── schemas.py          # 结构化领域数据模型 (Pydantic)
│   │   ├── llm_adapter.py      # DeepSeek 统一适配器 (支持 API / 动态 Mock)
│   │   ├── plugin_base.py      # "一切皆插件" 插件基类接口
│   │   ├── plugin_registry.py  # 插件动态注册与发现中心
│   │   └── harness.py          # 智能体执行与评测流水线 (Agent Harness)
│   ├── plugins/                # 业务插件库
│   │   ├── audit_fraud_plugin/ # 【核心插件】数智审计与舞弊穿透 (AuditMind)
│   │   │   ├── plugin.py       # 插件主逻辑与准则匹配
│   │   │   ├── tools.py        # Beneish M-Score / 三单勾稽 / 借贷平衡算子
│   │   │   └── prompts.py      # 注会准则专业 Prompt 库
│   │   └── cost_analysis_plugin/# 【拓展插件】本量利分析与管理会计决策 (CostAgent)
│   │       ├── plugin.py
│   │       └── tools.py        # 边际贡献率 / 保本点 / 安全边际算子
│   ├── exporters/              # 结构化成果生成器
│   │   ├── excel_exporter.py   # 标准审计工作底稿 (.xlsx) 导出
│   │   ├── pdf_exporter.py     # 审计风险穿透报告 (.pdf) 导出
│   │   └── json_exporter.py    # 结构化结果 (.json) 导出
│   ├── benchmark/              # 评测基座与自动化评分
│   │   ├── test_cases.py       # 4 大实战案例库 (真值标注与脱敏数据)
│   │   └── benchmark_runner.py # 自动化指标评分卡 (Precision/Recall/F1/零幻觉率)
│   └── ui/                     # 现场路演原型
│       ├── app.py              # Streamlit Web 大屏演示系统
│       └── cli.py              # 命令行运行与批量导出入口
├── tests/                      # 自动化单元测试与集成测试
│   └── test_harness.py
└── output/                     # 成果输出目录 (Excel / PDF / JSON)
```

---

## 🎯 实战案例库 (Benchmark Cases)

1. **案例 1：华创数智科技（跨期提前确认收入与应收账款虚增）**
   - **痛点**：资产负债表日前（12月30日）突击确认 1,250 万元未验收集成项目尾款，三单比对发现凭证日期早于发票与客户终验报告日期，Beneish M-Score > -1.78；
   - **智能体动作**：依据 CAS 14 新收入准则五步法锁定控制权未转移事实，生成《营业收入截止测试底稿》并提出审计调减建议。
2. **案例 2：恒远重工制造（虚假采购与存货在途挂账异常）**
   - **痛点**：年末向成立仅2个月的空壳供应商预付 860 万元采购特种钢材并在途挂账，库房无入库记录与物流记录；
   - **智能体动作**：依据 CAS 1 存货准则与 CSA 1141 准则锁定存货虚增与入库单缺失，生成在途物资实质性测试底稿。
3. **案例 3：天辰供应链科技（关联方隐蔽资金体外循环）**
   - **痛点**：通过隐蔽关联方以贸易货款名义转出 1,500 万元，3日内原路以借款形式回流，无真实实物交付；
   - **智能体动作**：依据 CAS 36 关联方披露准则识别体外循环与商业实质缺失，输出专项关联交易排查底稿。
4. **案例 4：北方精密工业（合规企业基准对照组）**
   - **特征**：三单勾稽完全一致，凭证、发票、合同、银行流水真实闭环，评测基座输出 `CLEAN` 合规结论。

---

## 🚀 快速启动指南

### 1. 运行自动化测试与评测基座
```bash
# 运行全部自动化单元与集成测试 (100% 通过)
uv run pytest -v

# 运行评测基座基准测试 (输出 Rich 终端评分卡)
uv run python src/ui/cli.py --benchmark
```

### 2. 命令行单案例执行与成果导出
```bash
# 运行案例 0 (华创数智科技) 并自动生成 Excel 底稿、PDF 报告与 JSON 数据
uv run python src/ui/cli.py --case 0 --export
```

### 3. 启动现场路演 Web 交互大屏 (Streamlit)
```bash
uv run streamlit run src/ui/app.py
```
> 启动后访问 `http://localhost:8501`，可在 Web 界面实时切换案例、配置模型 API、查看 CoT 推理流与一键下载成果文件！
