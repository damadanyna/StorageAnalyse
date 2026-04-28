<template>
  <v-container fluid>

    <!-- ── Barre d'actions ── -->
    <v-row align="center" class="mb-4">
      <v-col cols="auto">
        <v-select
          v-model="selectedDrive"
          :items="drives"
          label="Lecteur"
          density="compact"
          variant="outlined"
          hide-details
          style="width: 120px"
        />
      </v-col>
      <v-col cols="auto">
        <v-btn
          color="primary"
          :loading="loading"
          :disabled="loading"
          prepend-icon="mdi-magnify-scan"
          @click="startScan"
        >
          Scanner {{ selectedDrive }}:\
        </v-btn>
      </v-col>
      <v-col cols="auto" v-if="folders.length">
        <v-chip color="success" variant="tonal" size="small">
          {{ folders.length }} dossiers racine
        </v-chip>
      </v-col>
      <v-col cols="auto" v-if="scanInfo">
        <v-chip :color="scanInfoColor" variant="tonal" size="small">
          {{ scanInfoLabel }}
        </v-chip>
      </v-col>
      <v-spacer />
      <v-col cols="auto" v-if="folders.length">
        <v-btn variant="text" size="small" prepend-icon="mdi-expand-all" @click="expandAll">
          Tout ouvrir
        </v-btn>
        <v-btn variant="text" size="small" prepend-icon="mdi-collapse-all" @click="collapseAll">
          Tout fermer
        </v-btn>
      </v-col>
    </v-row>

    <!-- ── Erreur ── -->
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="error = null"
    >
      {{ error }}
    </v-alert>

    <!-- ── Dashboard scan ── -->
    <v-row v-if="isDashboardVisible" justify="center" class="my-8">
      <v-col cols="12" md="9" lg="8">
        <v-card variant="outlined" class="pa-4">
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div class="text-overline text-medium-emphasis">Dashboard d analyse</div>
              <div class="text-h6">{{ loading ? 'Lecture du MFT en cours' : 'Dernier chargement termine' }}</div>
              <div class="text-body-2 text-medium-emphasis">{{ currentProgressMessage }}</div>
            </div>
            <v-progress-circular
              v-if="loading"
              indeterminate
              color="primary"
              size="52"
            />
            <v-chip v-else :color="progressColor(lastProgressType)" variant="tonal">
              {{ loading ? 'En cours' : 'Termine' }}
            </v-chip>
          </div>

          <v-progress-linear
            class="mt-4"
            :model-value="estimatedProgress"
            :color="progressColor(lastProgressType)"
            :indeterminate="loading && estimatedProgress < 5"
            rounded
            height="10"
          />

          <v-row class="mt-4" dense>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Etape</div>
                <div class="text-body-1 font-weight-medium">{{ currentStageLabel }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Evenements</div>
                <div class="text-body-1 font-weight-medium">{{ progressEvents.length }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Derniere source</div>
                <div class="text-body-1 font-weight-medium">{{ scanInfoLabel }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Progression estimee</div>
                <div class="text-body-1 font-weight-medium">{{ estimatedProgress }}%</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Duree</div>
                <div class="text-body-1 font-weight-medium">{{ elapsedLabel }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Lecteur</div>
                <div class="text-body-1 font-weight-medium">{{ selectedDrive }}:</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Fichiers a analyser</div>
                <div class="text-body-1 font-weight-medium">{{ totalFilesLabel }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Fichiers analyses</div>
                <div class="text-body-1 font-weight-medium">{{ processedFilesLabel }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Fichier en cours</div>
                <div class="text-body-2 font-weight-medium text-truncate">{{ currentAnalyzedFile }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Vitesse analyse</div>
                <div class="text-body-1 font-weight-medium">{{ analysisSpeedLabel }}</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Passe 1</div>
                <div class="text-body-2 font-weight-medium">{{ passOneFilesLabel }} fichiers</div>
                <div class="text-body-2 text-medium-emphasis">{{ passOneDirsLabel }} dossiers</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Passe 2</div>
                <div class="text-body-2 font-weight-medium">{{ passTwoSizedFilesLabel }} tailles trouvees</div>
                <div class="text-body-2 text-medium-emphasis">sur {{ totalFilesLabel }} fichiers</div>
              </v-sheet>
            </v-col>
            <v-col cols="12" sm="4">
              <v-sheet rounded="lg" border class="pa-3">
                <div class="text-caption text-medium-emphasis">Passe 3</div>
                <div class="text-body-2 font-weight-medium">{{ passThreeRecoveredLabel }} tailles recuperees</div>
                <div class="text-body-2 text-medium-emphasis">fallback fichiers verrouilles</div>
              </v-sheet>
            </v-col>
          </v-row>

          <v-card variant="tonal" color="primary" class="mt-4 pa-3">
            <div class="text-caption text-medium-emphasis">Avancement detaille</div>
            <div class="text-body-1 font-weight-medium mt-1">{{ processedFilesLabel }} / {{ totalFilesLabel }}</div>
            <div class="text-body-2 text-medium-emphasis mt-1">{{ currentProgressMessage }}</div>
          </v-card>

          <v-card variant="outlined" class="mt-4 pa-3">
            <div class="text-subtitle-2 mb-2">Derniers fichiers analyses</div>
            <v-list density="compact" class="recent-files-list">
              <v-list-item v-for="(file, index) in recentAnalyzedFiles" :key="`${file}-${index}`" min-height="32">
                <v-list-item-title class="text-body-2 text-truncate">{{ file }}</v-list-item-title>
              </v-list-item>
              <v-list-item v-if="recentAnalyzedFiles.length === 0" min-height="32">
                <v-list-item-title class="text-body-2 text-medium-emphasis">Aucun fichier encore remonte par l analyse.</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card>

          <div class="mt-4 flex items-center justify-between gap-3 flex-wrap">
            <div class="text-subtitle-2">Journal complet du chargement</div>
            <v-btn
              variant="text"
              size="small"
              prepend-icon="mdi-delete-sweep-outline"
              :disabled="loading || progressEvents.length === 0"
              @click="clearProgressHistory"
            >
              Effacer
            </v-btn>
          </div>

          <v-timeline density="compact" side="end" align="start" class="mt-4 progress-timeline">
            <v-timeline-item
              v-for="(entry, index) in displayProgressEvents"
              :key="`${entry.timestamp}-${index}`"
              :dot-color="progressColor(entry.type)"
              size="small"
            >
              <div class="flex items-center justify-between gap-3">
                <div>
                  <div class="text-body-2 font-weight-medium">{{ progressStageLabel(entry.stage) }}</div>
                  <div class="text-body-2 text-medium-emphasis">{{ entry.message }}</div>
                </div>
                <div class="text-caption text-disabled">{{ formatProgressTime(entry.timestamp) }}</div>
              </div>
            </v-timeline-item>
          </v-timeline>
        </v-card>
      </v-col>
    </v-row>

    <!-- ── Arborescence ── -->
    <div class=" overflow-auto max-h-[87vh]">
      <v-card v-if="!loading && folders.length" variant="outlined">
        <v-list density="compact" nav>
          <FolderItem
            v-for="folder in folders"
            :key="folder.record_number"
            :folder="folder"
            :depth="0"
            :drive="selectedDrive"
            :total-size="totalScannedSize"
            :expanded-ids="expandedIds"
            @toggle="toggleFolder"
          />
        </v-list>
      </v-card>
    </div>

    <!-- ── État vide ── -->
    <v-row v-if="!loading && !folders.length && !error" justify="center" class="my-8">
      <v-col cols="auto" class="text-center">
        <v-icon size="64" color="medium-emphasis">mdi-folder-search-outline</v-icon>
        <p class="mt-3 text-medium-emphasis">Lance un scan pour voir l'arborescence</p>
      </v-col>
    </v-row>

  </v-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import FolderItem from './FolderItem.vue'

const folders       = ref([])
const loading       = ref(false)
const error         = ref(null)
const expandedIds   = ref(new Set())
const progressEvents = ref([])
const scanInfo      = ref(null)
const selectedDrive = ref('C')
const drives        = ref(['C'])
const scanStartedAt = ref(null)
const scanFinishedAt = ref(null)
const dashboardVisible = ref(false)
let dashboardHideTimer = null
let removeProgressListener = null
let removeCacheUpdatedListener = null

const DASHBOARD_GRACE_MS = 6000

function clearDashboardHideTimer() {
  if (dashboardHideTimer) {
    clearTimeout(dashboardHideTimer)
    dashboardHideTimer = null
  }
}

function scheduleDashboardHide() {
  clearDashboardHideTimer()
  dashboardHideTimer = setTimeout(() => {
    dashboardVisible.value = false
  }, DASHBOARD_GRACE_MS)
}

async function startScan() {
  clearDashboardHideTimer()
  dashboardVisible.value = true
  loading.value     = true
  error.value       = null
  folders.value     = []
  expandedIds.value = new Set()
  scanInfo.value    = null
  progressEvents.value = []
  scanStartedAt.value = Date.now()
  scanFinishedAt.value = null

  try {
    const result = await window.mftAPI.scan(selectedDrive.value, 1)
    folders.value = result?.summary ?? []
    scanInfo.value = result?.scanInfo ?? null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    scanFinishedAt.value = Date.now()
    scheduleDashboardHide()
  }
}

async function loadDriveSummary(drive, { forceScan = false, keepDashboard = false } = {}) {
  const normalizedDrive = String(drive || selectedDrive.value || 'C').trim().replace(/[:\\/]+$/g, '').charAt(0).toUpperCase()
  if (!normalizedDrive) return

  if (!forceScan) {
    try {
      const cached = await window.mftAPI.getSummary(normalizedDrive)
      if (cached?.cached) {
        folders.value = cached.summary ?? []
        scanInfo.value = cached.scanInfo ?? null
        error.value = null
        return
      }
    } catch {
      // Fall through to an explicit scan if the summary is not available yet.
    }
  }

  if (keepDashboard) {
    await startScan()
    return
  }

  loading.value = true
  error.value = null
  try {
    const result = await window.mftAPI.scan(normalizedDrive, 1)
    folders.value = result?.summary ?? []
    scanInfo.value = result?.scanInfo ?? null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const scanInfoLabelMap = {
  cache: 'Resultat depuis cache',
  delta: 'Resultat mis a jour par delta USN',
  scan: 'Resultat depuis scan reel',
}

const scanInfoColorMap = {
  cache: 'info',
  delta: 'warning',
  scan: 'success',
}

const scanInfoLabel = computed(() => {
  const source = scanInfo.value?.source
  return scanInfoLabelMap[source] ?? 'En attente'
})

const scanInfoColor = computed(() => {
  const source = scanInfo.value?.source
  return scanInfoColorMap[source] ?? 'secondary'
})

const totalScannedSize = computed(() => {
  return folders.value.reduce((sum, folder) => sum + (folder.size_bytes || 0), 0)
})

function toggleFolder(id) {
  const next = new Set(expandedIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedIds.value = next
}

function getAllIds(items, ids = []) {
  for (const item of items) {
    ids.push(item.record_number)
    if (item.child?.length) getAllIds(item.child, ids)
  }
  return ids
}

function expandAll()  { expandedIds.value = new Set(getAllIds(folders.value)) }
function collapseAll() { expandedIds.value = new Set() }

const progressStageLabelMap = {
  start: 'Preparation',
  open: 'Ouverture du volume',
  cache: 'Cache',
  delta: 'Delta USN',
  elevation: 'Elevation',
  'usn-enum': 'Enumeration USN',
  'mft-read': 'Lecture du MFT',
  fallback: 'Fallback fichiers verrouilles',
  finalize: 'Finalisation',
  done: 'Termine',
  error: 'Erreur',
  scan: 'Analyse',
}

const currentProgressMessage = computed(() => {
  return progressEvents.value.at(-1)?.message ?? 'Initialisation du scan...'
})

const currentStageLabel = computed(() => {
  return progressStageLabel(progressEvents.value.at(-1)?.stage)
})

const isDashboardVisible = computed(() => loading.value || dashboardVisible.value)

const latestProgressByStage = computed(() => {
  const map = {}
  for (const entry of progressEvents.value) {
    if (entry?.type === 'progress' && entry.stage) {
      map[entry.stage] = entry
    }
  }
  return map
})

const latestAnalysisEvent = computed(() => {
  for (let index = progressEvents.value.length - 1; index >= 0; index -= 1) {
    const entry = progressEvents.value[index]
    if (entry?.type === 'progress' && Number.isFinite(entry.processedCount)) {
      return entry
    }
  }
  return null
})

const currentAnalyzedFile = computed(() => {
  return latestAnalysisEvent.value?.currentFile ?? 'Initialisation...'
})

const totalFilesLabel = computed(() => {
  const total = latestAnalysisEvent.value?.totalFiles ?? latestAnalysisEvent.value?.totalCount
  if (!Number.isFinite(total)) return 'Calcul en cours'
  return new Intl.NumberFormat('fr-FR').format(total)
})

const processedFilesLabel = computed(() => {
  const processed = latestAnalysisEvent.value?.processedCount
  if (!Number.isFinite(processed)) return '0'
  return new Intl.NumberFormat('fr-FR').format(processed)
})

const recentAnalyzedFiles = computed(() => {
  const recent = []
  const seen = new Set()
  for (let index = progressEvents.value.length - 1; index >= 0; index -= 1) {
    const currentFile = progressEvents.value[index]?.currentFile
    if (!currentFile || seen.has(currentFile)) continue
    seen.add(currentFile)
    recent.push(currentFile)
    if (recent.length >= 12) break
  }
  return recent
})

function formatInteger(value, fallback = '0') {
  if (!Number.isFinite(value)) return fallback
  return new Intl.NumberFormat('fr-FR').format(value)
}

const passOneFilesLabel = computed(() => formatInteger(latestProgressByStage.value['usn-enum']?.totalFiles))
const passOneDirsLabel = computed(() => formatInteger(latestProgressByStage.value['usn-enum']?.totalDirs))
const passTwoSizedFilesLabel = computed(() => formatInteger(latestProgressByStage.value['mft-read']?.filesWithSize))
const passThreeRecoveredLabel = computed(() => formatInteger(latestProgressByStage.value.fallback?.filesRecovered))

const analysisSpeedLabel = computed(() => {
  if (!scanStartedAt.value) return '0 fichier/s'
  const lastCount = latestProgressByStage.value['mft-read']?.processedCount
    ?? latestProgressByStage.value.fallback?.processedCount
    ?? latestAnalysisEvent.value?.processedCount
  if (!Number.isFinite(lastCount) || lastCount <= 0) return '0 fichier/s'
  const end = loading.value ? Date.now() : (scanFinishedAt.value ?? Date.now())
  const elapsedSeconds = Math.max(1, (end - scanStartedAt.value) / 1000)
  const speed = lastCount / elapsedSeconds
  return `${speed >= 10 ? speed.toFixed(0) : speed.toFixed(1)} fichier/s`
})

const displayProgressEvents = computed(() => {
  return [...progressEvents.value].reverse()
})

const progressPercentByStage = {
  start: 5,
  open: 10,
  elevation: 15,
  cache: 100,
  delta: 75,
  'usn-enum': 35,
  'mft-read': 70,
  fallback: 88,
  finalize: 95,
  done: 100,
  error: 100,
  scan: 50,
}

const lastProgressType = computed(() => progressEvents.value.at(-1)?.type ?? 'status')

const estimatedProgress = computed(() => {
  const structuredProcessed = latestAnalysisEvent.value?.processedCount
  const structuredTotal = latestAnalysisEvent.value?.totalCount ?? latestAnalysisEvent.value?.totalFiles
  if (Number.isFinite(structuredProcessed) && Number.isFinite(structuredTotal) && structuredTotal > 0) {
    return Math.min(100, Math.max(0, Math.round((structuredProcessed / structuredTotal) * 100)))
  }

  const lastEntry = progressEvents.value.at(-1)
  if (!lastEntry) return 0

  const stageValue = progressPercentByStage[lastEntry.stage] ?? 0
  const match = String(lastEntry.message ?? '').match(/(\d{1,3})%/)
  if (match) {
    const parsed = Number(match[1])
    if (Number.isFinite(parsed)) {
      if (lastEntry.stage === 'mft-read') return Math.max(stageValue, Math.min(95, parsed))
      return Math.max(stageValue, Math.min(100, parsed))
    }
  }

  return stageValue
})

const elapsedLabel = computed(() => {
  if (!scanStartedAt.value) return '0 s'
  const end = loading.value ? Date.now() : (scanFinishedAt.value ?? Date.now())
  const seconds = Math.max(0, Math.round((end - scanStartedAt.value) / 1000))
  return `${seconds} s`
})

function progressStageLabel(stage) {
  return progressStageLabelMap[stage] ?? 'Analyse'
}

function progressColor(type) {
  if (type === 'error') return 'error'
  if (type === 'warning') return 'warning'
  if (type === 'success') return 'success'
  return 'primary'
}

function formatProgressTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function clearProgressHistory() {
  progressEvents.value = []
  scanStartedAt.value = null
  scanFinishedAt.value = null
}

onMounted(() => {
  window.mftAPI.getDrives()
    .then(async availableDrives => {
      if (!Array.isArray(availableDrives) || availableDrives.length === 0) return
      drives.value = availableDrives
      if (!availableDrives.includes(selectedDrive.value)) {
        selectedDrive.value = availableDrives[0]
      }
      await loadDriveSummary(selectedDrive.value, { forceScan: false, keepDashboard: false })
    })
    .catch(() => {})

  removeProgressListener = window.mftAPI.onScanProgress(payload => {
    progressEvents.value = [...progressEvents.value, payload]
    if (!scanStartedAt.value) scanStartedAt.value = Date.now()
    if (payload.type === 'success' || payload.type === 'error') {
      scanFinishedAt.value = Date.now()
      scheduleDashboardHide()
    }
  })

  removeCacheUpdatedListener = window.mftAPI.onCacheUpdated(payload => {
    if (!payload || payload.drive !== selectedDrive.value || loading.value) return
    folders.value = payload.summary ?? []
    scanInfo.value = payload.scanInfo ?? null
  })
})

watch(selectedDrive, async (nextDrive, previousDrive) => {
  if (!nextDrive || nextDrive === previousDrive) return
  expandedIds.value = new Set()
  await loadDriveSummary(nextDrive, { forceScan: false, keepDashboard: false })
})

onBeforeUnmount(() => {
  clearDashboardHideTimer()
  removeProgressListener?.()
  removeProgressListener = null
  removeCacheUpdatedListener?.()
  removeCacheUpdatedListener = null
})
</script>

<style scoped>
.progress-timeline {
  max-height: 320px;
  overflow: auto;
}

.recent-files-list {
  max-height: 220px;
  overflow: auto;
}
</style>
