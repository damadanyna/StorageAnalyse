import { ref } from 'vue'

export function useMFT() {
  const folders  = ref([])
  const loading  = ref(false)
  const error    = ref(null)
  const scanInfo = ref(null)

  async function scan(drive = 'C', depth = null) {
    loading.value = true
    error.value   = null
    folders.value = []
    scanInfo.value = null

    try {
      // window.mftAPI exposé par le preload
      const result = await window.mftAPI.scan(drive, depth)
      folders.value = result?.summary ?? []
      scanInfo.value = result?.scanInfo ?? null
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { folders, loading, error, scanInfo, scan }
}
