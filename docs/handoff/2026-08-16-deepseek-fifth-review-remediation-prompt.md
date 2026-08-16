# DeepSeek Agent Harness 第五轮整改主提示词

> 适用项目：`distribution-network-line-transformer-verification`
> 工作目录：`D:\电力`
> 审核基线：Git `main` 分支，提交 `6405518`
> 生成日期：2026-08-16
> 用途：在第四轮整改和 GLM 第五轮初审之后，完成证据链、指标边界、物理校验策略、Streamlit 兼容性和展示完整性的收口整改。

---

## 一、直接复制给 DeepSeek 的主提示词

你正在维护一个面向“电网/能源数字化实习”作品集的项目：

`distribution-network-line-transformer-verification`

请在仓库 `D:\电力` 中执行第五轮整改。你可以修改代码、测试、文档和可再生证据，但必须遵守本文的范围、验证规则和提交要求。不要只写建议，必须实际检查、修改、测试并提交。

### 1. 当前基线与已知状态

- 基线提交：`6405518 chore: refresh robustness evidence with complete metrics`
- 当前自动化检查：
  - `80 passed`
  - Ruff：`All checks passed!`
- 第四轮已完成的主要内容包括：
  - Top-k 指标排除部分不可评估候选；
  - 鲁棒性实验增加部分完整指标；
  - 物理越限类型可配置；
  - 运行清单增加输出哈希；
  - 页面可在非仓库工作目录启动；
  - schema-v2 证据重新生成。
- 不得因现有测试通过而认定第五轮无需修改。本轮发现的是现有测试未覆盖的边界和契约问题。

开始前必须阅读：

1. `docs/handoff/2026-08-16-fifth-review-report.md`
2. `docs/handoff/2026-08-16-deepseek-fourth-review-remediation-prompt.md`
3. `README.md`
4. `docs/methodology.md`
5. `src/ltverify/contracts.py`
6. `data/README.md`
7. `configs/default.yaml`
8. 涉及的源代码及测试，不得只根据审核报告改代码。

### 2. 对第五轮初审结论的校正

GLM 初审确认了若干正确方向，但其中几项结论不完整或与仓库现状不符。实施时以代码和可复现实验为准：

1. **实验清单尚未完整记录基础配置。** 目前只有 `base_config_path`，没有 `base_config_sha256` 和基础配置的解析后快照。
2. **鲁棒性看板尚未展示新增指标。** 实验 CSV 虽包含 PR-AUC 等列，但页面选择器仍缺少 `pr_auc`、`pr_auc_scored`、`scored_coverage` 和 `insufficient_data_rate`。
3. **Streamlit 最低版本不能只提高到 1.49。** 项目同时使用 `st.dataframe(width="stretch")` 和 `st.plotly_chart(width="stretch")`；后者从 Streamlit 1.51 才支持该参数，因此统一下限应为 `streamlit>=1.51,<2`。
4. **物理校验问题不只是文档缺一句“零容忍”。** 当前基础工况和时序工况对可配置严重等级的执行语义并不一致，配置项也缺少枚举校验。

### 3. 强制工作方式

按以下顺序执行：

1. 先检查工作树，保留用户已有修改和未跟踪文件。
2. 为每个已确认缺陷先补失败测试或最小复现。
3. 再修改实现。
4. 运行定向测试。
5. 运行完整测试、Ruff 和证据一致性检查。
6. 代码稳定后再重新生成耗时证据，避免反复跑 30 天或 130 组实验。
7. 分主题提交，提交信息必须准确。

禁止：

- 删除或覆盖 `docs/handoff/2026-08-16-fifth-review-report.md`；
- 使用 `git reset --hard`、`git clean -fd` 或覆盖用户工作树；
- 为了让测试通过而弱化断言、跳过测试或吞掉异常；
- 编造准确率、PR-AUC、实验次数或运行时间；
- 把绝对本机路径写入可交付证据；
- 未经用户要求推送远程仓库；
- 在所有修改完成前反复运行完整 130 组实验。

---

## 二、G0：建立失败复现与契约测试

先添加能稳定暴露下列问题的测试。测试应围绕公开行为或产物契约，不要过度绑定内部实现。

### G0.1 运行清单完整性

至少覆盖：

