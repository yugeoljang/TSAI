<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createProvider,
  createUpstream,
  deleteProvider,
  deleteUpstream,
  listProviders,
  listUpstreams,
  updateProvider,
  updateUpstream,
} from '@/api/catalog'
import { ApiError } from '@/api/http'
import { useAsync } from '@/composables/useAsync'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import type { Provider, UpstreamEndpoint } from '@/types/api'

const { data, loading, error, run } = useAsync(
  async () => {
    const [providers, upstreams] = await Promise.all([listProviders(), listUpstreams()])
    return { providers, upstreams }
  },
  { providers: [] as Provider[], upstreams: [] as UpstreamEndpoint[] },
)

const nameOf = computed(() => new Map(data.value.providers.map((p) => [p.id, p.name])))

function report(e: unknown, fallback: string) {
  ElMessage.error(e instanceof ApiError ? e.friendly : fallback)
}

// ---------------- 供应商 ----------------

const provDialog = ref(false)
const provEditing = ref<Provider | null>(null)
const provForm = reactive({ name: '', officialUrl: '', pricingUrl: '', enabled: true })
const provSaving = ref(false)

function openProvider(p?: Provider) {
  provEditing.value = p ?? null
  Object.assign(provForm, {
    name: p?.name ?? '',
    officialUrl: p?.officialUrl ?? '',
    pricingUrl: p?.pricingUrl ?? '',
    enabled: p?.enabled ?? true,
  })
  provDialog.value = true
}

async function saveProvider() {
  if (!provForm.name.trim()) return ElMessage.warning('请填写供应商名称')
  provSaving.value = true
  try {
    const payload = {
      name: provForm.name.trim(),
      officialUrl: provForm.officialUrl.trim() || null,
      pricingUrl: provForm.pricingUrl.trim() || null,
      enabled: provForm.enabled,
    }
    if (provEditing.value) await updateProvider(provEditing.value.id, payload)
    else await createProvider(payload)
    ElMessage.success('已保存')
    provDialog.value = false
    await run()
  } catch (e) {
    report(e, '保存供应商失败')
  } finally {
    provSaving.value = false
  }
}

async function toggleProvider(p: Provider, enabled: boolean) {
  try {
    await updateProvider(p.id, { enabled })
    await run()
  } catch (e) {
    report(e, '切换状态失败')
    await run() // 失败时回到服务端真实状态，避免开关显示与后端不一致
  }
}

