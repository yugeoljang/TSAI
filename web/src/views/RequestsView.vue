<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listAttempts, listRequests } from '@/api/gateway'
import { ApiError } from '@/api/http'
import { useAsync } from '@/composables/useAsync'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import AttemptTimeline from '@/components/AttemptTimeline.vue'
import type { FinalStatus, GatewayRequest, RouteAttempt } from '@/types/api'

const { data, loading, error, run } = useAsync(() => listRequests(20), [] as GatewayRequest[])

// requestId -> 尝试链，展开时按需加载
const attemptsMap = ref<Record<string, RouteAttempt[]>>({})
const attemptsError = ref<Record<string, string>>({})

const STATUS: Record<FinalStatus, { label: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  success: { label: '成功', type: 'success' },
  all_failed: { label: '全部失败', type: 'danger' },
  timeout: { label: '整体超时', type: 'warning' },
  client_error: { label: '参数错误（未切换）', type: 'info' },
}

async function onExpand(row: GatewayRequest, expanded: GatewayRequest[]) {
  if (!expanded.some((r) => r.requestId === row.requestId)) return
  if (attemptsMap.value[row.requestId]) return
  try {
    attemptsMap.value = { ...attemptsMap.value, [row.requestId]: await listAttempts(row.requestId) }
  } catch (e) {
    attemptsError.value = {
      ...attemptsError.value,
      [row.requestId]: e instanceof ApiError ? e.friendly : '加载尝试记录失败',
    }
  }
}

function fmtTime(s?: string | null): string {
  if (!s) return '—'
  return s.replace('T', ' ').replace(/\.\d+/, '').replace('Z', '')
}

onMounted(run)
</script>

<template>
  <div class="page">
    <PageHeader title="路由记录" desc="最近 20 次网关调用。展开任意一行可以查看完整的上游尝试链与切换原因。">
      <template #actions>
        <el-button @click="run">刷新</el-button>
      </template>
    </PageHeader>

    <AsyncSection
      :loading="loading"
      :error="error"
      :empty="data.length === 0"
      empty-text="还没有调用记录。到「调用测试」发送一次请求即可产生。"
      @retry="run"
    >
      <el-table :data="data" border row-key="requestId" @expand-change="onExpand">
        <el-table-column type="expand">
          <template #default="{ row }: { row: GatewayRequest }">
            <div class="expand">
              <el-alert
                v-if="attemptsError[row.requestId]"
                type="error"
                show-icon
                :closable="false"
                :title="attemptsError[row.requestId]"
              />
              <AttemptTimeline
                v-else-if="attemptsMap[row.requestId]?.length"
                :attempts="attemptsMap[row.requestId]"
              />
              <el-skeleton v-else :rows="2" animated />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="{ row }: { row: GatewayRequest }">
            <el-tag v-if="row.finalStatus" :type="STATUS[row.finalStatus]?.type ?? 'info'" size="small">
              {{ STATUS[row.finalStatus]?.label ?? row.finalStatus }}
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="routeKey" min-width="140">
          <template #default="{ row }: { row: GatewayRequest }">
            <span class="mono">{{ row.routeKey }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最终上游" min-width="150">
          <template #default="{ row }: { row: GatewayRequest }">
            <span v-if="row.finalUpstreamDisplayName">{{ row.finalUpstreamDisplayName }}</span>
            <span v-else class="muted">无（未成功）</span>
          </template>
        </el-table-column>
        <el-table-column label="尝试次数" width="100" align="center">
          <template #default="{ row }: { row: GatewayRequest }">
            <el-tag :type="row.attemptCount > 1 ? 'warning' : 'info'" size="small">
              {{ row.attemptCount }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }: { row: GatewayRequest }">
            <span class="mono muted">{{ fmtTime(row.startedAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="请求 ID" min-width="180">
          <template #default="{ row }: { row: GatewayRequest }">
            <span class="mono muted">{{ row.requestId }}</span>
          </template>
        </el-table-column>
      </el-table>
    </AsyncSection>
  </div>
</template>

<style scoped>
.expand {
  padding: 12px 24px;
}
</style>
