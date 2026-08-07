<script setup lang="ts">
defineProps<{ title: string; desc?: string }>()
</script>

<template>
  <header class="ph">
    <div>
      <h2>{{ title }}</h2>
      <p v-if="desc" class="desc">{{ desc }}</p>
    </div>
    <div class="actions"><slot name="actions" /></div>
  </header>
</template>

<style scoped>
.ph {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.actions {
  flex-shrink: 0;
}
</style>