- schema-v2 清单的 `output_paths` 与 `output_sha256` 键集合不相等时必须失败；
- 哈希映射为空但输出列表非空时必须失败；
- 出现额外哈希、重复路径、绝对路径或 `..` 路径穿越时必须失败；
- 哈希值不是 64 位十六进制字符串时必须失败；
- 修改 `config.snapshot.yaml` 后，报告生成必须拒绝继续，而不是只验证其他 CSV/JSON。

### G0.2 评估指标边界

至少覆盖：

- 真值全为 0 时，PR-AUC 不得写成可比较的 `0.0`；
- 真值全为 1 时，也必须明确其不可用于二分类区分能力比较；
- 只有同时存在正负样本时，主 PR-AUC 才标记为适用；
- Top-k 候选的分数或权重为 `NaN`、`+inf`、`-inf` 时均不可进入候选池；
- 空候选集和不足 k 个候选的行为必须保持明确、可解释。

### G0.3 物理校验策略

至少覆盖：

- `critical_violation_types` 中的拼写错误或未知类型在配置加载阶段失败；
- 重复类型被拒绝或规范化，行为必须明确；
- 基础工况出现被配置为 warning 的已求解网络越限时，不应被无条件当作 critical 终止；
- 基础工况和时序工况使用相同严重等级策略；
- 潮流不收敛始终是硬失败，不因从 `critical_violation_types` 移除而降级。

### G0.4 页面与依赖契约

至少覆盖：

- 鲁棒性页面能够选择并渲染 `pr_auc`、`pr_auc_scored`、`scored_coverage`、`insufficient_data_rate`；
- 指标列包含空值时页面不崩溃，并明确显示“不可用/不适用”；
- schema 版本缺失、旧版本、当前版本、未来版本分别进入预期分支；
- 项目声明的 Streamlit 最低版本与实际使用的 API 匹配。

---

## 三、G1：修复运行证据链与清单校验

### G1.1 把配置快照纳入可验证证据链

当前流水线会写入 `config.snapshot.yaml`，报告也会读取它，但它没有进入输出哈希集合。这意味着配置快照被篡改后，其他文件的哈希仍可能全部通过，报告却会基于被修改的配置重新计算。

必须完成：

1. 将 `config.snapshot.yaml` 纳入 `output_paths` 和 `output_sha256`；
2. 同时校验配置快照哈希与清单顶层 `config_sha256` 一致；
3. 报告读取快照前必须先完成上述校验；
4. 旧清单若缺少该字段，应进入清晰的兼容/拒绝路径，不能静默视为完整 schema-v2；
5. 更新集成测试的预期输出集合。

建议不变量：

```text
sha256(config.snapshot.yaml)
  == manifest.config_sha256
  == manifest.output_sha256["config.snapshot.yaml"]
```

若项目使用规范化配置内容计算 `config_sha256`，则需要明确“文件字节哈希”和“规范化配置哈希”的区别，并分别命名，不能让同一字段承担两种语义。

### G1.2 严格校验清单的完整性和安全路径

对 schema-v2 清单，验证函数必须至少满足：

```text
set(output_paths) == set(output_sha256.keys())
```

并补充以下约束：

- `output_paths` 不得重复；
- 每个条目必须是相对运行目录的安全路径；
- 禁止绝对路径；
- 禁止 `..` 逃逸运行目录；
- 每个哈希必须是 64 位十六进制 SHA-256；
- 文件必须存在且实测哈希匹配；
- 出现缺项或多项都必须失败，不能只遍历已有哈希。

错误信息要包含具体文件或字段，便于用户定位，但不要泄露无关系统路径。

### G1.3 补齐鲁棒性实验清单

`reports/metrics/robustness_experiment_manifest.json` 及其生成代码必须增加：

- `artifact_schema_version`；
- `experiment_config_sha256`；
- `experiment_config_snapshot`；
- `base_config_sha256`；
- `base_config_snapshot`（最终解析、合并后的有效基础配置）；
- 可移植的相对路径；
- 关键输出文件哈希。

注意区分：

- 实验矩阵配置；
- 基础业务配置；
- 合并解析后的实际运行配置。

不能只保存 YAML 文件路径，因为路径本身不能证明实验使用了什么内容。

---

## 四、G2：修复评估指标的统计语义

### G2.1 PR-AUC 必须增加适用性状态

当前在真实错误数为 0 时可能得到 `pr_auc=0.0`，这会被误读为模型表现极差；实际上单类别真值下不存在可比较的二分类排序任务。

统一规则：

