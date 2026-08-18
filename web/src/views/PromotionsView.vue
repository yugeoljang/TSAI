<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createPromotion, deletePromotion, listPromotions, listProviders, updatePromotion } from '@/api/catalog'
import { ApiError } from '@/api/http'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import SourceLink from '@/components/SourceLink.vue'
import type {
  Promotion, PromotionLifecycleStatus, PromotionStatus, PromotionType, Provider,
} from '@/types/api'

const TYPE_LABEL: Record<PromotionType, string> = { discount: '折扣', credit: '赠送额度', price_change: '价格调整' }
const TYPE_COLOR: Record<PromotionType, 'danger' | 'success' | 'warning'> = { discount: 'danger', credit: 'success', price_change: 'warning' }
const LIFE_LABEL: Record<PromotionLifecycleStatus, string> = { draft: '待核验', upcoming: '未开始', active: '进行中', expired: '已过期' }
const LIFE_COLOR: Record<PromotionLifecycleStatus, 'info' | 'primary' | 'success' | 'warning'> = { draft: 'info', upcoming: 'primary', active: 'success', expired: 'warning' }

const providers = ref<Provider[]>([])
const promotions = ref<Promotion[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const providerFilter = ref('')
const typeFilter = ref<PromotionType | ''>('')
const lifecycleFilter = ref<PromotionLifecycleStatus | ''>('')
const keyword = ref('')

const dialog = ref(false)
const editing = ref<Promotion | null>(null)
const saving = ref(false)
const form = reactive({
  providerId: '', title: '', type: 'discount' as PromotionType, description: '', sourceUrl: '',
  startsAt: '', endsAt: '', status: 'draft' as PromotionStatus, verifiedAt: '',
})

function messageOf(e: unknown, fallback: string): string { return e instanceof ApiError ? e.friendly : fallback }
function nowIso(): string { return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z') }

async function load() {
  loading.value = true
  error.value = null
  try {
    const [providerData, promotionData] = await Promise.all([listProviders(), listPromotions()])
    providers.value = providerData
    promotions.value = promotionData
  } catch (e) { error.value = messageOf(e, '加载活动失败') }
  finally { loading.value = false }
}

const nameOf = computed(() => new Map(providers.value.map((p) => [p.id, p.name])))
const rows = computed(() => {
  const term = keyword.value.trim().toLowerCase()
  return promotions.value
    .filter((p) => !providerFilter.value || p.providerId === providerFilter.value)
    .filter((p) => !typeFilter.value || p.type === typeFilter.value)
    .filter((p) => !lifecycleFilter.value || p.lifecycleStatus === lifecycleFilter.value)
    .filter((p) => !term || `${p.title} ${p.description ?? ''}`.toLowerCase().includes(term))
})
const counts = computed(() => ({
  active: promotions.value.filter((p) => p.lifecycleStatus === 'active').length,
  upcoming: promotions.value.filter((p) => p.lifecycleStatus === 'upcoming').length,
  draft: promotions.value.filter((p) => p.lifecycleStatus === 'draft').length,
  expired: promotions.value.filter((p) => p.lifecycleStatus === 'expired').length,
}))

function open(row?: Promotion) {
  editing.value = row ?? null
  Object.assign(form, {
    providerId: row?.providerId ?? providers.value[0]?.id ?? '', title: row?.title ?? '',
    type: row?.type ?? 'discount', description: row?.description ?? '', sourceUrl: row?.sourceUrl ?? '',
    startsAt: row?.startsAt ?? '', endsAt: row?.endsAt ?? '', status: row?.status ?? 'draft',
    verifiedAt: row?.verifiedAt ?? '',
  })
  dialog.value = true
}

function fillVerificationTime() {
  if (form.status === 'verified' && !form.verifiedAt) form.verifiedAt = nowIso()
}

async function save() {
  if (!form.providerId || !form.title.trim()) return ElMessage.warning('请填写供应商和活动标题')
  if (form.status === 'verified' && (!form.sourceUrl.trim() || !form.startsAt || !form.endsAt || !form.verifiedAt)) {
    return ElMessage.warning('发布为已验证活动时，必须填写来源、有效期和核验时间')
  }
  saving.value = true
  try {
    const payload = {
      providerId: form.providerId, title: form.title.trim(), type: form.type,
      description: form.description.trim() || null, sourceUrl: form.sourceUrl.trim() || null,
      startsAt: form.startsAt || null, endsAt: form.endsAt || null,
      status: form.status, verifiedAt: form.verifiedAt || null,
    }
    if (editing.value) await updatePromotion(editing.value.id, payload)
    else await createPromotion(payload)
    dialog.value = false
    ElMessage.success(editing.value ? '活动已更新' : '活动已添加')
    await load()
  } catch (e) { ElMessage.error(messageOf(e, '保存活动失败')) }
  finally { saving.value = false }
}

async function remove(row: Promotion) {
  try {
    await ElMessageBox.confirm(`删除活动「${row.title}」？`, '确认删除', { type: 'warning' })
    await deletePromotion(row.id)
    ElMessage.success('活动已删除')
    await load()
  } catch (e) { if (e !== 'cancel' && e !== 'close') ElMessage.error(messageOf(e, '删除失败')) }
}

function fmtRange(p: Promotion): string {
  const d = (s?: string | null) => (s ? s.slice(0, 10) : '不限')
  return `${d(p.startsAt)} ~ ${d(p.endsAt)}`
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader title="活动信息" desc="维护折扣、赠送额度和价格调整，并区分待核验、未开始、进行中和已过期。">
      <template #actions><el-button @click="load">刷新</el-button><el-button type="primary" @click="open()">添加活动</el-button></template>
    </PageHeader>

    <div class="summary">
      <el-tag type="success">进行中 {{ counts.active }}</el-tag>
      <el-tag type="primary">未开始 {{ counts.upcoming }}</el-tag>
      <el-tag type="info">待核验 {{ counts.draft }}</el-tag>
      <el-tag type="warning">已过期 {{ counts.expired }}</el-tag>
    </div>
    <div class="filters">
      <el-select v-model="providerFilter" placeholder="全部供应商" clearable style="width: 170px"><el-option v-for="p in providers" :key="p.id" :label="p.name" :value="p.id" /></el-select>
      <el-select v-model="typeFilter" placeholder="全部类型" clearable style="width: 150px"><el-option v-for="(label, key) in TYPE_LABEL" :key="key" :label="label" :value="key" /></el-select>
      <el-select v-model="lifecycleFilter" placeholder="全部状态" clearable style="width: 150px"><el-option v-for="(label, key) in LIFE_LABEL" :key="key" :label="label" :value="key" /></el-select>
      <el-input v-model="keyword" placeholder="搜索标题或说明" clearable style="width: 240px" />
    </div>

    <AsyncSection :loading="loading" :error="error" :empty="rows.length === 0" empty-text="没有符合条件的活动" @retry="load">
      <el-table :data="rows" border stripe>
        <el-table-column label="状态" width="100"><template #default="{ row }: { row: Promotion }"><el-tag :type="LIFE_COLOR[row.lifecycleStatus]" size="small" :effect="row.active ? 'dark' : 'light'">{{ LIFE_LABEL[row.lifecycleStatus] }}</el-tag></template></el-table-column>
        <el-table-column label="供应商" width="125"><template #default="{ row }: { row: Promotion }">{{ nameOf.get(row.providerId) ?? row.providerId }}</template></el-table-column>
        <el-table-column label="类型" width="110"><template #default="{ row }: { row: Promotion }"><el-tag :type="TYPE_COLOR[row.type]" size="small" effect="plain">{{ TYPE_LABEL[row.type] }}</el-tag></template></el-table-column>
        <el-table-column label="活动" min-width="280"><template #default="{ row }: { row: Promotion }"><div>{{ row.title }}</div><div class="muted">{{ row.description || '—' }}</div></template></el-table-column>
        <el-table-column label="有效期" width="190"><template #default="{ row }: { row: Promotion }"><span class="mono">{{ fmtRange(row) }}</span></template></el-table-column>
        <el-table-column label="来源 / 核对时间" width="155"><template #default="{ row }: { row: Promotion }"><SourceLink :url="row.sourceUrl" :verified-at="row.verifiedAt" /></template></el-table-column>
        <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }: { row: Promotion }"><el-button link type="primary" @click="open(row)">编辑</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
      </el-table>
    </AsyncSection>

    <el-dialog v-model="dialog" :title="editing ? '编辑活动' : '添加活动'" width="620px">
      <el-form label-width="100px">
        <el-form-item label="供应商" required><el-select v-model="form.providerId" style="width: 100%"><el-option v-for="p in providers" :key="p.id" :label="p.name" :value="p.id" /></el-select></el-form-item>
        <el-form-item label="活动标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="类型" required><el-select v-model="form.type" style="width: 100%"><el-option v-for="(label, key) in TYPE_LABEL" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="官方来源" :required="form.status === 'verified'"><el-input v-model="form.sourceUrl" placeholder="https://..." /></el-form-item>
        <el-form-item label="开始时间" :required="form.status === 'verified'"><el-date-picker v-model="form.startsAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss[Z]" style="width: 100%" /></el-form-item>
        <el-form-item label="结束时间" :required="form.status === 'verified'"><el-date-picker v-model="form.endsAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss[Z]" style="width: 100%" /></el-form-item>
        <el-form-item label="发布状态" required><el-radio-group v-model="form.status" @change="fillVerificationTime"><el-radio value="draft">待核验草稿</el-radio><el-radio value="verified">已核验发布</el-radio><el-radio value="expired">手动结束</el-radio></el-radio-group></el-form-item>
        <el-form-item label="核验时间" :required="form.status === 'verified'"><el-input v-model="form.verifiedAt" placeholder="2026-08-18T12:00:00Z" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.summary, .filters { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
</style>
