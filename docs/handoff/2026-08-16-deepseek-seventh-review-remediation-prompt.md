# DeepSeek Agent Harness 第七轮整改主提示词

> 适用项目：`distribution-network-line-transformer-verification`
> 工作目录：`D:\电力`
> 已提交审核基线：Git `main`，HEAD `26a4a55`
> 当前工作树验证基线：pytest 104 passed；Ruff all checks passed
> 生成日期：2026-08-16

---

## 一、直接复制给 DeepSeek 的主提示词

你正在维护一个面向“电网/能源数字化实习”作品集的项目：

`distribution-network-line-transformer-verification`

请在仓库 `D:\电力` 中执行第七轮整改。必须先保护当前工作树中的并发修改，再补失败测试、修改实现、验证证据并创建本地提交。不要只给建议，不要因为现有测试通过就宣称收口。

### 1. 开始前必须阅读

1. `docs/handoff/2026-08-16-seventh-review-report.md`
2. `docs/handoff/2026-08-16-deepseek-sixth-review-remediation-prompt.md`
3. `README.md`
4. `docs/methodology.md`
5. `data/README.md`
6. `src/ltverify/experiments.py`
7. `src/ltverify/manifest.py`
8. `src/ltverify/pipeline.py`
9. `src/ltverify/report.py`
10. `tests/unit/test_evidence.py` 及相关集成测试。

### 2. 当前工作树不是干净基线

审核结束时，HEAD 仍为 `26a4a55`，但另一位 AI 已留下未提交补丁：

```text
M app/pages/5_robustness.py
M src/ltverify/config.py
M src/ltverify/experiments.py
M src/ltverify/plotting.py
M tests/integration/test_pages.py
M tests/unit/test_config.py
?? docs/handoff/2026-08-16-seventh-review-report.md
```

这些修改主要处理 GLM 的 T-1～T-3：旧实验文件名兼容、`non_convergence` 迁移提示、移动重复检查。它们不是 Codex 产生的，也尚未提交。

要求：

- 禁止使用 reset/checkout/clean 丢弃它们；
- 先逐文件阅读和运行相关测试；
- T-1 兼容与 T-3 文案可在确认无副作用后保留；
- T-2 仅把重复检查移出循环仍没有真实验证价值，必须由本轮“权威输出精确集合”校验替代；
- 把这组并发修改与本轮核心证据修复分开提交，提交说明准确；
- 保留未跟踪审核报告。

### 3. 第七轮独立审核结论

GLM 所称“只剩 3 项 P4、可以收口”的结论不成立。Codex 通过内存篡改复现确认：

```text
tampered_experiment_snapshot ACCEPTED
false_status_counts ACCEPTED
aggregate_hash_removed ACCEPTED
```

此外，当前默认交付清单仍包含：

```json
"input_paths": ["configs\\default.yaml"]
```

使用绝对配置路径构建清单时还会记录本机绝对路径。

本轮优先级：

- P1：实验清单验证器接受内部矛盾的证据；
- P2：默认运行清单的输入路径仍不可移植；
- P3：终止型 base-case 缺结构化违规详情；
- P3：路径安全检查依赖当前操作系统，字典重复检查无效。

### 4. 已独立确认通过的内容

不要无目的重写以下部分：

- 当前工作树 pytest：`104 passed in 32.01s`；
- Ruff：`All checks passed!`；
- 当前默认报告和默认清单可字节级复现；
- 当前默认运行输出哈希全部通过；
- 当前实验清单声明的两个实际文件存在且哈希匹配；
- 当前嵌入实验配置快照和基础配置快照确实与仓库配置相符；
- schema `2.5`、`inf`、`True` 页面均安全停止；
- schema 3 不再绘制 PR 曲线；
- 仓库外 CWD 能正确解析 `configs/robustness.yaml` 的基础配置；
- 报告已经做到先验签、后解析；
- Streamlit 下限、PR-AUC、Top-k 和物理严重等级主逻辑无须再次改写。

### 5. 全局约束

