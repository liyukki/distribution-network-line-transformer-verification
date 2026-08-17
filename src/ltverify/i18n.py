"""Pure display-layer localization for the Streamlit dashboard."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, cast

import pandas as pd

Locale = Literal["zh-CN", "en-US"]
DEFAULT_LOCALE: Locale = "zh-CN"
SUPPORTED_LOCALES: tuple[Locale, ...] = ("zh-CN", "en-US")

_ZH = {
    "language.zh-CN": "简体中文",
    "language.en-US": "English",
    "failed_case_count": "存在 {count} 个失败案例",
    "not_applicable": "不适用",
    "app.title": "线变关系智能校验看板",
    "app.language": "界面语言",
    "app.run_directory": "运行目录",
    "app.demo_mode": "演示评价模式",
    "app.demo_caption": "演示评价模式下才显示物理真值与真实标签。",
    "app.missing_run": (
        "请先运行 python -m ltverify run-all --config configs/default.yaml，"
        "然后在左侧填写运行目录。"
    ),
    "app.predicted_alerts": "预测告警数",
    "app.top1_rate": "Top-1 修正率",
    "app.automatic_coverage": "自动推荐覆盖率",
    "app.run_status": "运行状态",
    "app.run_identifier": "运行标识: {run_id}",
    "app.hash_verified": "清单 SHA-256 哈希一致性已校验（非数字签名）",
    "app.artifact_load_failed": "运行产物加载失败：{detail}",
    "app.artifact_load_failed_generic": (
        "运行产物加载失败。请运行 python -m ltverify run-all --config configs/default.yaml 后重试。"
    ),
    "nav.network": "网络拓扑",
    "nav.diagnosis": "配变诊断",
    "nav.similarity": "相似度矩阵",
    "nav.evaluation": "模型评估",
    "nav.robustness": "鲁棒性实验",
    "common.load_home_first": "请先在主页加载运行目录。",
    "network.title": "网络拓扑",
    "network.demo_caption": "演示评价模式：线条颜色按物理馈线着色；标记颜色为电压等级。",
    "network.normal_caption": "普通模式：线路为中性色，不展示物理馈线归属；标记颜色为电压等级。",
    "network.ledger_comparison": "台账与推荐对照",
    "network.physical_truth": "物理真值（仅演示评价模式）",
    "diagnosis.title": "配变诊断",
    "diagnosis.select_transformer": "选择配变",
    "diagnosis.decision": "判定",
    "diagnosis.reported_feeder": "台账馈线",
    "diagnosis.recommended_feeder": "推荐馈线",
    "diagnosis.confidence": "置信度",
    "diagnosis.coverage": "覆盖率",
    "diagnosis.data_quality": "数据质量标记: {quality}",
    "similarity.title": "相似度矩阵",
    "similarity.matrix_type": "矩阵类型",
    "similarity.mode.raw": "原始电压",
    "similarity.mode.residual": "去公共趋势残差",
    "similarity.mode.difference": "一阶差分",
    "similarity.caption": "矩阵按所选模式在共同有效时间点上计算 Pearson 相关系数。",
    "evaluation.title": "模型评估",
    "evaluation.legacy_warning": (
        "该运行目录由旧版本生成（指标口径不兼容），旧版 PR-AUC 不作为当前口径展示，"
        "PR 曲线不可用；请重新运行 python -m ltverify run-all 后再查看。"
    ),
    "evaluation.newer_warning": (
        "该运行目录使用未验证的 schema 版本 {version}；仅展示已验证的有限字段，"
        "不执行依赖 schema-v2 的派生计算。"
    ),
    "evaluation.invalid_schema": "运行目录清单版本非法: {version}，无法可靠展示。",
    "evaluation.caption": (
        "主指标为精确率/召回率/F1/PR-AUC（连续异常分数）与 Top-1/Top-2；"
        "可评分子集 PR-AUC 须与可评分覆盖率同时解读；三馈线场景下 Top-3 不适用，"
        "不使用准确率作为主结论。"
    ),
    "evaluation.pr_unsupported": "该运行目录不绘制 PR 曲线（旧版或未验证的 schema）。",
    "evaluation.pr_requires_truth": "PR 曲线需要真实标签，请开启左侧的演示评价模式。",
    "robustness.title": "鲁棒性实验",
    "robustness.aggregates_path": "实验聚合 CSV 路径（robustness_aggregates.csv）",
    "robustness.summary_path": "案例明细 CSV 路径（robustness_summary.csv，仅用于明细与失败原因）",
    "robustness.missing_products": (
        "未找到实验聚合产物，请先运行 python -m ltverify experiments --config "
        "configs/robustness.yaml"
    ),
    "robustness.load_failed": "鲁棒性产物加载失败：{detail}",
    "robustness.load_failed_generic": (
        "鲁棒性产物加载失败。请重新运行 python -m ltverify experiments --config "
        "configs/robustness.yaml 后重试。"
    ),
    "robustness.verification.strict_verified": "已完成严格源配置核验（名称、哈希与快照全部一致）。",
    "robustness.verification.artifact_hashes_verified": "产物哈希已验证，但未完成源配置严格核验。",
    "robustness.verification.legacy_unverified": "旧版实验产物未经当前哈希链验证。",
    "robustness.family": "实验族",
    "robustness.metric": "指标",
    "robustness.caption": (
        "PR-AUC 为主样本口径；可评分子集 PR-AUC 须与可评分覆盖率同时解读；空值显示为不适用。"
    ),
    "robustness.missing_metric": "{metric} 不适用：聚合产物缺少 {column} 列",
    "robustness.nonnumeric_metric": "{metric} 不适用：{column} 不是可用数值列",
    "robustness.empty_metric": "{metric} 不适用：{column} 全为空值",
    "robustness.aggregates": "聚合汇总",
    "robustness.case_details": "案例明细与失败原因",
    "robustness.failed_cases": "存在 {count} 个失败案例，详见明细表。",
    "plot.confusion.title": "混淆矩阵",
    "plot.confusion.predicted": "预测标签",
    "plot.confusion.actual": "真实标签",
    "plot.confusion.negative": "未误判",
    "plot.confusion.positive": "误判",
    "plot.count": "数量",
    "plot.voltage.title": "配变电压曲线（标幺值）",
    "plot.time": "时间",
    "plot.voltage": "电压 (p.u.)",
    "plot.candidate.title": "{transformer_id} 候选馈线评分",
    "plot.candidate.feeder": "候选馈线",
    "plot.candidate.score": "增强评分",
    "plot.similarity.title": "配变相似度矩阵",
    "plot.correlation": "相关系数",
    "plot.topology.title": "网络拓扑",
    "plot.voltage_level": "电压等级 (kV)",
    "plot.bus": "母线",
    "plot.pr.title": "PR 曲线",
    "plot.pr.legend": "PR 曲线",
    "plot.precision": "精确率",
    "plot.recall": "召回率",
    "plot.robustness.title": "{family} — {metric}（均值 ± 样本标准差）",
    "plot.aggregate_missing": "鲁棒性图缺少列: {missing}；请传入实验聚合产物 robustness_aggregates.csv（而非原始案例表 robustness_summary.csv）",
}

_EN = {
    "language.zh-CN": "简体中文",
    "language.en-US": "English",
    "failed_case_count": "{count} failed cases found",
    "not_applicable": "N/A",
    "app.title": "Line-transformer relationship verification dashboard",
    "app.language": "Interface language",
    "app.run_directory": "Run directory",
    "app.demo_mode": "Evaluation demo mode",
    "app.demo_caption": "Physical truth and actual labels are shown only in evaluation demo mode.",
    "app.missing_run": (
        "Run python -m ltverify run-all --config configs/default.yaml, then enter the run "
        "directory in the sidebar."
    ),
    "app.predicted_alerts": "Predicted alerts",
    "app.top1_rate": "Top-1 correction rate",
    "app.automatic_coverage": "Automatic recommendation coverage",
    "app.run_status": "Run status",
    "app.run_identifier": "Run identifier: {run_id}",
    "app.hash_verified": "Manifest SHA-256 hashes verified (not a digital signature)",
    "app.artifact_load_failed": "Artifact loading failed: {detail}",
    "app.artifact_load_failed_generic": (
        "Artifact loading failed. Run python -m ltverify run-all --config "
        "configs/default.yaml and try again."
    ),
    "nav.network": "Network topology",
    "nav.diagnosis": "Transformer diagnosis",
    "nav.similarity": "Similarity matrix",
    "nav.evaluation": "Model evaluation",
    "nav.robustness": "Robustness experiments",
    "common.load_home_first": "Load a run directory on the home page first.",
    "network.title": "Network topology",
    "network.demo_caption": "Evaluation demo mode: lines are colored by physical feeder and markers by voltage level.",
    "network.normal_caption": "Normal mode: neutral lines hide physical feeder ownership; markers show voltage level.",
    "network.ledger_comparison": "Ledger and recommendation comparison",
    "network.physical_truth": "Physical truth (evaluation demo mode only)",
    "diagnosis.title": "Transformer diagnosis",
    "diagnosis.select_transformer": "Select transformer",
    "diagnosis.decision": "Decision",
    "diagnosis.reported_feeder": "Reported feeder",
    "diagnosis.recommended_feeder": "Recommended feeder",
    "diagnosis.confidence": "Confidence",
    "diagnosis.coverage": "Coverage",
    "diagnosis.data_quality": "Data-quality flags: {quality}",
    "similarity.title": "Similarity matrix",
    "similarity.matrix_type": "Matrix type",
    "similarity.mode.raw": "Raw voltage",
    "similarity.mode.residual": "Common-trend residual",
    "similarity.mode.difference": "First difference",
    "similarity.caption": "Pearson correlations use common valid timestamps under the selected mode.",
    "evaluation.title": "Model evaluation",
    "evaluation.legacy_warning": (
        "This run uses an older incompatible metric schema. Legacy PR-AUC is hidden and the "
        "precision-recall curve is unavailable. Rerun python -m ltverify run-all."
    ),
    "evaluation.newer_warning": (
        "This run uses unverified schema version {version}. Only verified basic fields are shown; "
        "schema-v2 derived calculations are disabled."
    ),
    "evaluation.invalid_schema": "Invalid run-manifest schema version: {version}. Reliable display is unavailable.",
    "evaluation.caption": (
        "Headline metrics are precision, recall, F1, PR-AUC from the continuous anomaly score, "
        "Top-1, and Top-2. Scored-subset PR-AUC must be read with scored coverage. Top-3 is not "
        "applicable in a three-feeder scenario; accuracy is not used as a headline metric."
    ),
    "evaluation.pr_unsupported": "The precision-recall curve is unavailable for an old or unverified schema.",
    "evaluation.pr_requires_truth": "The precision-recall curve requires actual labels. Enable evaluation demo mode.",
    "robustness.title": "Robustness experiments",
    "robustness.aggregates_path": "Aggregate CSV path (robustness_aggregates.csv)",
    "robustness.summary_path": "Case-detail CSV path (robustness_summary.csv; details and failures only)",
    "robustness.missing_products": (
        "No aggregate experiment artifact was found. Run python -m ltverify experiments "
        "--config configs/robustness.yaml."
    ),
    "robustness.load_failed": "Robustness artifact loading failed: {detail}",
    "robustness.load_failed_generic": (
        "Robustness artifact loading failed. Rerun python -m ltverify experiments --config "
        "configs/robustness.yaml and try again."
    ),
    "robustness.verification.strict_verified": "Strict source-config verification passed (name, hash, and snapshot match).",
    "robustness.verification.artifact_hashes_verified": "Artifact hashes passed, but strict source-config verification was not completed.",
    "robustness.verification.legacy_unverified": "Legacy experiment artifacts are not verified by the current hash chain.",
    "robustness.family": "Experiment family",
    "robustness.metric": "Metric",
    "robustness.caption": (
        "PR-AUC uses all main samples. Scored-subset PR-AUC must be read with scored coverage; "
        "null values are shown as not applicable."
    ),
    "robustness.missing_metric": "{metric} is not applicable: aggregate artifact lacks column {column}",
    "robustness.nonnumeric_metric": "{metric} is not applicable: {column} is not a usable numeric column",
    "robustness.empty_metric": "{metric} is not applicable: {column} contains only null values",
    "robustness.aggregates": "Aggregate summary",
    "robustness.case_details": "Case details and failure reasons",
    "robustness.failed_cases": "{count} failed cases found; see the detail table.",
    "plot.confusion.title": "Confusion matrix",
    "plot.confusion.predicted": "Predicted label",
    "plot.confusion.actual": "True label",
    "plot.confusion.negative": "Negative",
    "plot.confusion.positive": "Positive",
    "plot.count": "Count",
    "plot.voltage.title": "Transformer voltage curves (p.u.)",
    "plot.time": "Time",
    "plot.voltage": "Voltage (p.u.)",
    "plot.candidate.title": "{transformer_id} candidate feeder scores",
    "plot.candidate.feeder": "Candidate feeder",
    "plot.candidate.score": "Enhanced score",
    "plot.similarity.title": "Transformer similarity matrix",
    "plot.correlation": "Correlation",
    "plot.topology.title": "Network topology",
    "plot.voltage_level": "Voltage level (kV)",
    "plot.bus": "Bus",
    "plot.pr.title": "PR curve",
    "plot.pr.legend": "PR curve",
    "plot.precision": "Precision",
    "plot.recall": "Recall",
    "plot.robustness.title": "{family} — {metric} (mean ± sample standard deviation)",
    "plot.aggregate_missing": "Robustness figure is missing columns: {missing}. Use robustness_aggregates.csv, not raw robustness_summary.csv.",
}

TRANSLATIONS: Mapping[Locale, Mapping[str, str]] = MappingProxyType(
    {
        "zh-CN": MappingProxyType(_ZH),
        "en-US": MappingProxyType(_EN),
    }
)

_METRIC_LABELS: Mapping[Locale, Mapping[str, str]] = {
    "zh-CN": {
        "precision": "精确率",
        "recall": "召回率",
        "f1": "F1",
        "pr_auc": "PR-AUC",
        "pr_auc_scored": "可评分子集 PR-AUC",
        "top1_correction_rate": "Top-1 修正率",
        "top2_correction_rate": "Top-2 修正率",
        "top3_correction_rate": "Top-3 修正率",
        "automatic_coverage": "自动推荐覆盖率",
        "scored_coverage": "可评分覆盖率",
        "insufficient_data_rate": "数据不足率",
        "n_total": "样本总数",
        "n_actual_errors": "实际错误数",
        "runtime_seconds": "运行时间（秒）",
        "convergence_rate": "收敛率",
        "violation_count": "违规数",
        "maximum_power_balance_error_mw": "最大功率平衡误差（MW）",
        "non_convergence_count": "不收敛数",
        "power_balance_count": "功率不平衡数",
        "voltage_out_of_bounds_count": "电压越限数",
        "transformer_overload_count": "配变过载数",
        "voltage_min_pu": "最低电压（p.u.）",
        "voltage_max_pu": "最高电压（p.u.）",
        "maximum_transformer_loading_percent": "最大配变负载率（%）",
    },
    "en-US": {
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1",
        "pr_auc": "PR-AUC",
        "pr_auc_scored": "Scored-subset PR-AUC",
        "top1_correction_rate": "Top-1 correction rate",
        "top2_correction_rate": "Top-2 correction rate",
        "top3_correction_rate": "Top-3 correction rate",
        "automatic_coverage": "Automatic recommendation coverage",
        "scored_coverage": "Scored coverage",
        "insufficient_data_rate": "Insufficient-data rate",
        "n_total": "Total samples",
        "n_actual_errors": "Actual errors",
        "runtime_seconds": "Runtime (seconds)",
        "convergence_rate": "Convergence rate",
        "violation_count": "Violation count",
        "maximum_power_balance_error_mw": "Maximum power-balance error (MW)",
        "non_convergence_count": "Non-convergence count",
        "power_balance_count": "Power-balance violation count",
        "voltage_out_of_bounds_count": "Voltage out-of-bounds count",
        "transformer_overload_count": "Transformer overload count",
        "voltage_min_pu": "Minimum voltage (p.u.)",
        "voltage_max_pu": "Maximum voltage (p.u.)",
        "maximum_transformer_loading_percent": "Maximum transformer loading (%)",
    },
}

_FAMILY_LABELS: Mapping[Locale, Mapping[str, str]] = {
    "zh-CN": {
        "ablation": "消融实验",
        "ledger_error_rate": "台账错误率",
        "missing_rate": "数据缺失率",
        "pv_scale": "光伏出力倍率",
        "time_shift_steps": "时间错位步数",
        "voltage_noise_std_pu": "电压噪声标准差（p.u.）",
    },
    "en-US": {
        "ablation": "Ablation",
        "ledger_error_rate": "Ledger error rate",
        "missing_rate": "Missing rate",
        "pv_scale": "PV scale",
        "time_shift_steps": "Time-shift steps",
        "voltage_noise_std_pu": "Voltage-noise standard deviation (p.u.)",
    },
}

_COLUMN_LABELS: Mapping[Locale, Mapping[str, str]] = {
    "zh-CN": {
        "transformer_id": "配变编号",
        "reported_feeder_id": "台账馈线",
        "recommended_feeder_id": "推荐馈线",
        "physical_feeder_id": "物理馈线",
        "transformer_capacity_kva": "配变容量（kVA）",
        "customer_type": "用户类型",
        "current_score": "当前馈线评分",
        "best_score": "最佳候选评分",
        "margin": "评分差距",
        "coverage": "数据覆盖率",
        "predicted_is_mislinked": "预测是否错挂",
        "confidence": "置信度",
        "decision": "判定",
        "anomaly_score": "异常分数",
        "family": "实验族",
        "value": "实验水平",
        "n_completed": "完成案例数",
        "failure_count": "失败案例数",
        "case_id": "案例编号",
        "seed": "随机种子",
        "status": "状态",
        "error_type": "错误类型",
        "error_message": "错误信息",
    },
    "en-US": {
        "transformer_id": "Transformer ID",
        "reported_feeder_id": "Reported feeder",
        "recommended_feeder_id": "Recommended feeder",
        "physical_feeder_id": "Physical feeder",
        "transformer_capacity_kva": "Transformer capacity (kVA)",
        "customer_type": "Customer type",
        "current_score": "Current-feeder score",
        "best_score": "Best-candidate score",
        "margin": "Score margin",
        "coverage": "Data coverage",
        "predicted_is_mislinked": "Predicted mislink",
        "confidence": "Confidence",
        "decision": "Decision",
        "anomaly_score": "Anomaly score",
        "family": "Experiment family",
        "value": "Experiment level",
        "n_completed": "Completed cases",
        "failure_count": "Failed cases",
        "case_id": "Case ID",
        "seed": "Random seed",
        "status": "Status",
        "error_type": "Error type",
        "error_message": "Error message",
    },
}

_VALUE_LABELS: Mapping[Locale, Mapping[str, Mapping[object, object]]] = {
    "zh-CN": {
        "decision": {
            "automatic_recommendation": "自动推荐",
            "insufficient_data": "数据不足",
            "no_change": "无需变更",
        },
        "status": {"completed": "已完成", "failed": "失败", "running": "运行中"},
        "verification_state": {
            "strict_verified": "严格验证通过",
            "artifact_hashes_verified": "产物哈希验证通过",
            "legacy_unverified": "旧版未验证",
        },
        "data_quality": {
            "ok": "正常",
            "noisy": "含噪声",
            "missing": "缺失",
            "interpolated": "已插值",
            "spike": "尖峰",
            "time_shifted": "时间错位",
        },
        "customer_type": {
            "residential": "居民",
            "commercial": "商业",
            "mixed": "混合",
            "industrial": "工业",
        },
        "boolean": {True: "是", False: "否"},
        "ablation": {
            "full": "完整方法",
            "without_difference": "移除差分特征",
            "without_events": "移除事件特征",
            "without_power": "移除功率特征",
            "without_residual": "移除残差特征",
            "without_rolling": "移除滚动特征",
        },
    },
    "en-US": {
        "decision": {
            "automatic_recommendation": "Automatic recommendation",
            "insufficient_data": "Insufficient data",
            "no_change": "No change",
        },
        "status": {"completed": "Completed", "failed": "Failed", "running": "Running"},
        "verification_state": {
            "strict_verified": "Strictly verified",
            "artifact_hashes_verified": "Artifact hashes verified",
            "legacy_unverified": "Legacy unverified",
        },
        "data_quality": {
            "ok": "OK",
            "noisy": "Noisy",
            "missing": "Missing",
            "interpolated": "Interpolated",
            "spike": "Spike",
            "time_shifted": "Time shifted",
        },
        "customer_type": {
            "residential": "Residential",
            "commercial": "Commercial",
            "mixed": "Mixed",
            "industrial": "Industrial",
        },
        "boolean": {True: "Yes", False: "No"},
        "ablation": {
            "full": "Full method",
            "without_difference": "Without difference features",
            "without_events": "Without event features",
            "without_power": "Without power features",
            "without_residual": "Without residual features",
            "without_rolling": "Without rolling features",
        },
    },
}

_COLUMN_DOMAINS = {
    "decision": "decision",
    "status": "status",
    "data_quality_flag": "data_quality",
    "customer_type": "customer_type",
    "predicted_is_mislinked": "boolean",
}


def normalize_locale(value: object) -> Locale:
    """Return a supported locale, falling back to Simplified Chinese."""
    if value in SUPPORTED_LOCALES:
        return cast(Locale, value)
    return DEFAULT_LOCALE


def translate(locale: Locale | str, key: str, **values: object) -> str:
    """Translate one required UI key and format its named values."""
    normalized = normalize_locale(locale)
    return TRANSLATIONS[normalized][key].format(**values)


def translate_value(locale: Locale | str, domain: str, value: object) -> object:
    """Translate one known categorical value without changing unknown evidence."""
    normalized = normalize_locale(locale)
    if domain == "data_quality" and isinstance(value, str) and "|" in value:
        separator = "｜" if normalized == "zh-CN" else " | "
        return separator.join(
            str(translate_value(normalized, domain, part)) for part in value.split("|")
        )
    return _VALUE_LABELS[normalized].get(domain, {}).get(value, value)


def metric_label(locale: Locale | str, metric: str) -> str:
    """Return a localized metric label or preserve an unknown metric key."""
    normalized = normalize_locale(locale)
    return _METRIC_LABELS[normalized].get(metric, metric)


def family_label(locale: Locale | str, family: str) -> str:
    """Return a localized experiment-family label."""
    normalized = normalize_locale(locale)
    return _FAMILY_LABELS[normalized].get(family, family)


def column_label(locale: Locale | str, column: str) -> str:
    """Return a localized direct, metric, mean, or standard-deviation column label."""
    normalized = normalize_locale(locale)
    direct = _COLUMN_LABELS[normalized].get(column)
    if direct is not None:
        return direct
    if column.startswith("mean_"):
        label = metric_label(normalized, column.removeprefix("mean_"))
        return f"{label} 均值" if normalized == "zh-CN" else f"{label} mean"
    if column.startswith("std_"):
        label = metric_label(normalized, column.removeprefix("std_"))
        return (
            f"{label} 样本标准差" if normalized == "zh-CN" else f"{label} sample standard deviation"
        )
    metric = metric_label(normalized, column)
    return metric if metric != column else column


def localize_frame(frame: pd.DataFrame, locale: Locale | str) -> pd.DataFrame:
    """Return a localized display copy while leaving canonical input untouched."""
    normalized = normalize_locale(locale)
    localized = frame.copy(deep=True)
    original_families = localized["family"].copy() if "family" in localized.columns else None
    for column, domain in _COLUMN_DOMAINS.items():
        if column in localized.columns:
            localized[column] = localized[column].map(
                lambda value, value_domain=domain: translate_value(normalized, value_domain, value)
            )
    if original_families is not None:
        if "value" in localized.columns:
            for index, family in original_families.items():
                if family == "ablation":
                    localized.at[index, "value"] = translate_value(
                        normalized,
                        "ablation",
                        localized.at[index, "value"],
                    )
        localized["family"] = original_families.map(
            lambda value: family_label(normalized, str(value))
        )
    localized = localized.rename(
        columns={column: column_label(normalized, str(column)) for column in localized.columns}
    )
    return localized