- 只有 `y_true` 同时包含 0 和 1 时才计算主 PR-AUC；
- 否则：
  - `pr_auc = null`；
  - `pr_auc_applicable = false`；
  - 记录不可适用原因，如 `single_class_all_negative` 或 `single_class_all_positive`；
- 正常双类别数据：
  - `pr_auc_applicable = true`；
  - 输出有限数值；
- `pr_auc_scored` 使用同样的双类别适用性约束；
- 聚合、CSV、JSON、页面、报告和文档都必须能处理空值，不得强制填 0。

如保留 `n_actual_errors`、`n_actual_correct` 等上下文字段，应继续输出，以便解释为何不适用。

### G2.2 Top-k 的“有限值”必须名副其实

当前 `.notna()` 不能排除正负无穷。对参与排序的分数和样本权重：

1. 先显式转为数值；
2. 使用 `numpy.isfinite` 判断；
3. 任一必要字段非有限时，该候选不得进入 Top-k 排序；
4. 对被排除数量输出可解释计数；
5. 更新数据契约，明确 `NaN` 和无穷都属于不可评估。

不要依赖“当前算法通常不会产生无穷”作为省略验证的理由，评估模块必须对输入契约负责。

### G2.3 类型契约同步

如果 `EvaluationResult.metrics` 现在的类型注解只允许 `float | int`，但实际已经包含 `null`、布尔值、字典或原因字符串，应改成真实契约，例如 TypedDict、dataclass 或至少 `dict[str, object]`。不要保留明显错误的类型声明。

---

## 五、G3：统一物理越限配置语义

### G3.1 校验允许的违规类型

为 `critical_violation_types` 建立唯一允许集合。至少覆盖项目当前已实现的已求解网络违规类型，例如：

- 电压上越限；
- 电压下越限；
- 线路过载；
- 变压器过载。

具体枚举名称必须以代码现有输出为准，不要凭本文中文描述另造字符串。

要求：

- 配置加载时拒绝未知值；
- 对大小写、空格是否规范化作出明确决定；
- 不允许拼写错误静默导致风险降级；
- 枚举在配置模型、校验逻辑、文档和测试中共用，避免复制后漂移。

### G3.2 基础工况与时序工况使用同一严重等级策略

当前基础工况只要存在任何 violation 就可能直接终止，而时序工况会区分 critical/warning。这与配置化设计不一致。

建议统一为：

```text
潮流不收敛：始终 fatal
已求解网络违规：根据 critical_violation_types 分类
terminate_on_critical=true：存在 critical 时终止
terminate_on_critical=false：记录 critical，但允许后续流程继续
warning：记录并继续
```

实现要求：

- 静态校验结果不能只返回无类型的消息列表；
- 应保留违规类型、严重等级、对象、实测值、阈值等结构化字段；
- 基础工况和时序工况复用同一分类函数；
- 非收敛与已求解后的工程越限分开表达；
- 若最终选择不同策略，必须给出充分业务理由并在配置、README、方法文档中明确，不得保持当前隐式不一致。

### G3.3 文档说明默认策略

默认配置若把所有四类已求解网络越限都列为 critical，文档必须明确：

- 默认策略相当于对这些越限零容忍；
- 用户可以只对已求解网络违规进行显式降级；
- 潮流不收敛始终是硬失败，不属于可随意降级的普通越限。

---

## 六、G4：修复看板、schema 兼容和报告输出行为

### G4.1 鲁棒性看板展示完整指标

在 `app/pages/5_robustness.py` 中加入并正确解释：

- `pr_auc`：主样本口径；
- `pr_auc_scored`：仅可评分子集的诊断口径；
- `scored_coverage`：可评分覆盖率；
- `insufficient_data_rate`：数据不足率。

要求：

- 页面明确区分主指标与诊断指标；
- `null` 显示为“不适用”，不能替换成 0；
- 聚合前处理空值，避免错误均值；
- 页面测试的合成数据必须包含这些列；
- 至少为每个新增选择项执行一次渲染测试。

### G4.2 明确 schema 三态兼容策略

不要把 `artifact_schema_version != 2` 一律当作 legacy，也不要简单改成 `< 2` 后默认接受所有未来版本。

建议实现三态：

1. 缺失或 `< 2`：legacy，显示兼容提示并隐藏不可靠字段；
2. `== 2`：当前受支持版本；
3. `> 2`：newer/unsupported，提示当前应用未验证该版本；只有在必需字段验证通过时才允许有限展示，否则安全拒绝。

