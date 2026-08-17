# 论文图表

本目录中的 PNG 图由 `scripts/generate_paper_figures.py` 从已提交的公开证据文件生成，不手工录入实验结果。

```text
.venv/Scripts/python.exe scripts/generate_paper_figures.py
```

图表来源包括 `reports/metrics/default_summary.json`、公开默认运行的混淆矩阵以及 `reports/metrics/robustness_aggregates.csv`。生成脚本只读取这些文件，不会修改证据包。
