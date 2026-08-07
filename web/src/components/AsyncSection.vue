<script setup lang="ts">
/**
 * 统一的加载 / 错误 / 空 三态容器。
 * 页面把数据区块包进来，就不会出现白屏或「加载失败后一片空白」。
 */
defineProps<{
  loading: boolean
  error: string | null
  empty?: boolean
  emptyText?: string
}>()

defineEmits<{ retry: [] }>()
</script>

<template>
  <div>
    <el-skeleton v-if="loading" :rows="4" animated />

    <el-alert
      v-else-if="error"
      type="error"
      show-icon
      :closable="false"
      title="加载失败"
      class="err"
    >
      <div class="err-body">
        <span>{{ error }}</span>
        <el-button size="small" @click="$emit('retry')">重试</el-button>
      </div>
    </el-alert>

    <el-empty v-else-if="empty" :description="emptyText ?? '暂无数据'" />

    <slot v-else />
  </div>
</template>

<style scoped>
.err {
  margin: 8px 0;
}
.err-body {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}
</style>
