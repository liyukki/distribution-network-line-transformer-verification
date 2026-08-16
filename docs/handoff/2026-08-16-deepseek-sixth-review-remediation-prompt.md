# DeepSeek Agent Harness 第六轮整改主提示词

> 适用项目：`distribution-network-line-transformer-verification`
> 工作目录：`D:\电力`
> 审核基线：Git `main` 分支，提交 `67aaeb3`
> 当前验证基线：pytest 94 passed；Ruff all checks passed
> 生成日期：2026-08-16

---

## 一、直接复制给 DeepSeek 的主提示词

你正在维护一个用于“电网/能源数字化实习”作品集的项目：

`distribution-network-line-transformer-verification`

请在仓库 `D:\电力` 中执行第六轮整改。必须实际检查代码、先补失败测试、完成修改、重新验证并创建本地提交。不要只输出建议，不要因为当前 94 项测试通过就跳过本轮问题。

### 1. 开始前必须阅读

1. `docs/handoff/2026-08-16-sixth-review-report.md`
2. `docs/handoff/2026-08-16-deepseek-fifth-review-remediation-prompt.md`
3. `README.md`
4. `docs/methodology.md`
5. `data/README.md`
6. `configs/default.yaml`
7. `configs/robustness.yaml`
8. 本文列出的源代码和测试文件。

### 2. 第六轮独立审核结论

GLM 报告中“仅剩 3 项 P4、可以收口”的结论不成立。Codex 已通过源码检查和运行时复现确认：

- 1 项 P1：交付版鲁棒性清单声明的输出文件不存在；
- 3 项 P2：实验配置依赖 CWD、报告先读取后验签、schema 边界崩溃或误分类；
- 3 项 P3：报告目标可互相覆盖、base-case 违规不可追溯且配置语义矛盾、metrics 类型契约错误。

本轮不是继续增加算法，而是完成证据交付、路径可移植性和边界安全的最后收口。

### 3. 已独立确认通过的内容

以下部分已经独立验证，不要无目的重写：

- 完整 pytest：`94 passed in 27.21s`；
- Ruff：`All checks passed!`；
- 默认运行清单的 13 个产物哈希可验证；
- 默认报告和默认清单副本可字节级复现；
- 5 个 Streamlit 页面可从仓库外工作目录启动；
- 单类别 PR-AUC 输出 `null + applicable=false`；
- Top-k 会排除 NaN 和正负无穷；
- Streamlit 下限 `>=1.51,<2` 正确，无需再次调整。

### 4. 全局约束

- 保留用户现有未跟踪文件 `docs/handoff/2026-08-16-sixth-review-report.md`；
- 禁止 `git reset --hard`、`git clean -fd`、覆盖用户文件；
- 不得推送远程仓库；
- 不得编造指标、实验数量、哈希或运行结果；
- 不得手工修改生成证据中的哈希来“对齐”；
- 每个问题先写能失败的回归测试，再改实现；
- 代码稳定前不要运行耗时的完整 130 组实验；
- 不做与本轮问题无关的算法升级或目录重构；
- 路径处理必须同时适用于 Windows 和 POSIX。

---

## 二、G0：先建立失败复现

先补测试并确认它们在当前基线 `67aaeb3` 上因对应缺陷失败。不要先改实现再补一个永远为绿的测试。

### G0.1 鲁棒性证据清单

测试必须读取交付目录中的：

- `reports/metrics/robustness_experiment_manifest.json`；
- 清单中 `output_files` 声明的每个文件。

断言：

1. 每个声明文件在清单所在目录真实存在；
2. 文件名与实际交付文件完全一致；
3. 实测 SHA-256 与清单一致；
4. 不允许通过把 `experiment_` 临时替换成 `robustness_` 来验证；
5. 不允许存在未被清单覆盖的核心 summary/aggregates 文件。

当前基线应稳定失败，因为清单声明 `experiment_summary.csv` 和 `experiment_aggregates.csv`，实际交付的是 `robustness_summary.csv` 和 `robustness_aggregates.csv`。

### G0.2 仓库外实验配置解析

在测试中：

1. 使用绝对路径指向 `configs/robustness.yaml`；
2. 将 CWD 切换到 `tmp_path`；
3. 使用零案例或最小一案例配置，避免运行完整实验；
4. 断言基础配置能基于实验配置文件位置解析；
5. 断言生成清单不含盘符绝对路径和 Windows 专属反斜杠逻辑路径。

当前基线会尝试读取：

```text
<临时目录>/configs/default.yaml
```

