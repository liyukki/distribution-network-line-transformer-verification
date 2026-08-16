# DeepSeek GitHub 公开上架前整改执行提示词

> 使用方式：将本文完整交给 DeepSeek V4 及其 agent harness。目标是把当前项目整理成可公开展示、可供电网/能源数字化实习面试使用的 GitHub 作品。严格执行“红测 → 最小修复 → 仓库清理 → CI → 发布验收”，不得直接 push 或擅自重写 Git 历史。

## 1. 角色与最终目标

你是本项目的 GitHub 公开发布整改执行者。项目业务代码和实验链路已基本完成，本轮不是继续堆算法，而是完成公开发布门禁：

1. 修复两组仍可复现的运行时输入契约缺陷；
2. 统一 Python 格式并建立 GitHub Actions；
3. 清理 Notebook 本机绝对路径和公开主分支中的内部 Agent 工作材料；
4. 保留真实实验失败边界与证据可追溯性；
5. 产出明确的 `PUBLIC_READY=YES/NO` 验收结论。

最终仓库应适合本科生投递“电网/能源数字化、数据分析、电力软件、算法工程实习”，但不得声称已现场部署、使用真实电网数据或达到生产准确率。

## 2. 当前基线与已验证事实

执行基线：

```text
code_review_anchor = 4252aef docs: archive seventh-eighth-ninth review reports
expected_branch = main
remote = 未配置
```

本文会作为锚点之后的一笔纯文档提交交给你，因此不要要求当前 `HEAD` 必须等于 `4252aef`。开始前应确认：`4252aef` 是当前 `HEAD` 的祖先、锚点之后只有本交接文档或用户明确说明的提交，并且工作区干净；如出现其他代码变更，先报告差异，不要覆盖。

Codex 已现场验证：

```text
pytest: 263 passed
coverage: 91%（ltverify 总计 1699 statements，146 miss）
ruff check: All checks passed!
wheel: distribution_network_line_transformer_verification-0.1.0-py3-none-any.whl 构建成功
Notebook: 01/02/03 均可由 nbconvert 从头执行
report_summary_byte_match=True
report_manifest_byte_match=True
experiment_manifest_level=strict
robustness_loader_state=strict_verified
robustness_rows=130
MIT LICENSE 存在
基础 secret/private-key 扫描未发现明显凭据
```

同时确认：

```text
ruff format --check src app tests scripts
# 41 files would be reformatted

git rev-list --count HEAD
# 100

git log 作者
# 当前提交均为 Codex <codex@openai.com>
```

现有权威 evidence manifest 引用了仍存在的历史提交：

```text
default_manifest.json -> 533b64a09570b80533e26724430089bc61c755da
robustness_experiment_manifest.json -> 59a623e09b4ea470a149a93d9e8efa51d2008fe7
```

因此本轮严禁随意 squash、filter-repo、rebase 根历史或重新初始化当前仓库。历史被改写后，这两条证据引用会失效，除非重新生成全部权威证据。

## 3. 不可违反的约束

1. 先确认 HEAD 和工作区；不得 reset、clean、checkout 覆盖用户文件。
2. 不修改特征、评分权重、阈值、标签、评价口径、仿真参数和 30 天/130 案例数据。
3. 不重跑默认 30 天流水线和 130 案例实验；本轮仅复现已有 evidence。
4. 不删除或伪造失败边界：默认结果仍是 F1 0.167、PR-AUC 0.378，必须诚实保留。
5. 不添加未经真实运行生成的截图、指标、徽章或 CI 状态。
6. 不猜测用户姓名、GitHub 用户名、邮箱或远端地址。
7. 不配置 remote、不创建 GitHub 仓库、不 push、不发布 release。
8. 不把 Codex 提交批量改写成用户作者；需要用户身份的最终发布提交由用户本人完成。
9. 所有删除内部文档的操作必须通过普通 Git 提交完成，确保可从历史恢复；禁止永久清理 Git 对象。
10. 最终若任一强制门禁失败，必须输出 `PUBLIC_READY=NO`。

