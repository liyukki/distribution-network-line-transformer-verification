# DeepSeek V4 Agent Harness 第八轮整改提示词

> 用途：把本文件完整交给 DeepSeek V4 及其 Agent Harness，在仓库内执行第八轮整改。
>
> 本文件是 Codex 基于 `c74d75b` 的独立复核结论。不要把
> `docs/handoff/2026-08-16-eighth-review-report.md` 中“零缺陷、直接收口”的判断当作验收结果。

---

## 一、任务身份与工作边界

你现在是该仓库的实现负责人，项目名称为：

`distribution-network-line-transformer-verification`

请在仓库 `D:\电力` 中执行第八轮整改。必须先复现本文列出的反例，再修改实现、补测试、运行全量验证并创建本地提交。不要只给建议，不要因为当前 136 个测试通过就宣称完成。

本轮允许修改业务代码、测试和必要文档，但必须遵守以下边界：

1. 不得执行 `git reset --hard`、`git clean`、`git checkout --` 等破坏性命令；
2. 不得覆盖或删除用户及其他 AI 的未跟踪文件；
3. 不得擅自提交以下现存未跟踪审查材料：
   - `docs/handoff/2026-08-16-seventh-review-report.md`
   - `docs/handoff/2026-08-16-eighth-review-report.md`
4. 不得 push、开 PR 或改远端；只创建本地、主题清晰的提交；
5. 不得用降低校验强度、跳过测试、吞掉异常或删除证据字段的方式让测试变绿；
6. 不得重写算法指标或重新宣称模型效果；本轮重点是失败证据、实验产物加载边界和清单契约；
7. 除非实际修改实验生成算法、实验配置或实验数据，否则不要重跑 130 案例鲁棒性实验；
8. 除非完成态流水线产物格式或默认配置发生变化，否则不要重跑 30 天默认流水线。

开始前执行并保存输出：

```powershell
git status --short --branch
git log --oneline --decorate -15
git diff --check
```

当前复核基线应为：

```text
HEAD = c74d75b
pytest = 136 passed
ruff = All checks passed!
```

若实际状态不同，先判断差异是否为其他执行者留下的修改；只能在其上增量工作，不得回滚。

---

## 二、第八轮独立审核结论

第七轮要求的大部分修复已经正确落地，且当前交付证据本身仍然正确：

- 完整测试：`136 passed in 33.18s`；
- Ruff：`All checks passed!`；
- 默认 run manifest 通过 `verify_manifest_hashes`；
- `default_summary.json` 与 `default_manifest.json` 可由源运行逐字节复现；
- 权威实验清单在同时传入 `configs/robustness.yaml` 和 `configs/default.yaml` 时严格通过。

但“已有证据正确”不等于“所有失败与输入边界都已闭合”。Codex 额外构造出以下反例：

```text
failed_output_paths []
snapshot_exists True
failed_manifest_verification=REJECTED
  schema-v2 manifest 必须包含 config.snapshot.yaml 哈希

missing_family exceptions ["'family'"]
malformed_csv exceptions ['Error tokenizing data ...']
missing_summary_status exceptions ["'status'"]

experiment_without_sources=ACCEPTED
missing_input_paths=ACCEPTED
```

因此本轮不能收口。优先级如下：

| 编号 | 优先级 | 问题 |
|---|---:|---|
| E8-1 | P2 | 终止型失败清单清空 `output_paths`，导致自己的 schema-v2 校验器拒绝该清单 |
| E8-2 | P2 | 鲁棒性页面对坏 CSV、缺关键列和缺 `status` 直接崩溃，且权威产物展示前没有验签 |
| E8-3 | P3 | `verify_manifest_hashes` 会接受缺失的 `input_paths`，未落实 schema 字段契约 |
| E8-4 | P3 | 实验清单的“离线部分校验”和“带源配置严格校验”未在 API/文档中清楚区分 |
| E8-5 | P3 | `validate_portable_relative_path` 的“跨 OS 可移植”声明仍未覆盖 Windows 保留名和尾随点/空格 |

---

## 三、G0：先补必失败回归测试

实现修改前先提交或至少运行以下失败测试，确认它们在 `c74d75b` 上确实失败。测试应直接断言契约，不要只断言某个实现细节。

### G0.1 失败清单必须可自验证

