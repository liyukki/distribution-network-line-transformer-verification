# 公开默认合成证据包

本目录 `default_run/` 保存一份已通过 manifest SHA-256 校验的默认 30 天合成仿真运行产物，用于让全新 clone 无需访问本机 ignored `runs/` 即可独立验证并复现规范报告。

- 数据全部为项目生成的合成仿真数据，不含真实电网数据。
- 包大小约 4.6 MiB，共 14 个文件。
- run ID：`20260816T121851Z-fb16e1`
- 源 commit：`533b64a09570b80533e26724430089bc61c755da`
- Python：3.12.13
- 关键包：pandapower 3.5.4、pandas 2.3.3、numpy 2.4.6、pydantic 2.13.4、scikit-learn 1.9.0、pyarrow 24.0.0

`manifest.json` 是 SHA-256 完整性清单，不是数字签名。它能检测意外损坏或未同步更新清单的修改；若攻击者可同时改写产物与同目录清单，单靠 SHA-256 不能证明发布者身份或来源真实性。

将本包纳入 Git 的原因：让全新 clone 能独立执行：

```text
python -m ltverify report --run-dir reports/evidence/default_run --output <临时目录>/default_summary.json --manifest-output <临时目录>/default_manifest.json
```

并与 `reports/metrics/default_summary.json`、`reports/metrics/default_manifest.json` 逐字节比较。

注意：默认 30 天重新运行会产生新的 run ID、时间戳和 manifest commit，不保证与历史报告逐字节相同。公开证据复现是“验证历史权威 run”；重新运行仿真是“生成新的 run”，两者语义不同。
