# Line-Transformer Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可复现的配电网线变关系校验项目，从平衡交流时序潮流生成量测和错误台账，完成可解释的异常检测、正确馈线推荐、鲁棒性实验与中文可视化看板。

**Architecture:** 采用配置驱动的 Python 包。网络、时序曲线、潮流、扰动、预处理、候选特征、评分和评价通过稳定的数据表契约串联，物理真值只允许进入评价模块。默认使用自建三馈线 pandapower 网络；生成产物供命令行、实验报告和 Streamlit 看板共同读取。

**Tech Stack:** Python 3.11、pandapower、NumPy、pandas、scikit-learn、PyArrow、Pydantic、PyYAML、Plotly、Streamlit、pytest、ruff、Jupyter。

## Global Constraints

- 默认环境为 Windows PowerShell，所有路径使用 `pathlib.Path`，代码不得依赖当前盘符。
- Python 版本固定为 `>=3.11,<3.13`；应用依赖使用有上下界的版本范围，安装后的精确版本写入运行清单。
- 默认网络固定为1个110 kV外部电网、1台110/10 kV主变、3条10 kV馈线、每条8台10/0.4 kV配变。
- 默认时序固定为30天、15分钟分辨率、2880个时刻、随机种子42。
- 仿真输入使用kV、MW、Mvar、km和ohm/km；电压输出使用标幺值；功率正方向为上级电网向下游供电。
- 第一版使用平衡正序交流潮流；不得把结果描述成三相不平衡现场模型。
- `physical_feeder_id`、`is_mislinked`和错误注入种子不得出现在模型特征表。
- 测试集不得用于阈值、权重或超参数选择；按场景、日期块和种子分组切分。
- 第一版不使用GNN、DTW、深度学习、实时数据库或真实电网敏感数据。
- 不写未经实验验证的准确率；简历数字必须能由固定命令复现。
- 生成的大型Parquet、模型和运行目录不提交Git；提交小型fixture、配置、指标摘要和图表。
- 所有新增功能遵循测试驱动开发；每个任务完成后运行目标测试与全量快速测试，再提交。

---

## File Map

| 路径 | 单一职责 |
|---|---|
| `pyproject.toml` | 包元数据、依赖、pytest与ruff配置 |
| `requirements.txt` | 用户一键安装入口，与pyproject应用依赖保持一致 |
| `configs/default.yaml` | 默认网络、时序、扰动、算法和输出配置 |
| `configs/robustness.yaml` | 鲁棒性实验参数网格 |
| `src/ltverify/config.py` | 配置模型与YAML加载 |
| `src/ltverify/contracts.py` | 数据表字段、契约校验与领域异常 |
| `src/ltverify/network.py` | 网络构造、设备映射和拓扑导出 |
| `src/ltverify/profiles.py` | 确定性负荷与光伏曲线生成 |
| `src/ltverify/validation.py` | 潮流收敛、电压与功率平衡检查 |
| `src/ltverify/simulation.py` | 时序潮流与干净量测导出 |
| `src/ltverify/corruption.py` | 错误台账与量测扰动生成 |
| `src/ltverify/preprocessing.py` | 对齐、插值、覆盖度和公共趋势消除 |
| `src/ltverify/features.py` | 配变—候选馈线特征构造 |
| `src/ltverify/scoring.py` | 加权评分、异常判定与馈线推荐 |
| `src/ltverify/evaluation.py` | 真值合并、检测和推荐指标 |
| `src/ltverify/experiments.py` | 实验矩阵生成、运行与汇总 |
| `src/ltverify/io.py` | Parquet、CSV、JSON原子化读写 |
| `src/ltverify/manifest.py` | 运行环境、输入输出和配置哈希记录 |
| `src/ltverify/pipeline.py` | 阶段编排及产物目录管理 |
| `src/ltverify/plotting.py` | 可复用Plotly图表 |
| `src/ltverify/cli.py`、`__main__.py` | 命令行入口 |
| `app/data_access.py` | 看板产物加载与用户提示 |
| `app/streamlit_app.py`、`app/pages/*.py` | 中文多页看板 |
| `tests/unit/*.py` | 纯函数和数据契约测试 |
| `tests/integration/*.py` | 小网络全流水线和CLI测试 |
| `notebooks/*.ipynb` | 网络、基线和鲁棒性教学分析 |
| `docs/methodology.md` | 电气机理、公式和模型限制 |
| `docs/interview-guide.md` | 面试讲解、常见追问和诚实边界 |
| `scripts/*.ps1` | Windows一键运行入口 |

---

### Task 1: Bootstrap, Configuration, and Data Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `configs/default.yaml`
- Create: `src/ltverify/__init__.py`
- Create: `src/ltverify/config.py`
- Create: `src/ltverify/contracts.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_contracts.py`

**Interfaces:**
- Produces: `AppConfig`, `load_config(path: Path) -> AppConfig`, `DataContractError`, `validate_columns(frame, required, table_name) -> None`.
- Consumes: no project code.

- [x] **Step 1: Create packaging and dependency files**

Use this dependency contract in `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "distribution-network-line-transformer-verification"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  "numpy>=1.26,<3",
  "pandas>=2.2,<3",
  "pandapower>=3.0,<4",
  "scikit-learn>=1.5,<2",
  "pyarrow>=17,<30",
  "pydantic>=2.8,<3",
  "PyYAML>=6,<7",
  "plotly>=5.24,<7",
  "streamlit>=1.38,<2",
]

[project.optional-dependencies]
dev = ["pytest>=8,<10", "pytest-cov>=5,<8", "ruff>=0.6,<1", "jupyter>=1,<2"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py311"
```