## 4. 当前发布阻塞问题

### R1（P1）：在集合运算前未验证 manifest 元素类型

位置：

```text
src/ltverify/data_access.py::discover_completed_run_dir
src/ltverify/data_access.py::load_run_artifacts
```

当前代码先执行：

```python
set(output_paths)
```

若 manifest 为：

```json
{
  "artifact_schema_version": 2,
  "status": "completed",
  "output_paths": [[]],
  "output_sha256": {}
}
```

Codex 实测：

```text
unhashable_loader_result=TypeError
unhashable_discovery_result=TypeError
```

这会绕过 `ArtifactLoadError`，使 Streamlit 在选择默认 run 或显式加载 run 时出现 traceback。

重复路径也没有在发现阶段被拒绝。较新的 completed run 若重复声明 `config.snapshot.yaml`，当前结果：

```text
duplicate_discovery_selected=run-20260816T999999-duplicate
duplicate_selected_load_result=ArtifactLoadError(output_paths 存在重复条目)
```

即自动发现会选择结构非法的新 run，遮挡更旧的有效 run。

### R2（P2）：首页比例指标只检查有限性，未检查类型和范围

位置：

```text
src/ltverify/data_access.py::_validate_metrics
```

当前通过 `float(value)` 接受字符串数值，也未限制比例范围。Codex 实测：

```text
metrics.f1 = 999.0
out_of_range_f1_result=999.0
```

这会把语义非法但哈希一致的证据展示为 `F1=999.000`。F1、Top-k 和覆盖率属于比例，不只是“有限浮点数”。

### R3（公开仓库卫生）：Notebook 保存了本机绝对路径

以下已提交 Notebook 输出含 `D:\电力\...`：

```text
notebooks/01_network_sanity.ipynb
notebooks/02_baseline_analysis.ipynb
notebooks/03_robustness_analysis.ipynb
```

三个 Notebook 虽然可执行，但公开输出不应绑定本机盘符。需修改展示代码并重新执行，使输出只包含仓库相对路径。

### R4（质量门禁）：未统一格式且没有 GitHub Actions

当前 `ruff check` 通过，但 `ruff format --check` 报 41 个文件需要格式化；仓库不存在 `.github/workflows/`。公开项目缺少自动测试证明。

### R5（作品集呈现）：公开主分支包含大量内部 Agent 交接材料

当前主分支含：

```text
docs/handoff/                  # 多轮 DeepSeek/Codex 提示词与审查报告
docs/superpowers/plans/        # 内部执行计划
docs/superpowers/specs/        # 内部设计过程材料
```

这些材料对内部开发有价值，但会淹没项目方法、实验、数据字典和面试展示。发布主分支应保留透明的 AI 使用说明和精简审计摘要，而不是保留十余份原始 Agent prompt。

注意：从当前工作树删除这些文件不会删除 Git 历史，也不会破坏 evidence 引用；不要重写历史。

## 5. G0：先写失败测试

先只添加测试，不修改实现。建议提交：

```text
test: reproduce github-release manifest and metric regressions
```

### 5.1 manifest 元素类型与重复项

修改：

```text
tests/unit/test_app_data_access.py
tests/integration/test_streamlit_smoke.py
```

至少新增参数化测试：

```python
@pytest.mark.parametrize(
    "output_paths",
    [
        [[]],
        [{}],
        [1],
        [None],
        ["metrics.json", ["predictions.parquet"]],
    ],
)
def test_loader_rejects_non_string_output_path_elements(...):
    ...
```

要求：

1. `load_run_artifacts` 统一抛 `ArtifactLoadError`，不能泄漏 `TypeError`；
2. `discover_completed_run_dir` 跳过坏候选并选择旧的完整 completed run；
3. Streamlit `AppTest.exception` 为空，页面显示可操作错误；
4. 元素验证必须发生在 `set()`、排序、集合差或路径拼接前；
5. 重复 `output_paths` 在发现阶段直接跳过；
6. `output_paths` 与 `output_sha256` keys 不一致的候选也跳过；
7. 合法额外产物仍然允许。