在 `tests/integration/test_pipeline.py` 扩展当前
`test_critical_base_case_terminate_writes_structured_failure_summary`：

1. 保留现有结构化字段断言；
2. 断言失败目录中的 `config.snapshot.yaml` 确实存在；
3. 断言失败清单的 `output_paths` 和 `output_sha256` 包含该快照；
4. 对失败清单调用 `verify_manifest_hashes(manifest, run_dir)`，必须通过；
5. 断言 `output_sha256["config.snapshot.yaml"] == manifest["config_sha256"]`。

再增加至少两个失败阶段：

- base-case `converged=False`；
- base-case 之后发生普通异常，例如模拟阶段抛出 `RuntimeError("probe")`。

两种失败清单都必须：

- `status == "failed"`；
- 保留配置快照哈希闭环；
- 通过 `verify_manifest_hashes`；
- 普通后续异常不得错误继承 `stage=base_case_validation` 等陈旧上下文。

不要把测试改成“失败清单允许缺少 config snapshot”。这会削弱已经公开的 schema-v2 证据契约。

### G0.2 鲁棒性页面不得因用户输入崩溃

在 `tests/integration/test_pages.py` 使用 `AppTest` 增加以下反例：

1. 聚合 CSV 缺 `family`；
2. 聚合 CSV 为语法损坏的 CSV；
3. 聚合 CSV 为空文件；
4. 聚合 CSV 的目标 `mean_<metric>` 不是可用数值；
5. summary CSV 缺 `status`；
6. summary CSV 含未知状态；
7. 输入路径指向目录而不是普通文件；
8. 当前命名产物的文件字节被修改，但同目录 manifest 仍保留旧哈希。

每个用例都必须断言：

```text
len(app_test.exception) == 0
```

并断言页面显示明确的 `st.error` 或 `st.warning`。对于哈希不一致的当前权威产物，必须停止展示图表和表格，不能降级为“照常读取”。

### G0.3 当前权威实验产物应在解析前验签

构造一个临时完整实验目录，包含：

```text
robustness_summary.csv
robustness_aggregates.csv
robustness_experiment_manifest.json
```

测试顺序必须体现“先验签，后解析”：

1. 文件与 manifest 完全匹配时页面正常渲染；
2. 修改 aggregates 字节但不更新 manifest，页面拒绝；
3. 修改 summary 字节但不更新 manifest，页面拒绝；
4. manifest 非法 JSON、schema 非法、核心输出哈希缺失时页面安全停止；
5. 旧命名 `experiment_*` 没有可用清单时允许兼容读取，但页面必须明确标注“未验证/旧版”，不得显示成已验签证据。

### G0.4 `input_paths` 字段类型和存在性

在 `tests/unit/test_manifest.py` 为 `verify_manifest_hashes` 增加：

- 缺少 `input_paths`：拒绝；
- `input_paths=None`：拒绝；
- `input_paths="default.yaml"`：拒绝，而不是逐字符遍历；
- `input_paths={"name": "default.yaml"}`：拒绝；
- 列表中含非字符串：拒绝；
- 列表中重复：拒绝；
- 空列表：按本项目 schema-v2 的“一次运行至少一个配置输入”契约拒绝；
- `input_paths=["default.yaml"]`：通过。

错误信息需点名 `input_paths`，避免出现来自字符迭代的偶然路径错误。

### G0.5 明确实验清单的两级验证模式

基于当前权威实验清单建立两个测试：

1. **严格模式**：传入两份真实配置路径；篡改 name/hash/snapshot 任一层都拒绝；
2. **离线模式**：不传源配置，只能证明 schema、输出文件哈希、计数和字段格式，不能宣称证明配置快照来自原始 YAML。

当前以下反例会被接受，这是离线模式能力边界，不应再被称作“完整自验证”：

```python
tampered["experiment_config_snapshot"] = {"forged": True}
tampered["base_config_snapshot"] = {"forged": True}
tampered["experiment_config_sha256"] = "0" * 64
tampered["base_config_sha256"] = "1" * 64
verify_experiment_manifest(tampered, artifact_dir)  # 当前通过
```

测试必须迫使调用方显式选择验证级别，或让返回值/结果对象明确表明是否完成了源配置核验。

### G0.6 真正的 Windows/POSIX 可移植名称

为 `validate_portable_relative_path` 增加跨平台纯字符串测试，至少覆盖每一层路径组件：

