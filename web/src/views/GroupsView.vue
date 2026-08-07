<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addMember,
  createGroup,
  deleteGroup,
  getGroup,
  listGroups,
  removeMember,
  reorderMembers,
  updateGroup,
  updateMember,
} from '@/api/groups'
import { listUpstreams } from '@/api/catalog'
import { ApiError } from '@/api/http'
import { useAsync } from '@/composables/useAsync'
import AsyncSection from '@/components/AsyncSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import type { ApiGroup, ApiGroupDetail, ApiGroupMember, UpstreamEndpoint } from '@/types/api'

const { data, loading, error, run } = useAsync(
  async () => {
    const [groups, upstreams] = await Promise.all([listGroups(), listUpstreams()])
    return { groups, upstreams }
  },
  { groups: [] as ApiGroup[], upstreams: [] as UpstreamEndpoint[] },
)

const selectedId = ref<string | null>(null)
const detail = ref<ApiGroupDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref<string | null>(null)

function report(e: unknown, fallback: string) {
  ElMessage.error(e instanceof ApiError ? e.friendly : fallback)
}

async function loadDetail(id: string) {
  selectedId.value = id
  detailLoading.value = true
  detailError.value = null
  try {
    detail.value = await getGroup(id)
  } catch (e) {
    detail.value = null
    detailError.value = e instanceof ApiError ? e.friendly : '加载分组详情失败'
  } finally {
    detailLoading.value = false
  }
}

async function refreshAll() {
  await run()
  if (selectedId.value && data.value.groups.some((g) => g.id === selectedId.value)) {
    await loadDetail(selectedId.value)
  } else {
    selectedId.value = data.value.groups[0]?.id ?? null
    detail.value = null
    if (selectedId.value) await loadDetail(selectedId.value)
  }
}

// ---------------- 分组表单 ----------------

const groupDialog = ref(false)
const groupEditing = ref<ApiGroup | null>(null)
const groupSaving = ref(false)
const routeKeyError = ref('') // 409 冲突的专门提示
const groupForm = reactive({ name: '', routeKey: '', maxAttempts: 3, enabled: true })

function openGroup(g?: ApiGroup) {
  groupEditing.value = g ?? null
  routeKeyError.value = ''
  Object.assign(groupForm, {
    name: g?.name ?? '',
    routeKey: g?.routeKey ?? '',
    maxAttempts: g?.maxAttempts ?? 3,
    enabled: g?.enabled ?? true,
  })
  groupDialog.value = true
}

async function saveGroup() {
  routeKeyError.value = ''
  if (!groupForm.name.trim()) return ElMessage.warning('请填写分组名称')
  if (!groupEditing.value && !groupForm.routeKey.trim()) return ElMessage.warning('请填写 routeKey')

  groupSaving.value = true
  try {
    if (groupEditing.value) {
      // routeKey 创建后不可改（后端 ApiGroupUpdate 也不含该字段）
      await updateGroup(groupEditing.value.id, {
        name: groupForm.name.trim(),
        maxAttempts: groupForm.maxAttempts,
        enabled: groupForm.enabled,
      })
    } else {
      const created = await createGroup({
        name: groupForm.name.trim(),
        routeKey: groupForm.routeKey.trim(),
        maxAttempts: groupForm.maxAttempts,
        enabled: groupForm.enabled,
      })
      selectedId.value = created.id
    }
    ElMessage.success('已保存')
    groupDialog.value = false
    await refreshAll()
  } catch (e) {
    // 409 是 routeKey 被占用，给出定位到字段的提示而非笼统报错
    if (e instanceof ApiError && e.code === 409) {
      routeKeyError.value = e.message || '该 routeKey 已被占用，请换一个'
    } else {
      report(e, '保存分组失败')
    }
  } finally {
    groupSaving.value = false
  }
}

