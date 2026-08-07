<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listGroups } from '@/api/groups'
import { listAttempts, sendChat, type ChatResult } from '@/api/gateway'
import { ApiError, isMockOn } from '@/api/http'
import { faultConfig, type FaultScenario } from '@/api/mock/db'
import { useAsync } from '@/composables/useAsync'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import AttemptTimeline from '@/components/AttemptTimeline.vue'
import type { ApiGroup, RouteAttempt } from '@/types/api'

const { data: groups, loading, error, run } = useAsync(listGroups, [] as ApiGroup[])

const routeKey = ref('')
const question = ref('用一句话介绍你自己，并说明你是哪个模型。')
const sending = ref(false)

const result = ref<ChatResult | null>(null)
const failure = ref<{ message: string; requestId?: string } | null>(null)
const attempts = ref<RouteAttempt[]>([])

const enabledGroups = computed(() => groups.value.filter((g) => g.enabled))

// Mock 模式下允许现场切换第一上游的故障场景，用来演示自动切换
const mockMode = isMockOn()
const scenario = ref<FaultScenario>('normal')
const SCENARIOS: { value: FaultScenario; label: string }[] = [
  { value: 'normal', label: '正常返回' },
  { value: 'timeout', label: '超时（应切换）' },
  { value: 'rate_limited', label: '429 限流（应切换）' },
  { value: 'server_error', label: '500 错误（应切换）' },
  { value: 'client_error', label: '400 参数错误（不应切换）' },
]

function onScenarioChange(v: FaultScenario) {
  faultConfig.firstUpstream = v
}

async function send() {
  if (!routeKey.value) return ElMessage.warning('请选择一个分组')
  if (!question.value.trim()) return ElMessage.warning('请输入问题')

  sending.value = true
  result.value = null
  failure.value = null
  attempts.value = []

  try {
    result.value = await sendChat(routeKey.value, question.value.trim())
  } catch (e) {
    // 失败时同样要显示请求 ID，便于对照路由记录排查
    failure.value =
      e instanceof ApiError
        ? { message: e.friendly, requestId: e.requestId }
        : { message: (e as Error)?.message ?? '调用失败' }
  } finally {
    sending.value = false
  }

  // 无论成功失败都尝试取本次的尝试链（D6 未做完时的兜底展示路径）
  const rid = result.value?.requestId ?? failure.value?.requestId
  if (rid) {
    try {
      attempts.value = await listAttempts(rid)
    } catch {
      /* 后端未实现记录接口时静默跳过，不影响主流程 */
    }
  }
}

onMounted(async () => {
  await run()
  routeKey.value = enabledGroups.value[0]?.routeKey ?? ''
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="调用测试"
      desc="选择分组后发送真实问题。响应头 X-Upstream 是最终服务本次请求的上游，X-Request-Id 可用于追查路由记录。"
    />

    <AsyncSection :loading="loading" :error="error" @retry="run">
      <el-empty
        v-if="enabledGroups.length === 0"
        description="没有可用分组。请先到「API 分组」创建分组并加入至少一个上游。"
      />

      <template v-else>
        <el-card shadow="never" class="card">
          <el-form label-width="90px">
            <el-form-item label="分组">
              <el-select v-model="routeKey" style="width: 320px">
                <el-option
                  v-for="g in enabledGroups"
                  :key="g.id"
                  :label="`${g.name}（${g.routeKey}）`"
                  :value="g.routeKey"
                />
              </el-select>
              <span class="muted hint">routeKey 会作为 model 字段发送</span>
            </el-form-item>

            <el-form-item v-if="mockMode" label="故障模拟">
              <el-radio-group v-model="scenario" size="small" @change="onScenarioChange">
                <el-radio-button v-for="s in SCENARIOS" :key="s.value" :value="s.value">
                  {{ s.label }}
                </el-radio-button>
              </el-radio-group>
              <div class="muted">仅 Mock 模式可用：控制第一优先级上游的返回结果，其余上游一律正常。</div>
            </el-form-item>

            <el-form-item label="问题">
              <el-input v-model="question" type="textarea" :rows="3" placeholder="输入要发送给模型的问题" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="sending" @click="send">发送请求</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 成功 -->
        <el-card v-if="result" shadow="never" class="card">
          <template #header>
            <div class="res-head">
              <span>调用成功</span>
              <div class="tags">
                <el-tag type="success" effect="dark">
                  最终上游：{{ result.finalUpstream || '未知' }}
                </el-tag>
                <el-tag type="info" class="mono">{{ result.requestId || '无请求 ID' }}</el-tag>
              </div>
            </div>
          </template>
          <pre class="answer">{{ result.answer }}</pre>
          <div v-if="result.usage" class="muted usage">
            tokens：输入 {{ result.usage.prompt_tokens }} / 输出
            {{ result.usage.completion_tokens }} / 合计 {{ result.usage.total_tokens }}
          </div>
        </el-card>

        <!-- 失败 -->
        <el-card v-if="failure" shadow="never" class="card">
          <template #header>
            <div class="res-head">
              <span>调用失败</span>
              <el-tag v-if="failure.requestId" type="info" class="mono">{{ failure.requestId }}</el-tag>
            </div>
          </template>
          <el-alert type="error" show-icon :closable="false" :title="failure.message" />
        </el-card>

        <!-- 路由尝试链 -->
        <el-card v-if="attempts.length > 0" shadow="never" class="card">
          <template #header>本次路由尝试（共 {{ attempts.length }} 次）</template>
          <AttemptTimeline :attempts="attempts" />
        </el-card>
      </template>
    </AsyncSection>
  </div>
</template>

<style scoped>
.card {
  margin-bottom: 16px;
}
.hint {
  margin-left: 12px;
}
.res-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.tags {
  display: flex;
  gap: 8px;
}
.answer {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.7;
}
.usage {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}
</style>
