<script setup lang="ts">
/** 价格单元格。价格缺失时显示「—」，绝不显示 0 —— MVP 验收明写条款。 */
const props = defineProps<{
  value?: number | null
  currency?: string
}>()

const symbol: Record<string, string> = { CNY: '¥', USD: '$' }

function format(v: number): string {
  // 保留有效小数，避免 0.15 被显示成 0.2
  return v < 1 ? v.toFixed(2).replace(/0+$/, '').replace(/\.$/, '') : v.toFixed(2)
}
</script>

<template>
  <span v-if="props.value === null || props.value === undefined" class="missing" title="该模型暂无价格数据">
    —
  </span>
  <span v-else class="price">
    {{ symbol[props.currency ?? ''] ?? '' }}{{ format(props.value) }}
  </span>
</template>

<style scoped>
.missing {
  color: var(--el-text-color-placeholder);
  cursor: help;
}
.price {
  font-variant-numeric: tabular-nums;
}
</style>
