<script setup lang="ts">
/** 来源链接 + 核对日期。所有价格与活动数据都必须标明出处。 */
defineProps<{
  url?: string | null
  verifiedAt?: string | null
}>()
</script>

<template>
  <div class="source">
    <el-link v-if="url" :href="url" target="_blank" rel="noopener noreferrer" type="primary" :underline="false">
      官方来源
    </el-link>
    <span v-else class="none">无来源</span>
    <span v-if="verifiedAt" class="date">核对于 {{ verifiedAt }}</span>
  </div>
</template>

<style scoped>
.source {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}
.date {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.none {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}
</style>
