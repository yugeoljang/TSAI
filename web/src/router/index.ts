import { createRouter, createWebHistory } from 'vue-router'

// 顺序即左侧导航顺序，也正好是 MVP §8 的演示流程顺序
export const NAV = [
  { path: '/prices', name: 'prices', title: '模型价格', icon: 'Coin' },
  { path: '/promotions', name: 'promotions', title: '活动信息', icon: 'Bell' },
  { path: '/providers', name: 'providers', title: '供应商 / API', icon: 'Connection' },
  { path: '/groups', name: 'groups', title: 'API 分组', icon: 'Files' },
  { path: '/playground', name: 'playground', title: '调用测试', icon: 'ChatDotRound' },
  { path: '/requests', name: 'requests', title: '路由记录', icon: 'Histogram' },
] as const

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/prices' },
    { path: '/prices', name: 'prices', component: () => import('@/views/PricesView.vue') },
    { path: '/promotions', name: 'promotions', component: () => import('@/views/PromotionsView.vue') },
    { path: '/providers', name: 'providers', component: () => import('@/views/ProvidersView.vue') },
    { path: '/groups', name: 'groups', component: () => import('@/views/GroupsView.vue') },
    { path: '/playground', name: 'playground', component: () => import('@/views/PlaygroundView.vue') },
    { path: '/requests', name: 'requests', component: () => import('@/views/RequestsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/prices' },
  ],
})

export default router
