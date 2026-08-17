# 线变关系智能校验工具使用说明

本文档面向第一次接触本项目的学生、开发者和面试官，说明如何安装、运行、查看结果、复现实验以及排查常见问题。项目全部公开结果来自合成配电网仿真，不含真实电网数据。

## 1. 项目能做什么

工具校验“10 kV 馈线—配电变压器”台账从属关系。它先生成物理拓扑和时序潮流量测，再构造一份可能存在错误的台账副本，最后利用配变电压、有功功率及事件同步性完成：

- 疑似错误检测；
- 候选馈线排序；
- 推荐馈线与置信度输出；
- 数据不足的保守拒绝；
- 默认运行、鲁棒性实验、图表和报告的证据追溯。

这是一套研究型工程原型，不是生产调度系统。默认公开结果的 F1 为 0.167，说明当前合成参数下馈线间可分性较弱；项目价值在于完整实现和公开失效边界，而非制造高指标。

## 2. 环境要求

- Python 3.11 或 3.12；不支持 Python 3.13。
- Windows 10/11、Linux 或 macOS。
- 默认完整运行建议至少预留 4 GB 内存和数十分钟；小规模冒烟配置通常在数分钟内完成。
- PDF 与论文图表重建需要可选的 `docs` 依赖。
- GitHub 发布或拉取不是本地运行的必要条件。

先确认 Python 版本：

```text
python --version
```

Windows 同时安装多个 Python 时可使用：

```text
py -3.12 --version
```

## 3. 安装

### 3.1 Windows

在仓库根目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

如需重建论文图表和 PDF：

```powershell
.venv/Scripts/python.exe -m pip install -e ".[dev,docs]"
```

### 3.2 Linux 或 macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

重建论文时安装：

```bash
.venv/bin/python -m pip install -e ".[dev,docs]"
```

### 3.3 安装自检

```text
.venv/Scripts/python.exe -m ltverify --help
```

Linux/macOS 将解释器路径替换为 `.venv/bin/python`。帮助中应出现 `run-all`、`experiments` 和 `report` 三个命令。

## 4. 快速开始

### 4.1 运行小规模冒烟场景

建议第一次先运行 3 馈线 × 3 配变、1 天的测试配置：

```text
.venv/Scripts/python.exe -m ltverify run-all --config tests/fixtures/small_config.yaml
```

命令完成后会输出类似 `runs/run-...` 的目录。该目录是后续报告和看板的输入。

### 4.2 运行默认 30 天场景

Windows 一键脚本：

```powershell
scripts/run_pipeline.ps1
```

跨平台等价命令：

```text
.venv/Scripts/python.exe -m ltverify run-all --config configs/default.yaml
```

Linux/macOS：

```bash
.venv/bin/python -m ltverify run-all --config configs/default.yaml
```

默认场景包括 3 条馈线、每条 8 台配变、30 天和 15 分钟采样间隔，共 2880 个时刻。重新运行会生成新的 run ID 和时间戳，不会逐字节等于历史公开运行。

## 5. 命令行

### 5.1 `run-all`：完整流水线

```text
python -m ltverify run-all --config <YAML配置路径>
```

依次完成网络构建、负荷/光伏曲线、时序潮流、物理校验、台账错误与量测扰动、预处理、候选特征、评分、评价和运行清单写入。潮流不收敛是硬失败；配置指定的严重物理越限也会终止流水线。

### 5.2 `experiments`：鲁棒性和消融实验

```text
python -m ltverify experiments --config configs/robustness.yaml
```

标准配置执行 130 个案例：5 个单因素实验族 × 4 个水平 × 5 个随机种子，加上 6 个消融版本 × 5 个随机种子。输出目录名称以 `runs/experiments-` 开头。

### 5.3 `report`：验证后生成规范摘要

```text
python -m ltverify report \
  --run-dir reports/evidence/default_run \
  --output <输出目录>/default_summary.json \
  --manifest-output <输出目录>/default_manifest.json
```

Windows PowerShell 示例：

```powershell
$out = Join-Path $env:TEMP "ltverify-report"
New-Item -ItemType Directory -Path $out -Force | Out-Null
.venv/Scripts/python.exe -m ltverify report `
  --run-dir reports/evidence/default_run `
  --output (Join-Path $out "default_summary.json") `
  --manifest-output (Join-Path $out "default_manifest.json")
```

`report` 会先检查 schema-v2 清单、输出声明、路径安全性和 SHA-256，再解析数据。篡改产物但不更新清单时，读取会被拒绝。

## 6. 可视化看板

### 6.1 启动

Windows 推荐：

```powershell
scripts/run_dashboard.ps1 -RunDir reports/evidence/default_run
```

也可以先设置环境变量后启动：

```powershell
$env:LTVERIFY_RUN_DIR = "reports/evidence/default_run"
.venv/Scripts/python.exe -m streamlit run app/streamlit_app.py
```

Linux/macOS：

```bash
LTVERIFY_RUN_DIR=reports/evidence/default_run \
  .venv/bin/python -m streamlit run app/streamlit_app.py
