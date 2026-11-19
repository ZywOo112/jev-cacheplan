# Shared Context 基准与复现

## 数据与任务

复跑SOLO固定源码中的`demo.shared(128, ratio, 42, count)`；三组ratio=0.80/0.97/0.983。每组128条×10字段，退款/换货各64条。生成器、原始字段序和原始记录序均为作者设置，不为制造加速另行打乱。

原字段：`record_id, customer_request, company_policy, service_context, profile_0…profile_5`；NDV=128、128、1、1、4、8、16、32、64、64。前两个唯一字段在前是作者负载的一部分，不代表所有生产数据都这样组织。长中性填充控制prefill负载。共享比例定义为**NDV小于行数的列中所有字段值Token / 全表所有字段值Token**，不含JSON键/模板，不等于实际cache比例。

`benchmarks/dataset_manifests.json`保留完整生成参数、NDV、字段Token范围、原canonical dataset SHA256、Tokenizer SHA和源文件SHA。canonical SHA采用作者Pandas records-JSON字节口径，与本机JSONL物理文件SHA不同。三组最大完整Prompt=1401/8881/15611，16384上下文包含完整输入和1个输出Token，不截断。

固定问题：`Does the customer_request ask for a monetary refund?`；Noul顺序[False, True]，label sidecar不输入模型。作者生成器和API不改写成我们的原创内容。

## 重跑

```bash
python scripts/fetch_solo.py
python scripts/verify_model.py
python scripts/benchmark.py prepare
bash scripts/start.sh
python scripts/benchmark.py run --stop-service
```

完整模型/tokenizer和GPU服务需按deployment.md提前准备；这些命令会进行**明确的新测量**，普通CPU测试不调用。`prepare`会核对生成数据与已有canonical SHA及固定Tokenizer一致；数据已存在时验证，不覆盖。新测量使用唯一`runs/shared_<uuid>`；各扫描另有子目录，不覆盖原结果。

核心97%每方法3次，顺序O/S、S/O、O/S；拓展80%、98.3%各2次，顺序O/S、S/O。每次128条、4并发，新增请求种子0，max_tokens1，固定模型和LoRA。

每扫描独立cache_salt，4次预热使用另一盐；开场做“新盐0→同盐正命中→另一新盐0”的真实隔离探针。warm-up 56次和probe 3次不计14扫描/1792正式决策。cache_salt隔离匹配，不会清空物理缓存容量或移除其他进程资源竞争。benchmark需独立本机服务端口，其他请求混入时计数一致性检查应失败。

## 结果与指标

`benchmarks/results/run_metrics.csv`为本机14轮全精度标量，附run_id、顺序、原performance/config哈希；配置和完整布局计划/explain在同目录JSON。其他数据有：原始响应核验摘要、共享资源异常观察、数据manifest。没有上传庞大的HTTP日志/重复长输入/模型权重/进程状态。

公开的`analysis_summary.json`保留原实测汇总；作者RTX4090公开数值不混入该表。`scripts/benchmark.py analyze`只读取已有CSV，不需要模型；新run可用`analyze --session runs/shared_<uuid>`。

- 核心8.47× = `415.0719844880514 / 48.99948832881637`；为中位耗时之比，不是平均配对加速。
- 拓展12.84× = `740.0075889801374 / 57.64764999237377`。
- 核心89.46% = `1016928 / 1136750 × 100%`；来自逐响应usage，Prometheus token计数逐轮一致。
- Records/s=128/整轮耗时；Input Tokens/s含命中Token，是逻辑吞吐，不是GPU实际计算Token或FLOPs。
- 时间包含真实规划、DataFrame归一化、完整序列化/校验、有界HTTP审计与结果恢复；不含服务启动、预热、explain、metrics等待、质量计算和落盘。

`layout_plans.json`附实际row_order/column_order和原explain；explain的adjacent_prefix_bytes是UTF-8结构诊断，不是cache Token指标。每轮自动核验完整内容、schema、唯一记录/请求ID、合法置换、二维概率和一维标签恢复。

## 与原测量的差异和限制

原14轮为共享单卡L40、BF16、vLLM0.31.0、16K、4并发、batch2048、APC、align、eager、GPU利用率预算0.4661；结果包含共享任务波动。一次最低空闲3924MiB，低于原4096MiB启动余量，相关不利观察未删除。公开示例提高启动余量到5120MiB；新测量应记录自己的实际环境，不能当作原14轮配置完全相同。

公开入口重构了路径、配置和telemetry模块；原核心算法、模型版本、问题和输入不变，但新代码计时开销/硬件条件仍可能不同。本次发布只做CPU回归和历史证据验证，未重新验证GPU性能数字；历史与新测量结果必须分开。

合成100% Accuracy仅代表简单退款/换货标签；128行、一个种子、有限重复和共享硬件不支持广泛性能保证。本项目没有APC-off、其他优化器或独立行/列因果消融，也没有复现论文Qwen2.5/LOTUS十万行全部主表。

历史ContractNLI原始合同顺序已有较好共享前缀，SOLO未改善；Original/SOLO平均时间比约0.3591×。负结果独立保留在边界摘要，不与shared正向结果混为同一个基准，不以此改写任何原实验数据。