### 5.2 metrics 类型、范围和计数关系

对 `_validate_metrics` 至少新增：

```python
@pytest.mark.parametrize("value", [-0.01, 1.01, 999.0, "0.8", True, float("nan"), float("inf")])
def test_loader_rejects_invalid_f1(value, ...):
    ...
```

对以下比例字段分别覆盖：

```text
f1
top1_correction_rate
automatic_coverage
```

最低契约：

- `f1`：必须存在、必须为非 bool 的 JSON number、有限且位于 `[0,1]`；
- `automatic_coverage`：必须存在、必须为非 bool 的 JSON number、有限且位于 `[0,1]`；
- `top1_correction_rate`：允许 `null` 表示不适用，否则必须满足同一比例契约；
- `n_predicted`：必须为非 bool、非负整数；
- `n_total`：必须为非 bool、正整数；
- `n_predicted <= n_total`；
- 若 `n_actual_errors` 存在，则必须为 `[0,n_total]` 内整数。

所有坏 metrics 测试必须同步更新 manifest 哈希，证明失败来自语义契约而不是 checksum。

至少增加一个 AppTest：hash 一致但 `f1=999.0` 时页面无 traceback、出现 `st.error`、不显示 `999.000`。

### 5.3 红测证据

进入实现前运行新增测试并记录：

```text
c12/当前基线上的失败测试名
实际异常类型
期望的领域错误
```

不得通过故意引入语法错误制造红测。

## 6. G1：抽取唯一的 manifest 声明验证入口

避免 `data_access.py`、`manifest.py` 各自复制验证逻辑。建议在：

```text
src/ltverify/manifest.py
```

新增公共纯函数：

```python
def validate_output_declarations(
    manifest: dict[str, object],
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Validate output_paths/output_sha256 without touching the filesystem."""
```

它必须按以下顺序验证：

1. `output_paths` 是 list；
2. 每个元素是非空 string；
3. 每个路径通过 `validate_portable_relative_path`；
4. 不存在重复路径；
5. `output_sha256` 是 dict；
6. 每个 key 是 string 且通过 portable path 验证；
7. 每个 hash 是 64 位小写十六进制 string；
8. paths 集合与 hash keys 集合精确一致；
9. 返回不可变 paths tuple 和已类型收紧的 hash dict。

然后：

- `verify_manifest_hashes` 调用该函数后再访问文件系统；
- `load_run_artifacts` 调用该函数，检查 dashboard required subset，再做完整哈希；
- `discover_completed_run_dir` 调用该函数，捕获 `ValueError/TypeError` 后跳过候选；
- 任何 consumer 不再对 raw manifest 直接 `set(output_paths)`。

错误政策：

- verifier 可抛 `ValueError`；
- loader 转成 `ArtifactLoadError`；
- discovery 视为坏候选并 `continue`；
- Streamlit 不出现 traceback。

不要把 `verify_manifest_hashes` 整体调用在 discovery 中；发现阶段保持轻量，不对每个候选重算大文件哈希。

建议提交：

```text
fix: validate manifest declarations before collection operations
```

## 7. G2：实现严格的 dashboard metrics 契约

修改：

```text
src/ltverify/data_access.py
```

不要用 `float("0.8")` 把字符串伪装成 JSON number。建议使用 `numbers.Real/Integral`，并显式拒绝 bool：

```python
from numbers import Integral, Real

def _require_ratio_metric(
    metrics: dict[str, object],
    key: str,
    *,
    allow_none: bool,
) -> float | None:
    value = metrics.get(key)
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ArtifactLoadError(f"metrics.{key} 必须是 [0,1] 内有限数值")
    numeric = float(value)
    if not np.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ArtifactLoadError(f"metrics.{key} 必须是 [0,1] 内有限数值")
    return numeric
```