- 禁止 `git reset --hard`、`git clean -fd`、覆盖用户并发修改；
- 不得推送远程仓库；
- 不得手工改哈希或指标冒充重新生成；
- 所有核心缺陷先补红灯测试，再改实现；
- 不得通过降低断言、捕获所有异常或 skip 测试来变绿；
- 仅在代码稳定后重新生成必要证据；
- 本轮不需要重跑 130 组实验，除非你修改了实验算法、实验配置或生成数据；
- 默认运行清单路径字段改变后，默认流水线必须真实重跑；
- 路径校验必须在 Windows 和 POSIX 上语义一致。

---

## 二、G0：先建立必失败回归测试

### G0.1 配置快照与真实配置不一致

在 `tests/unit/test_evidence.py` 或 `tests/unit/test_experiments.py` 中：

1. 读取当前权威 `robustness_experiment_manifest.json`；
2. 使用 `copy.deepcopy` 创建内存副本；
3. 把 `experiment_config_snapshot["base_config"]` 改成 `evil.yaml`；
4. 仍传入真实 `configs/robustness.yaml` 和 `configs/default.yaml`；
5. 断言 `verify_experiment_manifest` 必须拒绝，并指出 experiment snapshot 不一致；
6. 再修改 `base_config_snapshot` 中一个实际参数，断言 base snapshot 不一致。

当前基线会错误接受这两种篡改。

### G0.2 case_counts 与 CSV 状态不一致

保持 130 行 CSV 和所有文件哈希不变，只把内存清单改为：

```python
manifest["case_counts"] = {
    "total": 130,
    "completed": 0,
    "failed": 130,
}
```

当前验证器只检查 `total == completed + failed` 和 summary 行数，因此会接受。新测试必须断言失败。

再覆盖：

- `total/completed/failed` 为 bool、float、字符串时拒绝；
- 任一计数为负数时拒绝；
- CSV 出现未知状态值时拒绝；
- `completed` 和 `failed` 必须分别等于 CSV 中真实状态计数。

### G0.3 核心输出哈希集合不完整

从内存清单删除 `robustness_aggregates.csv` 哈希，只保留 summary 哈希。当前验证器仍会通过。

新契约必须要求：

```python
set(output_files) == {
    "robustness_summary.csv",
    "robustness_aggregates.csv",
}
```

缺少、增加或改名任一核心文件都必须失败。

### G0.4 快照名称字段一致性

当调用方传入配置文件路径时，测试以下篡改均应失败：

- `experiment_config_name != experiment_config_path.name`；
- `base_config_name != base_config_path.name`；
- 实验 YAML 的解析后对象与嵌入 snapshot 不一致；
- 基础配置的 `load_config(...).model_dump(mode="json")` 与嵌入 snapshot 不一致。

### G0.5 默认运行清单输入路径可移植性

为 `build_manifest` 增加测试：

- 传入相对 Windows 风格路径时，`input_paths` 不含反斜杠；
- 传入绝对路径时，`input_paths` 不含盘符、用户目录或绝对路径；
- 当前交付 `reports/metrics/default_manifest.json` 的所有路径字段不含 `\`；
- 清单仍通过配置哈希与产物哈希校验。

### G0.6 跨平台路径穿越

对运行清单和实验清单验证器分别测试：

```text
../evil.csv
..\evil.csv
C:\evil.csv
/absolute/evil.csv
\\server\share\evil.csv
```

无论测试运行在 Windows 还是 POSIX，全部必须拒绝。

### G0.7 终止型 base-case 失败清单

模拟：

- `base_case.severity == "critical"`；
- `terminate_on_critical == true`；
- 含一个 `transformer_overload` 违规。

运行应失败，但新生成的失败 `manifest.json` 必须在 `failure_summary` 中保存：

```json
{
  "stage": "base_case_validation",
  "severity": "critical",
  "violation_count": 1,
  "violation_types": ["transformer_overload"],
  "violations": ["transformer overload: trafo 1 at 150.0%"]
}
```

原有 `error_type` 和 `message` 可保留。测试不得只断言抛出了 RuntimeError。

---

## 三、G1：强化实验清单的内部一致性

### G1.1 精确锁定权威输出

在 `verify_experiment_manifest` 中先验证：

```python
REQUIRED_EXPERIMENT_OUTPUTS = frozenset(
    {"robustness_summary.csv", "robustness_aggregates.csv"}
)
```

要求 `set(output_files) == REQUIRED_EXPERIMENT_OUTPUTS`。

当前并发补丁中的：

```python
len(output_files) != len(set(output_files))
```

没有实际意义，因为 Python/JSON 字典在进入验证函数时已经不可能保留重复键。请删除这段死检查。若未来需要检测原始 JSON 重复键，必须在 JSON 解析阶段使用 `object_pairs_hook`，不属于本轮范围。

### G1.2 对外部配置、名称、哈希和快照做四方一致性检查

当 `experiment_config_path` 被提供时，验证：

```text
path.name == manifest.experiment_config_name
sha256(path bytes) == manifest.experiment_config_sha256
_portable(yaml.safe_load(path)) == manifest.experiment_config_snapshot
```

当 `base_config_path` 被提供时，验证：

```text
path.name == manifest.base_config_name
sha256(path bytes) == manifest.base_config_sha256
_portable(load_config(path).model_dump(mode="json"))
    == manifest.base_config_snapshot