```

浏览器默认打开 `http://localhost:8501`。看板只接受当前 schema-v2 运行目录，并在展示前验证清单哈希。

### 6.2 界面语言

侧边栏“界面语言”提供“简体中文”和 `English`。默认简体中文。切换会更新入口、导航、五个页面、图表、指标卡和展示表格；T001、F01、文件名、命令、kV、p.u.、PR-AUC 和 SHA-256 等技术标识保持原样。

翻译发生在展示副本，不修改 DataFrame、算法字段、运行产物或哈希。

### 6.3 五个页面

1. **网络拓扑**：查看母线、线路和配变结构；普通模式用中性色隐藏物理馈线，演示评价模式才显示真值着色。
2. **配变诊断**：选择配变，查看台账馈线、推荐馈线、判定、置信度、覆盖率、电压曲线和候选评分。
3. **相似度矩阵**：切换原始电压、去公共趋势残差和一阶差分，观察 Pearson 相关矩阵。
4. **模型评估**：查看混淆矩阵、Precision、Recall、F1、PR-AUC、Top-k 和覆盖率。PR 曲线需要真实标签，只在演示评价模式显示。
5. **鲁棒性实验**：加载聚合结果和案例明细，按实验族和指标查看均值、样本标准差和失败原因。

### 6.4 演示评价模式

演示评价模式会显示物理真值、真实标签和 PR 曲线，只用于合成数据评价。普通业务模式默认关闭，避免在模型输入或普通展示中泄漏真值。

## 7. 运行产物

每个已完成运行通常包含：

| 文件 | 用途 |
|---|---|
| `manifest.json` | schema、配置摘要、输入输出声明和 SHA-256 |
| `config.snapshot.yaml` | 实际运行配置快照 |
| `truth_topology.csv` | 物理馈线真值，仅用于评价 |
| `reported_ledger.csv` | 可能含错误的台账副本 |
| `observed_measurements.parquet` | 注入噪声、缺失和时移后的量测 |
| `candidate_features.parquet` | 配变—候选馈线特征 |
| `predictions.parquet` | 判定、推荐、分数、覆盖率与置信度 |
| `metrics.json` | 检测、排序、覆盖率和物理校验指标 |
| `confusion_matrix.csv` | 二分类混淆矩阵计数 |
| `simulation_validation.csv` | 每时刻收敛、电压、负载率和功率平衡 |

详细字段见[数据字典](../data/README.md)，算法定义见[方法论](methodology.md)。

### 7.1 判定值

- `automatic_recommendation`：门禁同时满足，可自动推荐候选馈线；
- `review_required`：证据提示异常但不足以自动推荐，需人工复核；
- `no_change`：未发现足够的台账异常证据；
- `insufficient_data`：有效覆盖率或候选证据不足，不强行判定。

### 7.2 指标口径

- **Precision/Recall/F1**：台账错误检测指标；
- **PR-AUC**：连续 `anomaly_score` 的排序质量，适合正负样本不平衡场景；
- **PR-AUC scored**：仅可评分子集的诊断口径，必须与 `scored_coverage` 同时解读；
- **Top-1/Top-2 修正率**：实际错误配变中，物理馈线进入候选排序前 1/2 的比例；
- **automatic_coverage**：获得自动推荐的设备比例；
- **insufficient_data_rate**：被数据质量门禁拒绝的比例。

三馈线场景中 Top-3 没有区分度，项目标记为不适用。Accuracy 不作为主结论。

## 8. 公开证据复现

仓库自带 `reports/evidence/default_run/`，新 clone 不需要先运行 30 天仿真即可验证历史权威结果。

生成临时报告后，Windows 可逐字节比较：

```powershell
Compare-Object `
  (Get-Content "$out/default_summary.json" -Raw) `
  (Get-Content "reports/metrics/default_summary.json" -Raw)
Compare-Object `
  (Get-Content "$out/default_manifest.json" -Raw) `
  (Get-Content "reports/metrics/default_manifest.json" -Raw)
```

没有输出表示文本一致；发布审计使用字节哈希作更严格比较。

清单是完整性机制而不是身份认证：SHA-256 能发现意外损坏或只改产物未改清单的变化；若攻击者能同时改写产物和清单，它不能证明发布者身份。详细说明见[公开审计摘要](audit-summary.md)和[证据包说明](../reports/evidence/README.md)。

## 9. 鲁棒性实验

运行：

```text
.venv/Scripts/python.exe -m ltverify experiments --config configs/robustness.yaml
```

权威发布结果位于：

- `reports/metrics/robustness_summary.csv`：逐案例结果；
- `reports/metrics/robustness_aggregates.csv`：跨随机种子聚合；
- `reports/metrics/robustness_experiment_manifest.json`：配置快照、计数和输出哈希。

