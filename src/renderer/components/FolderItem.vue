<template>
  <div>
    <v-list-item
      :style="{ paddingLeft: `${16 + depth * 20}px` }"
      :active="false"
      rounded="lg"
      class="folder-item"
      @click="hasChildren ? $emit('toggle', folder.record_number) : null"
    >
      <template #prepend>
        <v-icon
          v-if="hasChildren"
          :icon="isExpanded ? 'mdi-chevron-down' : 'mdi-chevron-right'"
          size="18" class="mr-1" color="medium-emphasis"
        />
        <v-icon v-else size="18" class="mr-1" style="opacity: 0" />
        <v-icon
          :icon="isExpanded ? 'mdi-folder-open' : 'mdi-folder'"
          :color="folderColor" size="20" class="mr-2"
        />
      </template>

      <v-list-item-title class="folder-name">{{ folder.name }}</v-list-item-title>

      <template #append>
        <div class="folder-stats">
          <v-progress-linear
            :model-value="folder.percent"
            :color="barColor(folder.percent)"
            bg-color="surface-variant"
            rounded height="6" class="folder-bar"
          />
          <div class="folder-info">
            <span class="text-caption text-medium-emphasis">{{ folder.size_display }}</span>
            <v-chip :color="barColor(folder.percent)" size="x-small" variant="tonal" class="ml-2">
              {{ folder.percent }}%
            </v-chip>
          </div>
        </div>
      </template>
    </v-list-item>

    <template v-if="isExpanded && hasChildren">
      <FolderItem
        v-for="child in folder.child"
        :key="child.record_number"
        :folder="child"
        :depth="depth + 1"
        :expanded-ids="expandedIds"
        @toggle="$emit('toggle', $event)"
      />
    </template>

    <v-divider v-if="depth === 0" class="my-1" opacity="0.1" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  folder:      { type: Object, required: true },
  depth:       { type: Number, default: 0 },
  expandedIds: { type: Set,    required: true },
})

defineEmits(['toggle'])

const hasChildren = computed(() => props.folder.child?.length > 0)
const isExpanded  = computed(() => props.expandedIds.has(props.folder.record_number))

const folderColor = computed(() => {
  const colors = ['amber', 'orange', 'deep-orange', 'brown', 'blue-grey']
  return colors[Math.min(props.depth, colors.length - 1)]
})

function barColor(percent) {
  if (percent >= 60) return 'error'
  if (percent >= 30) return 'warning'
  return 'success'
}
</script>

<style scoped>
.folder-item { cursor: pointer; min-height: 44px; transition: background-color 0.15s; }
.folder-name { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px; }
.folder-stats { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; min-width: 180px; }
.folder-bar { width: 140px; }
.folder-info { display: flex; align-items: center; justify-content: flex-end; }
</style>