```text
CON
con.txt
AUX
aux.csv
NUL
COM1
LPT9
foo:bar.csv
trailingdot.
"trailingspace "
nested/aux.txt
```

这些名称在 POSIX 上可能可创建，但在 Windows 上保留、别名化或不可正常落盘；若函数继续宣称“portable, OS-independent”，必须统一拒绝。正常名称和正常多层相对路径应继续通过。

---

## 四、G1：修复失败清单的证据闭环

问题位于 `src/ltverify/pipeline.py` 的异常分支：

```python
_write_manifest(manifest, run_dir, [])
```

这会覆盖此前状态，把实际存在的 `config.snapshot.yaml` 从声明和哈希中删除。修复要求：

1. 一旦配置快照成功写入，任何后续 `running/completed/failed` 清单都必须声明并哈希该快照；
2. base-case 终止失败清单至少应包含：

```json
{
  "status": "failed",
  "output_paths": ["config.snapshot.yaml"],
  "output_sha256": {
    "config.snapshot.yaml": "<真实 SHA-256>"
  }
}
```

3. `output_sha256["config.snapshot.yaml"]` 必须等于顶层 `config_sha256`；
4. 不要把未完成或半写入的业务产物伪装成完整输出；失败清单可只固定已经完成且安全的最小证据集；
5. 配置复制自身失败时要定义明确行为：不能留下一个自称 schema-v2、却必然无法验证的持久化 manifest；
6. 最好把“配置快照已就绪”和“失败时应声明哪些已完成文件”的逻辑收敛到小型 helper，避免异常分支再次传空列表；
7. 保持当前 `failure_summary` 的结构化 base-case 字段；不要退回只有拼接字符串；
8. 后续普通异常只能包含其真实阶段上下文，不得复用 base-case 上下文。

验收核心不是“文件存在”，而是：

```python
verify_manifest_hashes(failed_manifest, failed_run_dir)  # 不抛异常
```

---

## 五、G1：为鲁棒性页面建立安全加载边界

当前 `app/pages/5_robustness.py` 直接执行：

```python
aggregates = pd.read_csv(aggregates_file)
aggregates["family"]
summary["status"]
```

文本框路径是用户输入边界，CSV 也是外部输入；未捕获异常不是可接受行为。

### 5.1 抽离可测试加载器

不要继续把所有解析、验签和列校验堆在 Streamlit 顶层。建议在 `src/ltverify/` 新增小型加载函数或复用现有 artifacts 模块，负责：

1. 路径必须存在且为普通文件；
2. 对当前权威命名，发现同目录 `robustness_experiment_manifest.json`；
3. 先解析清单并执行输出哈希验证，再读取业务表格；
4. 安全捕获 JSON/文件/CSV 解码与解析错误，并转换为用户可读的领域错误；
5. 校验 aggregates 和 summary 的最小 schema；
6. 返回验证状态，例如 `strict_verified`、`artifact_hashes_verified`、`legacy_unverified`，供页面展示；
7. 页面只负责把领域错误显示为 `st.error` 并安全停止，不显示 Python traceback。

不要使用宽泛的裸 `except Exception: pass`。可以在加载器边界捕获已知的 `OSError`、`UnicodeError`、`json.JSONDecodeError`、`pandas.errors.ParserError`、`EmptyDataError` 及验证器抛出的契约错误，并保留简洁原因。

### 5.2 当前命名与旧命名分流

- `robustness_*`：视为当前 schema 产物；若 sibling manifest 存在，必须验签后展示；manifest 存在但非法或哈希不一致时硬停止。
- 当前命名但没有 manifest：不得默认为可信。可以拒绝，也可以显著标注“未验证”，但不得与已验签状态混淆。
- `experiment_*`：仅作为明确的 legacy 兼容路径；安全解析并显示弃用/未验证警告。
- 手工选择不同目录中的 aggregate 与 summary：必须阻止混批，或分别清楚显示各自验证状态。不能只在默认路径选择时防混批。

### 5.3 最小表结构

至少验证：

- aggregates：非空、含 `family` 和 `value`；`family` 有非空可选值；选中指标对应的 `mean_<metric>` 可转换为有限数值或明确为不适用；
- summary：含 `status`；状态值只允许 `completed/failed`；若来自当前清单，行数和状态计数由 `verify_experiment_manifest` 复核；
- 任何验证失败都不得调用绘图函数或展示可能误导的表格。

