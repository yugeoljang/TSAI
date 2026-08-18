<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createModel,
  createPrice,
  deleteModel,
  deletePrice,
  listModels,
  listPriceHistory,
  listPrices,
  listProviders,
  updateModel,
} from '@/api/catalog'
import { ApiError } from '@/api/http'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import PriceCell from '@/components/PriceCell.vue'
import SourceLink from '@/components/SourceLink.vue'
import type { ModelCatalogEntry, PriceSnapshot, Provider } from '@/types/api'

interface Row extends ModelCatalogEntry {
  providerName: string
  price?: PriceSnapshot
}

const providers = ref<Provider[]>([])
const models = ref<ModelCatalogEntry[]>([])
const prices = ref<PriceSnapshot[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const providerFilter = ref('')
const keyword = ref('')
const showDisabled = ref(false)

const modelDialog = ref(false)
const modelEditing = ref<ModelCatalogEntry | null>(null)
const modelSaving = ref(false)
const modelForm = reactive({
  providerId: '', upstreamModelId: '', displayName: '', contextWindow: null as number | null,
  sourceUrl: '', verifiedAt: '', enabled: true,
})

const priceDialog = ref(false)
const priceModel = ref<ModelCatalogEntry | null>(null)
const priceSaving = ref(false)
const priceForm = reactive({
  currency: 'CNY', input: null as number | null, output: null as number | null,
  sourceUrl: '', effectiveFrom: '', verifiedAt: '',
})

const historyDialog = ref(false)
const historyModel = ref<ModelCatalogEntry | null>(null)
const history = ref<PriceSnapshot[]>([])
const historyLoading = ref(false)

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.friendly : fallback
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const result = await Promise.all([
      listProviders(), listModels({ includeDisabled: true }), listPrices(),
    ])
    providers.value = result[0]
    models.value = result[1]
    prices.value = result[2]
  } catch (e) {
    error.value = messageOf(e, '加载模型价格失败')
  } finally {
    loading.value = false
  }
}

const rows = computed<Row[]>(() => {
  const nameOf = new Map(providers.value.map((p) => [p.id, p.name]))
  const priceOf = new Map(prices.value.map((p) => [p.modelCatalogEntryId, p]))
  const term = keyword.value.trim().toLowerCase()
  return models.value
    .filter((m) => !providerFilter.value || m.providerId === providerFilter.value)
    .filter((m) => showDisabled.value || m.enabled)
    .filter((m) => !term || `${m.displayName} ${m.upstreamModelId}`.toLowerCase().includes(term))
    .map((m) => ({ ...m, providerName: nameOf.get(m.providerId) ?? m.providerId, price: priceOf.get(m.id) }))
})

const missingCount = computed(() => rows.value.filter((r) => !r.price).length)
const staleCount = computed(() => rows.value.filter((r) => {
  const verified = r.price?.verifiedAt ?? r.verifiedAt
  if (!verified) return true
  const age = Date.now() - new Date(verified).getTime()
  return !Number.isFinite(age) || age > 30 * 86400000
}).length)

function openModel(row?: ModelCatalogEntry) {
  modelEditing.value = row ?? null
  Object.assign(modelForm, {
    providerId: row?.providerId ?? providers.value[0]?.id ?? '',
    upstreamModelId: row?.upstreamModelId ?? '',
    displayName: row?.displayName ?? '',
    contextWindow: row?.contextWindow ?? null,
    sourceUrl: row?.sourceUrl ?? providers.value.find((p) => p.id === (row?.providerId ?? providers.value[0]?.id))?.pricingUrl ?? '',
    verifiedAt: row?.verifiedAt ?? today(), enabled: row?.enabled ?? true,
  })
  modelDialog.value = true
}

async function saveModel() {
  if (!modelForm.providerId || !modelForm.upstreamModelId.trim() || !modelForm.displayName.trim()
    || !modelForm.sourceUrl.trim() || !modelForm.verifiedAt) {
    return ElMessage.warning('请填写供应商、模型 ID、名称、来源和核验日期')
  }
  modelSaving.value = true
  try {
    const payload = {
      upstreamModelId: modelForm.upstreamModelId.trim(), displayName: modelForm.displayName.trim(),
      contextWindow: modelForm.contextWindow, sourceUrl: modelForm.sourceUrl.trim(),
      verifiedAt: modelForm.verifiedAt, enabled: modelForm.enabled,
    }
    if (modelEditing.value) await updateModel(modelEditing.value.id, payload)
    else await createModel({ providerId: modelForm.providerId, ...payload })
    modelDialog.value = false
    ElMessage.success(modelEditing.value ? '模型已更新' : '模型已添加')
    await load()
  } catch (e) {
    ElMessage.error(messageOf(e, '保存模型失败'))
  } finally {
    modelSaving.value = false
  }
}

