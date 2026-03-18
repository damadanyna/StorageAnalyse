import { ref } from 'vue'

export function useMFT() {
  const folders  = ref([])
  const loading  = ref(false)
  const error    = ref(null)

  async function scan(drive = 'C', depth = null) {
    loading.value = true
    error.value   = null
    folders.value = []

    try {
      // window.mftAPI exposé par le preload
      folders.value = await window.mftAPI.scan(drive, depth)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { folders, loading, error, scan }
}
