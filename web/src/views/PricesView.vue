<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listModels, listPrices, listProviders } from '@/api/catalog'
import { useAsync } from '@/composables/useAsync'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import PriceCell from '@/components/PriceCell.vue'
import SourceLink from '@/components/SourceLink.vue'
import type { ModelCatalogEntry, PriceSnapshot, Provider } from '@/types/api'

interface Row extends ModelCatalogEntry {
  providerName: string
  price?: PriceSnapshot
}

const providerFilter = ref<string>('')

const { data, loading, error, run } = useAsync(
  async () => {
    const [providers, models, prices] = await Promise.all([
      listProviders(),
      listModels(),
      listPrices(),
    ])
    return { providers, models, prices }
  },
  { providers: [] as Provider[], models: [] as ModelCatalogEntry[], prices: [] as PriceSnapshot[] },
)

const rows = computed<Row[]>(() => {
  const { providers, models, prices } = data.value
  const nameOf = new Map(providers.map((p) => [p.id, p.name]))
  // 价格按 modelCatalogEntryId 关联；关联不上就是没有价格，保持 undefined
  const priceOf = new Map(prices.map((p) => [p.modelCatalogEntryId, p]))

  return models
    .filter((m) => !providerFilter.value || m.providerId === providerFilter.value)
    .map((m) => ({
      ...m,
      providerName: nameOf.get(m.providerId) ?? m.providerId,
      price: priceOf.get(m.id),
    }))
})

/** 缺价格的模型数量 —— 明确告知用户，而不是悄悄显示成 0 */
const missingCount = computed(() => rows.value.filter((r) => !r.price).length)

onMounted(run)
</script>

<template>
  <div class="page">
    <PageHeader
      title="模型价格"
      desc="所有单价均为「每 100 万 tokens」。价格会变化，最终以各平台官方页面与控制台结算为准。"
    >
      <template #actions>
        <el-select v-model="providerFilter" placeholder="全部供应商" clearable style="width: 180px">
          <el-option
            v-for="p in data.providers"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
      </template>
    </PageHeader>

    <el-alert
      v-if="missingCount > 0 && !loading && !error"
      type="info"
      show-icon
      :closable="false"
      class="notice"
      :title="`有 ${missingCount} 个模型暂无价格数据，表中以「—」表示，不代表免费。`"
    />

    <AsyncSection :loading="loading" :error="error" :empty="rows.length === 0" @retry="run">
      <el-table :data="rows" border stripe>
        <el-table-column prop="providerName" label="供应商" width="130" />
        <el-table-column label="模型" min-width="220">
          <template #default="{ row }: { row: Row }">
            <div>{{ row.displayName }}</div>
            <div class="muted mono">{{ row.upstreamModelId }}</div>
          </template>
        </el-table-column>
        <el-table-column label="上下文" width="110" align="right">
          <template #default="{ row }: { row: Row }">
            <span v-if="row.contextWindow">{{ (row.contextWindow / 1000).toFixed(0) }}K</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="输入价 / 1M" width="120" align="right">
          <template #default="{ row }: { row: Row }">
            <PriceCell
              :value="row.price?.inputPricePerMillionTokens"
              :currency="row.price?.currency"
            />
          </template>
        </el-table-column>
        <el-table-column label="输出价 / 1M" width="120" align="right">
          <template #default="{ row }: { row: Row }">
            <PriceCell
              :value="row.price?.outputPricePerMillionTokens"
              :currency="row.price?.currency"
            />
          </template>
        </el-table-column>
        <el-table-column label="币种" width="80">
          <template #default="{ row }: { row: Row }">
            <span v-if="row.price">{{ row.price.currency }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="来源 / 核对时间" width="160">
          <template #default="{ row }: { row: Row }">
            <SourceLink
              :url="row.price?.sourceUrl ?? row.sourceUrl"
              :verified-at="row.price?.verifiedAt ?? row.verifiedAt"
            />
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
</style>