```

错误信息应明确是哪一层不一致：name、hash 或 snapshot。

当调用方没有提供原始配置路径时，只能验证名称格式、哈希格式、snapshot 类型和输出证据；文档不得宣称这种模式能证明 snapshot 与原始 YAML 一致。

### G1.3 严格验证 case_counts

要求：

- `case_counts` 必须是字典；
- `total/completed/failed` 必须是 plain int，拒绝 bool；
- 全部非负；
- `total == completed + failed`；
- summary 必须包含 `status` 列；
- status 只允许 `completed` 或 `failed`；
- `len(summary) == total`；
- `(summary.status == "completed").sum() == completed`；
- `(summary.status == "failed").sum() == failed`。

### G1.4 不要把当前证据通过与验证器完整混为一谈

当前权威证据确实满足真实快照、130 completed、两个文件哈希。这证明当前证据内容正确，不证明旧验证器足够严格。

修复后必须执行两组测试：

1. 当前权威证据正向通过；
2. G0.1～G0.4 的所有篡改副本逐项拒绝。

---

## 四、G2：统一跨平台安全相对路径契约

### G2.1 提取一个共享路径验证函数

建议在 `src/ltverify/manifest.py` 定义并由实验模块复用：

```python
def validate_portable_relative_path(value: object, *, field: str) -> str:
    ...