### 5.4 源配置核验状态

运行目录目前只有实验 CSV 与 manifest，没有复制两份配置快照。因此要诚实区分：

- 仅依据 manifest 验证输出哈希；
- 额外找到并传入真实 `configs/robustness.yaml`、`configs/default.yaml` 后完成严格源配置核验。

如果页面能可靠解析仓库中的两份配置路径，则调用严格模式；否则显示“产物哈希已验证，但源配置未交叉核验”，不得使用“完全自验证”措辞。

---

## 六、G1：收紧运行清单字段契约

`verify_manifest_hashes` 当前使用：

```python
for name in manifest.get("input_paths", []):
```

这使缺失字段被当作空列表接受，也让错误类型可能被逐字符或逐键遍历。

修复要求：

1. `input_paths` 必须存在；
2. 必须为 `list[str]`；
3. 本项目一次运行必须至少含一个配置输入；
4. 拒绝重复项；
5. 对每项调用共享的 portable path validator；
6. 错误信息明确区分“字段缺失/类型错误/重复/路径非法”；
7. 保持当前交付 `input_paths=["default.yaml"]` 通过；
8. 不要把 Pydantic 模型存在当成原始 JSON 已验证，`report` 读取的是普通字典，验证函数必须自行执行边界检查。

若项目文档坚持 `input_paths` 只存“配置文件名”而不是一般相对路径，还应统一要求单个路径组件，并让文档、生成器和验证器三者一致。

---

## 七、G1：区分实验清单的部分校验与严格校验

上一轮已经明确：未提供原始配置路径时，不可能证明嵌入 snapshot 与原始 YAML 一致。本轮应把这个边界落实到公开 API 和文档，而不是只留在整改提示词里。

可选设计二选一：

### 方案 A：显式模式参数

```python
verify_experiment_manifest(
    manifest,
    artifact_dir,
    experiment_config_path=...,
    base_config_path=...,
    require_source_configs=True,
)
```

`require_source_configs=True` 时两份路径缺任一项都失败；返回或日志清楚表明严格验证完成。

### 方案 B：拆分两个公开函数

```python
verify_experiment_artifacts(...)
verify_experiment_manifest_with_sources(...)
```

第一个只验证 schema、输出哈希和案例计数；第二个在其基础上强制执行 name/hash/snapshot 与两份源配置的四方一致性。

无论采用哪种方案，都必须：

1. 更新 docstring，删除当前“config hashes against embedded snapshots”这种无条件表述；
2. README、`docs/methodology.md`、`data/README.md` 明确两级能力；
3. 给出严格调用示例，包含两份配置路径；
4. 将 `test_delivered_robustness_manifest_is_self_verifying` 改为准确名称，例如 `...passes_strict_source_verification`；
5. 鲁棒性页面显示实际完成的验证级别；
6. 不要试图从 snapshot 重新序列化 YAML 并与原始字节哈希比较；解析对象与原始 YAML 字节不是同一证据层。

---

## 八、G2：补齐跨平台名称规则

当前 helper 已正确拒绝反斜杠、盘符、绝对路径、空段、`.` 和 `..`，但它的 docstring 宣称“portable, OS-independent”，还应处理 Windows 文件名规则。

建议对每个 POSIX 分段执行：

1. 拒绝 `<>:"|?*` 和 NUL/控制字符；
2. 拒绝尾随空格或尾随点；
3. 大小写不敏感地拒绝 `CON/PRN/AUX/NUL/COM1..COM9/LPT1..LPT9`，即使带扩展名；
4. 保持普通 Unicode 文件名可用，不要无理由限制为 ASCII；
5. 增加正常嵌套相对路径测试，防止过度收紧。

如果团队决定 helper 只保证“无路径穿越”而不保证跨 OS 可落盘，也可以缩小函数名和 docstring 的承诺；但当前生成器和文档继续声称“跨 OS 可移植”时，必须完成上述规则。

---

## 九、文档与证据策略

需要更新：

- `README.md`
- `docs/methodology.md`
- `data/README.md`
- 相关函数 docstring

文档必须准确说明：

