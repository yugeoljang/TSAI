<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listPromotions, listProviders } from '@/api/catalog'
import { useAsync } from '@/composables/useAsync'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import SourceLink from '@/components/SourceLink.vue'
import type { Promotion, PromotionType, Provider } from '@/types/api'

const activeOnly = ref(false)

const TYPE_LABEL: Record<PromotionType, string> = {
  discount: '折扣',
  credit: '赠送额度',
  price_change: '价格调整',
}

const TYPE_COLOR: Record<PromotionType, string> = {
  discount: 'danger',
  credit: 'success',
  price_change: 'warning',
}

const { data, loading, error, run } = useAsync(
  async () => {
    const [providers, promotions] = await Promise.all([listProviders(), listPromotions()])
    return { providers, promotions }
  },
  { providers: [] as Provider[], promotions: [] as Promotion[] },
)

const nameOf = computed(() => new Map(data.value.providers.map((p) => [p.id, p.name])))

// active 由后端按当前时间推导，前端只做展示与筛选
const rows = computed(() =>
  activeOnly.value ? data.value.promotions.filter((p) => p.active) : data.value.promotions,
)

const expiredCount = computed(() => data.value.promotions.filter((p) => !p.active).length)

function fmtRange(p: Promotion): string {
  const d = (s?: string | null) => (s ? s.slice(0, 10) : '不限')
  return `${d(p.startsAt)} ~ ${d(p.endsAt)}`
}

onMounted(run)
</script>

<template>
  <div class="page">
    <PageHeader title="活动信息" desc="价格调整与优惠活动。已过期的活动会明确标记，不会伪装成进行中。">
      <template #actions>
        <el-checkbox v-model="activeOnly">只看进行中</el-checkbox>
      </template>
    </PageHeader>

    <el-alert
      v-if="expiredCount > 0 && !activeOnly && !loading && !error"
      type="info"
      show-icon
      :closable="false"
      class="notice"
      :title="`共 ${expiredCount} 条活动已过期，已在列表中标记。`"
    />

    <AsyncSection
      :loading="loading"
      :error="error"
      :empty="rows.length === 0"
      empty-text="没有符合条件的活动"
      @retry="run"
    >
      <el-table :data="rows" border stripe>
        <el-table-column label="状态" width="100">
          <template #default="{ row }: { row: Promotion }">
            <el-tag v-if="row.active" type="success" effect="dark" size="small">进行中</el-tag>
            <el-tag v-else type="info" size="small">已过期</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="供应商" width="130">
          <template #default="{ row }: { row: Promotion }">
            {{ nameOf.get(row.providerId) ?? row.providerId }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }: { row: Promotion }">
            <el-tag :type="TYPE_COLOR[row.type]" size="small" effect="plain">
              {{ TYPE_LABEL[row.type] ?? row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="活动" min-width="280">
          <template #default="{ row }: { row: Promotion }">
            <div :class="{ dim: !row.active }">{{ row.title }}</div>
            <div class="muted">{{ row.description }}</div>
          </template>
        </el-table-column>
        <el-table-column label="有效期" width="200">
          <template #default="{ row }: { row: Promotion }">
            <span class="mono" :class="{ dim: !row.active }">{{ fmtRange(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源 / 核对时间" width="160">
          <template #default="{ row }: { row: Promotion }">
            <SourceLink :url="row.sourceUrl" :verified-at="row.verifiedAt" />
          </template>
        </el-table-column>
      </el-table>
    </AsyncSection>
  </div>
</template>

<style scoped>
.notice {
  margin-bottom: 12px;
}
.dim {
  color: var(--el-text-color-placeholder);
  text-decoration: line-through;
}
</style>
