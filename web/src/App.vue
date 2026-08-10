<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { isMockOn, setMockOn } from '@/api/http'
import { NAV } from '@/router'

const route = useRoute()
const mock = ref(isMockOn())

/**
 * 切换 Mock 后整页重载：各页面缓存的数据来自不同数据源，
 * 重载是最不容易出错的做法，也让切换行为对演示者一目了然。
 */
function onToggleMock(val: boolean) {
  setMockOn(val)
  window.location.reload()
}
</script>

<template>
  <el-container class="shell">
    <el-aside width="200px" class="aside">
      <div class="brand">
        <strong>Personal Gateway</strong>
        <span class="brand-sub">Plus 管理端</span>
      </div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item v-for="item in NAV" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="hint">
          调用时把分组的 <code class="mono">routeKey</code> 填进 OpenAI 请求体的
          <code class="mono">model</code> 字段
        </div>
        <div class="switch">
          <span class="switch-label">Mock 模式</span>
          <el-switch v-model="mock" @change="onToggleMock" />
        </div>
      </el-header>

      <el-alert
        v-if="mock"
        type="warning"
        show-icon
        :closable="false"
        class="banner"
        title="当前处于 Mock 模式：数据仅存在于浏览器内存，刷新即重置，未经过真实后端。"
      />

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.shell {
  height: 100%;
}
.aside {
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
}
.brand {
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.brand-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.menu {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
}
.hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.switch {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch-label {
  font-size: 13px;
}
.banner {
  border-radius: 0;
}
.main {
  padding: 0;
  overflow-y: auto;
}
</style>
