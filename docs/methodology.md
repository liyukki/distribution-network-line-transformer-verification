# 方法论

## 潮流与单位约定

- 标幺值：电压以母线额定电压为基准导出 voltage_pu；常规工况目标 0.90–1.10 p.u.。
- 节点类型：外部电网为平衡（slack）节点提供电压参考；聚合负荷为 PQ 节点。
- 功率正方向：上级电网向负荷供电为正；光伏反送时净有功允许为负。
- 功率平衡检查：supply = ext_grid + sgen，demand_and_losses = load + line losses + trafo losses，误差阈值 1e-6 MW。
- 模型限制：平衡正序交流潮流，不描述三相不平衡现场系统。

## Pearson 相关系数

r = cov(x, y) / (σx · σy)，仅在共同有效时间点计算，最少样本 16，任一序列零方差时输出 NaN。注意 Pearson 本身对平移与尺度不敏感，无需先做 z-score。

## 公共趋势消除与一阶差分

公共电压分量取同一时刻全部配变的行中位数并从各列减去；一阶差分在插值之后计算：d_t = v_t − v_{t−1}。

## 滚动相关与事件匹配

滚动窗口内逐窗计算候选与群组中心差分的相关系数（min_periods = window/2），取中位数与 10% 分位数。事件定义为各序列自身绝对一阶差分超过自身 0.90 分位数的时刻，两事件集合用 Jaccard 相似度衡量。

## 加权评分与判定规则

score(t, f) = Σ w_i × feature_i(t, f)；相关系数先线性映射到 [0, 1]，权重对可用特征再归一化，覆盖率是门禁而非分数分量。当前台账分低于 current_score_threshold 且 margin = best − current 超过 margin_threshold 才输出自动推荐，置信度 = coverage × clip((margin − τ) / (1 − τ), 0, 1)。证据不足时输出 insufficient_data。

## 评价指标

Precision = TP/(TP+FP)，Recall = TP/(TP+FN)，F1 为调和平均，PR-AUC 为精度-召回曲线下面积；Top-1/Top-3 仅在真实错误样本上统计推荐命中。类别不平衡场景不以 Accuracy 为主指标。

## 数据划分与泄漏防护

按仿真场景、日期块和随机种子分组，60/20/20 划分训练/验证/测试；physical_feeder_id、is_mislinked 与错误注入种子禁止进入特征矩阵；群组中心计算始终排除候选自身；测试集不参与阈值、权重与超参数选择。