```

契约：

- 必须是非空字符串；
- 禁止任何反斜杠 `\`；
- 禁止盘符前缀；
- 禁止 UNC；
- 使用 `PurePosixPath` 判断绝对路径和 `..`；
- 建议拒绝 `.`、空段和目录结尾；
- 返回已验证的原字符串，不负责猜测或修复恶意输入。

`verify_manifest_hashes` 和 `verify_experiment_manifest` 必须调用同一函数，不能各自复制平台相关的 `Path(text).parts` 判断。

### G2.2 修复默认运行 input_paths

当前 `build_manifest` 使用 `str(config_path)`，会写入反斜杠或绝对路径。

推荐统一记录逻辑文件名：

```python
input_paths=[config_path.name]
```

配置内容身份已经由：

- `config_sha256`；
- `config.snapshot.yaml`；
- snapshot 输出哈希；

共同保证，因此没有必要在可交付清单中泄露本机原始位置。

如果保留相对目录信息，只允许经过明确项目根归一化后的 POSIX 相对路径；不得依据 CWD 猜测项目根。对本项目而言保存文件名最简单可靠。

### G2.3 更新路径文档

明确区分：

- 清单逻辑名称：可移植标识；
- 实际运行时 Path：只在进程内使用；
- 配置身份：由快照和 SHA-256 保证。

不要再把 Windows `str(Path)` 写进 JSON 后称为“可移植相对路径”。

---

## 五、G3：终止型 base-case 的结构化失败证据

### G3.1 在抛异常前建立失败上下文

推荐在 `run_pipeline` 中维护：

```python
failure_context: dict[str, object] = {}
```

当 base-case critical 且准备终止时，先设置：

```python
failure_context = {
    "stage": "base_case_validation",
    "severity": base_case.severity,
    "violation_count": len(base_case.violations),
    "violation_types": list(base_case.violation_types),
    "violations": list(base_case.violations),
}
```

随后再抛异常。在顶层 except 中把上下文合并进 `failure_summary`。

要求：

- 不改变原有终止策略；
- 不吞掉原始错误类型和消息；
- warning 和 terminate=false 的 completed run 继续写 metrics；
- critical terminate=true 的 failed run 写 failure_summary；
- non-convergence 可使用 `stage=base_case_validation`、`violation_types=["non_convergence"]`；
- 其他未知异常不伪造违规字段。

### G3.2 失败清单类型契约

当前 `RunManifest.failure_summary` 类型只允许 `dict[str, str]`。如果加入整数和列表，应同步改为真实类型，例如：

```python
failure_summary: dict[str, object] | None = None
```

并更新相关测试与数据说明。

---

## 六、G4：处理并发 T-1～T-3 补丁

### G4.1 T-1 旧实验名兼容

这不是收口阻断项。当前已有最新新命名实验目录，旧目录也可手工输入。

如果保留现有兼容补丁：

- 新命名必须始终优先；
- 增加的页面测试必须通过；
- 不得让 aggregates 与 summary 自动选择到不同实验目录；
- 最好让默认解析一次选定实验目录，再从同一目录寻找两个文件，避免部分生成目录导致数据混用。

如果无法保证同目录一致，宁可不自动兼容旧目录，只在提示中说明可手工输入。

### G4.2 T-3 迁移提示

`non_convergence` 的专用迁移提示与测试可以保留。确保未知其他类型仍显示通用允许值列表。

### G4.3 schema 页面测试补强

当前实现已经手工验证正确，但测试套件主要覆盖分类函数，没有完整锁定页面行为。补充 AppTest：

- 2.5、inf、True：无 exception、有 error、0 个 Plotly 图；
- schema 3：有 warning、无 exception、仅基础图，不绘制 PR 曲线；
- schema 3 缺少当前 PR 依赖列：仍不崩溃。

不要修改已经正确的 schema 业务逻辑，只补回归保护。

---

## 七、G5：证据重新生成策略

### G5.1 必须重新生成默认运行证据

`build_manifest.input_paths` 修改后，执行新的默认 30 天流水线，生成：

- 新运行目录及 manifest；
- `reports/metrics/default_summary.json`；
- `reports/metrics/default_manifest.json`；
- README 中的新 run ID 和必要引用。

不得手工把旧清单中的 `configs\\default.yaml` 改成 `default.yaml`，因为那会让清单内容不再对应原生成代码和 source commit。

### G5.2 不需要重新跑 130 组实验

本轮只加强验证器，没有修改：

- 实验算法；
- `configs/robustness.yaml`；
- `configs/default.yaml`；
- 现有 130 组 CSV 数据。

因此可继续使用当前 130 组证据，但必须：

1. 用新验证器正向验证；
2. 确认快照与配置四方一致；
3. 确认 actual status counts 为 130 completed / 0 failed；
4. 确认两个输出哈希均匹配。

只有在你实际修改了上述配置或生成算法时，才需要重跑 130 组实验。

### G5.3 `.gitattributes` 验证

保留当前证据文件与配置文件的字节稳定策略，但额外检查：

- 新默认配置快照哈希在当前 checkout 通过；
- `git add --renormalize --dry-run` 或等价只读检查不会产生意外证据变化；
- JSON/CSV/YAML 在 Windows checkout 中仍可解析；
- 不以修改行尾的方式绕过测试。

---

## 八、建议提交边界

根据当前并发补丁，建议：

1. `fix: polish seventh-review compatibility feedback`
   - 只包含确认保留的 T-1/T-3 补丁及测试；
   - 不把无效重复检查单独提交。
2. `test: reproduce experiment manifest false positives`
3. `fix: enforce experiment manifest internal consistency`
4. `fix: make run manifest input paths portable`
5. `fix: preserve structured base-case failure context`
6. `test: cover invalid and future schema page behavior`
7. `docs: document seventh-review evidence contracts`
8. `chore: regenerate portable default-run evidence`

每个提交只暂存对应文件。不得把用户未跟踪审核报告误加入业务提交，除非用户明确要求归档该报告。

---

## 九、完整验证与验收门槛

至少执行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

定向执行：

```text
1. 当前权威实验清单 + 真实两份配置：验证通过
2. 篡改 experiment snapshot：拒绝
3. 篡改 base snapshot：拒绝
4. completed/failed 与 CSV 相反：拒绝
5. 删除 aggregates 哈希：拒绝
6. Windows/POSIX/UNC 路径穿越：全部拒绝
7. 绝对 config path 构建 run manifest：清单不泄露绝对路径
8. critical base-case terminate=true：失败清单含结构化违规详情
9. schema 2.5/inf/True/3 AppTest：状态和图表数量正确
10. 新默认报告与仓库交付 summary/manifest 字节级一致
```

最终门槛：

- pytest 用例数必须高于当前 104 且全部通过；
- Ruff 全绿；
- 所有篡改测试为红灯复现后转绿；
- 默认和实验清单正向验证均通过；
- 默认清单所有路径字段无 `\`、盘符、UNC 或绝对路径；
- 新默认 run ID、source commit、配置哈希一致；
- 当前 130 组实验仍为 130 completed / 0 failed；
- 不新增无理由 skip/xfail；
- `git status --short` 不含缓存、临时报告输出或误提交文件；
- 未推送远程。

---

## 十、最终回报格式

完成后必须报告：

1. 当前并发补丁分别如何处理；
2. P1/P2/P3 每项对应的实现和测试文件；
3. 三种清单假阳性篡改现在如何被拒绝；
4. pytest 精确数量、耗时和退出码；
5. Ruff 精确结果；
6. 新默认 run ID 和 source git commit；
7. 默认 summary/manifest 字节复现结果；
8. 实验清单正向验证及 130/130 状态结果；
9. 是否重跑 130 组实验及原因；
10. 每个本地提交哈希；
11. `git status --short`；
12. 明确声明未推送远程；
13. 未完成项必须明确列出，不得用“基本完成”代替。

---

## 十一、完成后交给第八轮审核 AI 的提示词

```text
请对 D:\电力 仓库执行第八轮独立审核。不要默认相信第七轮整改报告，也不要只运行 pytest。

