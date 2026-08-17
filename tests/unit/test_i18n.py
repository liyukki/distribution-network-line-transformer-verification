import pandas as pd
import pytest

from ltverify.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    TRANSLATIONS,
    column_label,
    family_label,
    localize_frame,
    metric_label,
    normalize_locale,
    translate,
    translate_value,
)


def test_catalogs_have_identical_nonempty_keys() -> None:
    assert DEFAULT_LOCALE == "zh-CN"
    assert SUPPORTED_LOCALES == ("zh-CN", "en-US")
    assert set(TRANSLATIONS["zh-CN"]) == set(TRANSLATIONS["en-US"])
    assert all(TRANSLATIONS[locale] for locale in SUPPORTED_LOCALES)
    assert all(
        isinstance(value, str) and value
        for locale in SUPPORTED_LOCALES
        for value in TRANSLATIONS[locale].values()
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("zh-CN", "zh-CN"),
        ("en-US", "en-US"),
        (None, "zh-CN"),
        ("fr-FR", "zh-CN"),
        (1, "zh-CN"),
    ],
)
def test_normalize_locale(raw: object, expected: str) -> None:
    assert normalize_locale(raw) == expected


def test_translate_formats_selected_catalog() -> None:
    assert translate("zh-CN", "failed_case_count", count=2) == "存在 2 个失败案例"
    assert translate("en-US", "failed_case_count", count=2) == "2 failed cases found"
    with pytest.raises(KeyError):
        translate("zh-CN", "missing.translation.key")


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("zh-CN", "自动推荐"), ("en-US", "Automatic recommendation")],
)
def test_translate_known_decision(locale: str, expected: str) -> None:
    assert translate_value(locale, "decision", "automatic_recommendation") == expected


@pytest.mark.parametrize(
    ("locale", "raw", "expected"),
    [
        ("zh-CN", "noisy|missing", "含噪声｜缺失"),
        ("en-US", "noisy|missing", "Noisy | Missing"),
    ],
)
def test_translate_composite_quality(locale: str, raw: str, expected: str) -> None:
    assert translate_value(locale, "data_quality", raw) == expected


def test_labels_cover_metrics_families_and_dynamic_columns() -> None:
    assert metric_label("zh-CN", "pr_auc_scored") == "可评分子集 PR-AUC"
    assert metric_label("en-US", "top1_correction_rate") == "Top-1 correction rate"
    assert family_label("zh-CN", "missing_rate") == "数据缺失率"
    assert family_label("en-US", "missing_rate") == "Missing-data rate"
    assert column_label("zh-CN", "transformer_id") == "配变编号"
    assert column_label("en-US", "mean_f1") == "F1 mean"
    assert column_label("zh-CN", "std_pr_auc") == "PR-AUC 样本标准差"


def test_unknown_identifier_is_preserved() -> None:
    assert translate_value("zh-CN", "decision", "future_value") == "future_value"
    assert column_label("zh-CN", "future_column") == "future_column"
    assert metric_label("zh-CN", "future_metric") == "future_metric"


def test_localize_frame_translates_copy_without_mutating_input() -> None:
    source = pd.DataFrame(
        {
            "transformer_id": ["T001"],
            "decision": ["automatic_recommendation"],
            "status": ["completed"],
            "pr_auc": [0.5],
        }
    )
    original = source.copy(deep=True)
    localized = localize_frame(source, "zh-CN")
    pd.testing.assert_frame_equal(source, original)
    assert localized.columns.tolist() == ["配变编号", "判定", "状态", "PR-AUC"]
    assert localized.iloc[0].tolist() == ["T001", "自动推荐", "已完成", 0.5]


def test_localize_frame_uses_family_to_translate_ablation_value() -> None:
    source = pd.DataFrame(
        {
            "family": ["ablation"],
            "value": ["without_events"],
            "mean_f1": [0.8],
        }
    )
    localized = localize_frame(source, "zh-CN")
    assert localized.columns.tolist() == ["实验族", "实验水平", "F1 均值"]
    assert localized.iloc[0].tolist() == ["消融实验", "移除事件特征", 0.8]


def test_localize_frame_translates_boolean_display_values() -> None:
    source = pd.DataFrame({"predicted_is_mislinked": [True, False]})
    chinese = localize_frame(source, "zh-CN")
    english = localize_frame(source, "en-US")
    assert chinese.iloc[:, 0].tolist() == ["是", "否"]
    assert english.iloc[:, 0].tolist() == ["Yes", "No"]
