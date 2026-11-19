# JEV-CachePlan 部署与环境

## 1. 两个环境，两个职责

| 环境 | 用途 | 测试过的关键版本 |
|---|---|---|
| `.venv-cpu` | 规划、HTTP客户端、数据生成、CPU测试 | Python3.12.3 / NumPy1.26.4 / Numba0.59.0 / Pandas2.1.4 / Requests2.31.0 |
| `.venv-gpu` | vLLM服务 | Python3.12.3 / vLLM0.31.0 / Torch2.13.0+cu130 / Transformers5.17.0 |

用 `bash scripts/install_cpu.sh` 建立客户端环境，用 `bash scripts/install_gpu.sh` 显式建立GPU环境。脚本遇到同名目录就退出，不覆盖已有环境。已有合法环境可直接复用：设置 `JEV_GPU_PYTHON` 指向其 `bin/python`。**不要把CPU固定版本与GPU冻结快照合并安装**，它们使用不同NumPy/Numba栈。`requirements/tested-*`是历史完整环境快照，`requirements/gpu.txt`是服务入口的关键依赖约束。

GPU依赖优先官方预编译wheel。CUDA13.0 wheel需匹配的NVIDIA驱动；本项目不安装/修改系统CUDA和驱动。如果这些固定版本没有适合本机的wheel，不要静默换成最新版或编译大型组件；先判断硬件/驱动兼容性。公开版的CPU客户端经过本次回归，GPU真实执行依据原工程历史结果，本次公开整理**没有再次加载模型**。

## 2. 固定上游与权重

```bash
python scripts/fetch_solo.py
export JEV_MODEL_DIR=/path/to/JEV-9B
export JEV_GPU_PYTHON="$PWD/.venv-gpu/bin/python"
python scripts/verify_model.py
```

SOLO安装为固定commit Git依赖，不把上游仓库嵌套提交。`fetch_solo.py`只为作者的`demo.py`与部署控制器显式获取同一个commit到忽略的`.cache/solo-source`；支持`SOLO_SOURCE_DIR`指定已有干净checkout，检查HEAD和工作区，不覆盖已有内容。

模型：`autotrust/JEV-9B`，revision `b63f651ce8ed64481d3f5e73ecdb05f740042f01`。目录至少包含模型分片、索引、config/tokenizer、calibration和`adapter_vllm/`。已有完整模型不应重新下载。若尚未取得模型，可在自己的GPU环境按官方模型卡使用固定revision显式下载；以下命令**会下载约18GB，仅在确有需要时执行**：

```bash
hf download autotrust/JEV-9B --revision b63f651ce8ed64481d3f5e73ecdb05f740042f01 --local-dir "$JEV_MODEL_DIR"
```

需要授权时自行在终端完成合法认证，不把凭据写进Git、配置或日志。`configs/model_files.json`提供原测量所用文件的大小/SHA256；`verify_model.py`只读校验，不下载、不改写。允许模型目录有额外官方文件，但清单文件必须一致。

## 3. 已知的限定兼容补丁

原环境的vLLM0.31.0使用作者提供的SM100 warmup导入守卫修复。只有遇到该已知兼容问题时，才在**专属GPU环境**运行：

```bash
"$JEV_GPU_PYTHON" scripts/patch_runtime.py
```

脚本调用固定SOLO `deploy/fix_vllm_warmup.py`，仅接受vLLM0.31.0与匹配源码签名，备份原文件、记录SHA；移动现有硬件guard，未更改Qwen推理算法。它会明确修改所选环境里的vLLM文件，不能在系统Python或其他人的环境运行。本次公开整理未执行补丁或安装命令。

## 4. 配置与服务

`configs/service.example.json`没有实际服务器UUID、账号、IP或绝对路径。环境变量覆盖：

| 变量 | 作用 |
|---|---|
| JEV_MODEL_DIR | 本地固定模型目录 |
| JEV_GPU_PYTHON | GPU环境解释器路径 |
| JEV_GPU | 用户选择的GPU索引或UUID |
| JEV_PORT | 本机端口，默认18765 |
| JEV_CONFIG | 自定义JSON配置路径 |
| JEV_MAX_MODEL_LEN | 完整上下文长度 |
| JEV_MEMORY_UTILIZATION | 显存利用率预算，必须重新结合资源判断 |
| SOLO_SOURCE_DIR | 已有固定SOLO源码目录 |
| JEV_CLIENT_PYTHON | shell启动/停止入口采用的CPU解释器 |

```bash
export JEV_GPU=0
export JEV_PORT=18765
bash scripts/start.sh
python scripts/service.py status
python scripts/decide.py --method cacheplan
bash scripts/stop.sh
```

启动前读取所选GPU当前可用显存，检查估计预算和余量；不因GPU利用率非零直接拒绝，也不停止其他任务。示例预算基于原单L40负载，**不是任意GPU通用最低需求**；`gpu_memory_utilization`不是显存硬上限，余量不是运行期预留。公开示例将启动余量设为5120MiB，原14轮实际使用4096MiB，差异保留在实验说明。

仅监听loopback，端口被占用时拒绝启动。服务进程由固定SOLO控制器维护，记录checkout/PID/PGID/start_ticks并在停服时核验所有权；不能用`pkill vllm`或停止其他人的服务。PID/日志/状态只写入被Git忽略的runtime。启动失败由原控制器清理自己的进程。

## 5. 实际推理协议

服务使用 `/v1/completions`、`jev-decision` LoRA、bare-v1模板，限制候选Token并返回logprobs，结合decision_head bias和每kind温度得到概率。不是调用官方模型卡中另一个示例服务的`/v1/decide`，也没有套用其默认1024截断规则。

```bash
# Noul：固定False/True
python scripts/decide.py --limit 1
# Choice：选项顺序即概率矩阵顺序
python scripts/decide.py --kind choice --options '["monetary refund","replacement","other"]' --question 'What does the customer request?'
# Score：固定0..5
python scripts/decide.py --kind score --question 'How strongly is a monetary refund requested, from 0 to 5?'
```

资料中的正式性能对照只跑了 Noul 退款意图。Choice、Score 命令演示通用接口。`--plan-only` 只计算布局。普通功能批次使用 2 个在途请求，正式 Shared Context 基准使用 4 个。兼容参数 `--method solo` 等同于 `--method cacheplan`；两种拼写都保留原有工件标识。
