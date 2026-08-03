<template>
  <tr
    v-if="variant !== 'grid'"
    class="explorer-row"
    :class="{ 'explorer-row--selected': selected }"
    @click="$emit('select')"
    @dblclick="$emit('open')"
    @contextmenu.prevent="$emit('contextmenu', $event)"
  >
    <td class="explorer-row__name">
      <span class="explorer-row__icon">
        <img v-if="iconUrl" :src="iconUrl" alt="" />
        <v-icon v-else :color="iconColor" size="20">{{ iconName }}</v-icon>
      </span>
      <span class="explorer-row__name-text" :title="item.name">{{ displayName }}</span>
    </td>
    <td class="explorer-row__type">{{ typeLabel }}</td>
    <td class="explorer-row__size">{{ item.size_display || '' }}</td>
  </tr>
  <div
    v-else
    class="explorer-grid-item"
    :class="{ 'explorer-grid-item--selected': selected }"
    @click="$emit('select')"
    @dblclick="$emit('open')"
    @contextmenu.prevent="$emit('contextmenu', $event)"
  >
    <span class="explorer-grid-item__icon">
      <img v-if="iconUrl" :src="iconUrl" alt="" />
      <v-icon v-else :color="iconColor" size="46">{{ iconName }}</v-icon>
    </span>
    <span class="explorer-grid-item__name" :title="item.name">{{ displayName }}</span>
    <span class="explorer-grid-item__meta">{{ item.size_display || '' }}</span>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  variant: { type: String, default: 'list' },
})
defineEmits(['select', 'open', 'contextmenu'])

const iconUrl = ref('')

const isDir = computed(() => props.item.is_dir !== false)
const ext = computed(() => String(props.item.ext || '').trim().toLowerCase())

const FILE_ICONS = {
  mp4: 'mdi-file-video', mkv: 'mdi-file-video', avi: 'mdi-file-video',
  mov: 'mdi-file-video', wmv: 'mdi-file-video', webm: 'mdi-file-video',
  mp3: 'mdi-file-music', wav: 'mdi-file-music', flac: 'mdi-file-music',
  aac: 'mdi-file-music', ogg: 'mdi-file-music', m4a: 'mdi-file-music',
  jpg: 'mdi-file-image', jpeg: 'mdi-file-image', png: 'mdi-file-image',
  gif: 'mdi-file-image', bmp: 'mdi-file-image', svg: 'mdi-file-image',
  webp: 'mdi-file-image', ico: 'mdi-file-image', tiff: 'mdi-file-image',
  pdf: 'mdi-file-pdf-box',
  doc: 'mdi-file-word', docx: 'mdi-file-word',
  xls: 'mdi-file-excel', xlsx: 'mdi-file-excel',
  ppt: 'mdi-file-powerpoint', pptx: 'mdi-file-powerpoint',
  txt: 'mdi-file-document-outline', md: 'mdi-language-markdown',
  csv: 'mdi-file-delimited',
  zip: 'mdi-zip-box', rar: 'mdi-zip-box', '7z': 'mdi-zip-box',
  tar: 'mdi-zip-box', gz: 'mdi-zip-box',
  js: 'mdi-language-javascript', ts: 'mdi-language-typescript',
  py: 'mdi-language-python', html: 'mdi-language-html5',
  css: 'mdi-language-css3', json: 'mdi-code-json',
  sql: 'mdi-database', sh: 'mdi-console',
  exe: 'mdi-application', iso: 'mdi-disc',
  dll: 'mdi-puzzle', msi: 'mdi-package-variant',
}

const FILE_COLORS = {
  mp4: 'blue', mkv: 'blue', avi: 'blue', mov: 'blue', webm: 'blue',
  mp3: 'purple', wav: 'purple', flac: 'purple', aac: 'purple', m4a: 'purple',
  jpg: 'teal', jpeg: 'teal', png: 'teal', gif: 'teal', svg: 'teal', webp: 'teal',
  pdf: 'red',
  doc: 'blue-darken-2', docx: 'blue-darken-2',
  xls: 'green-darken-2', xlsx: 'green-darken-2',
  ppt: 'orange-darken-2', pptx: 'orange-darken-2',
  txt: 'grey', md: 'grey-darken-1', csv: 'green',
  zip: 'amber-darken-2', rar: 'amber-darken-2', '7z': 'amber-darken-2',
  gz: 'amber-darken-2', tar: 'amber-darken-2',
  js: 'yellow-darken-3', ts: 'blue', py: 'blue-darken-1',
  html: 'orange-darken-2', css: 'blue', json: 'grey', sql: 'cyan-darken-2',
  exe: 'red-darken-2', iso: 'indigo', dll: 'grey-darken-2',
}

