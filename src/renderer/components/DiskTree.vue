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

    <!-- ── Loading ── -->
    <v-row v-if="loading" justify="center" class="my-8">
      <v-col cols="auto" class="text-center">
        <v-progress-circular indeterminate color="primary" size="48" />
        <p class="mt-3 text-medium-emphasis">Lecture du MFT en cours...</p>
      </v-col>
    </v-row>

    <!-- ── Arborescence ── -->
    <v-card v-if="!loading && folders.length" variant="outlined">
      <v-list density="compact" nav>
        <FolderItem
          v-for="folder in folders"
          :key="folder.record_number"
          :folder="folder"
          :depth="0"
          :expanded-ids="expandedIds"
          @toggle="toggleFolder"
        />
      </v-list>
    </v-card>

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
import { ref } from 'vue'
import FolderItem from './FolderItem.vue'

const folders       = ref([])
const loading       = ref(false)
const error         = ref(null)
const expandedIds   = ref(new Set())
const selectedDrive = ref('C')
const drives        = ['C', 'D', 'E', 'F']

async function startScan() {
  loading.value     = true
  error.value       = null
  folders.value     = []
  expandedIds.value = new Set()

  try {
    folders.value = await window.mftAPI.scan(selectedDrive.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

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
</script>