同时处理字符串、浮点、布尔、空值等非法版本输入，避免隐式比较异常。

### G4.3 把 Streamlit 最低版本提高到 1.51

同时修改：

- `pyproject.toml`；
- `requirements.txt`；
- 如存在锁文件或环境说明，也要同步。

统一为：

```text
streamlit>=1.51,<2
```

依据：

- Streamlit 1.49 的 `st.dataframe` 已支持 `width="stretch"`；
- Streamlit 1.50 的 `st.plotly_chart` 尚无 `width` 参数；
- Streamlit 1.51 的 `st.plotly_chart` 才支持 `width="stretch"`。

官方参考：

- https://docs.streamlit.io/1.48.0/develop/api-reference/data/st.dataframe
- https://docs.streamlit.io/1.49.0/develop/api-reference/data/st.dataframe
- https://docs.streamlit.io/1.50.0/develop/api-reference/charts/st.plotly_chart
- https://docs.streamlit.io/1.51.0/develop/api-reference/charts/st.plotly_chart

建议增加最小依赖环境验证脚本或 CI job，至少要避免“开发机最新版可运行，但声明的最低版本不可运行”。

### G4.4 消除报告命令的隐式伴生文件覆盖

当前报告生成可能无论用户指定什么输出文件，都在同目录写固定名称 `default_manifest.json`。这会产生意外副作用和覆盖风险。

修改为以下任一种清晰契约，优先第一种：

1. 新增显式 `--manifest-output` 参数；未指定时使用 `${report_stem}.manifest.json`；
2. 若仅允许规范目录输出，则明确拒绝任意输出路径，并记录在 CLI 帮助中。

要求：

- 不得静默覆盖无关的 `default_manifest.json`；
- CLI `--help` 和 README 示例同步；
- 测试自定义报告文件名时，断言伴生清单名称和位置；
- 若目标已存在，沿用项目现有覆盖策略并明确说明。

---

## 七、G5：证据重生成与文档同步

代码和定向测试全部稳定后，再重新生成可交付证据。

### G5.1 必须重新生成的内容

至少包括：

- 默认运行目录中的 schema-v2 清单及所有声明输出；
- 报告和报告清单；
- 鲁棒性实验清单；
- 若评估输出字段、聚合规则或实验指标发生改变，重新运行完整 130 组实验并生成对应 CSV/JSON/图表；
- README 中展示的数字、截图说明和运行命令。

不得只手工编辑生成产物中的哈希或数字。

### G5.2 证据验收

用自动化脚本验证：

- 清单列出的每个文件都存在；
- 每个哈希与文件实测值一致；
- 没有多余或缺失的哈希条目；
- 配置快照哈希链一致；
- JSON 中不存在非标准 `NaN`/`Infinity`；
- 证据中不存在 `D:\...` 等本机绝对路径；
- 130 组实验的组合数、种子数与实验配置一致；
- 页面实际读取的是新产物，而非旧缓存。

### G5.3 文档必须同步说明

更新 README、方法文档和数据契约，至少说明：

- PR-AUC 的适用条件和 `null` 语义；
- 主 PR-AUC 与 scored-only PR-AUC 的差别；
- Top-k 有限值资格规则；
- 配置快照如何参与证据验证；
- 实验清单同时固定实验配置和基础配置；
- 物理越限的默认 critical 策略；
- 非收敛始终硬失败；
- schema 兼容策略；
- Streamlit 最低版本为 1.51。

---

## 八、验证命令与验收门槛

根据仓库环境调整解释器路径，但最终至少执行：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

并执行以下定向验证：

1. 篡改临时运行目录中的 `config.snapshot.yaml`，确认报告拒绝生成；
2. 构造缺失哈希、额外哈希和路径穿越清单，确认全部拒绝；
3. 构造全负类、全正类和双类别评估数据，确认 PR-AUC 适用性正确；
4. 构造 `inf/-inf/NaN` 排序数据，确认 Top-k 排除；
5. 使用自定义 warning 物理配置跑基础工况和时序工况；
6. 页面测试覆盖四个新增鲁棒性指标和未来 schema；
7. 从仓库外工作目录启动或测试各 Streamlit 页面；
8. 校验生成证据的全部哈希和相对路径。

最终门槛：

- 完整 pytest 全绿；
- Ruff 全绿；
- 无跳过关键新增测试；
- 所有生成证据可由命令重现；
- Git 工作树中不包含缓存、临时输出或无关文件；
- 用户原有未跟踪文件得到保留。

