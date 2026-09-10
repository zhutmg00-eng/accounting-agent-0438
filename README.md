# DeepSeek-AuditMind: 复杂业财融合与数智舞弊穿透智能体

> **2026年北京市大学生数智会计创新应用竞赛 参赛作品**  
> 主办单位：北京市教育委员会 | 承办单位：中央财经大学会计学院  
> 团队开源仓库：[https://github.com/zhutmg00-eng/accounting-agent-0438](https://github.com/zhutmg00-eng/accounting-agent-0438)

---

## 🎯 参赛主线与系统定位 (Core Mission)

本项目聚焦竞赛核心场景——**「数智审计与舞弊穿透 (AuditMind)」**，打造从财务数据导入到审计底稿生成的完整闭环：

```
[企业财务总账/明细/流水] 
       │
       ▼
[确定性审计算子] ────► 借贷试算平衡、三单时序勾稽倒挂比对、Beneish M-Score 8变量操纵指数
       │
       ▼
[DeepSeek 大模型研判] ─► 依据 CAS 14(新收入)、CAS 1(存货)、CAS 36(关联方)、CSA 1141 准则深度定性
       │
       ▼
[数智穿透仪表盘] ───► 具体数据问题精准下钻（时序倒挂天数、借贷差额、8维雷达、体外资金闭环）
       │
       ▼
[结构化成果一键导出] ─► 标准审计工作底稿 (.xlsx)、数智穿透报告 (.pdf)、全量结构化数据 (.json)
```

> **功能划分说明**：
> - **核心参赛主线**：数智审计与舞弊穿透插件（现场演示与评测核心）；
> - **答辩扩展模块**：管理会计本量利决策插件（CostAgent，保留在侧边栏折叠区供评委提问时展开展示）。

---

## 🚀 竞赛原型核心补强与可靠性特性 (V2 升级)

1. **五分钟闭环演示体验**：
   - 界面分为数据导入、智能体研判、数据问题大屏、审计工作底稿、评测基座与一键导出 5 大清晰主流程。
2. **真实文件导入与字段级校验 (Issue 2)**：
   - 支持现场上传真实 **Excel 记账凭证表**、**CSV 增值税发票清单**、**CSV 银行对账单明细**；
   - 具备字段级严格校验与友好提示（缺失列、日期格式错误、金额非法），并提供开箱即用的标准模板下载。
3. **杜绝静默回退的三档运行模式 (Issue 3)**：
   - **🔴 严格在线模式 (Strict-Online)**：API 调用失败立即显式报错中断，绝不自动转为 Mock，确保模型真实可信；
   - **🟢 在线优先模式 (Online)**：优先调用线上 DeepSeek API，发生降级时显式记录并告警；
   - **🟡 离线确定性演示 (Mock/Demo)**：纯本地启发式规则推理，标注“模拟演示结果”，现场防掉线兜底保障。
4. **字段级与金额级（误差≤1%）严谨评测基座 (Issue 4)**：
   - 告别模糊文本关键词包含，采用枚举级风险类型匹配、严重度匹配、涉案金额误差（$\le 1\%$）判定及对照组零误报率统计。
5. **三层审计证据追溯链 (Issue 5)**：
   - 每项发现明确区分为：**【确定性客观事实】**、**【DeepSeek 大模型准则深度研判】**、**【待注册会计师现场核实程序】**，并在 Excel 与 PDF 中全面呈现。
6. **Windows 一键双击极速启动 (Issue 6)**：
   - 根目录下提供 `run.bat`，双击即可自检环境并直达浏览器演示大屏。

---

## 🏆 满足竞赛硬性要求对照表

| 竞赛通知硬性要求 | 本项目实现与落地保障 | 对应模块/文件 |
| :--- | :--- | :--- |
| **1. 核心模型**：必须使用至少一个大语言模型 | 原生集成 **DeepSeek-V3 / DeepSeek-R1**，提供严格在线模式与离线模式显式切换 | `src/core/llm_adapter.py` |
| **2. 输出格式**：必须输出结构化结果（表格/PDF） | 自动生成 **Excel 标准审计工作底稿 (.xlsx)**、**PDF 审计穿透报告** 与 **JSON** | `src/exporters/` |
| **3. 演示原型**：现场可实时处理样例数据 | 提供 **Streamlit 现代化 Web 演示大屏** 与 **run.bat 一键启动器**，支持现场上传真实文件 | `src/ui/app.py` & `run.bat` |
| **4. 专业深度**：围绕注会审计、舞弊场景 | 深度融入《中国注册会计师审计准则》(CSA 1141)、《企业会计准则》(CAS 14、CAS 1、CAS 36) 及 Beneish M-Score 模型 | `src/plugins/audit_fraud_plugin/` |

---

## ⚡ 极速启动与运行指南

### 方式一：Windows 一键启动（推荐比赛现场使用）
直接双击根目录下的 **`run.bat`**，系统将自动检查依赖并在默认浏览器打开：
👉 `http://localhost:8501`

### 方式二：命令行启动
```bash
# 1. 克隆项目与同步依赖
git clone https://github.com/zhutmg00-eng/accounting-agent-0438.git
cd accounting-agent-0438
uv sync   # 或 pip install -e .

# 2. 运行严谨评测基准套件 (自动化评分卡)
uv run python src/benchmark/benchmark_runner.py

# 3. 运行自动化单元测试 (全部通过)
uv run pytest -v

# 4. 启动 Streamlit 数据问题穿透大屏
uv run streamlit run src/ui/app.py
```

---

## 📂 核心代码目录结构

```
accounting-agent-0438/
├── run.bat                     # Windows 一键启动脚本
├── start_demo.ps1              # 演示增强自检启动脚本
├── ROADMAP.md                  # 产品演进与 Issue 清单
├── pyproject.toml              # 现代依赖与配置锁
├── data/
│   ├── templates/              # 供用户下载的标准 Excel/CSV 导入模板
│   └── cases/                  # 4 大实战基准案例数据
├── src/
│   ├── config.py               # 配置与环境变量管理
│   ├── core/                   # 核心智能体基座与微内核
│   │   ├── schemas.py          # 强类型数据模型与证据链定义
│   │   ├── llm_adapter.py      # 区分严格在线与模拟的三模 LLM 适配器
│   │   └── harness.py          # 智能体执行流水线与严谨评测引擎
│   ├── data_loader/            # 真实文件导入与校验器 (Issue 2)
│   │   └── file_importer.py    # Excel 凭证、CSV 发票与银行流水解析器
│   ├── plugins/                # 业务插件中心
│   │   ├── audit_fraud_plugin/ # 【主线】数智审计与舞弊穿透 (AuditMind)
│   │   └── cost_analysis_plugin/#【扩展】管理会计本量利决策 (CostAgent)
│   ├── ui/                     # 交互界面与仪表盘
│   │   ├── app.py              # Streamlit 比赛主线演示大屏
│   │   └── dashboard_view.py   # 数据问题穿透大屏 (8维雷达/时序倒挂/资金闭环)
│   ├── exporters/              # 成果导出器 (Excel/PDF/JSON)
│   └── benchmark/              # 评测基座与 4 大实战案例集
└── tests/                      # 自动化测试用例套件
```
