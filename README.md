# JEV-CachePlan

**面向批量语义决策的前缀缓存感知布局优化**

基于 JEV-9B 与 vLLM 的系统实现和性能验证。本项目把公开的前缀缓存感知行列重排方法接入批量推理流程，并在合成退款请求上测量布局对前缀缓存、耗时和结果恢复的影响。

[English](README_EN.md) · [系统架构](docs/architecture.md) · [部署](docs/deployment.md) · [实验复现](docs/benchmark.md) · [技术来源与许可](docs/third_party.md)

| 97% 核心配置 | 核心实测缓存比例 | 98.3% 拓展配置 |
| --- | --- | --- |
| **8.47×** 中位耗时加速 | **89.46%** 输入 Token 命中缓存 | **12.84×** 中位耗时加速 |

## JEV 与重复 Prefill

JEV-9B 对结构化记录和固定问题输出决策概率。模型卡描述了 Noul（二元判断）、Choice（选择）和 Score（评分）三种接口。本次正式性能实验只使用 **Noul**，判断客户请求是否要求货币退款。

批量请求反复输入相同的公司政策和服务背景。vLLM 通过匹配连续 Token 前缀复用已有 KV 缓存。如果唯一的 `record_id` 和不同的请求排在前面，后面的共享文本虽然相同，也难以形成可复用前缀。

## CachePlan 方法

**Original** 保留原字段序和原行序。**CachePlan** 将长且重复的字段提前，把共享前缀相似的记录排在一起，再用布局计划恢复原记录顺序。两组输入字段及取值、问题、模型和推理参数一致。模型权重与决策 LoRA 都来自固定版本。

![Original 和 CachePlan 的前缀组织对照示意图](assets/layout.svg)

*方法示意。完整的实测行列重排与字段统计见 [布局机制](docs/method.md)。*

## 系统架构

![JEV-CachePlan 处理流程，从结构化记录、LayoutPlan、vLLM 直到概率恢复和指标审计](assets/architecture.svg)

*系统示意，对应最终汇报第 6、8 页。项目实现了单卡服务部署、完整记录序列化和有界并发、候选单 Token 概率解析、按原位置与 ID 恢复，以及缓存与性能指标的交叉核验。图中不填入未经测量的概率。*

在一条实测合成记录中，请求节选为 “The item arrived broken. Please return the money I paid to my card.”。固定问题是 `Does the customer_request ask for a monetary refund?`。Original 返回 **True**，`P(True) = 0.998853`；CachePlan 同样返回 **True**，`P(True) = 0.999429`。模型实际接收完整记录，包括共享政策与服务背景。两种布局的概率对照和来源见 [实验复现](docs/benchmark.md#正确性与恢复)。

## 合成退款意图基准

每档 **128 条记录 × 10 个字段**，64 条退款、64 条换货，固定 `seed=42`。字段为 `record_id`、`customer_request`、`company_policy`、`service_context`、`profile_0` 至 `profile_5`。金额退款标签仅用于评估。

使用单张 NVIDIA L40、BF16、vLLM 0.31.0、16,384 Token 上下文、4 个在途请求，开启自动前缀缓存（APC）。每次扫描使用独立 `cache_salt`，方法执行顺序交错。三档共 **14 次完整扫描、1,792 次正式决策**。80%、97%、98.3% 表示可复用字段值 Token 占比，实际缓存命中通过 vLLM 响应测量。

| 可复用字段值 Token 占比 | 最大完整 Prompt | 每方法扫描 | Original 中位耗时 | CachePlan 中位耗时 | 中位耗时之比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 80% | 1,401 | 2 | 71.170 s | 34.510 s | 2.06× |
| 97%（核心） | 8,881 | 3 | 415.072 s | 48.999 s | **8.47×** |
| 98.3%（拓展） | 15,611 | 2 | 740.008 s | 57.648 s | **12.84×** |

## 实测结果与正确性

![97% 核心配置下 Original 和 CachePlan 的三轮平均耗时与吞吐](assets/core_timing_throughput.png)

- **核心耗时与吞吐。** 三轮平均耗时从 **415.265 s** 降至 **48.990 s**，平均总耗时降低约 **88.2%**；平均吞吐从约 **0.308** 升至 **2.613 条/秒**。上表的 **8.47×** 使用两组中位耗时。
- **实际缓存。** 两种布局每扫描均输入 **1,136,750 Token**。Original 命中 0，CachePlan 命中 **1,016,928 Token（89.46%）**。逐响应 `usage` 和服务端 `/metrics` 差值逐轮一致。 [缓存图](assets/cache.png)
- **逐请求延迟。** 核心配置每方法 384 条，平均客户端延迟从 **12.848 s** 降至 **1.519 s**。 [延迟分布](assets/latency.png) · [三轮复测](assets/repeat_timing.png)
- **结果恢复。** 14 次扫描均通过 ID、概率及标签恢复校验。七组配对的恢复后预测完全一致，合成标签准确率均为 **100%**。概率可随字段顺序变化。性能和准确率结论限于该合成负载。

[三档结果图](assets/speedup.png) · [14 次扫描的原始公开指标](benchmarks/results/run_metrics.csv) · [配置、布局计划与审计](docs/benchmark.md)

## Quick Start

CPU 示例只做布局计算与恢复检查。安装脚本建立项目专属客户端环境。

```bash
bash scripts/install_cpu.sh
source .venv-cpu/bin/activate
python scripts/cpu_example.py
python scripts/decide.py --method cacheplan --plan-only
python scripts/decide.py --compare --plan-only
python scripts/benchmark.py analyze
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

已有本地 JEV-9B 模型并按 [部署说明](docs/deployment.md) 启动服务后，可运行真实 Noul 示例。

```bash
python scripts/decide.py --method cacheplan
python scripts/decide.py --compare
```

旧参数 `--method solo` 仍可用。已有 JSON 的 `method` 值和结果文件名保持兼容，CLI 的 `display_name` 显示 Original 或 CachePlan。

## 技术来源

JEV-CachePlan 的贡献是将固定模型、决策 LoRA 和公开的前缀缓存感知布局方法集成到可测量的批量决策系统，并提供公开确定性合成负载的运行入口、恢复校验和本机实测证据。算法、模型及推理服务的出处和许可见 [第三方依赖与技术来源](docs/third_party.md)。与 21 页课程汇报的对应关系见 [展示对齐记录](docs/PRESENTATION_ALIGNMENT.md)。