async function removeProvider(p: Provider) {
  try {
    await ElMessageBox.confirm(`确定删除供应商「${p.name}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteProvider(p.id)
    ElMessage.success('已删除')
    await run()
  } catch (e) {
    report(e, '删除失败')
  }
}

// ---------------- 上游 ----------------

const upDialog = ref(false)
const upEditing = ref<UpstreamEndpoint | null>(null)
const upSaving = ref(false)
const upForm = reactive({
  providerId: '',
  displayName: '',
  baseUrl: '',
  apiKey: '',
  defaultModel: '',
  timeoutMs: 15000,
  enabled: true,
})

function openUpstream(u?: UpstreamEndpoint) {
  upEditing.value = u ?? null
  Object.assign(upForm, {
    providerId: u?.providerId ?? data.value.providers[0]?.id ?? '',
    displayName: u?.displayName ?? '',
    baseUrl: u?.baseUrl ?? '',
    apiKey: '', // 永远从空开始：编辑时留空即代表不修改
    defaultModel: u?.defaultModel ?? '',
    timeoutMs: u?.timeoutMs ?? 15000,
    enabled: u?.enabled ?? true,
  })
  upDialog.value = true
}

/** 非 HTTPS 且非本地地址时给出提示（最终以后端校验为准） */
const baseUrlWarning = computed(() => {
  const v = upForm.baseUrl.trim()
  if (!v) return ''
  const isLocal = /^https?:\/\/(127\.0\.0\.1|localhost|10\.0\.2\.2)(:|\/|$)/.test(v)
  if (!v.startsWith('https://') && !isLocal) return '生产地址建议使用 HTTPS，后端可能拒绝非 HTTPS 地址'
  return ''
})

async function saveUpstream() {
  if (!upForm.displayName.trim()) return ElMessage.warning('请填写显示名称')
  if (!upForm.baseUrl.trim()) return ElMessage.warning('请填写 Base URL')
  if (!upEditing.value && !upForm.apiKey.trim()) return ElMessage.warning('新增上游时 API Key 必填')

  upSaving.value = true
  try {
    if (upEditing.value) {
      // 关键：apiKey 为空时整个字段都不传（api 层会剔除），后端保持原 Key
      await updateUpstream(upEditing.value.id, {
        displayName: upForm.displayName.trim(),
        baseUrl: upForm.baseUrl.trim(),
        apiKey: upForm.apiKey,
        defaultModel: upForm.defaultModel.trim() || null,
        timeoutMs: upForm.timeoutMs,
        enabled: upForm.enabled,
      })
    } else {
      await createUpstream({
        providerId: upForm.providerId,
        displayName: upForm.displayName.trim(),
        baseUrl: upForm.baseUrl.trim(),
        apiKey: upForm.apiKey,
        defaultModel: upForm.defaultModel.trim() || null,
        timeoutMs: upForm.timeoutMs,
        enabled: upForm.enabled,
      })
    }
    ElMessage.success('已保存')
    upDialog.value = false
    await run()
  } catch (e) {
    report(e, '保存上游失败')
  } finally {
    // Key 用完立即从内存清掉，不留在响应式状态里
    upForm.apiKey = ''
    upSaving.value = false
  }
}

async function toggleUpstream(u: UpstreamEndpoint, enabled: boolean) {
  try {
    await updateUpstream(u.id, { enabled })
    await run()
  } catch (e) {
    report(e, '切换状态失败')
    await run()
  }
}

async function removeUpstream(u: UpstreamEndpoint) {
  try {
    await ElMessageBox.confirm(`确定删除上游「${u.displayName}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteUpstream(u.id)
    ElMessage.success('已删除')
    await run()
  } catch (e) {
    report(e, '删除失败')
  }
}

onMounted(run)
</script>

<template>
  <div class="page">
    <PageHeader
      title="供应商 / API 管理"
      desc="上游 API Key 加密保存在后端，界面只显示后四位，接口永不回显明文。"
    />

    <AsyncSection :loading="loading" :error="error" @retry="run">
      <!-- 上游是演示主角，放在前面 -->
      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-head">
            <span>上游 API（{{ data.upstreams.length }}）</span>
            <el-button
              type="primary"
              size="small"
              :disabled="data.providers.length === 0"
              @click="openUpstream()"
            >
              添加上游
            </el-button>
          </div>
        </template>

        <el-empty v-if="data.upstreams.length === 0" description="还没有上游，先添加两个用于演示故障切换" />
        <el-table v-else :data="data.upstreams" border stripe>
          <el-table-column label="显示名称" min-width="160">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <div>{{ row.displayName }}</div>
              <div class="muted">{{ nameOf.get(row.providerId) ?? row.providerId }}</div>
            </template>
          </el-table-column>
          <el-table-column label="Base URL" min-width="230">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <span class="mono">{{ row.baseUrl }}</span>
            </template>
          </el-table-column>
          <el-table-column label="API Key" width="120">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <span class="mono key">••••{{ row.apiKeyLastFour }}</span>
            </template>
          </el-table-column>
          <el-table-column label="默认模型" min-width="150">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <span v-if="row.defaultModel" class="mono">{{ row.defaultModel }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="超时" width="90" align="right">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <span class="mono">{{ row.timeoutMs }}ms</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <el-switch
                :model-value="row.enabled"
                @update:model-value="(v: boolean) => toggleUpstream(row, v)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" align="right">
            <template #default="{ row }: { row: UpstreamEndpoint }">
              <el-button link type="primary" size="small" @click="openUpstream(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="removeUpstream(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="card">
        <template #header>
          <div class="card-head">
            <span>供应商（{{ data.providers.length }}）</span>
            <el-button type="primary" size="small" @click="openProvider()">添加供应商</el-button>
          </div>
        </template>

        <el-table :data="data.providers" border stripe>
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column label="官网" min-width="220">
            <template #default="{ row }: { row: Provider }">
              <el-link v-if="row.officialUrl" :href="row.officialUrl" target="_blank" rel="noopener noreferrer" type="primary">
                {{ row.officialUrl }}
              </el-link>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="协议" width="180">
            <template #default="{ row }: { row: Provider }">
              <el-tag size="small" effect="plain">{{ row.protocolType }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }: { row: Provider }">
              <el-switch
                :model-value="row.enabled"
                @update:model-value="(v: boolean) => toggleProvider(row, v)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" align="right">
            <template #default="{ row }: { row: Provider }">
              <el-button link type="primary" size="small" @click="openProvider(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="removeProvider(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </AsyncSection>

    <!-- 供应商表单 -->
    <el-dialog v-model="provDialog" :title="provEditing ? '编辑供应商' : '添加供应商'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="provForm.name" placeholder="如 DeepSeek" />
        </el-form-item>
        <el-form-item label="官网">
          <el-input v-model="provForm.officialUrl" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="价格页">
          <el-input v-model="provForm.pricingUrl" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="provForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="provDialog = false">取消</el-button>
        <el-button type="primary" :loading="provSaving" @click="saveProvider">保存</el-button>
      </template>
    </el-dialog>

    <!-- 上游表单 -->
    <el-dialog v-model="upDialog" :title="upEditing ? '编辑上游' : '添加上游'" width="560px">
      <el-form label-width="100px">
        <el-form-item label="供应商" required>
          <el-select v-model="upForm.providerId" :disabled="!!upEditing" style="width: 100%">
            <el-option v-for="p in data.providers" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="upForm.displayName" placeholder="如 DeepSeek-主力" />
        </el-form-item>
        <el-form-item label="Base URL" required>
          <el-input v-model="upForm.baseUrl" placeholder="https://api.deepseek.com" />
          <div v-if="baseUrlWarning" class="warn">{{ baseUrlWarning }}</div>
        </el-form-item>
        <el-form-item label="API Key" :required="!upEditing">
          <el-input
            v-model="upForm.apiKey"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="upEditing ? `留空则保持原密钥（当前 ••••${upEditing.apiKeyLastFour}）` : '必填，保存后加密存储'"
          />
          <div class="muted">密钥仅用于本次提交，不会保存在浏览器中。</div>
        </el-form-item>
        <el-form-item label="默认模型">
          <el-input v-model="upForm.defaultModel" placeholder="如 deepseek-chat（可选）" />
        </el-form-item>
        <el-form-item label="超时(ms)">
          <el-input-number v-model="upForm.timeoutMs" :min="1000" :max="120000" :step="1000" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="upForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="upDialog = false">取消</el-button>
        <el-button type="primary" :loading="upSaving" @click="saveUpstream">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card {
  margin-bottom: 16px;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.key {
  letter-spacing: 1px;
}
.warn {
  font-size: 12px;
  color: var(--el-color-warning);
  margin-top: 4px;
}
</style>