重点核验：
1. verify_experiment_manifest 是否拒绝被篡改的 experiment_config_snapshot 和 base_config_snapshot；
2. 配置文件 name/hash/解析后 snapshot 是否四方一致；
3. case_counts.completed/failed 是否与 robustness_summary.csv 的实际 status 计数一致；
4. output_files 是否精确包含 robustness_summary.csv 与 robustness_aggregates.csv；
5. 删除 aggregates 哈希后验证器是否拒绝；
6. ../、..\\、盘符、POSIX 绝对路径和 UNC 是否在两个清单验证器中全部拒绝；
7. build_manifest 接收绝对配置路径时，input_paths 是否仍不泄露绝对路径；
8. 交付 default_manifest.json 是否不含反斜杠和绝对路径；
9. critical base-case terminate=true 的失败 manifest 是否含 stage/severity/count/types/messages；
10. schema 2.5、inf、True、3 的 AppTest 是否锁定错误、警告和图表数量；
11. 默认流水线是否真实重跑，summary 与 manifest 是否字节级复现；
12. 现有 130 组实验是否无需重跑且仍能通过加强后的验证器；
13. 独立运行完整 pytest、Ruff，并核对 git status 与提交边界。

请先按 P0/P1/P2/P3 排序 findings，再报告验证证据。若无问题，也要说明实际构造了哪些篡改副本，不能只复述整改者的测试结果。
```

---

## 十二、问题摘要

| 优先级 | 问题 | 已复现结果 |
|---|---|---|
| P1 | 实验快照未与真实配置比较 | 修改 snapshot 后验证器仍 ACCEPTED |
| P1 | case_counts 未与 CSV 状态比较 | 0 completed / 130 failed 的假清单仍 ACCEPTED |
| P1 | 核心输出集合不完整 | 删除 aggregates 哈希后仍 ACCEPTED |
| P2 | run manifest input_paths 不可移植 | 交付含 `configs\\default.yaml`，绝对调用会泄露盘符路径 |
| P3 | 终止型 base-case 无结构化详情 | 只有 error_type/message 字符串 |
| P3 | 路径穿越校验依赖本机 Path | Windows 风格 `..\\` 在 POSIX 上可能绕过 |
| P3 | 字典重复检查无实际作用 | JSON 重复键在进入函数前已丢失 |

完成本轮后，只有在第八轮无法再构造 P1/P2/P3 级反例时，才建议项目收口。
