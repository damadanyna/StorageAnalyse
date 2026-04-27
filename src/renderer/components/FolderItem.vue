<template>
  <div>
    <!-- ── Dossier ── -->
    <v-list-item
      v-if="folder.is_dir !== false"
      :style="{ paddingLeft: `${16 + depth * 20}px` }"
      :active="false"
      rounded="lg"
      class="folder-item"
      @click="toggleFolder"
    >
      <template #prepend>
        <v-progress-circular
          v-if="loadingFiles || loadingChildren"
          indeterminate size="14" width="2" class="mr-1"
        />
        <v-icon
          v-else-if="hasChildren || folder.file_count > 0"
          :icon="isExpanded ? 'mdi-chevron-down' : 'mdi-chevron-right'"
          size="18" class="mr-1" color="medium-emphasis"
        />
        <v-icon v-else size="18" class="mr-1" style="opacity: 0" />
        <v-icon
          :icon="isExpanded ? 'mdi-folder-open' : 'mdi-folder'"
          :color="folderColor"
          size="20" class="mr-2"
        />
      </template>

      <v-list-item-title class="folder-name">
        {{ folder.name }}
        <span v-if="folder.file_count > 0" class="text-caption text-disabled ml-1">
          ({{ folder.file_count }} fichiers)
        </span>
      </v-list-item-title>

      <template #append>
        <div class="folder-stats">
          <v-progress-linear
            :model-value="percent"
            :color="barColor(percent)"
            bg-color="surface-variant"
            rounded height="6" class="folder-bar"
          />
          <div class="folder-info">
            <span class="text-caption text-medium-emphasis">{{ folder.size_display }}</span>
            <v-chip :color="barColor(percent)" size="x-small" variant="tonal" class="ml-2">
              {{ percentLabel }}
            </v-chip>
          </div>
        </div>
      </template>
    </v-list-item>

    <!-- ── Fichier ── -->
    <v-list-item
      v-else
      :style="{ paddingLeft: `${16 + depth * 20 + 38}px` }"
      :active="false"
      rounded="lg"
      class="file-item"
    >
      <template #prepend>
        <v-icon :color="fileColor(folder.ext)" size="16" class="mr-2">
          {{ fileIcon(folder.ext) }}
        </v-icon>
      </template>

      <v-list-item-title class="file-name">{{ folder.name }}</v-list-item-title>

      <template #append>
        <div class="folder-stats">
          <v-progress-linear
            :model-value="percent"
            :color="barColor(percent)"
            bg-color="surface-variant"
            rounded height="4" class="folder-bar"
          />
          <div class="folder-info">
            <span class="text-caption text-disabled">{{ folder.size_display }}</span>
            <v-chip :color="barColor(percent)" size="x-small" variant="tonal" class="ml-2">
              {{ percentLabel }}
            </v-chip>
          </div>
        </div>
      </template>
    </v-list-item>

    <!-- ── Enfants récursifs ── -->
    <template v-if="folder.is_dir !== false && isExpanded">
      <!-- Sous-dossiers (depuis JSON initial) -->
      <FolderItem
        v-for="child in localChildren"
        :key="child.record_number"
        :folder="child"
        :depth="depth + 1"
        :parent-size="folder.size_bytes"
        :total-size="totalSize"
        :drive="drive"
        :expanded-ids="expandedIds"
        @toggle="emit('toggle', $event)"
      />
      <!-- Fichiers chargés à la demande -->
      <FolderItem
        v-for="file in loadedFiles"
        :key="file.record_number"
        :folder="file"
        :depth="depth + 1"
        :parent-size="folder.size_bytes"
        :total-size="totalSize"
        :drive="drive"
        :expanded-ids="expandedIds"
        @toggle="emit('toggle', $event)"
      />
    </template>

    <v-divider v-if="depth === 0 && folder.is_dir !== false" class="my-1" opacity="0.1" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  folder:      { type: Object,  required: true },
  depth:       { type: Number,  default: 0 },
  expandedIds: { type: Set,     required: true },
  parentSize:  { type: Number,  default: 0 },
  totalSize:   { type: Number,  default: 0 },
  drive:       { type: String,  default: 'C' },
})

const emit = defineEmits(['toggle'])

const loadedChildren = ref([])
const loadedFiles  = ref([])
const loadingFiles = ref(false)
const loadingChildren = ref(false)

const localChildren = computed(() => {
  if (props.folder.child?.length) return props.folder.child
  return loadedChildren.value
})
const hasChildren = computed(() => (props.folder.child_count ?? localChildren.value.length) > 0)
const isExpanded  = computed(() => props.expandedIds.has(props.folder.record_number))