整数计数同样通过独立 helper 验证。loader 返回前完成全部关系检查，页面不应再承担坏数据兜底，也不能把非法值默认为 0。

建议提交：

```text
fix: enforce dashboard metric ranges and count relations
```

## 8. G3：统一格式与仓库生成物忽略规则

### 8.1 `.gitignore`

加入：

```text
build/
dist/
.ipynb_checkpoints/
```

保留现有：

```text
.venv/
runs/
*.egg-info/
```

### 8.2 Ruff 格式

执行：

```powershell
.venv\Scripts\python.exe -m ruff format src app tests scripts
.venv\Scripts\python.exe -m ruff format --check src app tests scripts
.venv\Scripts\python.exe -m ruff check src app tests scripts
```

格式化是机械变更，单独提交。格式化后必须跑全量测试和 evidence reproduction，不能假设无行为变化。

建议提交：

```text
style: apply ruff formatting before public release
build: ignore local build and notebook artifacts
```

## 9. G4：清理 Notebook 本机路径并验证可执行性

修改三个 Notebook 中负责显示输出路径的代码。不要手工编辑 JSON output 字符串而保留会再次生成绝对路径的代码。

统一使用类似：

```python
relative_output = output.relative_to(ROOT)
relative_output
```

或：

```python
print(output.relative_to(ROOT).as_posix())
```

然后用当前环境重新执行 Notebook 到临时目录进行预检；确认通过后再以受控方式更新已提交 Notebook。可先创建临时输出目录：

```powershell
$notebookOutput = Join-Path ([System.IO.Path]::GetTempPath()) "ltverify-notebook-check"
New-Item -ItemType Directory -Path $notebookOutput -Force | Out-Null
```

最终要求：

```powershell
git grep -n -F 'D:\' -- notebooks
# 无输出

git grep -n -F 'C:\Users\' -- notebooks
# 无输出
```

并执行：

```powershell
.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute notebooks/01_network_sanity.ipynb --output-dir $notebookOutput --ExecutePreprocessor.timeout=600
.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute notebooks/02_baseline_analysis.ipynb --output-dir $notebookOutput --ExecutePreprocessor.timeout=600
.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute notebooks/03_robustness_analysis.ipynb --output-dir $notebookOutput --ExecutePreprocessor.timeout=600
```

临时目录预检全部成功后，才可对这三个明确路径分别使用 `--inplace` 更新已跟踪输出。执行前必须再次确认目标正是这三个 Notebook；执行产生的 `runs/` 保持 ignored，不得加入提交。

不要清空所有有价值的图表输出；公开 Notebook 应能直接看到教学结果，但不含本机路径、临时目录或 traceback。

建议提交：

```text
docs: make executed notebooks portable
```

## 10. G5：建立 GitHub Actions 发布门禁

创建：

```text
.github/workflows/ci.yml
```

推荐使用 `ubuntu-latest`、Python 3.11 和 3.12 矩阵。工作流至少包含：

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e ".[dev]"
      - run: python -m ruff check src app tests scripts
      - run: python -m ruff format --check src app tests scripts
      - run: python -m pytest --cov=ltverify --cov-report=term-missing --cov-fail-under=90 -q
      - run: python -m pip wheel . --no-deps --wheel-dir dist