const TYPE_LABELS = {
  pdf: 'Document PDF',
  doc: 'Document Word', docx: 'Document Word',
  xls: 'Classeur Excel', xlsx: 'Classeur Excel',
  ppt: 'Presentation PowerPoint', pptx: 'Presentation PowerPoint',
  txt: 'Document texte', md: 'Document Markdown', csv: 'Valeurs separees par des virgules',
  jpg: 'Image JPEG', jpeg: 'Image JPEG', png: 'Image PNG', gif: 'Image GIF',
  bmp: 'Image bitmap', svg: 'Image vectorielle', webp: 'Image WEBP', ico: 'Icone',
  mp3: 'Fichier audio MP3', wav: 'Fichier audio WAV', flac: 'Fichier audio FLAC',
  mp4: 'Fichier video MP4', mkv: 'Fichier video MKV', avi: 'Fichier video AVI',
  zip: 'Dossier compresse ZIP', rar: 'Archive RAR', '7z': 'Archive 7-Zip',
  exe: 'Application', msi: 'Package d installation Windows', iso: 'Image disque',
  json: 'Fichier JSON', js: 'Fichier JavaScript', ts: 'Fichier TypeScript',
  py: 'Script Python', html: 'Document HTML', css: 'Feuille de style CSS',
  dll: 'Extension d application', sql: 'Fichier SQL',
}

const iconName = computed(() => isDir.value ? 'mdi-folder' : (FILE_ICONS[ext.value] ?? 'mdi-file-outline'))
const iconColor = computed(() => isDir.value ? 'amber' : (FILE_COLORS[ext.value] ?? 'grey-lighten-1'))

function truncateName(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  const words = text.split(/\s+/).filter(Boolean)
  if (words.length > 5) {
    return `${words.slice(0, 5).join(' ')}...`
  }
  if (text.length > 26) {
    return `${text.slice(0, 23)}...`
  }
  return text
}

const displayName = computed(() => truncateName(props.item?.name))

const typeLabel = computed(() => {
  if (isDir.value) return 'Dossier de fichiers'
  if (!ext.value) return 'Fichier'
  return TYPE_LABELS[ext.value] ?? `Fichier ${ext.value.toUpperCase()}`
})

async function loadIcon() {
  if (!props.item?.path) {
    iconUrl.value = ''
    return
  }

  // Grid view is large enough to show Windows' content-peek folder thumbnail
  // (jumbo shell icon list), which the small/normal icon list never composes.
  if (props.variant === 'grid' && isDir.value) {
    try {
      const jumbo = await window.mftAPI.getJumboIcon(props.item.path, 256)
      if (jumbo?.dataUrl) {
        iconUrl.value = jumbo.dataUrl
        return
      }
    } catch {
      // Native module not built yet - fall through to the mdi-folder glyph below.
    }
  }

  // Electron's app.getFileIcon does not return usable icons for directories
  // on Windows (confirmed: fails even for plain local folders, not just
  // reparse points) - only worth calling for files. The jumbo native icon
  // above is the real fix for folders; until it is built, show the plain
  // folder glyph instead of a misleading fallback.
  if (isDir.value) {
    iconUrl.value = ''
    return
  }

  const size = props.variant === 'grid' ? 'normal' : 'small'
  try {
    const result = await window.mftAPI.getFileIcon(props.item.path, size)
    if (result?.dataUrl) {
      iconUrl.value = result.dataUrl
      return
    }
  } catch {
    // Fall through to the generic file glyph below.
  }

  iconUrl.value = ''
}

watch(() => [props.item?.path, props.variant], loadIcon, { immediate: true })
</script>

<style scoped>
.explorer-row {
  cursor: default;
  transition: background 0.12s ease;
}

.explorer-row:hover {
  background: rgba(255, 255, 255, 0.05);
}

.explorer-row--selected {
  background: rgba(83, 164, 255, 0.16) !important;
}

.explorer-row td {
  padding: 6px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 0.86rem;
  color: #e8edf7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.explorer-row__name {
  display: flex;
  align-items: center;
  gap: 10px;
}

.explorer-row__icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.explorer-row__icon img {
  width: 18px;
  height: 18px;
  object-fit: contain;
}

.explorer-row__name-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.explorer-row__type,
.explorer-row__size {
  color: rgba(214, 224, 238, 0.76);
}

.explorer-grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 8px;
  border-radius: 12px;
  cursor: default;
  transition: background 0.12s ease;
}

.explorer-grid-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.explorer-grid-item--selected {
  background: rgba(83, 164, 255, 0.16) !important;
}

.explorer-grid-item__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
}

.explorer-grid-item__icon img {
  width: 48px;
  height: 48px;
  object-fit: contain;
}

.explorer-grid-item__name {
  max-width: 120px;
  font-size: 0.82rem;
  text-align: center;
  color: #e8edf7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.explorer-grid-item__meta {
  font-size: 0.74rem;
  color: rgba(214, 224, 238, 0.68);
}
</style>