1. 完成态和失败态 schema-v2 manifest 都保留配置快照哈希闭环；
2. 当前实验产物在展示前会做何种验签；
3. 严格源配置验证与离线产物验证的区别；
4. legacy 实验 CSV 只兼容展示，不等于已验签；
5. 用户输入错误会转为页面错误提示，而不是应用崩溃。

证据策略：

- 本轮若只改失败分支、验证器、页面和文档，不需要重跑 30 天默认流水线；
- 不修改实验生成内容时，不需要重跑 130 案例实验；
- 现有交付证据仍必须通过严格验证和字节复现；
- 若你修改了完成态 manifest 内容、报告摘要内容或实验 manifest schema，才按影响范围重新生成真实证据；
- 不得手工编辑 JSON/CSV 来伪装“已重跑”。

---

## 十、推荐实施顺序与提交拆分

按以下顺序执行：

1. `test: reproduce eighth-review failure and page boundaries`
   - 只加 G0 失败测试；
   - 保存失败输出；
2. `fix: keep failed run manifests self-verifying`
   - 修复失败 manifest 配置快照闭环；
3. `fix: verify and safely load robustness artifacts`
   - 抽离加载器、验签、schema 检查、页面错误处理；
4. `fix: tighten portable manifest input contracts`
   - `input_paths` 类型/存在性和跨平台名称规则；
5. `docs: clarify experiment verification levels`
   - API/docstring/三份文档同步；
6. 如确需证据重生，单独 `chore: regenerate ... evidence`。

提交前逐次执行：

```powershell
git diff --check
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src app tests scripts
git status --short
```

不要把两个未跟踪审查报告混入上述提交。

---

## 十一、最终验收矩阵

| 验收项 | 必须结果 |
|---|---|
| base-case critical 终止 | 失败清单保留结构化违规详情 |
| base-case non-convergence | 失败清单保留结构化阶段信息 |
| 后续普通异常 | 不携带陈旧 base-case 上下文 |
| 所有已持久化失败清单 | `verify_manifest_hashes` 通过 |
| 配置快照闭环 | snapshot hash 等于顶层 config hash |
| 坏 aggregates CSV | 页面无未捕获异常，显示明确错误 |
| aggregates 缺 `family` | 页面无未捕获异常，不绘图 |
| summary 缺 `status` | 页面无未捕获异常，不展示误导性失败统计 |
| 当前产物哈希被篡改 | 页面验签失败并停止展示 |
| legacy 产物 | 可兼容时明确标记未验证 |
| 缺失/错误类型 `input_paths` | 验证器明确拒绝 |
| 严格实验验证 | 两份源配置 name/hash/snapshot 全部交叉一致 |
| 离线实验验证 | 明确只证明产物完整性，不冒充源配置核验 |
| Windows 保留名/尾随点空格 | portable validator 拒绝或缩小公开承诺 |
| 权威默认报告 | summary 与 manifest 仍可逐字节复现 |
| 权威实验清单 | 严格源配置验证通过 |
| 全量测试 | 全绿，数量不得少于当前 136 |
| Ruff | `All checks passed!` |

---

## 十二、最终回报格式

完成后只按以下结构回报，不要写空泛总结：

```text
1. 基线与工作树保护
   - 开始时 HEAD/status
   - 保留了哪些未跟踪文件

2. 失败测试复现
   - 每个反例在修复前的失败摘要

3. 实际修改
   - 文件路径
   - 契约变化
   - 为什么没有削弱校验

4. 失败清单证据
   - 一个真实/测试失败 manifest 的 output_paths
   - verify_manifest_hashes 结果
   - failure_summary 结构

5. 鲁棒性页面边界
   - 坏 CSV、缺列、哈希篡改的 AppTest 结果
   - 当前/离线/legacy 验证状态如何展示

6. 证据复核
   - 默认 report 字节复现
   - 实验 manifest 严格验证
   - 是否重跑 30 天/130 案例及理由

7. 全量验证
   - pytest 完整结果
   - Ruff 完整结果
   - git diff --check

8. 提交
   - commit hash 与主题
   - 最终 git status
   - 明确未 push

9. 下一轮审查提示
   - 只列仍需 Codex 独立验证的边界，不得自行宣布审查终止
```

最终完成标准不是“136 个旧测试仍通过”，而是本文反例先失败、修复后变绿，失败清单可由自身 verifier 验证，鲁棒性页面对外部输入不再崩溃且不会展示未验签的当前证据，同时现有权威证据保持可复现。