并抛出 `FileNotFoundError`。

### G0.3 报告必须先验签后读取

增加调用顺序测试。篡改一个已声明产物后：

- `verify_manifest_hashes` 必须先失败；
- `load_config`、`pd.read_csv`、`pd.read_parquet` 或完整 `load_run_artifacts` 不得被调用；
- 篡改为非法 YAML 时，也应先得到完整性错误，而不是 YAML/Pydantic 解析错误。

当前基线的实际顺序是：

```text
load_run_artifacts -> load_config -> verify_manifest_hashes
```

### G0.4 schema 非法值与未来版本

页面或抽取后的纯函数至少测试：

- 缺失：legacy；
- 整数 `1`：legacy；
- 整数 `2`：current；
- 整数 `3`：newer/unsupported；
- `2.5`：invalid，不得截断为 2；
- `float("inf")`：invalid，不得抛未捕获 `OverflowError`；
- `True`：invalid，不得当作 1；
- `"2"`：根据你选择的严格契约明确接受或拒绝，测试必须固定行为；
- 未来版本缺少当前 PR 曲线依赖列时，页面不得崩溃或继续执行不受支持的计算。

### G0.5 报告输出碰撞

测试以下情况必须在任何写入前失败：

- `output_path == manifest_output`；
- 两条路径文本不同但 `resolve()` 后相同；
- 输出目标会覆盖源运行目录中的 `manifest.json`、`config.snapshot.yaml` 或清单声明产物。

当前基线中，同一路径会先写摘要、再被清单静默覆盖，函数仍返回成功。

### G0.6 base-case 违规落盘

模拟一个 warning base-case 和一个 `terminate_on_critical=false` 的 critical base-case，断言 `metrics.json` 至少包含：

- `base_case_violation_count`；
- `base_case_violation_types`；
- `base_case_violations`；
- `base_case_severity`。

同时断言非收敛始终终止，不依赖可配置严重等级列表。

---

## 三、G1：修复鲁棒性实验产物契约

### G1.1 统一生成文件名、交付文件名和清单文件名

当前生成器写：

- `experiment_summary.csv`；
- `experiment_aggregates.csv`；
- `experiment_manifest.json`。

但仓库交付和看板使用：

- `robustness_summary.csv`；
- `robustness_aggregates.csv`；
- `robustness_experiment_manifest.json`。

不得继续使用“生成后人工改名，但清单不变”的流程。

推荐方案：统一采用 `robustness_*` 命名，因为 README、看板和现有交付文件已经使用该命名。需要同步修改：

- `src/ltverify/experiments.py`；
- `src/ltverify/cli.py`；
- `app/pages/5_robustness.py` 的默认路径；
- `tests/integration/test_experiment_smoke.py`；
- `tests/unit/test_experiments.py`；
- notebook、README 和数据说明中的文件引用；
- 最终生成清单中的 `output_files`。

如果你选择统一回 `experiment_*`，也可以，但必须同步修改所有消费者和仓库交付文件。只能保留一套权威命名。

### G1.2 增加实验清单验证函数

实现一个可复用验证入口，例如：

```python
def verify_experiment_manifest(
    manifest: dict[str, object],
    artifact_dir: Path,
    *,
    experiment_config_path: Path | None = None,
    base_config_path: Path | None = None,
) -> None:
    ...
```

至少校验：

- `artifact_schema_version` 是受支持整数；
- `output_files` 非空；
- 每个输出路径是安全相对路径；
- 路径不得绝对、不得包含 `..`、不得重复；
- 每个哈希为 64 位十六进制；
- 文件存在且实测哈希一致；
- `experiment_config_sha256` 和 `base_config_sha256` 均为合法哈希，快照字段存在；
- 调用方传入配置路径时，实测文件哈希必须分别等于清单中的配置哈希；
- `case_counts.total == completed + failed`；
- summary 行数与 `case_counts.total` 一致。

交付证据测试必须调用该验证函数，并显式传入仓库中的
`configs/robustness.yaml` 与 `configs/default.yaml`，不得写一套只适合当前
文件名的替换逻辑。普通消费者若没有原始配置文件，仍可验证输出文件、
哈希格式和嵌入快照；仓库验收必须执行完整配置文件哈希验证。

### G1.3 明确基础配置的相对路径语义

GLM 建议“直接相对实验配置父目录解析”，但如果只改代码，当前：

```yaml
base_config: configs/default.yaml
```

会被错误解析成 `configs/configs/default.yaml`。