async function removeGroup(g: ApiGroup) {
  try {
    await ElMessageBox.confirm(`确定删除分组「${g.name}」及其全部成员？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteGroup(g.id)
    if (selectedId.value === g.id) selectedId.value = null
    ElMessage.success('已删除')
    await refreshAll()
  } catch (e) {
    report(e, '删除失败')
  }
}

// ---------------- 成员 ----------------

const memberDialog = ref(false)
const memberSaving = ref(false)
const memberForm = reactive({ upstreamEndpointId: '', upstreamModelName: '' })

/** 已在本分组里的上游不再重复列出 */
const availableUpstreams = computed(() => {
  const used = new Set(detail.value?.members.map((m) => m.upstreamEndpointId) ?? [])
  return data.value.upstreams.filter((u) => !used.has(u.id))
})

function openMember() {
  const first = availableUpstreams.value[0]
  memberForm.upstreamEndpointId = first?.id ?? ''
  memberForm.upstreamModelName = first?.defaultModel ?? ''
  memberDialog.value = true
}

/** 选中上游后，自动带出它的默认模型，省去手打 */
function onPickUpstream(id: string) {
  const u = data.value.upstreams.find((x) => x.id === id)
  if (u?.defaultModel && !memberForm.upstreamModelName) {
    memberForm.upstreamModelName = u.defaultModel
  }
}

async function saveMember() {
  if (!memberForm.upstreamEndpointId) return ElMessage.warning('请选择上游')
  if (!memberForm.upstreamModelName.trim()) return ElMessage.warning('请填写上游真实模型名')
  memberSaving.value = true
  try {
    await addMember(selectedId.value!, {
      upstreamEndpointId: memberForm.upstreamEndpointId,
      upstreamModelName: memberForm.upstreamModelName.trim(),
    })
    ElMessage.success('已加入分组')
    memberDialog.value = false
    memberForm.upstreamModelName = ''
    await loadDetail(selectedId.value!)
  } catch (e) {
    report(e, '添加成员失败')
  } finally {
    memberSaving.value = false
  }
}

/**
 * 上移 / 下移。拖拽排序是 P1，本周不做。
 * 提交后用后端返回的数组重渲染，不做本地臆测。
 */
async function move(index: number, delta: number) {
  const members = detail.value?.members ?? []
  const target = index + delta
  if (target < 0 || target >= members.length) return

  const ids = members.map((m) => m.id)
  ;[ids[index], ids[target]] = [ids[target], ids[index]]

  try {
    const sorted = await reorderMembers(selectedId.value!, ids)
    detail.value = { ...detail.value!, members: sorted }
  } catch (e) {
    report(e, '调整顺序失败')
    await loadDetail(selectedId.value!)
  }
}

async function toggleMember(m: ApiGroupMember, enabled: boolean) {
  try {
    await updateMember(selectedId.value!, m.id, { enabled })
    await loadDetail(selectedId.value!)
  } catch (e) {
    report(e, '切换成员状态失败')
    await loadDetail(selectedId.value!)
  }
}

async function dropMember(m: ApiGroupMember) {
  try {
    await ElMessageBox.confirm(`将「${m.upstreamDisplayName}」移出分组？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await removeMember(selectedId.value!, m.id)
    ElMessage.success('已移出')
    await loadDetail(selectedId.value!)
  } catch (e) {
    report(e, '移出失败')
  }
}

async function copyRouteKey(key: string) {
  try {
    await navigator.clipboard.writeText(key)
    ElMessage.success(`已复制 routeKey：${key}`)
  } catch {
    ElMessage.warning('复制失败，请手动选择文本')
  }
}

onMounted(async () => {
  await run()
  if (data.value.groups.length > 0) await loadDetail(data.value.groups[0].id)
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="API 分组"
      desc="分组内按优先级从上到下依次尝试：上游超时 / 429 / 5xx 时自动切换下一个，400 / 422 参数错误则不切换。"
    >
      <template #actions>
        <el-button type="primary" @click="openGroup()">创建分组</el-button>
      </template>
    </PageHeader>

    <AsyncSection :loading="loading" :error="error" @retry="run">
      <el-empty v-if="data.groups.length === 0" description="还没有分组，先创建一个用于演示（如 demo-route）" />

      <el-row v-else :gutter="16">
        <!-- 分组列表 -->
        <el-col :span="7">
          <el-card shadow="never">
            <template #header>分组（{{ data.groups.length }}）</template>
            <div
              v-for="g in data.groups"
              :key="g.id"
              class="g-item"
              :class="{ active: g.id === selectedId }"
              @click="loadDetail(g.id)"
            >
              <div class="g-main">
                <div class="g-name">
                  {{ g.name }}
                  <el-tag v-if="!g.enabled" type="info" size="small">已停用</el-tag>
                </div>
                <div class="mono muted">{{ g.routeKey }}</div>
              </div>
              <el-button link type="danger" size="small" @click.stop="removeGroup(g)">删除</el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 分组详情 -->
        <el-col :span="17">
          <el-card shadow="never">
            <template #header>
              <div class="d-head">
                <span>{{ detail ? `成员 · ${detail.name}` : '成员' }}</span>
                <div v-if="detail">
                  <el-button size="small" @click="openGroup(detail)">编辑分组</el-button>
                  <el-button
                    type="primary"
                    size="small"
                    :disabled="availableUpstreams.length === 0"
                    @click="openMember"
                  >
                    添加成员
                  </el-button>
                </div>
              </div>
            </template>

            <AsyncSection :loading="detailLoading" :error="detailError" @retry="loadDetail(selectedId!)">
              <template v-if="detail">
                <el-descriptions :column="3" border size="small" class="meta">
                  <el-descriptions-item label="routeKey">
                    <span class="mono">{{ detail.routeKey }}</span>
                    <el-button link type="primary" size="small" @click="copyRouteKey(detail.routeKey)">
                      复制
                    </el-button>
                  </el-descriptions-item>
                  <el-descriptions-item label="最大尝试次数">{{ detail.maxAttempts }}</el-descriptions-item>
                  <el-descriptions-item label="路由策略">顺序故障切换</el-descriptions-item>
                </el-descriptions>

                <el-alert
                  type="info"
                  show-icon
                  :closable="false"
                  class="meta"
                  title="调用时把上面的 routeKey 填进 OpenAI 请求体的 model 字段，网关据此选择本分组。"
                />

                <el-empty
                  v-if="detail.members.length === 0"
                  description="分组内还没有成员。加入两个上游即可演示故障切换。"
                />
                <el-table v-else :data="detail.members" border>
                  <el-table-column label="优先级" width="90" align="center">
                    <template #default="{ $index }">
                      <el-tag :type="$index === 0 ? 'success' : 'info'" size="small">
                        {{ $index + 1 }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="上游" min-width="150">
                    <template #default="{ row }: { row: ApiGroupMember }">
                      {{ row.upstreamDisplayName ?? row.upstreamEndpointId }}
                    </template>
                  </el-table-column>
                  <el-table-column label="上游模型名" min-width="180">
                    <template #default="{ row }: { row: ApiGroupMember }">
                      <span class="mono">{{ row.upstreamModelName }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="启用" width="80">
                    <template #default="{ row }: { row: ApiGroupMember }">
                      <el-switch
                        :model-value="row.enabled"
                        @update:model-value="(v: boolean) => toggleMember(row, v)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="调整顺序" width="150" align="center">
                    <template #default="{ $index }">
                      <el-button-group>
                        <el-button size="small" :disabled="$index === 0" @click="move($index, -1)">
                          上移
                        </el-button>
                        <el-button
                          size="small"
                          :disabled="$index === detail!.members.length - 1"
                          @click="move($index, 1)"
                        >
                          下移
                        </el-button>
                      </el-button-group>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="right">
                    <template #default="{ row }: { row: ApiGroupMember }">
                      <el-button link type="danger" size="small" @click="dropMember(row)">移出</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
            </AsyncSection>
          </el-card>
        </el-col>
      </el-row>
    </AsyncSection>

    <!-- 分组表单 -->
    <el-dialog v-model="groupDialog" :title="groupEditing ? '编辑分组' : '创建分组'" width="480px">
      <el-form label-width="110px">
        <el-form-item label="分组名称" required>
          <el-input v-model="groupForm.name" placeholder="如 演示路由" />
        </el-form-item>
        <el-form-item label="routeKey" required :error="routeKeyError">
          <el-input
            v-model="groupForm.routeKey"
            :disabled="!!groupEditing"
            placeholder="如 demo-route"
            @input="routeKeyError = ''"
          />
          <div class="muted">
            {{ groupEditing ? 'routeKey 创建后不可修改' : '调用时填入 model 字段的值，需全局唯一' }}
          </div>
        </el-form-item>
        <el-form-item label="最大尝试次数">
          <el-input-number v-model="groupForm.maxAttempts" :min="1" :max="5" />
          <div class="muted">防止无限重试</div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="groupForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialog = false">取消</el-button>
        <el-button type="primary" :loading="groupSaving" @click="saveGroup">保存</el-button>
      </template>
    </el-dialog>

    <!-- 成员表单 -->
    <el-dialog v-model="memberDialog" title="添加分组成员" width="520px">
      <el-form label-width="110px">
        <el-form-item label="上游" required>
          <el-select v-model="memberForm.upstreamEndpointId" style="width: 100%" @change="onPickUpstream">
            <el-option v-for="u in availableUpstreams" :key="u.id" :label="u.displayName" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="上游模型名" required>
          <el-input v-model="memberForm.upstreamModelName" placeholder="如 deepseek-chat" />
          <div class="muted">该上游平台上的真实模型 ID，分组会把 routeKey 映射到它。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberDialog = false">取消</el-button>
        <el-button type="primary" :loading="memberSaving" @click="saveMember">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.g-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
}
.g-item:hover {
  background: var(--el-fill-color-light);
}
.g-item.active {
  background: var(--el-color-primary-light-9);
  box-shadow: inset 3px 0 0 var(--el-color-primary);
}
.g-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}
.d-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.meta {
  margin-bottom: 12px;
}
</style>
