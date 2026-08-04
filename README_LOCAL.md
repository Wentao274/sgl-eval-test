# sgl-eval 本地 CI/CD 使用说明

本文件补足 [`README.md`](README.md) 中**未覆盖**的本地脚本编排、Jenkins 流水线
与远程执行约定。sgl-eval 上游 README 讲的是单机一条命令跑评测;本文件讲的是
**如何在 Jenkins 上参数化触发、远程 ssh 到 GPU 主机跑、把结果/mail 发回**。

设计参照 [`lm-evaluation-harness`](https://github.com/maas/lm-evaluation-harness)
仓库(其 `Jenkinsfile` / `lm_eval_test.sh` / `run_eval.py` 三件套),命名、目录
层级、邮件渲染逻辑保持一致,仅按 sgl-eval 的参数面和 metrics 结构做适配。

---

## 1. 文件清单

| 文件 | 角色 | 对应 lm-evaluation-harness |
|------|------|-----------------------------|
| `sgl_eval_main.sh` | shell 主入口,定义 `run_task` 函数 | `lm_eval_test.sh` |
| `run_sgleval.py` | Python 编排器,Jenkins → shell 的桥 | `run_eval.py` |
| `Jenkinsfile` | Jenkins 声明式流水线 | `Jenkinsfile` |

`sgl_eval_main.sh` 不会自己读 Jenkins 参数;它通过环境变量接收所有配置,
由 `run_sgleval.py` 统一注入——与上游 lm-evaluation-harness 完全相同的分层。

---

## 2. 目录与日志层级(对齐 lm-evaluation-harness)

```
<WORK_DIR>/output/<tester>/<build_number>/<chip>/<model>/<timestamp>/
├── sgl-eval-<tasks>.log                      # 全程 tee 出来的总日志(邮件附件)
└── sgl_eval_<name>_<stamp>/                  # sgl-eval 自己生成的运行目录
    ├── metrics.json                          # 得分 + 元信息(邮件解析该文件)
    └── output-rs*.jsonl                      # 每样本预测流(可选)
```

`<tester>` / `<build_number>` / `<chip>` / `<model>` / `<timestamp>` 五层
与 lm-evaluation-harness 完全一致,便于跨框架横向比对。`sgl_eval_<name>_<stamp>/`
是 sgl-eval 内部的目录约定(`pipeline/setup.py:48-50`),`metrics.json` 由
`metrics.py:dump_run` 写入,邮件 stage 通过 `readJSON` 直接读取,不再解析 stdout
表格——比 lm-evaluation-harness 的正则表格提取更稳健。

---

## 3. 三种使用方式

### 3.1 直接调 shell(本地 smoke)

```bash
# 默认 gsm8k / 50 题 / localhost:30000
bash sgl_eval_main.sh

# 通过环境变量覆盖
MODEL_NAME=glm-5.2 \
DATASETS=gsm8k \
LLM_ADDR=http://10.201.149.34:8000/v1 \
EXAMPLES=50 \
OUTPUT_BASE=./output/smoke \
bash sgl_eval_main.sh
```

### 3.2 通过 run_sgleval.py 编排(本地复现 Jenkins 行为)

```bash
python3 run_sgleval.py \
    --tester liwt \
    --build-number manual001 \
    --chip nvidia-h100 \
    --model glm-5.2 \
    --base-url http://10.201.149.34:8000/v1 \
    --tasks gsm8k,aime25 \
    --examples 50 \
    --temperature 0.6 \
    --max-tokens 8192 \
    --thinking true
```

`run_sgleval.py` 会:
1. 创建 `./output/liwt/manual001/nvidia-h100/glm-5.2/<timestamp>/`
2. 设置环境变量(`MODEL_NAME` / `DATASETS` / `LLM_ADDR` / `OUTPUT_BASE` / ...)
3. 调 `bash sgl_eval_main.sh`,透传退出码

### 3.3 通过 Jenkins 触发(生产路径)

打开 Jenkins job → Build with Parameters → 勾选任务、填端点 → 构建。
Jenkins 通过 ssh 远程到 `REMOTE_HOST`(默认 `10.201.132.50`)在 `WORK_DIR` 下
跑 `run_sgleval.py`,完成后 scp 拉回结果、归档、发邮件。

---

## 4. Jenkins 参数清单(对应需求 #7 的「更多 sgl-eval 参数」)

| Jenkins 参数 | 对应 sgl-eval flag | 默认                             | 说明 |
|--------------|---------------------|--------------------------------|------|
| `TESTER` | — | `liwt`                         | 测试人员(目录分层用) |
| `CHIP` | — | `nvidia-h100`                  | 芯片平台(目录分层用) |
| `ENGINE` / `PD` | — | `vllm` / `agg`                 | 仅邮件展示,不传 sgl-eval |
| `MODEL` | `--model` | `glm-5.2`                      | 模型服务名 |
| `BASE_URL` | `--base-url` | `http://10.201.149.34:8000/v1` | 端点 |
| `API_KEY` | `--api-key` | 空 → `EMPTY`                    | 鉴权 |
| `TASK_GSM8K` / `TASK_AIME24` / `TASK_AIME25` / `TASK_AIME26` / `TASK_MMLU` / `TASK_GPQA` / `TASK_MMMU_PRO` | 位置参数 `<name>` | 见各 checkbox                    | 7 个基准一个 boolean,勾选后逗号拼接传 `--tasks` |
| `EXAMPLES` | `--num-examples` | 空                              | 空 = 跑全集 |
| `N_REPEATS` | `--n-repeats` | 空                              | 空 = 用各基准的 registry 默认(gsm8k/mmlu=1,aime=16,gpqa=8);填值则按该值执行 |
| `NUM_THREADS` | `--num-threads` | `8`                            | 并发线程数 |
| `TEMPERATURE` | `--temperature` | `0.0`                          | reasoning 模型按需调到 0.6/1.0 |
| `TOP_P` | `--top-p` | `0.95`                         | nucleus |
| `MAX_TOKENS` | `--max-tokens` | `131072`                       | 清空 = 不指定(NS 默认 None) |
| `THINKING` | `--thinking` / `--no-thinking` | 空                              | 空 = 用各基准 registry 默认 |
| `TASK_MAX_TOKENS_JSON` | (shell 内 per-task 覆盖) | 空                              | 例 `{"aime25":32768,"gpqa":32768}` |
| `DESCRIPTION` / `RECIPIENTS` / `WORK_DIR` | — | —                              | 元信息/邮件收件人/远程目录 |

**为什么有 `TASK_MAX_TOKENS_JSON`:** sgl-eval 的 `--max-tokens` 是全局的,但
不同基准对最 long-tail 长度需求差异极大(AIME 要长 thinking、gsm8k 不需要)。
`sgl_eval_main.sh:_resolve_max_tokens` 在循环每个任务时按 JSON 覆盖,
比多次 Jenkins 构建省事。

### 4.1 各基准的 registry 默认值(来自 `_registry.py:_TABLE`)

| 基准 | 默认 n_repeats | 默认 thinking | 说明 |
|------|----------------|----------------|------|
| `gsm8k` | 1 | false | 小学数学,single-shot accuracy |
| `aime24/25/26` | 16 | true | 30 题,pass@16 + majority@16 |
| `mmlu` | 1 | false | 多学科多选,single-shot accuracy |
| `gpqa` | 8 | true | Diamond 子集,pass@8 + majority@8 |
| `mmmu_pro` | 1 | false | 多模态 10 选择(实验性) |

这些默认值不传任何 flag 时生效;Jenkins 任一对应参数填了非空值就覆盖默认。

---

## 5. sgl-eval 完整命令行参数参考(需求 #7)

来源:`sgl_eval/cli.py:cmd_run`(`sgl-eval run --help`)。下面列出当前流水线
**未在 Jenkins 暴露**但 sgl-eval 本身支持的参数,留作扩展:

| flag | 类型 | 说明 | 是否在 Jenkins 中暴露 |
|------|------|------|-----------------------|
| `--from-dataset <path>` | str | 用自定义 NS-shape jsonl 替换 vendored 数据集 | 否(实验性) |
| `--out-dir <path>` | str | run 目录父目录,默认 `~/.sgl_eval` | 否(由 `run_sgleval.py` 固定到 `OUTPUT_BASE`) |
| `--no-dump-predictions` | flag | 不写 `output-rs*.jsonl` | 否(默认要保留预测流) |
| `--preset <name>` | str | 加载 `~/.sgl_eval/presets/<name>.yaml` | 否(与显式参数冲突) |

其余子命令(`list` / `ping` / `refresh` / `preset`)未接入流水线,本地直接用即可。

---

## 6. 邮件通知

- **触发条件**:`发送邮件` stage 永远执行(`catchError` 包裹,失败不阻塞 build)
- **数据源**:`metrics.json`(由 `sgl_eval/metrics.py:dump_run` 写入),用
  `readJSON` 步骤直接解析,不靠正则提 stdout 表格。
- **每任务展示**:
  - headline 指标(`score` 或 `pass@1[avg-of-k]`)
  - 辅助指标(`pass@k` / `majority@k` / `no_answer` / `stop_rate` /
    `truncated_rate` / `error_rate`)
  - 部分运行时额外展示 `[score_lower_bound, score_upper_bound]`
  - latency / throughput / token 统计
- **连通性失败**:单独红色告警框,内嵌失败 curl 响应片段
- **附件**:`sgl-eval-<tasks>.log` + 连通性预检日志

---

## 7. 故障排查

| 现象 | 排查路径 |
|------|----------|
| ping 输出空 response | reasoning 模型默认 `--max-tokens 64` 太小,被 thinking 吃满;调到 1024+ |
| gsm8k 大量 `no_answer` | `truncated_rate` 高 → 同上,加大 `--max-tokens` |
| `aime25` 跑 16 repeats 太慢 | 临时把 `N_REPEATS=4`;或只跑 `--num-examples 5` smoke |
| reasoning 模型温度选不对 | DSv3.2/V4 用 `1.0`,R1 系用 `0.6`,通用 instruct 用 `0.0` |
| 远程 venv 缺包 | 删 `.venv` 重跑环境检查 stage,Jenkins 会自动 `uv pip install .` |
| 邮件 metrics 全 N/A | `find reports/<tester>/<build> -name metrics.json` 看是否拉到本地;若拉到但 N/A,检查 `aggregate` 字段名 |
