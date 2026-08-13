#!/bin/bash
# sgl-eval 测试脚本主入口
#
# 设计参照 lm-evaluation-harness/lm_eval_test.sh:
#   - 顶层定义 run_task 函数,每个任务调用一次
#   - 通过环境变量接收运行期参数(由 run_sgleval.py 设置)
#   - 所有输出 tee 到统一日志文件,便于 Jenkins 邮件解析
#
# run_task 函数签名(需求 #1):
#   run_task MODEL DATASET BASE_URL EXAMPLES
#       MODEL     : 模型名称(传给 sgl-eval --model)
#       DATASET   : 单个数据集名(传给 sgl-eval run <DATASET>)
#       BASE_URL  : OpenAI 兼容端点 URL
#       EXAMPLES  : 样本数(--num-examples);为空则不指定该参数
#
# 其余 sgl-eval 参数通过环境变量传入(需求 #7):
#   API_KEY        OpenAI 风格 api key,默认 EMPTY
#   N_REPEATS      每题重复采样次数,空 = 用 registry 默认
#   NUM_THREADS    并发线程数,默认 15
#   TOP_P          nucleus 概率,默认 0.95
#   MAX_TOKENS     生成最大 token 数,空 = 不指定(NS 默认 None)
#   THINKING       true / false / 空(空 = 用 registry 默认)
#   DATASETS       逗号分隔的多任务列表(本次运行的全部任务)
#   OUTPUT_BASE    结果根目录,sgl-eval 会在此下创建 sgl_eval_<name>_<stamp>/
#   TASK_MAX_TOKENS_JSON  可选 JSON,形如 {"aime25":32768,"gpqa":32768},
#                          按任务覆盖 MAX_TOKENS(若设置则覆盖全局 MAX_TOKENS)
#   TASK_TEMPERATURE_JSON  按 task 指定采样温度的 JSON,形如
#                          {"gsm8k":0.0,"aime24":0.6,"gpqa":0.6}.留空则
#                          使用内置 R1 推荐默认(gsm8k/mmlu/mmmu_pro=0.0,
#                          aime24/25/26/gpqa=0.6). 温度是模型属性,跑 DSv3.2/V4
#                          时应覆盖为 1.0;greedy(n_repeats>1)时 sgl-eval 自身会告警

set -o pipefail

ROOT_PATH=$(cd "$(dirname "$0")"; pwd)
cd "${ROOT_PATH}"

