#!/usr/bin/env python3
"""sgl-eval 测试编排脚本。

由 Jenkinsfile 远程调用,负责:
1. 解析 Jenkins 传入的参数
2. 创建结果目录(结构对齐 lm-evaluation-harness):
       output/<tester>/<build_number>/<chip>/<model>/<timestamp>/
3. 设置环境变量并通过 bash 调用 sgl_eval_main.sh
4. 透传退出码

与 lm-evaluation-harness/run_eval.py 的差异:
   - 本仓库编排脚本命名为 run_sgleval.py(避免与其他测试框架的 run_eval.py 混淆,
     Jenkinsfile 清理残留进程时按全字符串 run_sgleval.py 匹配,不会误杀其他框架)
   - 不传 --model-path(sgl-eval 只用 OpenAI 兼容接口,不需要 tokenizer)
   - 增加 --n-repeats / --max-tokens / --thinking 等 sgl-eval 专属参数
   - 多任务由 --tasks 逗号分隔,在一次 bash 调用里串行执行
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Run sgl-eval test via shell script")
    parser.add_argument("--tester", required=True, help="测试人员名称")
    parser.add_argument("--build-number", required=True, help="Jenkins 构建编号")
    parser.add_argument("--chip", required=True, help="芯片平台名称")
    parser.add_argument("--model", required=True, help="模型服务名称(对应 sgl-eval --model)")
    parser.add_argument(
        "--base-url", required=True, help="OpenAI 兼容端点 URL(如 http://10.201.149.34:8000/v1)"
    )
    parser.add_argument("--api-key", default="EMPTY", help="API Key(无需认证时留空)")
    parser.add_argument(
        "--tasks",
        default="gsm8k",
        help="任务列表,逗号分隔(默认 gsm8k)。可选: gsm8k,aime24,aime25,aime26,mmlu,gpqa,mmmu_pro",
    )
    parser.add_argument("--examples", default="", help="样本数限制(空 = 不限制)")
    parser.add_argument(
        "--n-repeats",
        default="",
        help="每题采样次数(空 = 用各基准的 registry 默认;填值则按该值执行)",
    )
    parser.add_argument("--num-threads", default="15", help="并发线程数(默认 15)")
    parser.add_argument("--top-p", default="0.95", help="nucleus top_p(默认 0.95)")
    parser.add_argument(
        "--task-temperature-json",
        default="",
        help='按任务覆盖 temperature 的 JSON,例: {"aime25":0.6,"gpqa":0.6};'
        "留空则用 sgl_eval_main.sh 内置默认(R1 推荐:"
        "gsm8k/mmlu/mmmu_pro=0.0, aime24/25/26/gpqa=0.6)",
    )
    parser.add_argument(
        "--max-tokens", default="131072", help="生成最大 token 数(默认 131072;空 = 不指定)"
    )
    parser.add_argument(
        "--thinking",
        default="",
        choices=["", "true", "false"],
        help="覆盖 chat_template_kwargs.thinking(空 = 用各基准默认)",
    )
    parser.add_argument(
        "--task-max-tokens-json",
        default="",
        help='按任务覆盖 max_tokens 的 JSON,例: {"aime25":32768,"gpqa":32768}',
    )
    parser.add_argument(
        "--description", default="", help="模型服务描述信息(仅用于邮件展示,不影响执行)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    model_dir = args.model.split("/")[-1]
    output_dir = os.path.abspath(
        f"./output/{args.tester}/{args.build_number}/{args.chip}/{model_dir}/{timestamp}"
    )
    os.makedirs(output_dir, exist_ok=True)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    shell_script = os.path.join(script_dir, "sgl_eval_main.sh")

    if not os.path.exists(shell_script):
        print(f"Error: Shell script not found at {shell_script}")
        sys.exit(1)

    env = os.environ.copy()
    env["MODEL_NAME"] = args.model
    env["DATASETS"] = args.tasks
    env["LLM_ADDR"] = args.base_url
    env["API_KEY"] = args.api_key or "EMPTY"
    env["OUTPUT_BASE"] = output_dir
    if args.examples:
        env["EXAMPLES"] = args.examples
    if args.n_repeats:
        env["N_REPEATS"] = args.n_repeats
    env["NUM_THREADS"] = args.num_threads
    env["TOP_P"] = args.top_p
    if args.max_tokens:
        env["MAX_TOKENS"] = args.max_tokens
    if args.thinking:
        env["THINKING"] = args.thinking
    if args.task_max_tokens_json:
        env["TASK_MAX_TOKENS_JSON"] = args.task_max_tokens_json
    if args.task_temperature_json:
        env["TASK_TEMPERATURE_JSON"] = args.task_temperature_json

    cmd = ["bash", shell_script]

    print(f"Output directory: {output_dir}")
    print(f"Command: {' '.join(cmd)}")
    print("Environment overrides:")
    for k in [
        "MODEL_NAME",
        "DATASETS",
        "LLM_ADDR",
        "API_KEY",
        "OUTPUT_BASE",
        "EXAMPLES",
        "N_REPEATS",
        "NUM_THREADS",
        "TOP_P",
        "MAX_TOKENS",
        "THINKING",
        "TASK_MAX_TOKENS_JSON",
        "TASK_TEMPERATURE_JSON",
    ]:
        if k in env:
            print(f"  {k}={env[k]}")
    print("=" * 60)

    result = subprocess.run(cmd, env=env)

    print(f"Test completed. Output directory: {output_dir}")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