```

注意：

1. YAML 必须通过语法检查；
2. 不添加不存在的 secret；
3. 不伪造 CI badge；remote 未配置，无法现场证明 GitHub runner 通过；
4. 本地执行同等命令并记录结果；
5. 首次 push 后 CI 实际状态仍需用户在 GitHub 页面确认。

建议提交：

```text
ci: add python quality and test workflow
```

## 11. G6：整理公开主分支文档

### 11.1 创建精简 AI 使用说明

创建根目录：

```text
AI_USAGE.md
```

内容必须诚实、克制，至少说明：

- 项目使用多个 AI agent 辅助生成初稿、测试建议和代码审查；
- 项目所有结论以可执行测试、运行产物和 manifest 为准，而不是 AI 文本；
- 学生/仓库维护者负责需求选择、业务解释、运行验收和最终发布；
- AI 未被用于伪造真实电网数据、准确率或现场部署声明；
- 当前证据只适用于合成仿真。

不要写营销式“完全由本人独立完成”，也不要把责任全部推给 AI。

### 11.2 创建公开审计摘要

创建：

```text
docs/audit-summary.md
```

控制在约 800–1500 字，包含：

- 主要信任边界：真值隔离、manifest checksum、current schema、verify-before-parse；
- 典型修复案例：label leakage、NaN 排名、证据可复现、dashboard artifact binding；
- 最终测试/覆盖率/证据状态；
- checksum 不是数字签名；
- 未解决的研究限制。

不要复制十余轮 prompt 全文。

### 11.3 精简当前工作树

在确认 `AI_USAGE.md` 和 `docs/audit-summary.md` 完整后，从当前公开工作树移除：

```text
docs/handoff/
docs/superpowers/plans/
```

对 `docs/superpowers/specs/2026-08-15-line-transformer-verification-design.md`：

- 提炼业务仍有价值的内容到 `docs/design.md`；
- 随后移除原内部 spec 路径。

这些删除通过 Git 提交完成，不执行历史清理。提交前先列出删除清单；提交后用 `git show HEAD^:<path>` 确认至少一份旧文档仍可从历史恢复。

README 的“仓库结构”同步更新，不再引用内部 handoff/superpowers 目录。

建议提交：

```text
docs: replace internal agent handoffs with public audit summary
```

## 12. G7：增强 README 的公开作品表达

README 已经较完整，保留以下优点：

- 业务痛点明确；
- 方法、快速开始和限制齐全；
- 诚实报告 F1 0.167 的失败边界；
- 说明合成数据和非现场部署；
- MIT License。

新增或调整：

1. 在开头增加一句定位：`面向电网/能源数字化实习的可复现研究型原型`；
2. 新增“质量与复现”小节，列出测试命令、CI 文件和 evidence 命令，但测试数量不硬编码，避免以后漂移；
3. 增加 Windows 与 Linux/macOS 两套环境命令；
4. 链接 `AI_USAGE.md`、`docs/audit-summary.md`、`docs/design.md`；
5. 明确首次完整默认运行可能耗时，不把小型 fixture 结果冒充默认实验；
6. 保留真实失败边界，不能只展示成功截图。

截图政策：

- 如果 harness 具备真实浏览器截图能力，可从有效 completed small run 捕获首页、配变诊断、相似度矩阵 2–3 张 PNG，保存到 `docs/assets/`；
- 截图必须来自实际 Streamlit，不得用图像生成模型伪造；
- 如果没有真实截图能力，不创建假图，在最终报告中列为唯一可由用户手工完成的展示优化项；
- remote 未配置时不添加依赖仓库地址的 CI badge；首次 GitHub Actions 成功后再由用户添加。

LICENSE 的作者名同样不得猜测；保留 `Project Contributors`，并在最终报告提醒用户用自己的公开姓名或 GitHub handle 更新。

建议提交：

```text
docs: prepare readme for public portfolio release
```

## 13. Git 历史与发布策略

### 13.1 本轮采用的策略

采用“保留历史、精简当前树、透明披露 AI 使用”的策略：

- 不改写现有 100 个提交；
- evidence manifest 引用的 commit 继续可解析；
- 当前 main 树不再堆叠原始 Agent prompts；
- `AI_USAGE.md` 说明 AI 辅助；
- 用户用自己的 GitHub verified email 创建最终 release commit/tag。

### 13.2 禁止事项

不得：

- `git reset --hard`；
- `git rebase --root`；
- `git filter-branch` / `git filter-repo`；
- 创建 orphan branch 并替换 main；
- 把全部 Codex commit 批量改写成学生本人作者；
- 删除 evidence manifest 的 git commit 字段来掩盖历史；
- 在没有重新生成 evidence 的情况下做 squash-only 公共仓库。

### 13.3 用户发布前需亲自完成

DeepSeek 最终只报告，不执行：

1. 用户配置自己的 Git 姓名和 GitHub verified email；
2. 用户检查 `AI_USAGE.md` 是否符合个人表述；
3. 用户决定 LICENSE 显示姓名还是 GitHub handle；
4. 用户创建 GitHub repository；
5. 用户添加 `origin` 并首次 push；
6. 用户确认 GitHub Actions 两个 Python 版本实际通过；
7. 用户添加真实 CI badge 和仓库 URL；
8. 用户决定是否创建 `v0.1.0` tag/release。

## 14. 分阶段测试与提交纪律

每个阶段遵守：

```text
写测试
-> 运行并确认修复前失败
-> 最小实现
-> 运行对应小测试
-> 运行受影响集成测试
-> git diff --check
-> 只暂存该阶段文件
-> 检查 git diff --cached --name-status/stat
-> 提交
```

不得把代码逻辑修复、41 文件格式化、Notebook 输出、公开文档删除混在一个提交里。

推荐提交序列：

```text
test: reproduce github-release manifest and metric regressions
fix: validate manifest declarations before collection operations
fix: enforce dashboard metric ranges and count relations
build: ignore local build and notebook artifacts
style: apply ruff formatting before public release
docs: make executed notebooks portable
ci: add python quality and test workflow
docs: replace internal agent handoffs with public audit summary
docs: prepare readme for public portfolio release
```

## 15. 最终本地发布门禁

完成所有修改后，fresh 执行：

```powershell
.venv\Scripts\python.exe -m ruff format --check src app tests scripts
.venv\Scripts\python.exe -m ruff check src app tests scripts
.venv\Scripts\python.exe -m pytest --cov=ltverify --cov-report=term-missing --cov-fail-under=90 -q
git diff --check
git status --short
```

打包到系统临时目录，不在仓库生成未跟踪 `build/`：

```powershell
$wheelOutput = Join-Path ([System.IO.Path]::GetTempPath()) "ltverify-public-wheel"
New-Item -ItemType Directory -Path $wheelOutput -Force | Out-Null
.venv\Scripts\python.exe -m build --wheel --outdir $wheelOutput
```

如果项目未安装 `build` 模块，不新增运行依赖；可使用已验证的替代命令：

```powershell
$wheelOutput = Join-Path ([System.IO.Path]::GetTempPath()) "ltverify-public-wheel"
New-Item -ItemType Directory -Path $wheelOutput -Force | Out-Null
.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir $wheelOutput
```

命令后必须确认并清理其在仓库生成的 `build/`，同时 `.gitignore` 已覆盖该目录。

Notebook 门禁：

```text
三个 Notebook 执行成功
notebooks 中无 D:\ 本机路径
notebooks 中无 C:\Users\ 路径
notebooks 中无 traceback output
```

文档与仓库卫生门禁：

```text
README 本地链接全部存在
AI_USAGE.md 存在
docs/audit-summary.md 存在
docs/design.md 存在
当前工作树无 docs/handoff
当前工作树无 docs/superpowers/plans
.github/workflows/ci.yml 存在且 YAML 可解析
无 .env、私钥、API key、build、dist、runs、.venv 被跟踪
```

证据复现门禁：

```powershell
.venv\Scripts\python.exe -m ltverify report `
  --run-dir runs/run-20260816T121851-b42381de-ca6652 `
  --output $env:TEMP/ltverify-public-summary.json `
  --manifest-output $env:TEMP/ltverify-public-manifest.json
```