必须同时修改配置与解析器：

```yaml
# configs/robustness.yaml
base_config: default.yaml
```

实现规则：

```text
绝对 base_config：直接使用
相对 base_config：以 robustness.yaml 所在目录为基准
```

解析一次得到规范化 `base_config_path`，加载配置、计算哈希和写清单必须复用同一个 Path，禁止三处各自解析。

### G1.4 清单路径必须可移植

当前 `experiment_config_path` 可能写入：

```text
configs\robustness.yaml
```

或者在绝对参数下泄露 `D:\...`。

清单已经有快照和哈希，因此路径只应承担逻辑标识作用。推荐：

- 保存相对于项目配置根或实验清单的 POSIX 路径；或
- 保存 `experiment_config_name`、`base_config_name`，把内容身份交给 snapshot + SHA-256。

最终交付 JSON 中不得出现盘符绝对路径、用户目录或依赖操作系统的反斜杠路径。

---

## 四、G2：报告生成改成“先验签、后解析”

### G2.1 拆分加载阶段

当前 `generate_default_summary` 先调用 `load_run_artifacts` 和 `load_config`，然后才验证清单。必须改成：

```text
1. 只读取 manifest.json
2. 严格判断 schema
3. verify_manifest_hashes(manifest, run_dir)
4. 验签成功后 load_run_artifacts(run_dir)
5. 验签成功后 load_config(config.snapshot.yaml)
6. 计算并写报告
```

可在 `data_access.py` 中增加“只读取 manifest”函数，或在 report 模块使用现有安全 JSON 读取函数。不要为了复用 `load_run_artifacts` 而提前解析全部 Parquet。

### G2.2 保持错误边界清晰

- 哈希不匹配：报告完整性错误；
- 清单字段非法：清单契约错误；
- 已验签但内容无法解析：数据契约或配置错误；
- 错误信息说明具体阶段，不要把所有异常改成同一句。

更新现有篡改测试，使其不只是断言“最终抛异常”，还要断言解析器未在验签前执行。

### G2.3 防止输出覆盖

在写任何文件前：

1. 对 `output_path` 和 `manifest_output` 执行规范化；
2. 若两者相同，抛出 `ValueError`；
3. 读取源清单的 `output_paths`；
4. 禁止覆盖 `manifest.json`、`config.snapshot.yaml` 和任何已声明源产物；
5. 允许在运行目录中写新的、不与源证据重名的报告文件，或者更简单地要求输出在运行目录外；
6. CLI 返回非零并显示可行动错误。

测试必须断言碰撞失败后目标文件不存在或保持原字节不变。

---

## 五、G3：严格实现 schema 状态机

### G3.1 抽取可测试的版本分类函数

不要在 Streamlit 页面中直接 `int(raw_version)`。建议在 `src/ltverify/manifest.py` 或专门的小模块中实现：

```python
SchemaState = Literal["legacy", "current", "newer", "invalid"]

def classify_artifact_schema_version(raw: object) -> tuple[SchemaState, int | None]:
    ...
```

推荐严格契约：

- 仅接受 `int` 且拒绝 `bool`；
- `< 2` 为 legacy；
- `== 2` 为 current；
- `> 2` 为 newer；
- float、无穷、NaN、列表、空值和任意字符串为 invalid。

如果为兼容 JSON 外部来源而接受纯数字字符串，必须显式正则校验，禁止 `int(2.5)` 式截断。

### G3.2 页面按状态限制行为

- legacy：隐藏当前口径 PR-AUC/PR 曲线，提示重新生成；
- current：正常展示全部受支持内容；
- newer：提示当前应用未验证该版本，不执行 PR 曲线等依赖 schema-v2 的派生计算；
- invalid：显示清单版本非法，安全停止依赖产物契约的展示。

对于 newer，不得仅检查 `anomaly_score` 后就假设 `transformer_id`、`reported_feeder_id`、`physical_feeder_id` 等全部存在。

页面集成测试至少覆盖：

- `2.5` 不被当作 current；
- `inf` 无异常组件；
- `True` 不被当作 legacy 版本 1；
- schema 3 不绘制 PR 曲线；
- schema 3 缺少当前列时仍不崩溃。

---

## 六、G4：补齐 base-case 可观测性并消除配置矛盾

### G4.1 落盘结构化违规信息

在 `metrics.json` 中增加：

```json
{
  "base_case_violation_count": 1,
  "base_case_violation_types": ["transformer_overload"],
  "base_case_violations": ["transformer overload: trafo 1 at 110.0%"],
  "base_case_severity": "warning"
}
```

