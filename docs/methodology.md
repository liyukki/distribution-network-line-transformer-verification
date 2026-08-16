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

score(t, f) = Σ w_i × feature_i(t, f)；相关系数先线性映射到 [0, 1]，权重对可用特征再归一化，覆盖率是门禁而非分数分量。当前台账分低于 current_score_threshold 且 margin = best − current 超过 margin_threshold 才输出自动推荐。权重与阈值为预先固定的启发式参数，尚未经独立验证集标定；测试场景不参与任何选择。

三个层次需区分：candidate score（各候选馈线的相似度得分）、evidence gate（覆盖率与 available_feature_weight 的证据门槛，未过门槛输出 insufficient_data）、anomaly score（最终风险连续分）。

## 异常分数 anomaly_score

anomaly_score = coverage × min(1 − current_score, max(margin, 0))。该公式是对"当前归属不相似"与"替代归属有正向优势"两个条件的连续化；证据不足（decision = insufficient_data）的样本 anomaly_score 显式置 0.0，进入最低风险层。

## 评价指标

- Precision = TP/(TP+FP)，Recall = TP/(TP+FN)，F1 为调和平均；类别不平衡场景不以 Accuracy 为主指标。
- pr_auc：全样本主指标，用连续 anomaly_score 计算 AP；insufficient_data 样本以 0.0 参与——系统无法对真实错误评分时，整体运行效果应受到惩罚。
- pr_auc_scored：仅在 decision != insufficient_data 的子集上计算的诊断指标；子集为空或不含两类时输出 null，必须与 scored_coverage 同时解读，不得替代全样本 pr_auc。
- Top-1/Top-2 修正率：仅在真实错误样本上统计；候选进入排名须同时满足 enhanced_score 有限、available_feature_weight 有限且不低于证据门槛；每个设备对每个 k 单独计算有效候选数，有效候选少于 k 时该设备不可评价、不计入分子分母；同时报告 top{k}_evaluated_count 与 top{k}_evaluation_coverage。三馈线下 Top-3 不适用。排名同分时按 candidate_feeder_id 升序作确定性次序，不依赖 DataFrame 行顺序。
- 机会基线：三候选均匀随机排序下 Top-1/Top-2 期望约 1/3 与 2/3；默认场景 n=5 过小，不能作显著性结论。

## 数据划分与泄漏防护

按仿真场景、日期块和随机种子分组的 60/20/20 训练/验证/测试划分目前尚未接入生产链路（分组工具 grouped_scenario_split 已实现，列为后续工作）。physical_feeder_id、is_mislinked 与错误注入种子禁止进入特征矩阵；群组中心计算始终排除候选自身；测试集不参与阈值、权重与超参数选择。