要求：

```text
临时 summary 与 reports/metrics/default_summary.json 逐字节一致
临时 manifest 与 reports/metrics/default_manifest.json 逐字节一致
verify_experiment_manifest(... require_source_configs=True) -> strict
load_robustness_artifacts(...) -> strict_verified
summary rows -> 130
git cat-file -t 533b64a09570b80533e26724430089bc61c755da -> commit
git cat-file -t 59a623e09b4ea470a149a93d9e8efa51d2008fe7 -> commit
```

Secret/路径基础扫描：

```powershell
git grep -n -I -E "BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|sk-[A-Za-z0-9]|api[_-]?key|password" -- .
git grep -n -I -F "C:\Users\" -- .
git grep -n -I -F "D:\电力" -- README.md notebooks docs data reports src app
```

测试中用于恶意路径的固定字符串可保留；README、Notebook、公开文档和 evidence 不得包含本机工作路径。

## 16. 发布验收矩阵

| 项目 | 强制标准 |
|---|---|
| manifest 非字符串元素 | loader 领域错误；discovery 跳过；页面无 traceback |
| manifest 重复元素 | verifier 拒绝；discovery 跳过旧坏候选 |
| F1/覆盖率越界 | loader 拒绝；页面不展示非法数字 |
| 数字字符串/bool | 不能冒充比例或计数 |
| 测试 | 全量通过，coverage ≥ 90% |
| Ruff | check 与 format check 均通过 |
| Wheel | 在临时目录构建成功 |
| Notebook | 三本可执行，无本机路径和 traceback |
| CI | workflow 文件完整；本地等价命令通过 |
| README | 业务、方法、结果、限制、复现、AI 使用链接齐全 |
| 内部材料 | 当前树用 audit summary 替代原始 handoff/plan |
| Evidence | 两份 report 字节一致，experiment strict，130 行不变 |
| Git 历史 | 不改写，两个 evidence commit 仍存在 |
| Git 状态 | 无意外 tracked/untracked 文件 |
| Remote/Push | DeepSeek 未执行 |

