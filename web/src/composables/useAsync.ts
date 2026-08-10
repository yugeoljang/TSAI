import { ref, shallowRef } from 'vue'
import { ApiError } from '@/api/http'

/**
 * 统一的「加载中 / 出错 / 有数据」三态。
 * 每个数据区块都走它，是「任何错误都不出现白屏」这条验收项的实现基础。
 */
export function useAsync<T>(loader: () => Promise<T>, initial: T) {
  const data = shallowRef<T>(initial)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const loaded = ref(false)

  async function run(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await loader()
      loaded.value = true
    } catch (e) {
      error.value = e instanceof ApiError ? e.friendly : (e as Error)?.message || '未知错误'
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, loaded, run }
}