---

## 九、建议提交边界

建议按以下顺序提交，实际可根据代码耦合适度合并，但不得把全部内容塞进一个难审查提交：

1. `test: reproduce fifth-review evidence and metric gaps`
2. `fix: enforce complete portable artifact manifests`
3. `fix: handle metric applicability and finite top-k inputs`
4. `fix: align physical validation policy across run modes`
5. `fix: complete robustness dashboard and schema handling`
6. `fix: align streamlit dependency and report outputs`
7. `docs: document fifth-review contracts and policies`
8. `chore: regenerate fifth-review release evidence`

每次提交前执行相关定向测试。最后一个提交前执行完整测试和 Ruff。

不要推送远程；只创建本地提交，并在最终报告中列出提交哈希。

---

## 十、最终回报格式

完成后向用户提供一份简洁但可核验的执行报告，必须包含：

1. 修改摘要，按 G1—G5 分类；
2. 每个缺陷对应的实现文件与测试文件；
3. 完整 pytest 结果和 Ruff 结果；
4. 证据生成命令、实验组合数量和运行结果；
5. 清单哈希完整性检查结果；
6. 所有本地提交哈希；
7. 尚存风险或明确写“未发现已知阻断项”；
8. `git status --short` 输出；
9. 明确声明没有推送远程。

若某项无法完成，不得用“基本完成”掩盖。应报告：

- 阻断原因；
- 已验证事实；
- 尚未完成的文件或测试；
- 用户下一步可以执行的精确命令。

---

## 十一、完成后交给下一位审核 AI 的提示词

整改完成后，把下面文字连同仓库路径发给下一位审核 AI：

```text
请对 D:\电力 仓库执行第六轮独立审核，不要默认相信第五轮整改报告。

重点核验：
1. config.snapshot.yaml 是否真正进入清单哈希闭环，篡改后报告是否拒绝；
2. schema-v2 的 output_paths 与 output_sha256 是否严格一一对应，并拒绝危险路径；
3. 鲁棒性实验清单是否同时包含实验配置和基础配置的哈希、快照；
4. 单类别真值时 PR-AUC 是否为 null/不适用，而非 0 或误导性数值；
5. Top-k 是否排除 NaN 和正负无穷；
6. 基础工况与时序工况是否执行相同的物理严重等级策略；
7. 未知 critical_violation_types 是否在配置阶段失败；
8. 鲁棒性页面是否真实展示四个新增指标，并处理空值；
9. schema 缺失、旧版、当前版、未来版是否分支正确；
10. Streamlit 下限是否至少为 1.51，报告伴生清单是否不再隐式覆盖固定文件；
11. 重新计算全部证据哈希、实验组合数和 README 数字；
12. 独立运行完整 pytest、Ruff，并检查仓库外工作目录启动页面。

请先给出按严重度排序的 findings，再给出测试证据。若没有问题，也要说明具体检查了什么，不得只复述整改者的结论。
```

---

## 十二、本轮问题优先级摘要

| 优先级 | 问题 | 风险 |
|---|---|---|
| P1 | 配置快照未纳入哈希闭环 | 报告可能读取被篡改配置而清单仍通过 |
| P1 | 清单允许不完整哈希映射 | “验证成功”不能证明所有声明输出均被验证 |
| P1 | 实验清单缺基础配置哈希/快照 | 130 组实验无法完整追溯实际基础参数 |
| P1 | 单类别 PR-AUC 写成数值 | 对模型能力产生错误解释 |
| P2 | 鲁棒性页面遗漏新增指标 | 证据虽生成但作品演示无法展示关键结果 |
| P2 | Top-k 接受正负无穷 | 实现与“有限候选”契约不一致 |
| P2 | 物理严重等级策略不一致 | 配置可能在基础工况中失效，或拼写错误静默降级 |
| P2 | 未来 schema 被误判为 legacy | 新版本产物可能被错误解释 |
| P3 | Streamlit 下限过低 | 按声明安装的环境可能在页面运行时失败 |
| P3 | 报告隐式写固定伴生文件 | 自定义输出时可能覆盖无关文件 |

本轮目标不是继续堆叠算法，而是让“可复现、可解释、可演示、可审计”四条链真正闭合。完成这些整改后，该项目才更适合作为电网/能源数字化实习作品集提交。