要求：

- clean base-case 输出 count=0、空列表、severity=ok；
- warning 继续流水线但详情可追溯；
- critical 且 `terminate_on_critical=false` 继续时也必须记录详情；
- critical 且终止时，失败清单至少保留结构化 failure_summary；
- 不只保存前 N 条，当前 base-case 规模小，应保存全部违规。

### G4.2 将非收敛与可配置工程越限分离

当前代码和文档同时存在：

- “non_convergence 不受 critical_violation_types 影响，始终 fatal”；
- `ALLOWED_VIOLATION_TYPES` 和默认配置又包含 `non_convergence`。

这会让用户误以为删除该值可以降级非收敛。

推荐修复：

1. `critical_violation_types` 只允许已求解网络的三类工程违规：
   - `power_balance`；
   - `voltage_out_of_bounds`；
   - `transformer_overload`；
2. 从 `configs/default.yaml` 的该列表删除 `non_convergence`；
3. 非收敛继续由求解/仿真边界无条件 fatal；
4. 删除未使用的 `_CRITICAL_VIOLATION_TYPES` 常量；
5. 文档改成“3 类可配置工程违规 + 1 类不可降级非收敛”，不要再写含混的“默认四类均可配置”。

这一配置修改会改变配置文件哈希，因此最终默认运行和鲁棒性实验的证据必须重新生成。

---

## 七、G5：修正类型契约与测试数据

`src/ltverify/data_access.py` 当前声明：

```python
metrics: dict[str, float | int]
```

但实际 metrics 已包含：

- `None`；
- `bool`；
- 原因字符串；
- 列表或其他结构化上下文。

至少改为：

```python
metrics: dict[str, object]
```

更推荐定义 `TypedDict(total=False)` 表达稳定核心字段，但不要为本轮引入庞大类型体系。同步检查 `EvaluationResult`、报告摘要和页面测试夹具，确保它们不再假设所有指标都是浮点数。

---

## 八、G6：重新生成证据与文档

所有代码和定向测试稳定后再生成证据。

### G6.1 必须重新生成

- 默认 30 天运行目录；
- `reports/metrics/default_summary.json`；
- `reports/metrics/default_manifest.json`；
- 完整 130 组鲁棒性与消融实验；
- 统一命名后的 summary、aggregates 和 experiment manifest；
- README 中运行 ID、配置哈希、指标与文件名说明。

本轮修改了默认配置的 critical 列表，因此不能把旧 130 组结果配上新 base_config 哈希冒充新实验。必须真实重跑或保留旧配置并明确旧证据；推荐真实重跑。

### G6.2 生成后自动验收

编写或复用脚本验证：

1. 默认清单所有输出存在且哈希匹配；
2. 实验清单所有输出存在且哈希匹配；
3. 两个清单都不含绝对路径和 Windows 专属逻辑路径；
4. 配置快照和配置哈希一致；
5. 实验 summary 恰好 130 行；
6. `total == completed + failed == 130`；
7. README 数字来自新证据；
8. JSON 不含 NaN、Infinity；
9. 页面默认路径能直接打开新聚合文件；
10. 从仓库外 CWD 可解析绝对 experiment config 并运行最小实验。

### G6.3 文档同步

更新 README、`docs/methodology.md`、`data/README.md`：

- 统一鲁棒性产物名称；
- 说明实验配置相对路径基于实验 YAML 所在目录；
- 说明实验清单验证方法；
- 说明报告先验签后解析；
- 说明 schema 的 legacy/current/newer/invalid 状态；
- 说明 3 类可配置工程违规与不可降级非收敛；
- 说明 base-case 违规详情字段。

GLM 所提“给 Streamlit 1.51 增加推导注释”不是阻断项。第五轮整改文档已记录官方版本依据；可补充简短注释，但不要因此改动依赖版本或扩大范围。

---

## 九、建议实施顺序与提交边界

建议按以下提交拆分：

1. `test: reproduce sixth-review portability and evidence gaps`
2. `fix: make robustness artifacts self-verifying`
3. `fix: resolve experiment configs independently of cwd`
4. `fix: verify run artifacts before report parsing`
5. `fix: harden schema state and report output boundaries`
6. `fix: persist base-case violations and clarify fatal policy`
7. `fix: align artifact metrics type contracts`
8. `docs: document sixth-review artifact contracts`
9. `chore: regenerate sixth-review release evidence`