严格验证必须同时提供原始实验配置和基础配置：

```python
import json
from pathlib import Path

from ltverify.experiments import verify_experiment_manifest

artifact_dir = Path("reports/metrics")
manifest = json.loads(
    (artifact_dir / "robustness_experiment_manifest.json").read_text(encoding="utf-8")
)
mode = verify_experiment_manifest(
    manifest,
    artifact_dir,
    experiment_config_path=Path("configs/robustness.yaml"),
    base_config_path=Path("configs/default.yaml"),
    require_source_configs=True,
)
assert mode == "strict"
```

离线模式只证明产物内部一致，不能证明嵌入快照来自当前源 YAML。

## 10. 教学 Notebook

三个 Notebook 都可以从头执行：

1. `notebooks/01_network_sanity.ipynb`：网络结构与物理健全性；
2. `notebooks/02_baseline_analysis.ipynb`：原始 Pearson 基线和增强方法对比；
3. `notebooks/03_robustness_analysis.ipynb`：小型鲁棒性实验与聚合图。

启动 Jupyter：

```text
.venv/Scripts/python.exe -m jupyter lab
```

发布检查通过 `nbconvert --execute` 在临时目录执行，避免覆盖仓库中的 Notebook 输出。

## 11. 故障排查

### 11.1 `No module named ltverify`

确认当前目录是仓库根目录，并执行：

```text
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

### 11.2 看板提示运行目录无效

只选择状态为 `completed` 且包含 schema-v2 `manifest.json` 的运行目录。不要选择 `runs/` 根目录或单个文件。

### 11.3 清单哈希校验失败

运行产物被修改、复制不完整或清单没有同步更新。不要手工“修复”哈希来掩盖原因；重新运行流水线，或恢复完整的权威证据包。

### 11.4 `unexpected keyword argument 'locale'`

这通常发生在开发过程中：Streamlit 热重载了页面，却仍缓存旧版 Python 模块。停止旧进程并完整重启：

```text
Ctrl+C
.venv/Scripts/python.exe -m streamlit run app/streamlit_app.py
```

随后在浏览器按 `Ctrl+F5`。正式 clone 同一提交后启动不会产生这种新旧模块混用。

### 11.5 潮流不收敛或物理越限

先阅读失败运行 `manifest.json` 中的 `failure_summary`，再检查配置中的负荷、光伏、电压上下限、变压器容量和功率平衡容差。不要降低物理门槛只为让实验通过。

### 11.6 中文乱码

PowerShell 输出乱码不代表产物编码错误。仓库文本统一为 UTF-8；可先执行：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### 11.7 默认运行时间较长

先用 `tests/fixtures/small_config.yaml` 验证环境。默认配置包含 2880 次时序潮流，耗时显著高于冒烟场景。

## 12. 项目边界

- 全部公开数据是合成数据，不能外推为真实电网效果。
- 当前模型是平衡正序交流潮流，不处理三相不平衡、相别识别和户变关系。
- 默认结果 F1 仅 0.167，未达到生产使用要求。
- 权重和阈值为预先固定的启发式设置，尚未由独立真实数据标定。
- DTW、Isolation Forest、随机森林和 GNN 尚未接入主流水线，只能作为后续方向。
- 清单没有数字签名或远程可信时间戳。
- 工具输出应作为人工复核线索，不能直接驱动调度操作或资产台账修改。

## 13. 面试演示

推荐 3 分钟顺序：

1. **30 秒业务问题**：线路改造与台账更新不同步会影响线损、停电研判和数据贯通；
2. **30 秒数据链**：pandapower 构造物理网络，错误只写入台账副本，防止真值泄漏；
3. **60 秒算法**：原始相关只是基线，增强方案融合残差、差分、滚动、事件和有功证据，并使用覆盖率与间隔门禁；
4. **40 秒看板**：展示配变诊断、相似度矩阵、模型评估和鲁棒性页面；
5. **20 秒诚实边界**：默认 F1 0.167，说明当前参数下馈线可分性不足；
6. **20 秒工程价值**：强调 425+ 自动测试、证据哈希、配置快照、公开复现和中英文界面。

不要背诵“高准确率”。面试官更可能认可你能解释负面结果、定位原因并设计下一轮实验。更完整的话术见[面试指南](interview-guide.md)，系统架构见[设计说明](design.md)，AI 辅助边界见[AI 使用说明](../AI_USAGE.md)。

## 14. 质量检查

```text
.venv/Scripts/python.exe -m ruff format --check src app tests scripts
.venv/Scripts/python.exe -m ruff check src app tests scripts
.venv/Scripts/python.exe -m pytest --cov=ltverify --cov-report=term-missing --cov-fail-under=90
```

论文图表和 PDF：

```text
.venv/Scripts/python.exe scripts/generate_paper_figures.py
.venv/Scripts/python.exe scripts/build_paper.py
```

项目采用 MIT 许可证，详见[许可证](../LICENSE)。