async function removeModel(row: ModelCatalogEntry) {
  try {
    await ElMessageBox.confirm(`删除模型「${row.displayName}」？其价格历史也会一并删除。`, '确认删除', { type: 'warning' })
    await deleteModel(row.id)
    ElMessage.success('模型已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(messageOf(e, '删除失败'))
  }
}

function openPrice(row: Row) {
  priceModel.value = row
  Object.assign(priceForm, {
    currency: row.price?.currency ?? 'CNY', input: row.price?.inputPricePerMillionTokens ?? null,
    output: row.price?.outputPricePerMillionTokens ?? null,
    sourceUrl: row.price?.sourceUrl ?? row.sourceUrl ?? '', effectiveFrom: today(), verifiedAt: today(),
  })
  priceDialog.value = true
}

async function savePrice() {
  if (!priceModel.value) return
  if (priceForm.input === null && priceForm.output === null) return ElMessage.warning('输入价和输出价至少填写一项')
  if (!priceForm.sourceUrl.trim() || !priceForm.effectiveFrom || !priceForm.verifiedAt) {
    return ElMessage.warning('请填写来源、生效日期和核验日期')
  }
  priceSaving.value = true
  try {
    await createPrice({
      modelCatalogEntryId: priceModel.value.id, currency: priceForm.currency.toUpperCase(),
      inputPricePerMillionTokens: priceForm.input, outputPricePerMillionTokens: priceForm.output,
      sourceUrl: priceForm.sourceUrl.trim(), effectiveFrom: priceForm.effectiveFrom, verifiedAt: priceForm.verifiedAt,
    })
    priceDialog.value = false
    ElMessage.success('新价格快照已发布，旧价格已进入历史')
    await load()
  } catch (e) {
    ElMessage.error(messageOf(e, '保存价格失败'))
  } finally {
    priceSaving.value = false
  }
}

async function openHistory(row: Row) {
  historyModel.value = row
  history.value = []
  historyDialog.value = true
  historyLoading.value = true
  try { history.value = await listPriceHistory(row.id) }
  catch (e) { ElMessage.error(messageOf(e, '读取价格历史失败')) }
  finally { historyLoading.value = false }
}

async function removeSnapshot(item: PriceSnapshot) {
  try {
    await ElMessageBox.confirm('删除该价格快照？删除当前价格时会恢复上一版本。', '确认删除', { type: 'warning' })
    await deletePrice(item.id)
    if (historyModel.value) history.value = await listPriceHistory(historyModel.value.id)
    await load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(messageOf(e, '删除失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader title="模型与价格" desc="维护模型目录和可追溯价格快照。所有价格均为每 100 万 tokens。">
      <template #actions>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="openModel()">添加模型</el-button>
      </template>
    </PageHeader>

    <div class="filters">
      <el-select v-model="providerFilter" placeholder="全部供应商" clearable style="width: 180px">
        <el-option v-for="p in providers" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="keyword" clearable placeholder="搜索模型名称或模型 ID" style="width: 260px" />
      <el-checkbox v-model="showDisabled">显示已停用模型</el-checkbox>
    </div>

    <el-alert v-if="missingCount > 0 && !loading && !error" type="info" show-icon :closable="false" class="notice"
      :title="`有 ${missingCount} 个模型暂无价格数据，表中以「—」表示，不代表免费。`" />
    <el-alert v-if="staleCount > 0 && !loading && !error" type="warning" show-icon :closable="false" class="notice"
      :title="`有 ${staleCount} 个模型超过 30 天未核验或缺少核验时间，请打开官方来源确认。`" />

    <AsyncSection :loading="loading" :error="error" :empty="rows.length === 0" @retry="load">
      <el-table :data="rows" border stripe>
        <el-table-column label="状态" width="78"><template #default="{ row }: { row: Row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template></el-table-column>
        <el-table-column prop="providerName" label="供应商" width="120" />
        <el-table-column label="模型" min-width="210"><template #default="{ row }: { row: Row }">
          <div>{{ row.displayName }}</div><div class="muted mono">{{ row.upstreamModelId }}</div>
        </template></el-table-column>
        <el-table-column label="上下文" width="95" align="right"><template #default="{ row }: { row: Row }">
          {{ row.contextWindow ? `${Math.round(row.contextWindow / 1000)}K` : '—' }}
        </template></el-table-column>
        <el-table-column label="输入价 / 1M" width="115" align="right"><template #default="{ row }: { row: Row }">
          <PriceCell :value="row.price?.inputPricePerMillionTokens" :currency="row.price?.currency" />
        </template></el-table-column>
        <el-table-column label="输出价 / 1M" width="115" align="right"><template #default="{ row }: { row: Row }">
          <PriceCell :value="row.price?.outputPricePerMillionTokens" :currency="row.price?.currency" />
        </template></el-table-column>
        <el-table-column label="来源 / 核对时间" width="150"><template #default="{ row }: { row: Row }">
          <SourceLink :url="row.price?.sourceUrl ?? row.sourceUrl" :verified-at="row.price?.verifiedAt ?? row.verifiedAt" />
        </template></el-table-column>
        <el-table-column label="操作" width="245" fixed="right"><template #default="{ row }: { row: Row }">
          <el-button link type="primary" @click="openPrice(row)">{{ row.price ? '更新价格' : '添加价格' }}</el-button>
          <el-button link @click="openHistory(row)">历史</el-button>
          <el-button link @click="openModel(row)">编辑</el-button>
          <el-button link type="danger" @click="removeModel(row)">删除</el-button>
        </template></el-table-column>
      </el-table>
    </AsyncSection>

    <el-dialog v-model="modelDialog" :title="modelEditing ? '编辑模型' : '添加模型'" width="560px">
      <el-form label-width="100px">
        <el-form-item label="供应商" required><el-select v-model="modelForm.providerId" :disabled="!!modelEditing" style="width: 100%">
          <el-option v-for="p in providers" :key="p.id" :label="p.name" :value="p.id" />
        </el-select></el-form-item>
        <el-form-item label="模型 ID" required><el-input v-model="modelForm.upstreamModelId" placeholder="如 deepseek-chat" /></el-form-item>
        <el-form-item label="显示名称" required><el-input v-model="modelForm.displayName" /></el-form-item>
        <el-form-item label="上下文窗口"><el-input-number v-model="modelForm.contextWindow" :min="1" style="width: 100%" /></el-form-item>
        <el-form-item label="官方来源" required><el-input v-model="modelForm.sourceUrl" placeholder="https://..." /></el-form-item>
        <el-form-item label="核验日期" required><el-date-picker v-model="modelForm.verifiedAt" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="modelForm.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="modelDialog=false">取消</el-button><el-button type="primary" :loading="modelSaving" @click="saveModel">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="priceDialog" :title="`发布价格快照 · ${priceModel?.displayName ?? ''}`" width="560px">
      <el-alert title="保存后不会覆盖历史记录，旧价格会自动归档。" type="info" :closable="false" class="notice" />
      <el-form label-width="110px">
        <el-form-item label="币种" required><el-select v-model="priceForm.currency" style="width: 100%"><el-option label="CNY" value="CNY" /><el-option label="USD" value="USD" /><el-option label="EUR" value="EUR" /></el-select></el-form-item>
        <el-form-item label="输入价 / 1M"><el-input-number v-model="priceForm.input" :min="0" :precision="6" style="width: 100%" /></el-form-item>
        <el-form-item label="输出价 / 1M"><el-input-number v-model="priceForm.output" :min="0" :precision="6" style="width: 100%" /></el-form-item>
        <el-form-item label="官方来源" required><el-input v-model="priceForm.sourceUrl" placeholder="https://..." /></el-form-item>
        <el-form-item label="生效日期" required><el-date-picker v-model="priceForm.effectiveFrom" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="核验日期" required><el-date-picker v-model="priceForm.verifiedAt" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="priceDialog=false">取消</el-button><el-button type="primary" :loading="priceSaving" @click="savePrice">发布快照</el-button></template>
    </el-dialog>

    <el-drawer v-model="historyDialog" :title="`价格历史 · ${historyModel?.displayName ?? ''}`" size="620px">
      <el-table v-loading="historyLoading" :data="history" border>
        <el-table-column label="版本" width="75"><template #default="{ row }: { row: PriceSnapshot }"><el-tag v-if="row.isCurrent" type="success" size="small">当前</el-tag><span v-else class="muted">历史</span></template></el-table-column>
        <el-table-column label="输入 / 输出" min-width="145"><template #default="{ row }: { row: PriceSnapshot }">{{ row.currency }} {{ row.inputPricePerMillionTokens ?? '—' }} / {{ row.outputPricePerMillionTokens ?? '—' }}</template></el-table-column>
        <el-table-column prop="effectiveFrom" label="生效时间" width="115" />
        <el-table-column prop="verifiedAt" label="核验时间" width="115" />
        <el-table-column label="操作" width="70"><template #default="{ row }: { row: PriceSnapshot }"><el-button link type="danger" @click="removeSnapshot(row)">删除</el-button></template></el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.notice { margin-bottom: 12px; }
</style>
