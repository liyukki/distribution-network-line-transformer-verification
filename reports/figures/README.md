# 图表目录说明

本目录保存由流水线、Notebook 与实验生成的可复现图表。HTML 交互图不入 Git（见 .gitignore）；本 README 与指标摘要文件入 Git。

| 图表 | 来源 | 生成方式 |
|---|---|---|
| 01_network_sanity.html | notebooks/01_network_sanity.ipynb | Notebook 从头执行 |
| 02_baseline_analysis.html | notebooks/02_baseline_analysis.ipynb | Notebook 从头执行 |
| 03_robustness_analysis.html | notebooks/03_robustness_analysis.ipynb | Notebook 从头执行 |
| 看板图表 | app/ | Streamlit 运行时按需渲染 |

所有图表的数值均可通过 reports/metrics/ 与 runs/ 下的 manifest 追溯。