# ---------- 从环境变量读取配置(带默认值)----------
MODEL_NAME=${MODEL_NAME:-}
DATASETS=${DATASETS:-gsm8k}
LLM_ADDR=${LLM_ADDR:-http://127.0.0.1:8080}
API_KEY=${API_KEY:-EMPTY}
OUTPUT_BASE=${OUTPUT_BASE:-./output}
EXAMPLES=${EXAMPLES:-}
N_REPEATS=${N_REPEATS:-}
NUM_THREADS=${NUM_THREADS:-15}
TOP_P=${TOP_P:-0.95}
MAX_TOKENS=${MAX_TOKENS:-131072}
THINKING=${THINKING:-}
TASK_MAX_TOKENS_JSON=${TASK_MAX_TOKENS_JSON:-}
# R1-family 推荐:greedy benchmarks 用 0.0,pass@k 用 0.6;
# 跑 DSv3.2/V4 时应在外层(TASK_TEMPERATURE_JSON env / Jenkins param)覆盖为 1.0.
_DEFAULT_TASK_TEMPERATURE_JSON='{"gsm8k":0.0,"aime24":0.6,"aime25":0.6,"aime26":0.6,"mmlu":0.0,"gpqa":0.6,"mmmu_pro":0.0}'
TASK_TEMPERATURE_JSON=${TASK_TEMPERATURE_JSON:-$_DEFAULT_TASK_TEMPERATURE_JSON}

# ---------- 日志文件 ----------
TASKS_UNDERSCORE=$(echo "$DATASETS" | tr ',' '-')
LOG_FILE="${OUTPUT_BASE}/sgl-eval-${TASKS_UNDERSCORE}.log"
mkdir -p "${OUTPUT_BASE}"

# ---------- 按任务覆盖的 max_tokens ----------
_resolve_max_tokens() {
    local dataset="$1"
    local global_max_tokens="$MAX_TOKENS"
    if [ -n "$TASK_MAX_TOKENS_JSON" ]; then
        local per_task
        per_task=$(python3 -c "
import json, sys
try:
    m = json.loads('''${TASK_MAX_TOKENS_JSON}''')
except Exception:
    m = {}
v = m.get('${dataset}')
print(v if v is not None else '')
" 2>/dev/null || echo "")
        if [ -n "$per_task" ]; then
            echo "$per_task"
            return
        fi
    fi
    echo "$global_max_tokens"
}

# ---------- 按任务覆盖的 temperature ----------
# 与 _resolve_max_tokens 同形,但 fallback 是 0.0(greedy)而非全局变量
# (温度不再有"全局默认",只有 per-task JSON;未在 JSON 中的任务回退到 greedy).
_resolve_temperature() {
    local dataset="$1"
    local per_task_temp
    per_task_temp=$(python3 -c "
import json, sys
try:
    m = json.loads('''${TASK_TEMPERATURE_JSON}''')
except Exception:
    m = {}
v = m.get('${dataset}')
if v is None:
    print('')
else:
    print(v)
" 2>/dev/null || echo "")
    if [ -n "$per_task_temp" ]; then
        echo "$per_task_temp"
        return
    fi
    echo "0.0"
}

# ---------- run_task:接受 4 个位置参数 + 通过 env 读取扩展参数 ----------
run_task() {
    local MODEL="$1"        # 必填:模型名
    local DATASET="$2"      # 必填:数据集名
    local BASE_URL="$3"     # 必填:端点 URL
    local EXAMPLES="$4"     # 可空:样本数,空则不指定 --num-examples

    # 组装 sgl-eval run 命令的参数数组
    local cmd_args=(
        run "$DATASET"
        --base-url "$BASE_URL"
        --model "$MODEL"
        --api-key "$API_KEY"
        --num-threads "$NUM_THREADS"
        --top-p "$TOP_P"
        --out-dir "${OUTPUT_BASE}"
    )

    # ---- 需求 #2:样本数为空则不指定 --num-examples ----
    [ -n "$EXAMPLES" ] && cmd_args+=(--num-examples "$EXAMPLES")

    # ---- 扩展参数:repeats / max_tokens / thinking ----
    [ -n "$N_REPEATS" ] && cmd_args+=(--n-repeats "$N_REPEATS")

    local task_max_tokens
    task_max_tokens=$(_resolve_max_tokens "$DATASET")
    [ -n "$task_max_tokens" ] && cmd_args+=(--max-tokens "$task_max_tokens")

    local task_temperature
    task_temperature=$(_resolve_temperature "$DATASET")
    cmd_args+=(--temperature "$task_temperature")

    case "$THINKING" in
        true)  cmd_args+=(--thinking)    ;;
        false) cmd_args+=(--no-thinking) ;;
    esac

    echo ""                                          | tee -a "$LOG_FILE"
    echo "========================================"   | tee -a "$LOG_FILE"
    echo "Running Task: $DATASET"                    | tee -a "$LOG_FILE"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"        | tee -a "$LOG_FILE"
    echo "========================================"   | tee -a "$LOG_FILE"
    echo "Config:"                                   | tee -a "$LOG_FILE"
    echo "  MODEL         : $MODEL"                  | tee -a "$LOG_FILE"
    echo "  DATASET       : $DATASET"                | tee -a "$LOG_FILE"
    echo "  BASE_URL      : $BASE_URL"               | tee -a "$LOG_FILE"
    echo "  EXAMPLES      : ${EXAMPLES:-<unlimited>}"| tee -a "$LOG_FILE"
    echo "  N_REPEATS     : ${N_REPEATS:-<registry default>}" | tee -a "$LOG_FILE"
    echo "  NUM_THREADS   : $NUM_THREADS"            | tee -a "$LOG_FILE"
    echo "  TEMPERATURE   : ${task_temperature:-<greedy 0.0>}" | tee -a "$LOG_FILE"
    echo "  TOP_P         : $TOP_P"                  | tee -a "$LOG_FILE"
    echo "  MAX_TOKENS    : ${task_max_tokens:-<unlimited>}" | tee -a "$LOG_FILE"
    echo "  THINKING      : ${THINKING:-<registry default>}" | tee -a "$LOG_FILE"
    echo "  OUT_DIR       : ${OUTPUT_BASE}"          | tee -a "$LOG_FILE"
    echo "========================================"   | tee -a "$LOG_FILE"
    echo "Command: sgl-eval ${cmd_args[*]}"          | tee -a "$LOG_FILE"
    echo ""                                          | tee -a "$LOG_FILE"

    # ---- 失败不中断后续任务(catchError 风格)----
    # 需求 #2 核心命令:sgl-eval run <DATASET> --base-url <BASE_URL> --num-examples <EXAMPLES>
    if ! sgl-eval "${cmd_args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        echo "[WARN] task $DATASET failed (exit $?), continuing..." | tee -a "$LOG_FILE"
    fi
}

# ---------- 主流程:打印总体配置 + 按逗号分发到 run_task ----------
{
    echo "========================================"
    echo "sgl-eval Test Start"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    echo "Config:"
    echo "  LLM_ADDR       : $LLM_ADDR"
    echo "  MODEL_NAME     : $MODEL_NAME"
    echo "  DATASETS       : $DATASETS"
    echo "  EXAMPLES       : ${EXAMPLES:-<unlimited>}"
    echo "  N_REPEATS      : ${N_REPEATS:-<registry default>}"
    echo "  NUM_THREADS    : $NUM_THREADS"
    echo "  TOP_P          : $TOP_P"
    echo "  MAX_TOKENS     : ${MAX_TOKENS:-<unlimited>}"
    echo "  THINKING       : ${THINKING:-<registry default>}"
    echo "  TASK_MAX_TOKENS_JSON  : ${TASK_MAX_TOKENS_JSON:-<脚本内置 fallback 到 MAX_TOKENS>}"
    echo "  TASK_TEMPERATURE_JSON : ${TASK_TEMPERATURE_JSON}"
    echo "  OUTPUT_BASE    : $OUTPUT_BASE"
    echo "  LOG_FILE       : $LOG_FILE"
    echo "========================================"
} | tee "$LOG_FILE"

IFS=',' read -ra TASK_LIST <<< "$DATASETS"
for task in "${TASK_LIST[@]}"; do
    task=$(echo "$task" | xargs)   # 去除前后空白
    [ -z "$task" ] && continue
    run_task "$MODEL_NAME" "$task" "$LLM_ADDR" "$EXAMPLES"
done

echo ""                                          | tee -a "$LOG_FILE"
echo "========================================"   | tee -a "$LOG_FILE"
echo "sgl-eval Test Complete"                     | tee -a "$LOG_FILE"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"        | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE"                        | tee -a "$LOG_FILE"
echo "Output dir: $OUTPUT_BASE"                   | tee -a "$LOG_FILE"
echo "========================================"   | tee -a "$LOG_FILE"