async function toggleFolder() {
  // Si dossier vide et pas de fichiers → rien à faire
  if (!hasChildren.value && !(props.folder.file_count > 0)) return

  // ✅ Émet le toggle AVANT de charger (expand immédiat)
  emit('toggle', props.folder.record_number)

  // Charge les fichiers seulement si :
  // - on est en train d'ouvrir (pas de fermeture)
  // - pas encore chargés
  // - il y a des fichiers
  if (!isExpanded.value) {
    if (loadedChildren.value.length === 0 && !props.folder.child?.length && (props.folder.child_count ?? 0) > 0) {
      loadingChildren.value = true
      try {
        loadedChildren.value = await window.mftAPI.getChildren(props.drive, props.folder.record_number)
      } catch (e) {
        console.error('Erreur chargement sous-dossiers:', e)
      } finally {
        loadingChildren.value = false
      }
    }

    if (loadedFiles.value.length === 0 && props.folder.file_count > 0) {
      loadingFiles.value = true
      try {
        loadedFiles.value = await window.mftAPI.getFiles(props.drive, props.folder.record_number)
      } catch (e) {
        console.error('Erreur chargement fichiers:', e)
      } finally {
        loadingFiles.value = false
      }
    }
  }
}

const percent = computed(() => {
  const baseSize = props.totalSize || props.parentSize
  if (!baseSize || !props.folder.size_bytes) return 0
  return Math.min(100, (props.folder.size_bytes / baseSize) * 100)
})

const percentLabel = computed(() => {
  if (percent.value >= 10) return `${Math.round(percent.value)}%`
  if (percent.value >= 1) return `${percent.value.toFixed(1)}%`
  if (percent.value > 0) return `${percent.value.toFixed(2)}%`
  return '0%'
})

const folderColor = computed(() => {
  const colors = ['amber', 'orange', 'deep-orange', 'brown', 'blue-grey']
  return colors[Math.min(props.depth, colors.length - 1)]
})

function barColor(p) {
  if (p >= 60) return 'error'
  if (p >= 30) return 'warning'
  return 'success'
}

const FILE_ICONS = {
  mp4:'mdi-file-video', mkv:'mdi-file-video', avi:'mdi-file-video',
  mov:'mdi-file-video', wmv:'mdi-file-video', webm:'mdi-file-video',
  mp3:'mdi-file-music', wav:'mdi-file-music', flac:'mdi-file-music',
  aac:'mdi-file-music', ogg:'mdi-file-music', m4a:'mdi-file-music',
  jpg:'mdi-file-image', jpeg:'mdi-file-image', png:'mdi-file-image',
  gif:'mdi-file-image', bmp:'mdi-file-image', svg:'mdi-file-image',
  webp:'mdi-file-image', ico:'mdi-file-image', tiff:'mdi-file-image',
  pdf:'mdi-file-pdf-box',
  doc:'mdi-file-word', docx:'mdi-file-word',
  xls:'mdi-file-excel', xlsx:'mdi-file-excel',
  ppt:'mdi-file-powerpoint', pptx:'mdi-file-powerpoint',
  txt:'mdi-file-document-outline', md:'mdi-language-markdown',
  csv:'mdi-file-delimited',
  zip:'mdi-zip-box', rar:'mdi-zip-box', '7z':'mdi-zip-box',
  tar:'mdi-zip-box', gz:'mdi-zip-box',
  js:'mdi-language-javascript', ts:'mdi-language-typescript',
  py:'mdi-language-python', html:'mdi-language-html5',
  css:'mdi-language-css3', json:'mdi-code-json',
  sql:'mdi-database', sh:'mdi-console',
  exe:'mdi-application', iso:'mdi-disc',
  dll:'mdi-puzzle', msi:'mdi-package-variant',
}

const FILE_COLORS = {
  mp4:'blue', mkv:'blue', avi:'blue', mov:'blue', webm:'blue',
  mp3:'purple', wav:'purple', flac:'purple', aac:'purple', m4a:'purple',
  jpg:'teal', jpeg:'teal', png:'teal', gif:'teal', svg:'teal', webp:'teal',
  pdf:'red',
  doc:'blue-darken-2', docx:'blue-darken-2',
  xls:'green-darken-2', xlsx:'green-darken-2',
  ppt:'orange-darken-2', pptx:'orange-darken-2',
  txt:'grey', md:'grey-darken-1', csv:'green',
  zip:'amber-darken-2', rar:'amber-darken-2', '7z':'amber-darken-2',
  gz:'amber-darken-2', tar:'amber-darken-2',
  js:'yellow-darken-3', ts:'blue', py:'blue-darken-1',
  html:'orange-darken-2', css:'blue', json:'grey', sql:'cyan-darken-2',
  exe:'red-darken-2', iso:'indigo', dll:'grey-darken-2',
}

function fileIcon(ext)  { return FILE_ICONS[ext?.toLowerCase()]  ?? 'mdi-file-outline' }
function fileColor(ext) { return FILE_COLORS[ext?.toLowerCase()] ?? 'grey' }
</script>

<style scoped>
.folder-item { cursor: pointer; min-height: 44px; transition: background-color 0.15s; }
.folder-item:hover { background: rgba(var(--v-theme-primary), 0.05); }
.file-item { cursor: default; min-height: 36px; transition: background-color 0.15s; }
.file-item:hover { background: rgba(128,128,128, 0.04); }
.folder-name {
  font-size: 13px; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px;
}
.file-name {
  font-size: 12px; font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.7);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px;
}
.folder-stats { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; min-width: 180px; }
.folder-bar  { width: 140px; }
.folder-info { display: flex; align-items: center; justify-content: flex-end; }
</style>
