# JEV-CachePlan 技术来源与许可证

本项目的MIT仅覆盖我们有权许可的代码/文档/自绘资产；不覆盖模型、依赖或作者算法的独立版权，不宣称算法原创。

| 内容 | 来源/许可 | 本发行版处理 |
|---|---|---|
| SOLO算法、Serializer、JevBackend、生成器、服务控制器 | 0814wdwd/solo_jev固定commit，MIT；Copyright 2026 Yingze Li and Dong Wang | 固定Git依赖；可选源码显式获取到忽略目录，不复制/改名；保留licenses/SOLO-MIT.txt |
| JEV-9B/决策LoRA | AutoTrust，模型卡声明Apache-2.0；固定revision | 不分发权重；固定版本链接与校验清单 |
| 两个小型测试元数据fixture | 同版本JEV calibration.json/decision_head.json，Apache-2.0 | 原文件未修改；只供无权重CPU解析测试，见下述来源 |
| vLLM | vllm-project/vllm，Apache-2.0 | GPU环境依赖，不内嵌源码；限定补丁调用SOLO作者原工具 |
| shared合成数据方法 | SOLO作者demo.py，MIT | 引用固定生成器/seed/数据SHA；只分发统计、测量和小型自建示例 |
| ContractNLI数据 | Stanford官方独立许可 | 不分发数据集，只含本项目代码和负结果边界摘要 |

测试fixture原始来源：

- https://huggingface.co/autotrust/JEV-9B/blob/b63f651ce8ed64481d3f5e73ecdb05f740042f01/calibration.json
- https://huggingface.co/autotrust/JEV-9B/blob/b63f651ce8ed64481d3f5e73ecdb05f740042f01/adapter_vllm/decision_head.json

Apache-2.0许可全文见licenses/Apache-2.0.txt；模型卡归属为AutoTrust AI。未将这些元数据改写为自有原创。其他安装依赖维持自身许可证，具体以各上游发行内容为准。

本地实测CSV、原测量自绘图和公开版系统代码与原论文/作者发布数值分开。论文：Yingze Li et al., *Prefix-Cache-Aware Data Reordering for LLM-Augmented Database Analytics*, ICML2026，https://proceedings.mlr.press/v306/li26gn.html 。本仓库不重发整篇论文PDF或作者原始图；自绘架构图仍清楚注明基础算法/组件来源。

汇报所引用的资料包括 [公开布局方法](https://proceedings.mlr.press/v306/li26gn.html)、[固定布局实现](https://github.com/0814wdwd/solo_jev/tree/c5bed0511f3c90a83774f1a01e37da6b0b60fa22)、[固定 JEV-9B 模型卡](https://huggingface.co/autotrust/JEV-9B/tree/b63f651ce8ed64481d3f5e73ecdb05f740042f01)和 [vLLM 自动前缀缓存说明](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/)。许可文件见 [SOLO MIT](../licenses/SOLO-MIT.txt) 与 [Apache-2.0](../licenses/Apache-2.0.txt)。