Copy the nine application dependencies into `requirements.txt`, one per line. Ignore `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `data/raw/`, `data/interim/`, `data/processed/`, `runs/`, and `reports/figures/*.html` in `.gitignore`.

- [x] **Step 2: Create the environment and install the package**

Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: editable installation completes and `python -c "import ltverify"` exits with code 0.

- [x] **Step 3: Write failing configuration tests**

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from ltverify.config import load_config


def test_default_config_has_fixed_first_release_shape() -> None:
    cfg = load_config(Path("configs/default.yaml"))
    assert cfg.network.feeder_count == 3
    assert cfg.network.transformers_per_feeder == 8
    assert cfg.profiles.days == 30
    assert cfg.profiles.interval_minutes == 15
    assert cfg.random_seed == 42


def test_invalid_voltage_limits_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("validation:\n  voltage_min_pu: 1.1\n  voltage_max_pu: 0.9\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(path)
```

- [x] **Step 4: Run the configuration tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py -v`

Expected: FAIL because `ltverify.config` does not exist.

- [x] **Step 5: Implement typed configuration and default YAML**

Define these models in `config.py`:

```python
class NetworkConfig(BaseModel):
    feeder_count: int = Field(default=3, ge=2)
    transformers_per_feeder: int = Field(default=8, ge=3)
    hv_kv: float = 110.0
    mv_kv: float = 10.0
    lv_kv: float = 0.4


class ProfileConfig(BaseModel):
    start: datetime = datetime(2026, 1, 1)
    days: int = Field(default=30, ge=1)
    interval_minutes: int = Field(default=15, ge=1)
    power_factor: float = Field(default=0.95, gt=0.0, le=1.0)
    pv_scale: float = Field(default=1.0, ge=0.0, le=10.0)


class ValidationConfig(BaseModel):
    voltage_min_pu: float = 0.90
    voltage_max_pu: float = 1.10

    @model_validator(mode="after")
    def ordered_limits(self) -> "ValidationConfig":
        if self.voltage_min_pu >= self.voltage_max_pu:
            raise ValueError("voltage_min_pu must be lower than voltage_max_pu")
        return self


class CorruptionConfig(BaseModel):
    ledger_error_rate: float = Field(default=0.20, ge=0.0, le=1.0)
    voltage_noise_std_pu: float = Field(default=0.0005, ge=0.0)
    missing_rate: float = Field(default=0.01, ge=0.0, le=0.5)
    spike_rate: float = Field(default=0.001, ge=0.0, le=0.1)
    time_shift_steps: int = Field(default=0, ge=0, le=8)
    time_shift_device_rate: float = Field(default=0.10, ge=0.0, le=1.0)


class ScoringConfig(BaseModel):
    current_score_threshold: float = 0.70
    margin_threshold: float = 0.08
    minimum_coverage: float = 0.80


class AppConfig(BaseModel):
    random_seed: int = 42
    network: NetworkConfig = NetworkConfig()
    profiles: ProfileConfig = ProfileConfig()
    validation: ValidationConfig = ValidationConfig()
    corruption: CorruptionConfig = CorruptionConfig()
    scoring: ScoringConfig = ScoringConfig()
    output_root: Path = Path("runs")


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
```

Write every field explicitly in `configs/default.yaml`, using the values above.

- [x] **Step 6: Write and implement contract tests**

Test that missing columns raise an exact domain error:

```python
import pandas as pd
import pytest

from ltverify.contracts import DataContractError, validate_columns


def test_validate_columns_names_missing_fields() -> None:
    frame = pd.DataFrame({"timestamp": []})
    with pytest.raises(DataContractError, match="measurements missing columns: transformer_id"):
        validate_columns(frame, {"timestamp", "transformer_id"}, "measurements")
```

Implement `DataContractError(ValueError)` and `validate_columns`; keep required column sets `TRANSFORMER_MEASUREMENT_COLUMNS`, `FEEDER_MEASUREMENT_COLUMNS`, `LEDGER_COLUMNS`, and `TRUTH_COLUMNS` in this file.

- [x] **Step 7: Run quality checks and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/unit/test_contracts.py -v
.\.venv\Scripts\python.exe -m ruff check src tests
git add pyproject.toml requirements.txt .gitignore configs src tests
git commit -m "build: bootstrap configuration and data contracts"
```

Expected: all tests pass and ruff reports no errors.

---

### Task 2: Three-Feeder Network Builder and Topology Export

**Files:**
- Create: `src/ltverify/network.py`
- Test: `tests/unit/test_network.py`
- Create: `tests/fixtures/small_config.yaml`

**Interfaces:**
- Consumes: `NetworkConfig` from Task 1.
- Produces: `NetworkArtifacts`, `build_network(cfg: NetworkConfig) -> NetworkArtifacts`, `topology_frames(artifacts) -> tuple[pd.DataFrame, pd.DataFrame]`.

- [x] **Step 1: Write the network shape test**

```python
from ltverify.config import NetworkConfig
from ltverify.network import build_network


def test_default_network_contains_three_feeders_and_twenty_four_assets() -> None:
    artifacts = build_network(NetworkConfig())
    assert len(artifacts.asset_table) == 24
    assert artifacts.asset_table["physical_feeder_id"].nunique() == 3
    assert len(artifacts.net.load) == 24
    assert len(artifacts.net.trafo) == 25
    assert len(artifacts.feeder_head_lines) == 3
    assert artifacts.asset_table["transformer_id"].is_unique
```

- [x] **Step 2: Run the test and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_network.py -v`

Expected: FAIL because `ltverify.network` does not exist.

- [x] **Step 3: Implement the public artifact type**

```python
@dataclass(frozen=True)
class NetworkArtifacts:
    net: pandapowerNet
    asset_table: pd.DataFrame
    feeder_head_lines: dict[str, int]
    feeder_head_buses: dict[str, int]
```

`asset_table` must contain `transformer_id`, `physical_feeder_id`, `customer_type`, `transformer_capacity_kva`, `mv_bus`, `lv_bus`, `trafo_index`, `load_index`, and nullable `pv_index`.

- [x] **Step 4: Implement the deterministic network construction**

Use `pp.create_empty_network(f_hz=50.0)`, an external-grid bus at 110 kV, a main transformer created from parameters, and one 10 kV bus. For each feeder create one head bus and line, then eight serial 10 kV sections. At each section create a 0.4 kV bus, one 10/0.4 kV transformer and one load. Create a zero-output `sgen` for transformer positions 3 and 6 on each feeder.

Use these initial engineering values in named constants or config-backed helpers:

```python
LINE_R_OHM_PER_KM = 0.32
LINE_X_OHM_PER_KM = 0.35
LINE_C_NF_PER_KM = 10.0
LINE_MAX_I_KA = 0.25
FEEDER_HEAD_LENGTH_KM = 0.5
SECTION_LENGTH_KM = 0.8
DISTRIBUTION_TRAFO_SN_MVA = 0.4
DISTRIBUTION_TRAFO_VK_PERCENT = 4.0
DISTRIBUTION_TRAFO_VKR_PERCENT = 1.2
```

Assign customer types in the repeating order `residential`, `commercial`, `mixed`; name feeders `F01`–`F03` and transformers `T001`–`T024`.

- [x] **Step 5: Add topology export test and implementation**

Test:

```python
def test_topology_export_has_valid_endpoints() -> None:
    artifacts = build_network(NetworkConfig())
    nodes, edges = topology_frames(artifacts)
    assert {"node_id", "node_type", "voltage_kv"} <= set(nodes.columns)
    assert {"from_node", "to_node", "edge_type", "feeder_id"} <= set(edges.columns)
    assert set(edges["from_node"]) <= set(nodes["node_id"])
    assert set(edges["to_node"]) <= set(nodes["node_id"])
```

Implement topology rows from pandapower buses, lines and transformers. Use an empty string for the main-transformer `feeder_id`; do not infer feeder identity from row order.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_network.py -v
.\.venv\Scripts\python.exe -m ruff check src/ltverify/network.py tests/unit/test_network.py
git add src/ltverify/network.py tests/unit/test_network.py tests/fixtures/small_config.yaml
git commit -m "feat: build deterministic three-feeder network"
```

---

### Task 3: Static Power-Flow Validation

**Files:**
- Create: `src/ltverify/validation.py`
- Test: `tests/unit/test_validation.py`

**Interfaces:**
- Consumes: `NetworkArtifacts` and `ValidationConfig`.
- Produces: `PowerFlowValidation`, `run_static_validation(artifacts, cfg) -> PowerFlowValidation`.

- [x] **Step 1: Write failing physical-consistency tests**

```python
from ltverify.config import NetworkConfig, ValidationConfig
from ltverify.network import build_network
from ltverify.validation import run_static_validation


def test_static_case_converges_and_balances_power() -> None:
    artifacts = build_network(NetworkConfig())
    result = run_static_validation(artifacts, ValidationConfig())
    assert result.converged is True
    assert result.voltage_min_pu >= 0.90
    assert result.voltage_max_pu <= 1.10
    assert result.absolute_power_balance_error_mw < 1e-6
    assert result.violations == ()
```

- [x] **Step 2: Run the test and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_validation.py -v`

Expected: FAIL because the validation module is missing.

- [x] **Step 3: Implement validation with explicit power direction**

```python
@dataclass(frozen=True)
class PowerFlowValidation:
    converged: bool
    voltage_min_pu: float
    voltage_max_pu: float
    absolute_power_balance_error_mw: float
    violations: tuple[str, ...]
```

Call `pp.runpp(net, calculate_voltage_angles=False, init="auto")`. Compute:

```python
supply = net.res_ext_grid.p_mw.sum() + net.res_sgen.p_mw.sum()
demand_and_losses = (
    net.res_load.p_mw.sum()
    + net.res_line.pl_mw.sum()
    + net.res_trafo.pl_mw.sum()
)
balance_error = abs(float(supply - demand_and_losses))
```

Add violations for non-convergence, voltage below/above configured bounds, balance error at or above `1e-6`, and any transformer loading above 100%.

- [x] **Step 4: Add an intentional undervoltage test**

Multiply every load by 8, use a 0.95 p.u. lower bound, and assert that `violations` contains a message beginning with `voltage below` or `transformer overload`. This verifies that validation detects physical problems instead of merely returning numbers.

- [x] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_validation.py -v
git add src/ltverify/validation.py tests/unit/test_validation.py
git commit -m "feat: validate power-flow physical consistency"
```

---

### Task 4: Deterministic Load and Photovoltaic Profiles

**Files:**
- Create: `src/ltverify/profiles.py`
- Test: `tests/unit/test_profiles.py`

**Interfaces:**
- Consumes: `NetworkArtifacts`, `ProfileConfig`, integer random seed.
- Produces: `TimeSeriesProfiles`, `generate_profiles(artifacts, cfg, seed) -> TimeSeriesProfiles`.

- [x] **Step 1: Write failing shape, determinism, and physics tests**

```python
import numpy as np

from ltverify.config import NetworkConfig, ProfileConfig
from ltverify.network import build_network
from ltverify.profiles import generate_profiles


def test_profiles_are_deterministic_and_have_physical_shapes() -> None:
    artifacts = build_network(NetworkConfig())
    cfg = ProfileConfig(days=2, interval_minutes=15)
    first = generate_profiles(artifacts, cfg, seed=42)
    second = generate_profiles(artifacts, cfg, seed=42)
    assert first.load_p_mw.shape == (192, 24)
    assert first.load_p_mw.equals(second.load_p_mw)
    assert (first.load_p_mw >= 0).all().all()
    assert (first.load_q_mvar >= 0).all().all()
    assert (first.pv_p_mw >= 0).all().all()
    night = first.index.hour.isin([0, 1, 2, 3, 4])
    assert np.allclose(first.pv_p_mw.loc[night].to_numpy(), 0.0)
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_profiles.py -v`

- [x] **Step 3: Implement the profile container and time index**

```python
@dataclass(frozen=True)
class TimeSeriesProfiles:
    index: pd.DatetimeIndex
    load_p_mw: pd.DataFrame
    load_q_mvar: pd.DataFrame
    pv_p_mw: pd.DataFrame
```

Build the left-closed date range with `periods = days * 24 * 60 // interval_minutes`. DataFrame columns must be transformer IDs in asset-table order.

- [x] **Step 4: Implement customer, feeder, and transformer variation**

Use two normalized daily peaks for residential loads, a daytime plateau for commercial loads, and their mean for mixed loads. Multiply by a weekday/weekend factor, a feeder sinusoid with phase `2π * feeder_number / 3`, a transformer scale sampled once from `Uniform(0.8, 1.2)`, and clipped AR(1) noise with coefficient 0.85. Convert active power to reactive power with:

```python
q_mvar = p_mw * np.tan(np.arccos(cfg.power_factor))
```

Use a daylight sine curve from 06:00 to 18:00, a daily cloud factor from `Uniform(0.65, 1.0)`, and each PV asset's `0.12 MW * cfg.pv_scale` nameplate. Non-PV columns remain zero.

- [x] **Step 5: Add a seed-separation test**

Assert that seed 43 does not produce a DataFrame equal to seed 42 while retaining the same index and columns.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_profiles.py -v
git add src/ltverify/profiles.py tests/unit/test_profiles.py
git commit -m "feat: generate deterministic load and solar profiles"
```

---

### Task 5: Time-Series Simulation and Clean Measurements

**Files:**
- Create: `src/ltverify/simulation.py`
- Test: `tests/integration/test_simulation.py`

**Interfaces:**
- Consumes: `NetworkArtifacts`, `TimeSeriesProfiles`, `ValidationConfig`.
- Produces: `SimulationResult`, `simulate_time_series(artifacts, profiles, validation_cfg) -> SimulationResult`.

- [x] **Step 1: Write a four-step integration test**

```python
def test_short_simulation_emits_transformer_and_feeder_measurements() -> None:
    artifacts = build_network(NetworkConfig())
    profiles = generate_profiles(
        artifacts,
        ProfileConfig(days=1, interval_minutes=360),
        seed=42,
    )
    result = simulate_time_series(artifacts, profiles, ValidationConfig())
    assert len(result.transformer_measurements) == 4 * 24
    assert len(result.feeder_measurements) == 4 * 3
    assert result.failures.empty
    assert result.transformer_measurements["voltage_pu"].between(0.90, 1.10).all()
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_simulation.py -v`

- [x] **Step 3: Implement exact output contracts**

```python
@dataclass(frozen=True)
class SimulationResult:
    transformer_measurements: pd.DataFrame
    feeder_measurements: pd.DataFrame
    failures: pd.DataFrame
```

Transformer rows contain `timestamp`, `transformer_id`, `voltage_pu`, `p_mw`, `q_mvar`, and `data_quality_flag="clean"`. Feeder rows contain `timestamp`, `feeder_id`, `head_voltage_pu`, `p_mw`, and `q_mvar`. Failure rows contain `timestamp`, `error_type`, and `message`.

- [x] **Step 4: Implement the time-step update loop**

For each timestamp, assign each load's P/Q and each existing PV's active power, call `pp.runpp(net, init="results")`, then read:

- transformer voltage from the asset's `lv_bus` in `net.res_bus.vm_pu`;
- transformer P/Q from `net.res_trafo.p_hv_mw` and `q_hv_mvar` at `trafo_index`;
- feeder head voltage from `feeder_head_buses`;
- feeder P/Q from `net.res_line.p_from_mw` and `q_from_mvar` at `feeder_head_lines`.

On `LoadflowNotConverged`, append one failure row. The default pipeline must stop after simulation if failures are nonempty; the simulator itself returns collected failures for diagnosis.

- [x] **Step 5: Add reverse-power and repeatability assertions**

Create a high-PV four-step fixture by multiplying PV by 6 and reducing loads to 20%. Assert at least one transformer `p_mw < 0`. Run the normal fixture twice and assert exact DataFrame equality.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_simulation.py -v
git add src/ltverify/simulation.py tests/integration/test_simulation.py
git commit -m "feat: simulate clean transformer and feeder measurements"
```

---

### Task 6: Truth Isolation, Ledger Errors, and Measurement Disturbances

**Files:**
- Create: `src/ltverify/corruption.py`
- Test: `tests/unit/test_corruption.py`

**Interfaces:**
- Consumes: `NetworkArtifacts`, clean transformer measurements, `CorruptionConfig`, seed.
- Produces: `build_truth(artifacts)`, `corrupt_ledger(truth, rate, seed)`, `disturb_measurements(clean, cfg, seed)`.

- [x] **Step 1: Write failing ledger tests**

```python
def test_twenty_percent_ledger_corruption_changes_five_of_twenty_four() -> None:
    truth = build_truth(build_network(NetworkConfig()))
    ledger = corrupt_ledger(truth, rate=0.20, seed=42)
    merged = ledger.merge(truth, on="transformer_id", validate="one_to_one")
    changed = merged["reported_feeder_id"] != merged["physical_feeder_id"]
    assert changed.sum() == 5
    assert "physical_feeder_id" not in ledger.columns
    assert "is_mislinked" not in ledger.columns
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_corruption.py -v`

- [x] **Step 3: Implement truth and deterministic ledger corruption**

`build_truth` selects `transformer_id`, `physical_feeder_id`, `transformer_capacity_kva`, and `customer_type` from `asset_table`. `corrupt_ledger` samples `round(rate * n)` unique transformer IDs and assigns each a feeder sampled from all feeders except its physical feeder. Return only `transformer_id`, `reported_feeder_id`, `transformer_capacity_kva`, and `customer_type`.

- [x] **Step 4: Write failing disturbance tests**

```python
def test_disturbance_is_deterministic_and_preserves_schema(clean_measurements) -> None:
    cfg = CorruptionConfig(missing_rate=0.05, spike_rate=0.01)
    first = disturb_measurements(clean_measurements, cfg, seed=42)
    second = disturb_measurements(clean_measurements, cfg, seed=42)
    pd.testing.assert_frame_equal(first, second)
    assert set(TRANSFORMER_MEASUREMENT_COLUMNS) <= set(first.columns)
    assert first["voltage_pu"].isna().sum() > 0
    assert first["data_quality_flag"].str.contains("missing|spike|noisy").any()
```

- [x] **Step 5: Implement disturbances without changing clean input**

Copy the input deeply. Add normal voltage noise, sample exact row indices for missing values, and sample disjoint indices for spikes. When `time_shift_steps > 0`, select `round(time_shift_device_rate * device_count)` devices with a minimum of one and shift their value columns within each device group. Combine flags with `|` in the order `noisy`, `missing`, `spike`, `shifted`. Leave timestamps and IDs unchanged.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_corruption.py -v
git add src/ltverify/corruption.py tests/unit/test_corruption.py
git commit -m "feat: generate isolated truth and corrupted observations"
```

---

### Task 7: Measurement Preprocessing and Common-Mode Removal

**Files:**
- Create: `src/ltverify/preprocessing.py`
- Test: `tests/unit/test_preprocessing.py`

**Interfaces:**
- Consumes: observed long-form transformer measurements.
- Produces: `PreparedMeasurements`, `prepare_measurements(frame, interval_minutes, interpolation_limit, minimum_coverage)`.

- [x] **Step 1: Write failing interpolation and leakage tests**

```python
def test_preprocessing_interpolates_short_gap_and_retains_long_gap() -> None:
    frame = measurement_fixture_with_one_and_four_step_gaps()
    prepared = prepare_measurements(
        frame,
        interval_minutes=15,
        interpolation_limit=2,
        minimum_coverage=0.75,
    )
    assert prepared.voltage_wide.loc[SHORT_GAP_TIME, "T001"] == pytest.approx(1.0)
    assert pd.isna(prepared.voltage_wide.loc[LONG_GAP_MIDDLE, "T002"])
    assert np.nanmax(np.abs(prepared.residual_voltage_wide.median(axis=1))) < 1e-12
    assert "physical_feeder_id" not in prepared.long_form.columns
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_preprocessing.py -v`

- [x] **Step 3: Implement the prepared-data container**

```python
@dataclass(frozen=True)
class PreparedMeasurements:
    long_form: pd.DataFrame
    voltage_wide: pd.DataFrame
    residual_voltage_wide: pd.DataFrame
    voltage_diff_wide: pd.DataFrame
    p_wide: pd.DataFrame
    q_wide: pd.DataFrame
    coverage: pd.Series
```

- [x] **Step 4: Implement validation, alignment, interpolation, and residuals**

Reject duplicate `(timestamp, transformer_id)` pairs. Pivot P, Q and voltage to wide form, reindex to the complete date range, and run `interpolate(method="time", limit=interpolation_limit, limit_area="inside")`. Compute coverage before interpolation and exclude devices below `minimum_coverage` from automatic diagnosis. Compute common mode as the row median of voltage and subtract it from every column. Compute first differences after interpolation.

- [x] **Step 5: Add duplicate and low-coverage tests**

Assert duplicates raise `DataContractError("duplicate timestamp-transformer pairs")`. Assert a device below coverage remains in exported data but its coverage value is below threshold, enabling downstream refusal rather than silent deletion.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_preprocessing.py -v
git add src/ltverify/preprocessing.py tests/unit/test_preprocessing.py
git commit -m "feat: preprocess measurements and remove common voltage mode"
```

---

### Task 8: Candidate Feeder Feature Engineering

**Files:**
- Create: `src/ltverify/features.py`
- Test: `tests/unit/test_features.py`

**Interfaces:**
- Consumes: `PreparedMeasurements`, reported ledger, feeder measurements.
- Produces: `build_candidate_features(prepared, ledger, feeder_measurements, rolling_window, event_quantile) -> pd.DataFrame`.

- [x] **Step 1: Write a handcrafted candidate-ranking test**

Create 192 points where `T001` follows an F01 pattern, F01 peer transformers follow the same pattern with small noise, and F02 peers follow a phase-shifted pattern. Test:

```python
def test_candidate_features_favor_matching_feeder() -> None:
    prepared, ledger, feeder_measurements = candidate_feature_fixture()
    features = build_candidate_features(
        prepared,
        ledger,
        feeder_measurements,
        rolling_window=24,
        event_quantile=0.90,
    )
    t1 = features.query("transformer_id == 'T001'").set_index("candidate_feeder_id")
    assert t1.loc["F01", "diff_corr"] > t1.loc["F02", "diff_corr"]
    assert t1.loc["F01", "event_match"] > t1.loc["F02", "event_match"]
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_features.py -v`

- [x] **Step 3: Implement safe correlation and group-center helpers**

```python
def safe_corr(left: pd.Series, right: pd.Series, minimum_pairs: int = 16) -> float:
    paired = pd.concat([left, right], axis=1).dropna()
    if len(paired) < minimum_pairs or paired.iloc[:, 0].std() == 0 or paired.iloc[:, 1].std() == 0:
        return float("nan")
    return float(paired.iloc[:, 0].corr(paired.iloc[:, 1]))
```

For each candidate transformer and feeder, compute the peer center as the row median of ledger members, excluding the candidate itself. Require at least two peer devices; otherwise emit NaN features and `peer_count`.

- [x] **Step 4: Implement the exact feature schema**

Return one row per transformer–candidate feeder pair with:

```text
transformer_id, reported_feeder_id, candidate_feeder_id, peer_count,
raw_corr, residual_corr, diff_corr, rolling_corr_median,
rolling_corr_q10, event_match, active_power_corr, coverage
```

Rolling correlations use the configured sample window and `min_periods = rolling_window // 2`. Event match is Jaccard similarity between candidate and peer-center timestamps whose absolute first difference exceeds each series' own configured quantile. `active_power_corr` compares transformer active power to the matching legal feeder measurement; it must never aggregate using `physical_feeder_id`.

- [x] **Step 5: Add self-exclusion and no-truth tests**

Assert a one-device group yields `peer_count == 0` and NaN correlations. Assert the returned feature columns do not contain `physical_feeder_id`, `is_mislinked`, or `seed`.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_features.py -v
git add src/ltverify/features.py tests/unit/test_features.py
git commit -m "feat: engineer explainable feeder candidate features"
```

---

### Task 9: Baseline, Enhanced Scoring, and Feeder Recommendation

**Files:**
- Create: `src/ltverify/scoring.py`
- Test: `tests/unit/test_scoring.py`

**Interfaces:**
- Consumes: candidate feature table, ledger, `ScoringConfig`.
- Produces: `ScoreWeights`, `score_candidates(features, weights)`, `diagnose(scored, ledger, cfg)`.

- [x] **Step 1: Write failing weighted-score tests**

```python
def test_default_weights_sum_to_one() -> None:
    assert sum(asdict(ScoreWeights()).values()) == pytest.approx(1.0)


def test_diagnosis_flags_wrong_ledger_and_recommends_best_feeder() -> None:
    scored, ledger = scored_candidate_fixture()
    predictions = diagnose(
        scored,
        ledger,
        ScoringConfig(current_score_threshold=0.70, margin_threshold=0.08),
    )
    row = predictions.set_index("transformer_id").loc["T001"]
    assert bool(row["predicted_is_mislinked"]) is True
    assert row["recommended_feeder_id"] == "F02"
    assert row["decision"] == "automatic_recommendation"
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_scoring.py -v`

- [x] **Step 3: Implement baseline and default enhanced weights**

```python
@dataclass(frozen=True)
class ScoreWeights:
    raw_corr: float = 0.10
    residual_corr: float = 0.20
    diff_corr: float = 0.30
    rolling_corr_median: float = 0.15
    rolling_corr_q10: float = 0.10
    event_match: float = 0.10
    active_power_corr: float = 0.05
```

`baseline_score` equals `raw_corr`. `enhanced_score` is the weighted mean over available features after mapping correlations from `[-1, 1]` to `[0, 1]`; renormalize weights over nonmissing features. Coverage is a gate, not a score component.

- [x] **Step 4: Implement conservative diagnosis**

For each transformer, obtain current-ledger score and highest candidate score. Define `margin = best_score - current_score`. Return:

```text
transformer_id, reported_feeder_id, recommended_feeder_id,
current_score, best_score, margin, coverage,
predicted_is_mislinked, confidence, decision
```

Use `decision="insufficient_data"` below minimum coverage. Use `automatic_recommendation` only when current score is below threshold and margin exceeds threshold; otherwise use `no_change`. Confidence is `coverage * clip((margin - margin_threshold) / (1 - margin_threshold), 0, 1)`.

- [x] **Step 5: Add insufficient-data and stable-ledger tests**

Assert low coverage refuses automatic recommendation. Assert a transformer whose current feeder is already best remains `no_change` even when another candidate is close.

- [x] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_scoring.py -v
git add src/ltverify/scoring.py tests/unit/test_scoring.py
git commit -m "feat: score anomalies and recommend candidate feeders"
```

---

### Task 10: Leakage-Safe Evaluation and Scenario Splitting

**Files:**
- Create: `src/ltverify/evaluation.py`
- Test: `tests/unit/test_evaluation.py`

**Interfaces:**
- Consumes: predictions, truth topology, reported ledger, candidate scores.
- Produces: `EvaluationResult`, `evaluate_predictions(...)`, `grouped_scenario_split(...)`.

- [x] **Step 1: Write failing metric tests with known answers**

```python
def test_evaluation_computes_detection_and_correction_metrics() -> None:
    predictions, truth, ledger, candidate_scores = evaluation_fixture()
    result = evaluate_predictions(predictions, truth, ledger, candidate_scores)
    assert result.metrics["precision"] == pytest.approx(2 / 3)
    assert result.metrics["recall"] == pytest.approx(1.0)
    assert result.metrics["f1"] == pytest.approx(0.8)
    assert result.metrics["top1_correction_rate"] == pytest.approx(0.5)
    assert result.metrics["top3_correction_rate"] == pytest.approx(1.0)
    assert result.confusion_matrix.shape == (2, 2)
```

- [x] **Step 2: Run and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/unit/test_evaluation.py -v`

- [x] **Step 3: Implement evaluation with truth merge restricted to this module**

```python
@dataclass(frozen=True)
class EvaluationResult:
    metrics: dict[str, float | int]
    confusion_matrix: pd.DataFrame
    labeled_predictions: pd.DataFrame
```

Derive actual error from `reported_feeder_id != physical_feeder_id`. Use scikit-learn `precision_recall_fscore_support(..., average="binary", zero_division=0)`, `average_precision_score`, and `confusion_matrix(labels=[False, True])`. Compute Top-1 only on actual error rows; define it as recommended feeder equal to physical feeder. Compute Top-3 by sorting each transformer's candidate scores descending and checking whether the physical feeder is among the first three. Store sample counts, automatic-decision coverage and insufficient-data rate.

- [x] **Step 4: Implement grouped split and its isolation test**

`grouped_scenario_split(metadata, seed=42)` assigns whole `scenario_id` values to 60% train, 20% validation and 20% test using a deterministic shuffled group list. Assert the three scenario sets are pairwise disjoint and their union equals all scenarios.

- [x] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_evaluation.py -v
git add src/ltverify/evaluation.py tests/unit/test_evaluation.py
git commit -m "feat: evaluate detection and correction without leakage"
```

---

### Task 11: Artifact I/O, Manifests, and End-to-End Pipeline

**Files:**
- Create: `src/ltverify/io.py`
- Create: `src/ltverify/manifest.py`
- Create: `src/ltverify/pipeline.py`
- Create: `src/ltverify/cli.py`
- Create: `src/ltverify/__main__.py`
- Test: `tests/unit/test_io.py`
- Test: `tests/integration/test_pipeline.py`
- Test: `tests/integration/test_cli.py`

**Interfaces:**
- Consumes: all public functions from Tasks 1–10.
- Produces: atomic writers, `RunManifest`, `run_pipeline(config_path) -> Path`, and CLI subcommands.

- [x] **Step 1: Write atomic I/O tests**

Test that `write_parquet_atomic(frame, path)` creates the parent directory, round-trips all columns, and leaves no `.tmp` file. Test that an unsupported suffix raises `ValueError("unsupported table format")`.

- [x] **Step 2: Implement focused I/O helpers**

Provide `write_parquet_atomic`, `write_csv_atomic`, `write_json_atomic`, and matching readers. Write to a sibling temporary file, then replace the target with `Path.replace`. Encode JSON and CSV as UTF-8.

- [x] **Step 3: Write manifest tests and implement environment capture**

```python
def test_manifest_contains_reproduction_fields(tmp_path: Path) -> None:
    manifest = build_manifest(config_path=Path("configs/default.yaml"), run_dir=tmp_path)
    assert manifest.random_seed == 42
    assert len(manifest.config_sha256) == 64
    assert manifest.python_version.startswith("3.11")
    assert "pandapower" in manifest.package_versions
```

`RunManifest` stores run ID, UTC start/end timestamps, status, config hash, Git commit if available, Python version, relevant package versions, seed, input paths, output paths and failure summary.

Define the serialized type explicitly:

```python
class RunManifest(BaseModel):
    run_id: str
    started_at_utc: datetime
    finished_at_utc: datetime | None = None
    status: Literal["running", "completed", "failed"]
    config_sha256: str
    git_commit: str | None
    python_version: str
    package_versions: dict[str, str]
    random_seed: int
    input_paths: list[str]
    output_paths: list[str]
    failure_summary: dict[str, str] | None = None
```

- [x] **Step 4: Write the short end-to-end pipeline test**

Use `tests/fixtures/small_config.yaml` with 3 feeders, 3 transformers per feeder, 1 day and 6-hour intervals. Assert the run directory contains:

```text
config.snapshot.yaml
manifest.json
truth_topology.csv
reported_ledger.csv
transformer_measurements.parquet
feeder_measurements.parquet
observed_measurements.parquet
candidate_features.parquet
predictions.parquet
metrics.json
confusion_matrix.csv
network_nodes.csv
network_edges.csv
```

- [x] **Step 5: Implement `run_pipeline` stage order and failure semantics**

The exact order is load config, create run directory, snapshot config, build network, validate static case, generate profiles, simulate, stop on failures, export truth and ledger, disturb observations, preprocess, build features, score, diagnose, evaluate, write artifacts, complete manifest. Wrap execution so manifest status becomes `failed` with the exception type and message before re-raising.

- [x] **Step 6: Implement CLI and test help/run-all**

Use `argparse` with subcommands `simulate`, `corrupt`, `diagnose`, `evaluate`, and `run-all`. The initial public workflow must fully support `run-all`; other commands must validate prerequisite artifacts and print the missing file path. `python -m ltverify --help` exits 0; `python -m ltverify run-all --config tests/fixtures/small_config.yaml` prints the absolute run directory.

- [x] **Step 7: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_io.py tests/integration/test_pipeline.py tests/integration/test_cli.py -v
git add src/ltverify/io.py src/ltverify/manifest.py src/ltverify/pipeline.py src/ltverify/cli.py src/ltverify/__main__.py tests
git commit -m "feat: add reproducible end-to-end pipeline"
```

---

### Task 12: Robustness Experiment Matrix and Ablations

**Files:**
- Create: `configs/robustness.yaml`
- Create: `src/ltverify/experiments.py`
- Modify: `src/ltverify/cli.py`
- Test: `tests/unit/test_experiments.py`
- Test: `tests/integration/test_experiment_smoke.py`

**Interfaces:**
- Consumes: base configuration and `run_pipeline`-compatible stage functions.
- Produces: `ExperimentCase`, `expand_experiment_grid(path)`, `run_experiments(path, output_dir)` and aggregate metrics.

- [ ] **Step 1: Write the exact experiment configuration**

```yaml
base_config: configs/default.yaml
experiments:
  ledger_error_rate: [0.05, 0.10, 0.20, 0.30]
  voltage_noise_std_pu: [0.0, 0.0005, 0.001, 0.002]
  missing_rate: [0.0, 0.01, 0.05, 0.10]
  time_shift_steps: [0, 1, 2, 4]
  pv_scale: [0.0, 1.0, 2.0, 4.0]
ablation_features:
  - full
  - without_residual
  - without_difference
  - without_rolling
  - without_events
  - without_power
seeds: [42, 43, 44, 45, 46]
```

Run one factor at a time around the default base case; do not form the full Cartesian product.

- [ ] **Step 2: Write failing grid-expansion tests**

Assert there are `4 * 5 * 5 + 6 * 5 = 130` cases: five one-factor experiment families with four levels across five seeds, plus six ablations across five seeds. Assert case IDs are unique and encode family, level and seed.

- [ ] **Step 3: Implement experiment case expansion**

```python
@dataclass(frozen=True)
class ExperimentCase:
    case_id: str
    family: str
    value: str
    seed: int
    config_overrides: dict[str, object]
    enabled_features: tuple[str, ...]
```

Map each family to an exact config path. Map ablations to immutable feature-name tuples matching `ScoreWeights` fields.

- [ ] **Step 4: Write and implement a two-case smoke runner**

The integration fixture selects two cases and a one-day profile. Assert `experiment_summary.csv` has two rows and contains `case_id`, `family`, `value`, `seed`, `precision`, `recall`, `f1`, `top1_correction_rate`, `top3_correction_rate`, `automatic_coverage`, `runtime_seconds`, and `status`.

- [ ] **Step 5: Add aggregate summaries**

Group successful runs by family/value and export mean, sample standard deviation and run count for every metric. Failed runs remain in the raw summary and are not silently removed; aggregate output includes `failure_count`. Cache clean simulation artifacts by `(seed, pv_scale)` so ledger, noise, missingness, time-shift and ablation cases reuse identical physical data instead of repeating the same 2880潮流 calculations.

- [ ] **Step 6: Add the experiment CLI command**

Extend `cli.py` with `python -m ltverify experiments --config configs/robustness.yaml`. The command calls `run_experiments`, prints the absolute experiment directory, and exits nonzero only when grid expansion fails or every case fails. Individual failed cases remain recorded in the summary.

- [ ] **Step 7: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_experiments.py tests/integration/test_experiment_smoke.py -v
git add configs/robustness.yaml src/ltverify/experiments.py src/ltverify/cli.py tests
git commit -m "feat: run robustness and ablation experiments"
```

---

### Task 13: Reusable Figures and Streamlit Dashboard

**Files:**
- Create: `src/ltverify/plotting.py`
- Create: `app/data_access.py`
- Create: `app/streamlit_app.py`
- Create: `app/pages/1_network.py`
- Create: `app/pages/2_diagnosis.py`
- Create: `app/pages/3_similarity.py`
- Create: `app/pages/4_evaluation.py`
- Create: `app/pages/5_robustness.py`
- Test: `tests/unit/test_plotting.py`
- Test: `tests/unit/test_app_data_access.py`
- Test: `tests/integration/test_streamlit_smoke.py`

**Interfaces:**
- Consumes: one completed run directory and optional experiment summary.
- Produces: Plotly `Figure` functions, `RunArtifacts`, and six Chinese dashboard pages.

- [ ] **Step 1: Write figure contract tests**

```python
def test_confusion_matrix_figure_has_chinese_axes() -> None:
    figure = confusion_matrix_figure(np.array([[8, 1], [2, 5]]))
    assert figure.layout.xaxis.title.text == "预测标签"
    assert figure.layout.yaxis.title.text == "真实标签"
    assert len(figure.data) == 1
```

Add equivalent tests for voltage curves, candidate score bars, similarity heatmap, topology, PR curve and robustness line chart. Each function receives DataFrames or arrays and returns a `go.Figure` without reading files.

- [ ] **Step 2: Implement plotting functions and run unit tests**

Use consistent feeder colors, p.u. axis labels, tooltips with transformer/feeder IDs, and titles that include the scenario or method. Never display `Accuracy` as the headline metric.

- [ ] **Step 3: Write artifact-loader tests**

Test `load_run_artifacts(run_dir)` against a fixture run. Missing `predictions.parquet` must raise `ArtifactLoadError` whose message includes the absolute path and the command `python -m ltverify run-all --config configs/default.yaml`.

Implement the loader contract as:

```python
class ArtifactLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    manifest: dict[str, object]
    truth: pd.DataFrame
    ledger: pd.DataFrame
    observed_measurements: pd.DataFrame
    feeder_measurements: pd.DataFrame
    candidate_features: pd.DataFrame
    predictions: pd.DataFrame
    metrics: dict[str, float | int]
    confusion_matrix: pd.DataFrame
    network_nodes: pd.DataFrame
    network_edges: pd.DataFrame
```

- [ ] **Step 4: Implement the overview and five pages**

- Overview: run metadata, topology size, actual demo error count, predicted alert count, F1, Top-1 and coverage.
- Network: schematic topology colored by reported or recommended feeder.
- Diagnosis: transformer selector, original/difference voltage, all candidate scores, confidence and data-quality warning.
- Similarity: selectable raw/residual/difference similarity matrix.
- Evaluation: confusion matrix, PR curve, method comparison and sample counts.
- Robustness: family selector with mean and standard-deviation bands.

Hide physical truth unless the sidebar `演示评价模式` toggle is active. Cache only file reads with `st.cache_data`; do not cache mutable pandapower networks.

- [ ] **Step 5: Add Streamlit smoke test**

Use `streamlit.testing.v1.AppTest.from_file("app/streamlit_app.py")`, set the fixture run directory through an environment variable `LTVERIFY_RUN_DIR`, run the app, and assert `len(app.exception) == 0` and the title contains `线变关系智能校验`.

- [ ] **Step 6: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_plotting.py tests/unit/test_app_data_access.py tests/integration/test_streamlit_smoke.py -v
git add src/ltverify/plotting.py app tests
git commit -m "feat: add explainable Streamlit verification dashboard"
```

---

### Task 14: Documentation, Notebooks, and Windows Run Scripts

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `data/README.md`
- Create: `docs/methodology.md`
- Create: `docs/interview-guide.md`
- Create: `notebooks/01_network_sanity.ipynb`
- Create: `notebooks/02_baseline_analysis.ipynb`
- Create: `notebooks/03_robustness_analysis.ipynb`
- Create: `scripts/run_pipeline.ps1`
- Create: `scripts/run_dashboard.ps1`
- Test: `tests/unit/test_documentation.py`

**Interfaces:**
- Consumes: stable commands and artifact schemas from Tasks 1–13.
- Produces: user-facing learning, reproduction and interview materials.

- [ ] **Step 1: Write documentation acceptance tests**

Test that README contains these exact headings: `业务背景`, `方法`, `快速开始`, `实验设计`, `结果`, `项目限制`, `仓库结构`, `面试展示`. Test that it does not match the regular expression `准确率.{0,8}90\.3%`. Test that all commands use `python -m ltverify` or `streamlit run` and referenced local paths exist.

- [ ] **Step 2: Write README and data dictionary**

README must lead with the problem and one architecture diagram, then show installation, the small smoke run, the default run, dashboard startup, artifact table, experiment protocol, verified results, limitations and citation/provenance. Before full experiments exist, the result section must say `尚未运行完整实验，以下仅展示可复现流程，不报告性能结论。`

`data/README.md` defines every field, unit, direction, privacy status, generation method and whether the field may enter model features.

Use the MIT License text with copyright line `Copyright (c) 2026 Project Contributors`; do not insert a personal name without user approval.

- [ ] **Step 3: Write methodology and interview guide**

`docs/methodology.md` includes Pearson formula, first difference, rolling correlation, event Jaccard, weighted score, threshold rule, precision/recall/F1/PR-AUC, p.u. convention, slack/PQ nodes, power direction, balance check and balanced-model limitation.

`docs/interview-guide.md` includes a three-minute demo script and answers to: why different feeders can still be correlated, why z-score is unnecessary before Pearson, how threshold leakage is avoided, why not use GNN, how synthetic data differs from field data, and how to extend to unbalanced networks.

- [ ] **Step 4: Create three executable notebooks**

Use the repository's installed package rather than copying algorithm code into notebook cells. Each notebook starts with the config and run directory, has no hidden state, uses a fixed seed, writes figures only under `reports/figures/`, and executes from top to bottom without error. The three notebooks cover network sanity, baseline-vs-enhanced analysis and robustness aggregation respectively.

- [ ] **Step 5: Create Windows scripts**

`run_pipeline.ps1` resolves the repository root from `$PSScriptRoot`, verifies `.venv\Scripts\python.exe`, and runs `python -m ltverify run-all --config configs/default.yaml`. `run_dashboard.ps1` accepts a mandatory `-RunDir`, resolves it to an absolute path, sets `LTVERIFY_RUN_DIR`, and launches Streamlit with a hidden background helper window only if a helper process is needed.

- [ ] **Step 6: Run notebook and documentation checks**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_documentation.py -v
.\.venv\Scripts\python.exe -m jupyter nbconvert --execute --to notebook --inplace notebooks/01_network_sanity.ipynb
.\.venv\Scripts\python.exe -m jupyter nbconvert --execute --to notebook --inplace notebooks/02_baseline_analysis.ipynb
.\.venv\Scripts\python.exe -m jupyter nbconvert --execute --to notebook --inplace notebooks/03_robustness_analysis.ipynb
git add README.md LICENSE data docs/methodology.md docs/interview-guide.md notebooks scripts tests/unit/test_documentation.py
git commit -m "docs: add reproducible usage and interview materials"
```

---

### Task 15: Full Verification, Default Run, and Release Evidence

**Files:**
- Modify: `README.md`
- Create: `reports/metrics/default_summary.json`
- Create: `reports/metrics/robustness_summary.csv`
- Create: `reports/figures/README.md`
- Test: all tests.

**Interfaces:**
- Consumes: complete application and experiment runner.
- Produces: verified release evidence and measured README statements.

- [ ] **Step 1: Run static quality and complete tests**

```powershell
.\.venv\Scripts\python.exe -m ruff check src app tests
.\.venv\Scripts\python.exe -m pytest --cov=ltverify --cov-report=term-missing
```

Expected: ruff exits 0; every test passes; coverage report has no untested core module among `network`, `validation`, `corruption`, `features`, `scoring`, and `evaluation`.

- [ ] **Step 2: Run the default 30-day pipeline**

```powershell
.\.venv\Scripts\python.exe -m ltverify run-all --config configs/default.yaml
```

Expected: command prints a run directory; its manifest status is `completed`; simulation failures are zero; voltage and power-balance checks pass; metrics and figures exist.

- [ ] **Step 3: Run the robustness matrix**

```powershell
.\.venv\Scripts\python.exe -m ltverify experiments --config configs/robustness.yaml
```

Expected: 130 raw case rows exist. Every failed case includes an error type and message. Aggregate tables include means, standard deviations, successful counts and failure counts.

- [ ] **Step 4: Audit scientific claims against artifacts**

Copy only measured values from completed manifests and metric files into README. Confirm the default clean-test F1 statement, any improvement-over-baseline statement, and Top-1 statement can each be traced to an exact run ID. If enhanced scoring loses to the baseline in a scenario, preserve that result and explain it.

- [ ] **Step 5: Verify a clean checkout workflow**

Create a fresh non-workspace temporary directory, clone the local repository into it, create a new virtual environment, install the package, run the small integration configuration, and start the Streamlit smoke test. Remove only that explicitly resolved temporary directory after verification.

- [ ] **Step 6: Commit release evidence**

```powershell
git add README.md reports/metrics reports/figures/README.md
git commit -m "chore: record verified first-release evidence"
git status --short
```

Expected: final status is clean. Do not tag or push without an explicit user request.

---

## Completion Checklist

- [ ] All 15 task commits exist in order and each task passed its target tests before commit.
- [ ] Default network, profiles and ledger corruption match the fixed first-release shape.
- [ ] Physical truth is isolated and automated leakage tests pass.
- [ ] Default 30-day run completes with recorded physical checks.
- [ ] Baseline, enhanced score, ablations and five robustness families have reproducible metrics.
- [ ] Dashboard loads a completed run and explains a single-transformer decision.
- [ ] README clearly separates observed results, research targets and limitations.
- [ ] No performance number appears in resume material without a run ID and metric artifact.
- [ ] Full pytest and ruff checks pass from a clean environment.
- [ ] Repository is clean; no large generated run directory is tracked.