## 17. 最终回报格式

DeepSeek 最终必须按以下结构回报：

### A. 代码阻塞项

- R1/R2 根因；
- 修复文件、函数、测试名；
- 修复前异常与修复后结果；
- manifest 非字符串、重复项和 F1=999 三个反例结果。

### B. GitHub 工程化

- Ruff format 改动文件数；
- CI workflow 内容摘要；
- coverage、wheel、Notebook 结果；
- `.gitignore` 新增项。

### C. 公开文档

- 新增 `AI_USAGE.md`、`docs/audit-summary.md`、`docs/design.md`；
- 从当前树移除的内部目录列表；
- README 新增内容；
- 是否生成真实截图；若没有，明确列为用户手工项。

### D. 证据与历史

- report 两文件字节匹配；
- strict/strict_verified/130 行；
- 两个历史 commit 仍存在；
- 明确未重跑或改写 30 天/130 案例证据；
- 明确未 squash/rebase/filter history。

### E. 提交与状态

- 所有新提交 hash/subject；
- 最终 `git status --short`；
- 未配置 remote、未 push；
- 需要用户本人完成的身份、LICENSE、截图、GitHub Actions 首次确认事项。

### F. 发布判定

只能输出其一：

```text
PUBLIC_READY=YES
```

条件：所有强制本地门禁通过，唯一剩余事项仅为用户身份、创建远端、首次 GitHub CI 确认和可选截图。

或：

```text
PUBLIC_READY=NO
```

并列出仍阻塞公开发布的具体命令、文件和失败证据。

## 18. 完成定义

只有满足以下全部条件，才可声明本轮完成：

- manifest 元素类型和重复项在所有集合运算前验证；
- loader、discovery、Streamlit 对畸形 manifest 均安全；
- dashboard 比例和计数符合明确语义范围；
- Ruff check/format check、全量测试、coverage 和 wheel 全部通过；
- 三个 Notebook 可执行且不含本机路径；
- CI workflow 已加入；
- 当前公开树用精简审计摘要替代原始 Agent prompt 堆叠；
- README 适合实习作品展示且保留真实失败边界；
- evidence 字节复现、strict 验证和 130 行保持不变；
- 历史未改写，两个 evidence commit 仍存在；
- DeepSeek 没有猜测用户身份、配置远端或 push；
- 最终报告给出真实的 `PUBLIC_READY` 判定。
