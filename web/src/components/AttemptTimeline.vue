<script setup lang="ts">
/** 路由尝试链。调用测试页与路由记录页共用。 */
import type { ResultCategory, RouteAttempt } from '@/types/api'

defineProps<{ attempts: RouteAttempt[] }>()

const LABEL: Record<ResultCategory, string> = {
  success: '成功',
  network_error: '连接失败',
  timeout: '超时',
  rate_limited: '限流 429',
  server_error: '服务端错误 5xx',
  auth_error: '认证失败',
  client_error: '参数错误 4xx',
}

const COLOR: Record<ResultCategory, 'success' | 'danger' | 'warning' | 'info'> = {
  success: 'success',
  network_error: 'danger',
  timeout: 'warning',
  rate_limited: 'warning',
  server_error: 'danger',
  auth_error: 'danger',
  client_error: 'info',
}
</script>

<template>
  <el-timeline>
    <el-timeline-item
      v-for="a in attempts"
      :key="`${a.requestId}-${a.attemptIndex}`"
      :type="COLOR[a.resultCategory]"
      :hollow="a.resultCategory !== 'success'"
    >
      <div class="row">
        <span class="idx">第 {{ a.attemptIndex }} 次</span>
        <strong>{{ a.upstreamDisplayName ?? a.upstreamEndpointId }}</strong>
        <el-tag :type="COLOR[a.resultCategory]" size="small" effect="plain">
          {{ LABEL[a.resultCategory] ?? a.resultCategory }}
        </el-tag>
        <el-tag v-if="a.upstreamStatusCode" size="small" type="info">
          HTTP {{ a.upstreamStatusCode }}
        </el-tag>
        <span v-if="a.durationMs !== null && a.durationMs !== undefined" class="muted">
          {{ a.durationMs }}ms
        </span>
        <el-tag v-if="a.retryable" size="small" type="warning" effect="plain">可重试</el-tag>
      </div>
      <div class="muted mono">模型 {{ a.upstreamModelName ?? '—' }}</div>
      <div v-if="a.sanitizedError" class="err">{{ a.sanitizedError }}</div>
    </el-timeline-item>
  </el-timeline>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.idx {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.err {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-color-danger);
}
</style>