每个提交前运行相关定向测试。不要把测试、所有实现、130 组证据和文档全部压成一个不可审查提交。

---

## 十、验证命令与完成门槛

至少执行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

并执行：

```powershell
# 从仓库外 CWD 运行最小实验配置
# 对默认运行清单执行完整哈希验证
# 对鲁棒性实验清单执行完整哈希验证
# 从默认运行目录重新生成报告并与交付摘要字节比较
# 使用 Streamlit AppTest 覆盖非法和未来 schema
```

完成门槛：

- pytest 数量必须大于当前 94 项且全部通过；
- Ruff 全绿；
- 不得新增无理由 skip/xfail；
- 实验清单声明的文件必须按原名存在；
- 仓库外实验解析测试通过；
- 篡改产物时报告在任何配置/Parquet 解析前拒绝；
- schema `2.5`、`inf`、`True` 不崩溃且不冒充受支持版本；
- 相同报告输出路径被明确拒绝；
- base-case warning/critical 详情进入 metrics；
- 130 组实验真实完成并与新清单一致；
- `git status --short` 只允许用户原有未跟踪审核报告，不得包含临时文件；
- 不推送远程。

---

## 十一、最终回报格式

完成后必须报告：

1. 按 G1—G6 分类的修改摘要；
2. 每个问题对应的实现文件和回归测试；
3. pytest 精确数量、耗时和退出状态；
4. Ruff 精确结果；
5. 默认运行 ID；
6. 130 组实验的 total/completed/failed；
7. 默认清单和实验清单的独立哈希验证结果；
8. 仓库外 CWD 最小实验结果；
9. schema 边界 AppTest 结果；
10. 所有本地提交哈希；
11. `git status --short`；
12. 明确声明未推送远程；
13. 未完成项必须明确列出，不得使用“基本完成”掩盖。

---

## 十二、完成后交给第七轮审核 AI 的提示词

```text
请对 D:\电力 仓库执行第七轮独立审核。不要默认相信第六轮整改报告，也不要只运行 pytest。

重点核验：
1. reports/metrics 下鲁棒性实验清单声明的每个文件是否按原名存在，实测哈希是否一致；
2. 生成器、CLI、README、看板、notebook 和交付文件是否只保留一套权威命名；
3. 从仓库外 CWD 使用绝对 robustness.yaml 路径时，base_config 是否按 YAML 所在目录解析；
4. 实验清单是否不含绝对路径和 Windows 专属逻辑路径；
5. report 是否在 load_config/read_csv/read_parquet 之前完成 manifest 哈希验证；
6. output 与 manifest-output 相同或覆盖源产物时是否在写入前拒绝；
7. schema 2.5、inf、True、缺失、1、2、3 是否进入正确状态且页面不崩溃；
8. future schema 是否停止执行未经验证的 PR 曲线派生逻辑；
9. base-case warning 和 terminate_on_critical=false 的 critical 是否完整落盘类型、数量与消息；
10. non_convergence 是否从可配置降级类型中分离且仍始终 fatal；
11. RunArtifacts.metrics 类型是否与 None/bool/string 等实际值一致；
12. 默认 30 天和 130 组实验是否真实重跑，配置哈希、运行 ID、README 数字是否一致；
13. 独立运行完整 pytest、Ruff、两个清单验证和仓库外页面测试。

请先按 P0/P1/P2/P3 排序 findings，再报告验证证据。若没有问题，也要列明检查路径、命令和实测结果，不得复述整改者自报结论。
```

---

## 十三、问题优先级摘要

| 优先级 | 问题 | 当前可复现后果 |
|---|---|---|
| P1 | 鲁棒性清单文件名与交付文件不一致 | 按清单验证时两个输出均不存在 |
| P2 | base_config 依赖进程 CWD | 仓库外运行绝对实验配置仍 FileNotFoundError |
| P2 | 报告先解析后验签 | 被篡改产物会在完整性检查前被读取 |
| P2 | schema 强制 int 转换 | 2.5 冒充 v2，inf 页面崩溃，未来版本继续派生计算 |
| P3 | 两个报告输出目标可相同 | 清单静默覆盖摘要但命令返回成功 |
| P3 | base-case 只落 severity，非收敛配置语义矛盾 | 违规原因不可追溯，用户无法理解删除 non_convergence 是否有效 |
| P3 | RunArtifacts.metrics 类型过窄 | 类型契约与实际 JSON 值不一致 |

完成本轮后再讨论项目收口。在 P1/P2 未修复前，不得宣称证据链和跨环境复现已经完成。
