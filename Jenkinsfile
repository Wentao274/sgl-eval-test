pipeline {
    agent {
        label 'slave-2'
    }
    parameters {
        string(name: 'TESTER', defaultValue: 'liwt', description: '测试人员名称(必填)')
        string(name: 'CHIP', defaultValue: 'nvidia-h100', description: '芯片平台名称(必填)')
        choice(name: 'ENGINE', choices: ['vllm', 'sglang'], description: '推理框架(必填)')
        choice(name: 'PD', choices: ['agg', 'disagg'], description: 'PD分离模式(agg=非PD分离,disagg=PD分离)')
        string(name: 'MODEL', defaultValue: 'glm-5.2', description: '模型服务名称(必填,对应 sgl-eval --model)')
        string(name: 'BASE_URL', defaultValue: 'http://10.201.149.34:8000', description: 'OpenAI 兼容端点根 URL(必填,不带 /v1 后缀,流水线会自动拼接)')
        password(name: 'API_KEY', defaultValue: '', description: 'API Key(可选,无需认证时留空)')

        // 各基准一个 boolean,与 lm-evaluation-harness 风格一致
        booleanParam(name: 'TASK_GSM8K',  defaultValue: true,  description: '运行 gsm8k (小学数学,单 shot accuracy)')
        booleanParam(name: 'TASK_AIME24', defaultValue: true, description: '运行 aime24 (30 题,pass@16)')
        booleanParam(name: 'TASK_AIME25', defaultValue: true, description: '运行 aime25 (30 题,pass@16)')
        booleanParam(name: 'TASK_AIME26', defaultValue: true, description: '运行 aime26 (30 题,pass@16)')
        booleanParam(name: 'TASK_MMLU',   defaultValue: true, description: '运行 mmlu (多学科多选,single-shot accuracy)')
        booleanParam(name: 'TASK_GPQA',   defaultValue: true, description: '运行 gpqa Diamond (pass@8 + majority@8)')
        booleanParam(name: 'TASK_MMMU_PRO', defaultValue: false, description: '运行 mmmu_pro (多模态 10 选择,single-shot)')

        string(name: 'EXAMPLES',     defaultValue: '',    description: '样本数限制(空 = 不限制,跑全集)')
        string(name: 'N_REPEATS',    defaultValue: '',   description: '每题采样次数(空 = 各基准 registry 默认:gsm8k/mmlu=1, aime=16, gpqa=8;填值则按该值执行)')
        string(name: 'NUM_THREADS',  defaultValue: '32',  description: '并发线程数(默认 32)')
        string(name: 'TOP_P',        defaultValue: '0.95', description: 'nucleus top_p(默认 0.95)')
        string(name: 'MAX_TOKENS',   defaultValue: '131072', description: '生成最大 token 数(默认 131072;清空 = 不指定)')
        choice(name: 'THINKING',     choices: ['', 'true', 'false'], description: '覆盖 thinking 模式(空=用各基准默认:gsm8k/mmlu=false,aime/gpqa=true)')
        text(name: 'TASK_MAX_TOKENS_JSON', defaultValue: '', description: '按任务覆盖 max_tokens 的 JSON,例: {"aime25":32768,"gpqa":32768}')
        text(name: 'TASK_TEMPERATURE_JSON', defaultValue: '', description: '按任务覆盖 temperature 的 JSON,例: {"aime25":0.6,"gpqa":0.6};留空则用脚本内置 R1 推荐(gsm8k/mmlu/mmmu_pro=0.0, aime24/25/26/gpqa=0.6);跑 DSv3.2/V4 应填 1.0')

        string(name: 'DESCRIPTION', defaultValue: '', description: '模型服务描述信息(仅用于邮件展示)')
        text(name: 'RECIPIENTS',    defaultValue: 'liwt@zetyun.com', description: '报告邮件接收者(逗号分隔)')
        string(name: 'WORK_DIR',    defaultValue: '/dingofs/data2/userdata/liwt/maas-image/sgl-eval-test', description: '远程仓库目录,请不要改动')
    }
    environment {
        SSH_CREDENTIALS = 'HOST_SSH_KEY'
        REMOTE_HOST = '10.201.132.50'
        REMOTE_USER = 'root'
        // 用户在 BASE_URL 填根地址(可不带或带 /v1,可带或不带尾斜杠)。
        // 这里 idempotent 拼接出唯一的 OpenAI 兼容端点:
        //   先剥尾斜杠 → 再剥结尾 /v1(若有)→ 统一补 /v1
        // 例: http://h:8000 | http://h:8000/ | http://h:8000/v1 | http://h:8000/v1/
        //     都得到 http://h:8000/v1
        BASE_URL_V1 = "${params.BASE_URL.replaceAll('/+\$', '').replaceAll('/?v1\$', '')}/v1"
    }

    stages {
        stage('打印测试参数') {
            steps {
                script {
                    println("========================================")
                    println("=== 测试参数信息 ===")
                    println("========================================")
                    println("测试人员:        ${params.TESTER}")
                    println("芯片平台:        ${params.CHIP}")
                    println("推理框架:        ${params.ENGINE}")
                    println("PD分离模式:      ${params.PD}")
                    println("模型名称:        ${params.MODEL}")
                    println("BASE_URL:        ${params.BASE_URL}  (→ ${env.BASE_URL_V1})")
                    println("任务 GSM8K:      ${params.TASK_GSM8K}")
                    println("任务 AIME24:     ${params.TASK_AIME24}")
                    println("任务 AIME25:     ${params.TASK_AIME25}")
                    println("任务 AIME26:     ${params.TASK_AIME26}")
                    println("任务 MMLU:       ${params.TASK_MMLU}")
                    println("任务 GPQA:       ${params.TASK_GPQA}")
                    println("任务 MMMU_PRO:   ${params.TASK_MMMU_PRO}")
                    println("样本限制:        ${params.EXAMPLES ?: '无限制'}")
                    println("n_repeats:       ${params.N_REPEATS ?: 'registry default'}")
                    println("并发线程:        ${params.NUM_THREADS}")
                    println("top_p:           ${params.TOP_P}")
                    println("max_tokens:      ${params.MAX_TOKENS ?: 'unlimited'}")
                    println("thinking:        ${params.THINKING ?: 'registry default'}")
                    println("per-task max_tokens JSON: ${params.TASK_MAX_TOKENS_JSON ?: 'N/A'}")
                    println("per-task temperature JSON: ${params.TASK_TEMPERATURE_JSON ?: 'N/A(用脚本内置 R1 默认)'}")
                    println("模型描述:        ${params.DESCRIPTION}")
                    println("邮件接收者:      ${params.RECIPIENTS}")
                    println("工作目录:        ${params.WORK_DIR}")
                    println("构建编号:        #${BUILD_NUMBER}")
                    println("========================================")
                }
            }
        }

        stage('API 连通性预检') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    script {
                        try {
                            sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -o pipefail
{
    echo "=== 检查 API 连通性 (/v1/models) ==="
    HTTP_CODE=\$(curl -s --connect-timeout 10 -m 30 -o /dev/null -w "%{http_code}" ${env.BASE_URL_V1}/models)
    if [ "\${HTTP_CODE}" != "200" ]; then
        echo "ERROR: API 连通性检查失败, HTTP状态码: \${HTTP_CODE}, URL: ${env.BASE_URL_V1}/models"
        exit 1
    fi
    echo "API /models 连通性检查通过, HTTP状态码: \${HTTP_CODE}"

    echo "=== 检查 Chat Completions 接口 ==="
    CHAT_RESP=\$(curl -s --connect-timeout 10 -m 60 -w "\\n%{http_code}" ${env.BASE_URL_V1}/chat/completions \\
        -H "Content-Type: application/json" \\
        -d '{"model":"${params.MODEL}","messages":[{"role":"user","content":"hello"}],"max_tokens":10}')
    CHAT_HTTP_CODE=\$(echo "\${CHAT_RESP}" | tail -1)
    if [ "\${CHAT_HTTP_CODE}" != "200" ]; then
        echo "ERROR: Chat Completions 接口检查失败, HTTP状态码: \${CHAT_HTTP_CODE}"
        echo "响应内容: \$(echo "\${CHAT_RESP}" | head -n -1)"
        exit 1
    fi
    echo "Chat Completions 接口检查通过, HTTP状态码: \${CHAT_HTTP_CODE}"
} 2>&1 | tee /tmp/sgl_eval_connectivity_${BUILD_NUMBER}.log
ENDSSH
"""
                        } catch (Exception e) {
                            env.CONNECTIVITY_FAILED = 'true'
                            currentBuild.result = 'UNSTABLE'
                            println("=== API 连通性预检失败,后续阶段(环境检查、运行sgl-eval测试)将跳过 ===")
                        }
                    }
                }
            }
        }

        stage('环境检查') {
            when {
                expression { env.CONNECTIVITY_FAILED != 'true' }
            }
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e
cd ${params.WORK_DIR}
echo "工作目录: \$(pwd)"
ls -la

echo "=== 清理残留进程 (sgl-eval / run_sgleval) ==="
# 注意:pgrep -af 会全命令行匹配。Jenkins durable wrapper 的命令行里含
# 工作空间路径 ".../workspace/sgl-eval-test@tmp/...",会撞上 "sgl-eval" 关键字
# 被误杀,导致 sh step 异常终止。这里用更精确的"全字符串"匹配:
#   - "sgl-eval run"      :真正的 sgl-eval 运行命令(必带 run 子命令)
#   - "run_sgleval.py"    :我们的编排脚本(改用全字符串,避免命中其他框架的 run_eval.py / run_eval_xxx.py)
#   - 排除含 "jenkins" / "durable" / "@tmp" 的 Jenkins 内部进程
# pgrep -f 的 pattern 默认做正则匹配,转义为普通字符串以确保整串相等而非子串正则。
RESIDUAL=\$(pgrep -af "sgl-eval run|run_sgleval\\.py" 2>/dev/null | grep -vE "jenkins|durable|@tmp" || true)
if [ -n "\${RESIDUAL}" ]; then
    echo "发现残留进程:"
    echo "\${RESIDUAL}"
    echo "发送 SIGTERM..."
    echo "\${RESIDUAL}" | awk '{print \$1}' | xargs -r kill -TERM 2>/dev/null || true
    sleep 3
    REMAINING=\$(pgrep -af "sgl-eval run|run_sgleval\\.py" 2>/dev/null | grep -vE "jenkins|durable|@tmp" || true)
    if [ -n "\${REMAINING}" ]; then
        echo "残留进程未响应 SIGTERM,发送 SIGKILL..."
        echo "\${REMAINING}" | awk '{print \$1}' | xargs -r kill -KILL 2>/dev/null || true
        sleep 1
    fi
    FINAL=\$(pgrep -af "sgl-eval run|run_sgleval\\.py" 2>/dev/null | grep -vE "jenkins|durable|@tmp" || true)
    if [ -n "\${FINAL}" ]; then
        echo "WARN: 以下残留进程仍存在,需人工介入:"
        echo "\${FINAL}"
    else
        echo "残留进程清理完成"
    fi
else
    echo "未发现残留进程"
fi

echo "=== 设置权限 ==="
chmod +x sgl_eval_main.sh
chmod +x run_sgleval.py

echo "=== 检查并创建虚拟环境 ==="
if [ ! -d "${params.WORK_DIR}/.venv" ]; then
    export https_proxy=http://100.64.1.68:1080
    export http_proxy=http://100.64.1.68:1080
    echo "创建虚拟环境..."
    cd ${params.WORK_DIR}
    uv venv
    source .venv/bin/activate
    uv pip install .
    deactivate
    unset https_proxy
    unset http_proxy
fi

cd ${params.WORK_DIR}
echo "=== 虚拟环境准备完成 ==="
ENDSSH
"""
                }
            }
        }

        stage('运行sgl-eval测试') {
            when {
                expression { env.CONNECTIVITY_FAILED != 'true' }
            }
            steps {
                script {
                    def taskList = []
                    if (params.TASK_GSM8K)   taskList.add('gsm8k')
                    if (params.TASK_AIME24)  taskList.add('aime24')
                    if (params.TASK_AIME25)  taskList.add('aime25')
                    if (params.TASK_AIME26)  taskList.add('aime26')
                    if (params.TASK_MMLU)    taskList.add('mmlu')
                    if (params.TASK_GPQA)    taskList.add('gpqa')
                    if (params.TASK_MMMU_PRO) taskList.add('mmmu_pro')
                    if (taskList.isEmpty()) {
                        error '至少需要选择一个测试任务'
                    }
                    env.TASKS = taskList.join(',')

                    def modelDir = params.MODEL.contains("/") ? params.MODEL.split("/").last() : params.MODEL
                    env.MODEL_DIR = modelDir

                    env.API_KEY_STR = params.API_KEY?.toString() ?: ''

                    sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                        catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                            sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << ENDSSH
set -e
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
cd ${params.WORK_DIR}
source .venv/bin/activate
echo "=== 执行Python测试脚本 ==="
python3 run_sgleval.py \\
    --tester ${params.TESTER} \\
    --build-number ${BUILD_NUMBER} \\
    --chip ${params.CHIP} \\
    --model ${params.MODEL} \\
    --base-url ${env.BASE_URL_V1} \\
    --api-key "${env.API_KEY_STR ?: 'EMPTY'}" \\
    --tasks ${env.TASKS} \\
    --examples "${params.EXAMPLES}" \\
    --n-repeats "${params.N_REPEATS}" \\
    --num-threads "${params.NUM_THREADS}" \\
    --top-p "${params.TOP_P}" \\
    --max-tokens "${params.MAX_TOKENS}" \\
    --thinking "${params.THINKING}" \\
    --task-max-tokens-json '${params.TASK_MAX_TOKENS_JSON}' \\
    --task-temperature-json '${params.TASK_TEMPERATURE_JSON}' \\
    --description "${params.DESCRIPTION}"
echo "=== 测试脚本执行结束 ==="
echo "=== 输出目录 ==="
find output/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.MODEL_DIR}/ -type f
ENDSSH
"""
                        }
                    }
                }
            }
        }

        stage('拉取测试结果') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                        script {
                            def remoteDir = "${params.WORK_DIR}/output/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.MODEL_DIR}"
                            def localDir = "reports/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}"
                            def localBuildsDir = "builds/${BUILD_NUMBER}"
                            env.RESULT_DIR = "output/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.MODEL_DIR}"
                            echo "拉取测试结果目录: ${remoteDir}"

                            if (env.CONNECTIVITY_FAILED == 'true') {
                                echo "=== 连通性检查未通过,跳过测试结果目录拉取,仅拉取连通性预检日志 ==="
                            } else {
                                sh """
mkdir -p ${localDir}
scp -o StrictHostKeyChecking=no \
    -r ${REMOTE_USER}@${REMOTE_HOST}:${remoteDir} \
    ${localDir}/
echo "=== 拉取结果 ==="
find ${localDir}/ -type f
"""
                            }

                            sh """
mkdir -p ${localBuildsDir}
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    ${REMOTE_USER}@${REMOTE_HOST}:/tmp/sgl_eval_connectivity_${BUILD_NUMBER}.log \
    ./${localBuildsDir}/sgl_eval_connectivity_${BUILD_NUMBER}.log 2>/dev/null \
    && echo "连通性预检日志已拉取: ${localBuildsDir}/sgl_eval_connectivity_${BUILD_NUMBER}.log" \
    || echo "WARN: 连通性预检日志拉取失败"
"""
                        }
                    }
                }
            }
        }

        stage('发送邮件') {
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    script {
                        def logFileBase = "reports/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.MODEL_DIR}"

                        // 找到 sgl-eval-<tasks>.log
                        def logFiles = findFiles(glob: "${logFileBase}/**/sgl-eval-*.log")
                        def logFile = ""
                        def logContent = ""
                        if (logFiles.length > 0) {
                            logFile = logFiles[0].path
                            logContent = readFile(logFile)
                        }

                        // 连通性预检失败检测
                        def connectivityLogPath = "builds/${BUILD_NUMBER}/sgl_eval_connectivity_${BUILD_NUMBER}.log"
                        def connectivityLogContent = ""
                        def failureReason = ""
                        def connectivityFailureReason = ""
                        if (fileExists(connectivityLogPath)) {
                            connectivityLogContent = readFile(connectivityLogPath)
                            if (connectivityLogContent.contains("API 连通性检查失败") ||
                                connectivityLogContent.contains("Chat Completions 接口检查失败")) {
                                failureReason = "连通性检查未通过"
                                def logLines = connectivityLogContent.split('\n')
                                def collected = []
                                def inFailureSection = false
                                for (def ll : logLines) {
                                    if (ll.contains("检查 API 连通性") || ll.contains("Chat Completions 接口检查")) {
                                        inFailureSection = true
                                    }
                                    if (inFailureSection) {
                                        if (!collected.isEmpty() && ll.trim().startsWith("===") &&
                                            !ll.contains("检查 API 连通性") && !ll.contains("Chat Completions 接口检查")) {
                                            break
                                        }
                                        collected.add(ll)
                                    }
                                }
                                connectivityFailureReason = collected.join('\n').trim()
                            }
                        }
                        if (!failureReason && env.CONNECTIVITY_FAILED == 'true') {
                            failureReason = "连通性检查未通过"
                            connectivityFailureReason = "API 连通性或 Chat Completions 接口检查失败,具体日志未拉到,详见 Jenkins 控制台输出。"
                        }

                        // 从 metrics.json 提取每个任务的得分
                        def taskScores = [:]
                        def taskMetricsHtml = ""
                        def taskSummaryRows = ""
                        if (!failureReason) {
                            def metricsFiles = findFiles(glob: "${logFileBase}/**/sgl_eval_*/metrics.json")
                            for (def mf : metricsFiles) {
                                def json = readJSON(file: mf.path)
                                def taskName = json.name ?: "unknown"
                                def nRepeats = json.n_repeats ?: 1
                                def agg = json.aggregate ?: [:]
                                def scoreStr = "N/A"
                                def metricName = "score"
                                if (nRepeats > 1 && agg["pass@1"] != null) {
                                    metricName = "pass@1[avg-of-${nRepeats}]"
                                    def pass1 = agg["pass@1"] as Double
                                    def std = agg["pass@1_std"] as Double ?: 0.0
                                    def sem = agg["pass@1_sem"] as Double ?: 0.0
                                    scoreStr = String.format("%.2f%%", pass1 * 100)
                                    if (std > 0) {
                                        scoreStr += String.format(" +/- %.2f%% (SEM %.2f%%)", std * 100, sem * 100)
                                    }
                                } else if (agg["score"] != null) {
                                    scoreStr = String.format("%.2f%%", (agg["score"] as Double) * 100)
                                }
                                taskScores[taskName] = scoreStr
                                taskSummaryRows += "<tr><td>${taskName}</td><td>${scoreStr}</td></tr>"

                                // 单任务详情行(包含辅助指标)
                                def detailRows = ""
                                if (nRepeats > 1 && agg["pass@1"] != null) {
                                    detailRows += "<tr class=\"score-highlight\"><td>${taskName}</td><td>pass@1[avg-of-${nRepeats}]</td><td>${scoreStr}</td></tr>"
                                    if (agg["pass@${nRepeats}"] != null) {
                                        detailRows += "<tr><td>${taskName}</td><td>pass@${nRepeats}</td><td>${String.format("%.2f%%", (agg["pass@${nRepeats}"] as Double) * 100)}</td></tr>"
                                    }
                                    if (agg["majority@${nRepeats}"] != null) {
                                        detailRows += "<tr><td>${taskName}</td><td>majority@${nRepeats}</td><td>${String.format("%.2f%%", (agg["majority@${nRepeats}"] as Double) * 100)}</td></tr>"
                                    }
                                } else if (agg["score"] != null) {
                                    detailRows += "<tr class=\"score-highlight\"><td>${taskName}</td><td>score</td><td>${scoreStr}</td></tr>"
                                }
                                if (agg["no_answer"] != null) {
                                    detailRows += "<tr><td>${taskName}</td><td>no_answer</td><td>${String.format("%.2f%%", (agg["no_answer"] as Double) * 100)}</td></tr>"
                                }
                                if (agg["stop_rate"] != null) {
                                    detailRows += "<tr><td>${taskName}</td><td>stop_rate</td><td>${String.format("%.2f%%", (agg["stop_rate"] as Double) * 100)}</td></tr>"
                                }
                                if (agg["truncated_rate"] != null) {
                                    detailRows += "<tr><td>${taskName}</td><td>truncated_rate</td><td>${String.format("%.2f%%", (agg["truncated_rate"] as Double) * 100)}</td></tr>"
                                }
                                if (agg["error_rate"] != null) {
                                    detailRows += "<tr><td>${taskName}</td><td>error_rate</td><td>${String.format("%.2f%%", (agg["error_rate"] as Double) * 100)}</td></tr>"
                                }
                                // 部分运行 bounds
                                if (json["partial"] == true) {
                                    def lower = json["score_lower_bound"] as Double
                                    def upper = json["score_upper_bound"] as Double
                                    detailRows += "<tr><td colspan=\"2\"><em>partial score range</em></td><td>[${String.format("%.2f%%", lower * 100)}, ${String.format("%.2f%%", upper * 100)}]</td></tr>"
                                }

                                taskMetricsHtml += """
            <div class="section-title">${taskName} 任务测试结果</div>
            <table>
                <tr style="background-color: #e3f2fd;"><th>任务</th><th>指标</th><th>值</th></tr>
                ${detailRows}
            </table>
            <p style="font-size: 12px; color: #666;">metrics.json: ${mf.path}</p>
"""
                                if (json["latency_seconds"] != null || json["output_throughput_tps"] != null) {
                                    taskMetricsHtml += """
            <p style="font-size: 12px; color: #666;">
                latency: ${json["latency_seconds"] ?: 'N/A'}s |
                throughput: ${json["output_throughput_tps"] ?: 'N/A'} tok/s |
                completion tokens: ${json["total_completion_tokens"] ?: 'N/A'} |
                prompt tokens: ${json["total_prompt_tokens"] ?: 'N/A'}
            </p>
"""
                                }
                            }
                        }
                        if (failureReason) {
                            taskSummaryRows = "<tr><td colspan='2'>连通性检查未通过,任务未执行</td></tr>"
                        } else if (taskSummaryRows.isEmpty()) {
                            taskSummaryRows = "<tr><td colspan='2'>无任务执行或未找到 metrics.json</td></tr>"
                        }

                        def hasResult = !taskScores.isEmpty()
                        def resultStatus = hasResult ? "完成" : "失败/无结果"
                        if (failureReason) {
                            resultStatus = "失败/${failureReason}"
                        }

                        // 连通性失败 HTML 块
                        def connectivityFailureHtml = ""
                        if (failureReason) {
                            def escapedReason = (connectivityFailureReason ?: '')
                                .replace('&', '&amp;')
                                .replace('<', '&lt;')
                                .replace('>', '&gt;')
                            connectivityFailureHtml = """
            <div style="background-color: #ffebee; color: #000000; border-left: 4px solid #d32f2f; padding: 12px 15px; margin-top: 15px; border-radius: 3px;">
                <h3 style="color: #d32f2f; margin-top: 0; margin-bottom: 8px;">⚠️ 连通性检查未通过</h3>
                <p style="margin-top: 0; margin-bottom: 8px; color: #000000;">本次测试未能正常执行用例,原因是 API 连通性检查失败:</p>
                <pre style="background-color: #ffffff; color: #000000; padding: 10px; border-radius: 3px; overflow-x: auto; white-space: pre-wrap; margin: 0; font-family: Menlo, Consolas, monospace; font-size: 12px;">${escapedReason}</pre>
            </div>"""
                        }

                        def emailBody = """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background-color: #fff; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .header { background-color: ${hasResult ? '#4CAF50' : '#f44336'}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }
        .content { padding: 20px; }
        table { border-collapse: collapse; width: 100%; margin-top: 15px; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .footer { margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 0 0 5px 5px; color: #666; font-size: 12px; }
        .section-title { background-color: #e3f2fd; padding: 10px; margin-top: 20px; border-radius: 3px; font-weight: bold; }
        .score-highlight { background-color: #c8e6c9; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">sgl-eval 精度测试报告 - 构建 #${BUILD_NUMBER}</h2>
        </div>
        <div class="content">
            <h3>测试概要</h3>
            <table>
                <tr><th>项目</th><td>值</td></tr>
                <tr><th>构建编号</th><td>#${BUILD_NUMBER}</td></tr>
                <tr><th>模型服务描述</th><td>${params.DESCRIPTION}</td></tr>
                <tr><th>测试人员</th><td>${params.TESTER}</td></tr>
                <tr><th>芯片平台</th><td>${params.CHIP}</td></tr>
                <tr><th>推理框架</th><td>${params.ENGINE}</td></tr>
                <tr><th>PD分离模式</th><td>${params.PD}</td></tr>
                <tr><th>模型名称</th><td>${params.MODEL}</td></tr>
                <tr><th>API地址</th><td>${params.BASE_URL}</td></tr>
                <tr><th>测试任务</th><td>${env.TASKS ?: (failureReason ? '未执行(连通性检查未通过)' : 'N/A')}</td></tr>
                <tr><th>样本限制</th><td>${params.EXAMPLES ?: '无限制'}</td></tr>
                <tr><th>n_repeats</th><td>${params.N_REPEATS ?: 'registry default'}</td></tr>
                <tr><th>并发线程</th><td>${params.NUM_THREADS}</td></tr>
                <tr><th>top_p</th><td>${params.TOP_P}</td></tr>
                <tr><th>max_tokens</th><td>${params.MAX_TOKENS ?: 'unlimited'}</td></tr>
                <tr><th>thinking</th><td>${params.THINKING ?: 'registry default'}</td></tr>
                <tr><th>per-task max_tokens JSON</th><td>${params.TASK_MAX_TOKENS_JSON ?: 'N/A'}</td></tr>
                <tr><th>per-task temperature JSON</th><td>${params.TASK_TEMPERATURE_JSON ?: '脚本内置 R1 默认(gsm8k/mmlu/mmmu_pro=0.0, aime/gpqa=0.6)'}</td></tr>
                <tr><th>执行时间</th><td>${currentBuild.durationString}</td></tr>
                <tr><th>测试状态</th><td>${resultStatus}</td></tr>
                <tr><th>构建状态</th><td>${currentBuild.currentResult}</td></tr>
            </table>

            ${connectivityFailureHtml}

            <h3>任务汇总得分</h3>
            <table>
                <tr style="background-color: #e3f2fd;"><th>任务名称</th><th>得分</th></tr>
                ${taskSummaryRows}
            </table>

            ${taskMetricsHtml}

            <h3>输出目录</h3>
            <p>${failureReason ? 'N/A (连通性检查未通过)' : (env.RESULT_DIR ?: 'N/A')}</p>

            <p style="margin-top: 20px;">详细日志请查看附件。</p>
            <p>Jenkins 构建地址: <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>
        </div>
        <div class="footer">
            此邮件由 Jenkins 自动发送，请勿回复。
        </div>
    </div>
</body>
</html>"""

                        echo "=== sgl-eval 测试结果 ==="
                        echo "Build Number: ${BUILD_NUMBER}"
                        echo "结果目录: ${env.RESULT_DIR ?: 'N/A'}"
                        echo "测试状态: ${resultStatus}"
                        taskScores.each { k, v -> println("  ${k} 得分: ${v}") }

                        def attachPattern = ""
                        def attachPatterns = []
                        if (logFile) {
                            attachPatterns.add(logFile)
                        }
                        if (fileExists("builds/${BUILD_NUMBER}/sgl_eval_connectivity_${BUILD_NUMBER}.log")) {
                            attachPatterns.add("builds/${BUILD_NUMBER}/sgl_eval_connectivity_${BUILD_NUMBER}.log")
                        }
                        attachPattern = attachPatterns.join(',')
                        emailext(
                            subject: "[模型推理 - sgl-eval精度测试报告] #${BUILD_NUMBER} ${params.CHIP} - ${params.MODEL}",
                            body: emailBody,
                            to: "${params.RECIPIENTS}",
                            mimeType: 'text/html',
                            attachmentsPattern: attachPattern
                        )
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                archiveArtifacts artifacts: "reports/${params.TESTER}/${BUILD_NUMBER}/**,builds/${BUILD_NUMBER}/**", allowEmptyArchive: true, fingerprint: true
                echo "构建完成: ${currentBuild.currentResult}"
            }
        }
        cleanup {
            cleanWs()
        }
    }
}
