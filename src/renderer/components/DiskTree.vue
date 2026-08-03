<template>
  <v-container fluid class="disk-tree-shell">

    <section v-if="showStartupScreen" class="startup-screen">
      <div class="startup-screen__halo startup-screen__halo--left" />
      <div class="startup-screen__halo startup-screen__halo--right" />

      <div class="startup-screen__content">
        <div class="startup-screen__eyebrow">StorageAnalyse</div>
        <h1 class="startup-screen__title">Chargement de l'analyse du lecteur {{ selectedDrive }}:</h1>
        <p class="startup-screen__subtitle">
          {{ currentProgressMessage }}
        </p>

        <div class="startup-screen__chips">
          <v-chip color="primary" variant="flat" size="small">{{ currentStageLabel }}</v-chip>
          <v-chip color="white" variant="outlined" size="small">{{ estimatedProgress }}%</v-chip>
          <v-chip color="white" variant="outlined" size="small">{{ elapsedLabel }}</v-chip>
          <v-chip v-if="remainingTimeLabel !== 'Calcul...'" color="white" variant="outlined" size="small">Reste {{ remainingTimeLabel }}</v-chip>
        </div>

        <v-progress-linear
          class="startup-screen__bar"
          :model-value="estimatedProgress"
          :color="progressColor(lastProgressType)"
          :indeterminate="loading && estimatedProgress < 5"
          rounded
          height="12"
        />

        <div class="startup-screen__stats">
          <div class="startup-metric-card">
            <span class="startup-metric-card__label">Fichiers analyses</span>
            <strong class="startup-metric-card__value">{{ processedFilesLabel }}</strong>
          </div>
          <div class="startup-metric-card">
            <span class="startup-metric-card__label">Volume total</span>
            <strong class="startup-metric-card__value">{{ totalFilesLabel }}</strong>
          </div>
          <div class="startup-metric-card">
            <span class="startup-metric-card__label">Fichier en cours</span>
            <strong class="startup-metric-card__value startup-metric-card__value--small">{{ currentAnalyzedFile }}</strong>
          </div>
          <div class="startup-metric-card">
            <span class="startup-metric-card__label">Vitesse</span>
            <strong class="startup-metric-card__value">{{ analysisSpeedLabel }}</strong>
          </div>
          <div class="startup-metric-card">
            <span class="startup-metric-card__label">Temps restant</span>
            <strong class="startup-metric-card__value">{{ remainingTimeLabel }}</strong>
          </div>
        </div>

        <transition-group name="stage-card" tag="div" class="startup-screen__stages">
          <div
            v-for="stage in stageCards"
            :key="stage.key"
            class="stage-card"
            :class="[`stage-card--${stage.status}`]"
          >
            <div class="stage-card__header">
              <span class="stage-card__title">{{ stage.label }}</span>
              <span class="stage-card__percent">{{ stage.percent }}%</span>
            </div>
            <v-progress-linear
              :model-value="stage.percent"
              :color="stage.color"
              rounded
              height="7"
            />
            <div class="stage-card__message">{{ stage.message }}</div>
            <div class="stage-card__meta">{{ stage.meta }}</div>
            <div class="stage-card__eta">{{ stage.eta }}</div>
          </div>
        </transition-group>

        <v-card variant="outlined" class="startup-screen__journal pa-3">
          <div class="text-subtitle-2 mb-2">Dernieres remontees d'analyse</div>
          <v-list density="compact" class="recent-files-list recent-files-list--startup">
            <v-list-item v-for="(file, index) in recentAnalyzedFiles.slice(0, 8)" :key="`${file}-${index}`" min-height="34">
              <v-list-item-title class="text-body-2 text-truncate">{{ file }}</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="recentAnalyzedFiles.length === 0" min-height="34">
              <v-list-item-title class="text-body-2 text-medium-emphasis">Preparation des premieres donnees...</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>

        <div v-if="showHighlights" class="startup-screen__highlights">
          <v-card variant="outlined" class="highlight-card pa-3">
            <div class="highlight-card__header">
              <div>
                <div class="text-overline text-medium-emphasis">Apres scan</div>
                <div class="text-subtitle-1">Dossiers les plus lourds</div>
              </div>
              <v-chip color="success" variant="tonal" size="small">Top {{ topFolders.length }}</v-chip>
            </div>
            <v-list density="compact" class="highlight-list">
              <v-list-item v-for="folder in topFolders" :key="`folder-${folder.record_number}`" min-height="42">
                <template #prepend>
                  <v-icon color="warning" size="18">mdi-folder-star</v-icon>
                </template>
                <v-list-item-title class="text-body-2 font-weight-medium text-truncate">{{ folder.path }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption text-medium-emphasis">{{ folder.file_count }} fichiers · {{ folder.child_count }} sous-dossiers</v-list-item-subtitle>
                <template #append>
                  <div class="highlight-card__actions">
                    <v-btn icon="mdi-folder-open-outline" size="x-small" variant="text" @click.stop="openInExplorer(folder.path, 'folder')" />
                    <v-chip color="warning" variant="tonal" size="small">{{ folder.size_display }}</v-chip>
                  </div>
                </template>
              </v-list-item>
            </v-list>
          </v-card>

          <v-card variant="outlined" class="highlight-card pa-3">
            <div class="highlight-card__header">
              <div>
                <div class="text-overline text-medium-emphasis">Apres scan</div>
                <div class="text-subtitle-1">Fichiers les plus lourds</div>
              </div>
              <v-chip color="info" variant="tonal" size="small">Top {{ topFiles.length }}</v-chip>
            </div>
            <v-list density="compact" class="highlight-list">
              <v-list-item v-for="file in topFiles" :key="`file-${file.record_number}`" min-height="42">
                <template #prepend>
                  <v-icon color="info" size="18">mdi-file-chart</v-icon>
                </template>
                <v-list-item-title class="text-body-2 font-weight-medium text-truncate">{{ file.path }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption text-medium-emphasis">{{ file.ext || 'sans extension' }}</v-list-item-subtitle>
                <template #append>
                  <div class="highlight-card__actions">
                    <v-btn icon="mdi-folder-search-outline" size="x-small" variant="text" @click.stop="openInExplorer(file.path, 'file')" />
                    <v-chip color="info" variant="tonal" size="small">{{ file.size_display }}</v-chip>
                  </div>
                </template>
              </v-list-item>
            </v-list>
          </v-card>
        </div>

        <div v-if="showDistribution" class="startup-screen__distribution">
          <v-card variant="outlined" class="distribution-card pa-3">
            <div class="highlight-card__header">
              <div>
                <div class="text-overline text-medium-emphasis">Vue synthese</div>
                <div class="text-subtitle-1">Poids par dossier racine</div>
              </div>
            </div>
            <div class="mini-chart">
              <div v-for="entry in rootDistribution" :key="`root-${entry.key}`" class="mini-chart__row">
                <div class="mini-chart__label">{{ entry.label }}</div>
                <div class="mini-chart__bar-wrap">
                  <div class="mini-chart__bar mini-chart__bar--folder" :style="{ width: `${entry.percent}%` }" />
                </div>
                <div class="mini-chart__value">{{ entry.size_display }}</div>
              </div>
            </div>
          </v-card>

          <v-card variant="outlined" class="distribution-card pa-3">
            <div class="highlight-card__header">
              <div>
                <div class="text-overline text-medium-emphasis">Vue synthese</div>
                <div class="text-subtitle-1">Poids par type de fichier</div>
              </div>
            </div>
            <div class="mini-chart">
              <div v-for="entry in fileTypeDistribution" :key="`type-${entry.key}`" class="mini-chart__row">
                <div class="mini-chart__label">{{ entry.label }}</div>
                <div class="mini-chart__bar-wrap">
                  <div class="mini-chart__bar mini-chart__bar--type" :style="{ width: `${entry.percent}%` }" />
                </div>
                <div class="mini-chart__value">{{ entry.size_display }}</div>
              </div>
            </div>
          </v-card>
        </div>
      </div>
    </section>

    <!-- ── Barre d'actions ── -->
    <v-row v-if="folders.length || scanInfo" align="center" class="mb-4">
      <v-col cols="auto" v-if="folders.length">
        <v-chip color="success" variant="tonal" size="small">
          {{ currentLevelSummaryLabel }}
        </v-chip>
      </v-col>
      <v-col cols="auto" v-if="scanInfo">
        <v-chip :color="scanInfoColor" variant="tonal" size="small">
          {{ scanInfoLabel }}
        </v-chip>
      </v-col>
      <v-spacer />
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

          <div class="stage-card-grid mt-4">
            <div
              v-for="stage in stageCards"
              :key="`dashboard-${stage.key}`"
              class="stage-card"
              :class="[`stage-card--${stage.status}`]"
            >
              <div class="stage-card__header">
                <span class="stage-card__title">{{ stage.label }}</span>
                <span class="stage-card__percent">{{ stage.percent }}%</span>
              </div>
              <v-progress-linear
                :model-value="stage.percent"
                :color="stage.color"
                rounded
                height="7"
              />
              <div class="stage-card__message">{{ stage.message }}</div>
              <div class="stage-card__meta">{{ stage.meta }}</div>
              <div class="stage-card__eta">{{ stage.eta }}</div>
            </div>
          </div>

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
            <div class="text-body-2 text-medium-emphasis mt-1">Temps restant estime: {{ remainingTimeLabel }}</div>
          </v-card>

          <div v-if="showHighlights" class="highlight-grid mt-4">
            <v-card variant="outlined" class="highlight-card pa-3">
              <div class="highlight-card__header">
                <div class="text-subtitle-2">Dossiers les plus lourds</div>
                <div class="text-caption text-medium-emphasis">Dernier snapshot</div>
              </div>
              <v-list density="compact" class="highlight-list">
                <v-list-item v-for="folder in topFolders" :key="`dash-folder-${folder.record_number}`" min-height="40">
                  <v-list-item-title class="text-body-2 font-weight-medium text-truncate">{{ folder.path }}</v-list-item-title>
                  <v-list-item-subtitle class="text-caption text-medium-emphasis">{{ folder.file_count }} fichiers · {{ folder.child_count }} sous-dossiers</v-list-item-subtitle>
                  <template #append>
                    <div class="highlight-card__actions">
                      <v-btn icon="mdi-folder-open-outline" size="x-small" variant="text" @click.stop="openInExplorer(folder.path, 'folder')" />
                      <v-chip color="warning" variant="tonal" size="small">{{ folder.size_display }}</v-chip>
                    </div>
                  </template>
                </v-list-item>
              </v-list>
            </v-card>

            <v-card variant="outlined" class="highlight-card pa-3">
              <div class="highlight-card__header">
                <div class="text-subtitle-2">Fichiers les plus lourds</div>
                <div class="text-caption text-medium-emphasis">Depuis le cache MFT</div>
              </div>
              <v-list density="compact" class="highlight-list">
                <v-list-item v-for="file in topFiles" :key="`dash-file-${file.record_number}`" min-height="40">
                  <v-list-item-title class="text-body-2 font-weight-medium text-truncate">{{ file.path }}</v-list-item-title>
                  <v-list-item-subtitle class="text-caption text-medium-emphasis">{{ file.ext || 'sans extension' }}</v-list-item-subtitle>
                  <template #append>
                    <div class="highlight-card__actions">
                      <v-btn icon="mdi-folder-search-outline" size="x-small" variant="text" @click.stop="openInExplorer(file.path, 'file')" />
                      <v-chip color="info" variant="tonal" size="small">{{ file.size_display }}</v-chip>
                    </div>
                  </template>
                </v-list-item>
              </v-list>
            </v-card>
          </div>

          <div v-if="showDistribution" class="highlight-grid mt-4">
            <v-card variant="outlined" class="distribution-card pa-3">
              <div class="highlight-card__header">
                <div class="text-subtitle-2">Repartition par dossier racine</div>
                <div class="distribution-card__controls">
                  <div class="text-caption text-medium-emphasis">Top {{ rootDistribution.length }}</div>
                </div>
              </div>
              <div class="mini-chart">
                <button
                  v-for="entry in rootDistribution"
                  :key="`dashboard-root-${entry.key}`"
                  type="button"
                  class="mini-chart__row mini-chart__row--interactive"
                  @click="openDistributionFolder(entry)"
                >
                  <div class="mini-chart__label">{{ entry.label }}</div>
                  <div class="mini-chart__bar-wrap">
                    <div class="mini-chart__bar mini-chart__bar--folder" :style="{ width: `${entry.percent}%` }" />
                  </div>
                  <div class="mini-chart__value">{{ entry.size_display }}</div>
                </button>
              </div>
            </v-card>

            <v-card variant="outlined" class="distribution-card pa-3">
              <div class="highlight-card__header">
                <div class="text-subtitle-2">Repartition par type</div>
                <div class="distribution-card__controls">
                  <v-chip v-if="activeTypeFilter" size="x-small" color="info" variant="tonal">Type {{ activeTypeFilter }}</v-chip>
                  <div class="text-caption text-medium-emphasis">Top {{ fileTypeDistribution.length }}</div>
                </div>
              </div>
              <div class="mini-chart">
                <button
                  v-for="entry in fileTypeDistribution"
                  :key="`dashboard-type-${entry.key}`"
                  type="button"
                  class="mini-chart__row mini-chart__row--interactive"
                  :class="{ 'mini-chart__row--active': activeTypeFilter === entry.key }"
                  @click="toggleTypeFilter(entry.key)"
                >
                  <div class="mini-chart__label">{{ entry.label }}</div>
                  <div class="mini-chart__bar-wrap">
                    <div class="mini-chart__bar mini-chart__bar--type" :style="{ width: `${entry.percent}%` }" />
                  </div>
                  <div class="mini-chart__value">{{ entry.size_display }}</div>
                </button>
              </div>
            </v-card>
          </div>

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

    <!-- ── Explorateur ── -->
    <div class="explorer-shell">
      <v-card v-if="!loading && folders.length" variant="outlined" class="tree-surface">
        <div class="explorer-toolbar">
          <div class="explorer-breadcrumb">
            <v-btn icon="mdi-arrow-up" size="small" variant="text" density="comfortable" :disabled="currentPathSegments.length === 0" @click="goUp" />
            <button type="button" class="explorer-breadcrumb__item" :class="{ 'explorer-breadcrumb__item--active': currentPathSegments.length === 0 }" @click="goToSegment(-1)">
              <v-icon size="16">mdi-harddisk</v-icon>
              {{ selectedDrive }}:
            </button>
            <template v-for="(seg, idx) in currentPathSegments" :key="seg.record_number">
              <v-icon size="14" class="explorer-breadcrumb__sep">mdi-chevron-right</v-icon>
              <button
                type="button"
                class="explorer-breadcrumb__item"
                :class="{ 'explorer-breadcrumb__item--active': idx === currentPathSegments.length - 1 }"
                @click="goToSegment(idx)"
              >{{ seg.name }}</button>
            </template>
          </div>
          <div class="explorer-toolbar__actions">
            <v-chip v-if="activeTypeFilter" color="info" variant="tonal" size="small" closable @click:close="activeTypeFilter = null">
              Type: {{ activeTypeFilter }}
            </v-chip>
            <v-chip v-if="activeSizeFilter !== 'all'" color="warning" variant="tonal" size="small" closable @click:close="activeSizeFilter = 'all'">
              Taille: {{ sizeFilterLabel }}
            </v-chip>
            <v-btn-toggle v-model="viewMode" mandatory divided density="comfortable" variant="outlined">
              <v-btn value="list" icon="mdi-view-list-outline" />
              <v-btn value="grid" icon="mdi-view-grid-outline" />
            </v-btn-toggle>
            <v-select
              v-model="selectedDrive"
              :items="drives"
              label="Lecteur"
              density="compact"
              variant="outlined"
              hide-details
              class="explorer-toolbar__select"
            />
            <v-select
              v-model="activeSizeFilter"
              :items="sizeFilterOptions"
              label="Taille"
              density="compact"
              variant="outlined"
              hide-details
              class="explorer-toolbar__select explorer-toolbar__select--wide"
            />
            <v-btn
              color="primary"
              :loading="loading"
              :disabled="loading"
              prepend-icon="mdi-magnify-scan"
              class="explorer-toolbar__scan"
              @click="startScan"
            >
              Scanner {{ selectedDrive }}:\
            </v-btn>
            <v-chip color="success" variant="tonal" size="small">
              {{ currentLevelSummaryLabel }}
            </v-chip>
          </div>
        </div>

        <div v-if="explorerBusy" class="explorer-loading explorer-content">
          <v-progress-circular indeterminate color="primary" size="26" width="2" />
          <span class="text-body-2 text-medium-emphasis">Chargement du dossier...</span>
        </div>

        <div v-else-if="viewMode === 'list' && sortedRows.length" class="explorer-content explorer-content--table">
          <table class="explorer-table">
            <thead>
              <tr>
                <th class="explorer-table__col-name" @click="setSort('name')">
                  Nom <v-icon v-if="sortKey === 'name'" size="14">{{ sortDir === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down' }}</v-icon>
                </th>
                <th class="explorer-table__col-type" @click="setSort('type')">
                  Type <v-icon v-if="sortKey === 'type'" size="14">{{ sortDir === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down' }}</v-icon>
                </th>
                <th class="explorer-table__col-size" @click="setSort('size')">
                  Taille <v-icon v-if="sortKey === 'size'" size="14">{{ sortDir === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down' }}</v-icon>
                </th>
              </tr>
            </thead>
            <tbody>
              <ExplorerRow
                v-for="row in sortedRows"
                :key="row.record_number"
                :item="row"
                :selected="selectedItem === row.record_number"
                @select="selectedItem = row.record_number"
                @open="row.is_dir !== false ? enterFolder(row) : previewPath(row.path)"
                @contextmenu="openContextMenu({ event: $event, item: row })"
              />
            </tbody>
          </table>
        </div>

        <div v-else-if="sortedRows.length" class="explorer-content">
          <div class="explorer-grid">
            <ExplorerRow
              v-for="row in sortedRows"
              :key="row.record_number"
              variant="grid"
              :item="row"
              :selected="selectedItem === row.record_number"
              @select="selectedItem = row.record_number"
              @open="row.is_dir !== false ? enterFolder(row) : previewPath(row.path)"
              @contextmenu="openContextMenu({ event: $event, item: row })"
            />
          </div>
        </div>

        <div v-else class="explorer-empty explorer-content">
          <v-icon size="48" color="medium-emphasis">mdi-folder-open-outline</v-icon>
          <p>{{ hasActiveFilters ? 'Aucun element ne correspond aux filtres actifs.' : 'Ce dossier est vide.' }}</p>
        </div>
      </v-card>
    </div>

    <!-- ── État vide ── -->
    <v-row v-if="!loading && !folders.length && !error" justify="center" class="my-8">
      <v-col cols="auto" class="text-center">
        <v-icon size="64" color="medium-emphasis">mdi-folder-search-outline</v-icon>
        <p class="mt-3 text-medium-emphasis">Lance un scan pour voir l arborescence</p>
      </v-col>
    </v-row>

    <v-dialog v-model="previewDialog.open" max-width="980">
      <v-card>
        <v-card-title class="d-flex align-center justify-space-between gap-3">
          <span class="text-truncate">{{ previewDialog.name || 'Apercu' }}</span>
          <v-btn icon="mdi-close" variant="text" @click="closePreview" />
        </v-card-title>
        <v-card-subtitle>{{ previewDialog.path }}</v-card-subtitle>
        <v-card-text>
          <v-alert v-if="previewDialog.message" type="info" variant="tonal" class="mb-4">{{ previewDialog.message }}</v-alert>
          <div v-if="previewDialog.kind === 'image' && previewDialog.content" class="preview-image-wrap">
            <img :src="previewImageSrc" alt="Apercu" class="preview-image" />
          </div>
          <pre v-else-if="previewDialog.kind === 'text'" class="preview-text">{{ previewDialog.content }}</pre>
          <div v-else class="text-body-2 text-medium-emphasis">Aucun apercu direct disponible.</div>
          <div v-if="previewDialog.truncated" class="text-caption text-medium-emphasis mt-3">Le contenu a ete tronque pour conserver de bonnes performances.</div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" prepend-icon="mdi-content-copy" @click="copyPath(previewDialog.path)">Copier le chemin</v-btn>
          <v-btn color="primary" prepend-icon="mdi-open-in-new" @click="openPath(previewDialog.path, 'file')">Ouvrir</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="deleteDialog.open" max-width="520">
      <v-card>
        <v-card-title>Supprimer cet element ?</v-card-title>
        <v-card-text>
          <div class="text-body-2">{{ deleteDialog.path }}</div>
          <div class="text-caption text-medium-emphasis mt-2">L element sera envoye dans la corbeille Windows.</div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeDeleteDialog">Annuler</v-btn>
          <v-btn color="error" prepend-icon="mdi-delete-outline" :loading="deleteDialog.loading" @click="confirmDelete">Supprimer</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <div
      v-if="contextMenu.open"
      class="context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      @click.stop
    >
      <button type="button" class="context-menu__item" @click="triggerContextAction('open')">Ouvrir</button>
      <button type="button" class="context-menu__item" @click="triggerContextAction('reveal')">Afficher dans le dossier</button>
      <button type="button" class="context-menu__item" @click="triggerContextAction('copy')">Copier le chemin</button>
      <button v-if="contextMenu.item?.is_dir === false" type="button" class="context-menu__item" @click="triggerContextAction('preview')">Lire</button>
      <button type="button" class="context-menu__item context-menu__item--danger" @click="triggerContextAction('delete')">Supprimer</button>
    </div>

  </v-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ExplorerRow from './ExplorerRow.vue'

const emit = defineEmits(['disk-usage-change'])

const folders       = ref([])
const loading       = ref(false)
const error         = ref(null)
const progressEvents = ref([])
const scanInfo      = ref(null)
const selectedDrive = ref('C')
const drives        = ref(['C'])
const scanStartedAt = ref(null)
const scanFinishedAt = ref(null)
const dashboardVisible = ref(false)
const initialLoadPending = ref(true)
const highlights = ref({ folders: [], files: [], generatedAt: null })
const distribution = ref({ rootFolders: [], fileTypes: [], generatedAt: null })
const viewMode = ref('list')
const activeTypeFilter = ref(null)
const activeSizeFilter = ref('all')
const currentPathSegments = ref([])
const selectedItem = ref(null)
const explorerBusy = ref(false)
const sortKey = ref('name')
const sortDir = ref('asc')
const previewDialog = ref({ open: false, kind: null, path: '', name: '', content: '', mime: '', message: '', truncated: false })
const deleteDialog = ref({ open: false, loading: false, path: '', item: null })
const contextMenu = ref({ open: false, x: 0, y: 0, item: null })
let dashboardHideTimer = null
let removeProgressListener = null
let removeCacheUpdatedListener = null

const DASHBOARD_GRACE_MS = 6000
const SCAN_DEPTH = 1
const stageOrder = ['start', 'elevation', 'open', 'cache', 'delta', 'usn-enum', 'mft-read', 'fallback', 'done']
const sizeFilterOptions = [
  { title: 'Toutes tailles', value: 'all' },
  { title: 'Fichiers vides', value: 'empty' },
  { title: 'Moins de 100 Mo', value: 'lt-100mb' },
  { title: '100 Mo a 1 Go', value: '100mb-1gb' },
  { title: 'Plus de 1 Go', value: 'gt-1gb' },
]

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
  await runScan(selectedDrive.value, { preserveFolders: false, startup: false })
}

async function runScan(drive, { preserveFolders = false, startup = false } = {}) {
  const normalizedDrive = String(drive || selectedDrive.value || 'C').trim().replace(/[:\\/]+$/g, '').charAt(0).toUpperCase()
  if (!normalizedDrive) return

  clearDashboardHideTimer()
  dashboardVisible.value = true
  loading.value     = true
  error.value       = null
  if (!preserveFolders) {
    folders.value = []
  }
  currentPathSegments.value = []
  scanInfo.value    = null
  progressEvents.value = []
  scanStartedAt.value = Date.now()
  scanFinishedAt.value = null
  if (startup) {
    initialLoadPending.value = true
  }

  try {
    const result = await window.mftAPI.scan(normalizedDrive, SCAN_DEPTH)
    folders.value = result?.summary ?? []
    scanInfo.value = result?.scanInfo ?? null
    await refreshHighlights(normalizedDrive)
    await refreshDistribution(normalizedDrive)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    scanFinishedAt.value = Date.now()
    if (startup) {
      initialLoadPending.value = false
    }
    scheduleDashboardHide()
  }
}

async function loadDriveSummary(drive, { forceScan = false, startup = false } = {}) {
  const normalizedDrive = String(drive || selectedDrive.value || 'C').trim().replace(/[:\\/]+$/g, '').charAt(0).toUpperCase()
  if (!normalizedDrive) return

  await refreshDriveUsage(normalizedDrive)

  if (startup) {
    initialLoadPending.value = true
  }

  if (!forceScan) {
    try {
      const cached = await window.mftAPI.getSummary(normalizedDrive, { typeFilter: activeTypeFilter.value })
      if (cached?.cached) {
        folders.value = cached.summary ?? []
        scanInfo.value = cached.scanInfo ?? null
        error.value = null
        await refreshHighlights(normalizedDrive)
        await refreshDistribution(normalizedDrive)
        if (startup) {
          initialLoadPending.value = false
        }
        return
      }
    } catch {
      // Fall through to an explicit scan if the summary is not available yet.
    }
  }

  await runScan(normalizedDrive, { preserveFolders: false, startup })
}

async function refreshHighlights(drive) {
  try {
    const nextHighlights = await window.mftAPI.getHighlights(drive, { limit: 5 })
    highlights.value = {
      folders: Array.isArray(nextHighlights?.folders) ? nextHighlights.folders : [],
      files: Array.isArray(nextHighlights?.files) ? nextHighlights.files : [],
      generatedAt: nextHighlights?.generatedAt ?? null,
    }
  } catch {
    highlights.value = { folders: [], files: [], generatedAt: null }
  }
}

async function refreshDistribution(drive) {
  try {
    const nextDistribution = await window.mftAPI.getDistribution(drive, { limit: 6 })
    distribution.value = {
      rootFolders: Array.isArray(nextDistribution?.rootFolders) ? nextDistribution.rootFolders : [],
      fileTypes: Array.isArray(nextDistribution?.fileTypes) ? nextDistribution.fileTypes : [],
      generatedAt: nextDistribution?.generatedAt ?? null,
    }
  } catch {
    distribution.value = { rootFolders: [], fileTypes: [], generatedAt: null }
  }
}

async function refreshDriveUsage(drive) {
  try {
    const usage = await window.mftAPI.getDriveUsage(drive)
    emit('disk-usage-change', usage)
  } catch {
    emit('disk-usage-change', null)
  }
}

function clearFilters() {
  activeTypeFilter.value = null
  activeSizeFilter.value = 'all'
}

function toggleTypeFilter(typeKey) {
  activeTypeFilter.value = activeTypeFilter.value === typeKey ? null : typeKey
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

const hasActiveFilters = computed(() => Boolean(activeTypeFilter.value) || activeSizeFilter.value !== 'all')

function matchesSizeFilter(item) {
  const size = Number(item?.size_bytes ?? 0)
  if (activeSizeFilter.value === 'empty') return size === 0
  if (activeSizeFilter.value === 'lt-100mb') return size > 0 && size < 100 * 1024 * 1024
  if (activeSizeFilter.value === '100mb-1gb') return size >= 100 * 1024 * 1024 && size <= 1024 * 1024 * 1024
  if (activeSizeFilter.value === 'gt-1gb') return size > 1024 * 1024 * 1024
  return true
}

function withPath(item, parentPath) {
  return { ...item, path: item.path || `${parentPath}\\${item.name}` }
}

function withPaths(items, parentPath) {
  return (Array.isArray(items) ? items : []).map(item => withPath(item, parentPath))
}

const currentFolders = computed(() => {
  if (currentPathSegments.value.length === 0) {
    return folders.value.map(folder => withPath(folder, `${selectedDrive.value}:`))
  }
  return currentPathSegments.value.at(-1).children
})

const currentFiles = computed(() => {
  if (currentPathSegments.value.length === 0) return []
  return currentPathSegments.value.at(-1).files
})

const filteredFolders = computed(() => currentFolders.value.filter(matchesSizeFilter))
const filteredFiles = computed(() => currentFiles.value.filter(matchesSizeFilter))

const sizeFilterLabel = computed(() => {
  return sizeFilterOptions.find(option => option.value === activeSizeFilter.value)?.title ?? 'Toutes tailles'
})

const currentLevelSummaryLabel = computed(() => {
  const folderCount = filteredFolders.value.length
  const fileCount = filteredFiles.value.length
  if (currentPathSegments.value.length === 0) return `${folderCount} dossiers racine`
  return `${folderCount} dossiers · ${fileCount} fichiers`
})

function typeLabelOf(item) {
  if (item.is_dir !== false) return 'Dossier de fichiers'
  const ext = String(item.ext || '').trim().toLowerCase()
  return ext ? `Fichier ${ext.toUpperCase()}` : 'Fichier'
}

function compareRows(key, dir) {
  const mul = dir === 'asc' ? 1 : -1
  return (a, b) => {
    if (key === 'size') return mul * ((a.size_bytes ?? 0) - (b.size_bytes ?? 0))
    if (key === 'type') return mul * typeLabelOf(a).localeCompare(typeLabelOf(b), 'fr', { sensitivity: 'base' })
    return mul * String(a.name).localeCompare(String(b.name), 'fr', { numeric: true, sensitivity: 'base' })
  }
}

const sortedRows = computed(() => {
  const folderRows = [...filteredFolders.value].sort(compareRows(sortKey.value, sortDir.value))
  const fileRows = [...filteredFiles.value].sort(compareRows(sortKey.value, sortDir.value))
  return [...folderRows, ...fileRows]
})

function setSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

async function enterFolder(item) {
  if (!item || item.is_dir === false) return
  const path = item.path || `${currentFolderPath.value}\\${item.name}`
  explorerBusy.value = true
  try {
    const [children, files] = await Promise.all([
      item.child?.length
        ? Promise.resolve(withPaths(item.child, path))
        : window.mftAPI.getChildren(selectedDrive.value, item.record_number, { typeFilter: activeTypeFilter.value }).then(result => withPaths(result, path)),
      window.mftAPI.getFiles(selectedDrive.value, item.record_number, { typeFilter: activeTypeFilter.value }).then(result => withPaths(result, path)),
    ])
    currentPathSegments.value = [...currentPathSegments.value, {
      name: item.name,
      record_number: item.record_number,
      path,
      children,
      files,
    }]
    selectedItem.value = null
  } catch (e) {
    error.value = e?.message ?? 'Impossible d ouvrir ce dossier.'
  } finally {
    explorerBusy.value = false
  }
}

const currentFolderPath = computed(() => {
  return currentPathSegments.value.at(-1)?.path ?? `${selectedDrive.value}:`
})

function goToSegment(index) {
  if (index < 0) {
    currentPathSegments.value = []
  } else {
    currentPathSegments.value = currentPathSegments.value.slice(0, index + 1)
  }
  selectedItem.value = null
}

function goUp() {
  goToSegment(currentPathSegments.value.length - 2)
}

async function refreshCurrentLevel() {
  if (currentPathSegments.value.length === 0) {
    await loadDriveSummary(selectedDrive.value, { forceScan: false, startup: false })
    return
  }

  const segment = currentPathSegments.value.at(-1)
  explorerBusy.value = true
  try {
    const [children, files] = await Promise.all([
      window.mftAPI.getChildren(selectedDrive.value, segment.record_number, { typeFilter: activeTypeFilter.value }).then(result => withPaths(result, segment.path)),
      window.mftAPI.getFiles(selectedDrive.value, segment.record_number, { typeFilter: activeTypeFilter.value }).then(result => withPaths(result, segment.path)),
    ])
    const updated = [...currentPathSegments.value]
    updated[updated.length - 1] = { ...segment, children, files }
    currentPathSegments.value = updated
  } catch (e) {
    error.value = e?.message ?? 'Impossible de rafraichir ce dossier.'
  } finally {
    explorerBusy.value = false
  }
}

async function openDistributionFolder(entry) {
  const match = folders.value.find(folder => String(folder.record_number) === String(entry.key))
  const target = match
    ? withPath(match, `${selectedDrive.value}:`)
    : { record_number: Number(entry.key), name: entry.label, path: entry.path }
  currentPathSegments.value = []
  await enterFolder(target)
}

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
const showStartupScreen = computed(() => initialLoadPending.value && !error.value && folders.value.length === 0)

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

const remainingTimeSeconds = computed(() => {
  const total = latestAnalysisEvent.value?.totalCount ?? latestAnalysisEvent.value?.totalFiles
  const processed = latestAnalysisEvent.value?.processedCount
  if (!loading.value || !Number.isFinite(total) || !Number.isFinite(processed) || total <= 0 || processed <= 0 || processed >= total) {
    return 0
  }

  const elapsedSeconds = Math.max(1, ((Date.now()) - (scanStartedAt.value ?? Date.now())) / 1000)
  const speed = processed / elapsedSeconds
  if (!Number.isFinite(speed) || speed <= 0) return null
  return Math.max(0, Math.round((total - processed) / speed))
})

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return 'Calcul...'
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) return `${minutes} min ${remainingSeconds.toString().padStart(2, '0')} s`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours} h ${remainingMinutes.toString().padStart(2, '0')} min`
}

function formatStageEta(entry) {
  const seconds = getStageRemainingSeconds(entry)
  if (seconds === null) return 'ETA: calcul en cours'
  return `ETA: ${formatDuration(seconds)}`
}

function getStageRemainingSeconds(entry) {
  const processed = entry?.processedCount
  const total = entry?.totalCount ?? entry?.totalFiles
  if (!loading.value || !Number.isFinite(processed) || !Number.isFinite(total) || total <= 0 || processed <= 0 || processed >= total) {
    return 0
  }

  const stageEvents = progressEvents.value.filter(candidate => candidate?.type === 'progress' && candidate.stage === entry.stage)
  if (stageEvents.length < 2) return null

  const first = stageEvents[0]
  const last = stageEvents.at(-1)
  const firstTimestamp = first?.timestamp ? Date.parse(first.timestamp) : NaN
  const lastTimestamp = last?.timestamp ? Date.parse(last.timestamp) : NaN
  if (!Number.isFinite(firstTimestamp) || !Number.isFinite(lastTimestamp) || lastTimestamp <= firstTimestamp) {
    return null
  }

  const deltaProcessed = (last?.processedCount ?? 0) - (first?.processedCount ?? 0)
  const elapsedSeconds = Math.max(1, (lastTimestamp - firstTimestamp) / 1000)
  const speed = deltaProcessed / elapsedSeconds
  if (!Number.isFinite(speed) || speed <= 0) return null
  return Math.max(0, Math.round((total - processed) / speed))
}

const remainingTimeLabel = computed(() => {
  if (!loading.value && estimatedProgress.value >= 100) return '0 s'
  if (remainingTimeSeconds.value === null) return 'Calcul...'
  return formatDuration(remainingTimeSeconds.value)
})

const topFolders = computed(() => highlights.value.folders ?? [])
const topFiles = computed(() => highlights.value.files ?? [])
const showHighlights = computed(() => !loading.value && !showStartupScreen.value && (topFolders.value.length > 0 || topFiles.value.length > 0))
const rootDistribution = computed(() => {
  const total = distribution.value.rootFolders.reduce((sum, entry) => sum + (entry.size_bytes || 0), 0)
  return distribution.value.rootFolders.map(entry => ({
    ...entry,
    percent: total > 0 ? Math.max(6, Math.round((entry.size_bytes / total) * 100)) : 0,
  }))
})
const fileTypeDistribution = computed(() => {
  const total = distribution.value.fileTypes.reduce((sum, entry) => sum + (entry.size_bytes || 0), 0)
  return distribution.value.fileTypes.map(entry => ({
    ...entry,
    percent: total > 0 ? Math.max(6, Math.round((entry.size_bytes / total) * 100)) : 0,
  }))
})
const showDistribution = computed(() => !loading.value && !showStartupScreen.value && (rootDistribution.value.length > 0 || fileTypeDistribution.value.length > 0))

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

function resolveStagePercent(stage, entry) {
  const processed = entry?.processedCount
  const total = entry?.totalCount ?? entry?.totalFiles
  if (Number.isFinite(processed) && Number.isFinite(total) && total > 0) {
    return Math.max(0, Math.min(100, Math.round((processed / total) * 100)))
  }
  return entry ? (progressPercentByStage[stage] ?? 0) : 0
}

function resolveStageMeta(stage, entry) {
  if (!entry) return 'En attente'
  if (stage === 'usn-enum') {
    return `${formatInteger(entry.totalFiles)} fichiers · ${formatInteger(entry.totalDirs)} dossiers`
  }
  if (stage === 'mft-read') {
    return `${formatInteger(entry.processedCount)} / ${formatInteger(entry.totalFiles, '...')} fichiers · ${formatInteger(entry.filesWithSize)} tailles`
  }
  if (stage === 'fallback') {
    return `${formatInteger(entry.processedCount)} / ${formatInteger(entry.totalCount, '...')} fallback · ${formatInteger(entry.filesRecovered)} recuperes`
  }
  if (stage === 'cache' || stage === 'delta') {
    return 'Resultat incremental disponible'
  }
  if (stage === 'done') {
    return scanInfoLabel.value
  }
  return 'Analyse en cours'
}

const stageCards = computed(() => {
  const activeStage = progressEvents.value.at(-1)?.stage
  return stageOrder.map(stage => {
    const entry = latestProgressByStage.value[stage] ?? null
    let status = 'pending'
    if (entry) {
      status = loading.value && activeStage === stage ? 'active' : 'done'
    } else if (loading.value && activeStage === stage) {
      status = 'active'
    }

    return {
      key: stage,
      label: progressStageLabel(stage),
      percent: status === 'done' ? 100 : resolveStagePercent(stage, entry),
      message: entry?.message ?? (status === 'active' ? currentProgressMessage.value : 'En attente'),
      meta: resolveStageMeta(stage, entry),
      eta: entry ? formatStageEta(entry) : 'ETA: en attente',
      status,
      color: status === 'done' ? 'success' : status === 'active' ? 'primary' : 'grey',
    }
  })
})

async function openInExplorer(path, kind) {
  try {
    if (kind === 'file') {
      await window.mftAPI.revealPath(path)
      return
    }
    await window.mftAPI.openPath(path)
  } catch (e) {
    error.value = e?.message ?? 'Impossible d ouvrir le chemin dans l explorateur.'
  }
}

async function copyPath(path) {
  if (!path) return
  try {
    await window.mftAPI.copyText(path)
  } catch (e) {
    error.value = e?.message ?? 'Impossible de copier le chemin.'
  }
}

async function openPath(path, kind = 'folder') {
  await openInExplorer(path, kind)
}

async function previewPath(path) {
  try {
    const result = await window.mftAPI.previewPath(path)
    previewDialog.value = {
      open: true,
      kind: result?.kind ?? null,
      path: result?.path ?? path,
      name: result?.name ?? '',
      content: result?.content ?? '',
      mime: result?.mime ?? '',
      message: result?.message ?? '',
      truncated: Boolean(result?.truncated),
    }
  } catch (e) {
    error.value = e?.message ?? 'Impossible d ouvrir l apercu.'
  }
}

function closePreview() {
  previewDialog.value = { open: false, kind: null, path: '', name: '', content: '', mime: '', message: '', truncated: false }
}

function requestDelete(item) {
  deleteDialog.value = {
    open: true,
    loading: false,
    path: item?.path ?? '',
    item,
  }
}

function closeDeleteDialog() {
  deleteDialog.value = { open: false, loading: false, path: '', item: null }
}

function removeItemByPath(items, targetPath) {
  return items.filter(item => item?.path !== targetPath)
}

function removeItemEverywhere(targetPath) {
  folders.value = folders.value.filter(folder => (folder.path || `${selectedDrive.value}:\\${folder.name}`) !== targetPath)
  currentPathSegments.value = currentPathSegments.value.map(segment => ({
    ...segment,
    children: removeItemByPath(segment.children, targetPath),
    files: removeItemByPath(segment.files, targetPath),
  }))
}

async function confirmDelete() {
  if (!deleteDialog.value.path) return
  deleteDialog.value = { ...deleteDialog.value, loading: true }
  try {
    await window.mftAPI.trashPath(deleteDialog.value.path)
    removeItemEverywhere(deleteDialog.value.path)
    await loadDriveSummary(selectedDrive.value, { forceScan: true, startup: false })
    closeDeleteDialog()
  } catch (e) {
    deleteDialog.value = { ...deleteDialog.value, loading: false }
    error.value = e?.message ?? 'Suppression impossible.'
  }
}

async function handleNodeAction(payload) {
  closeContextMenu()
  const { action, item } = payload ?? {}
  if (!item?.path) return
  if (action === 'copy') {
    await copyPath(item.path)
    return
  }
  if (action === 'open') {
    await openPath(item.path, item.is_dir === false ? 'file' : 'folder')
    return
  }
  if (action === 'reveal') {
    await openInExplorer(item.path, 'file')
    return
  }
  if (action === 'preview') {
    await previewPath(item.path)
    return
  }
  if (action === 'delete') {
    requestDelete(item)
  }
}

function openContextMenu(payload) {
  const nativeEvent = payload?.event
  const item = payload?.item ?? null
  if (!nativeEvent || !item?.path) return
  contextMenu.value = {
    open: true,
    x: nativeEvent.clientX,
    y: nativeEvent.clientY,
    item,
  }
}

function closeContextMenu() {
  contextMenu.value = { open: false, x: 0, y: 0, item: null }
}

async function triggerContextAction(action) {
  const item = contextMenu.value.item
  closeContextMenu()
  await handleNodeAction({ action, item })
}

const previewImageSrc = computed(() => {
  if (previewDialog.value.kind !== 'image' || !previewDialog.value.content || !previewDialog.value.mime) return ''
  return `data:${previewDialog.value.mime};base64,${previewDialog.value.content}`
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
  window.addEventListener('click', closeContextMenu)
  window.addEventListener('blur', closeContextMenu)
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
    refreshHighlights(payload.drive)
    refreshDistribution(payload.drive)
  })

  window.mftAPI.getDrives()
    .then(async availableDrives => {
      if (!Array.isArray(availableDrives) || availableDrives.length === 0) return
      drives.value = availableDrives
      if (!availableDrives.includes(selectedDrive.value)) {
        selectedDrive.value = availableDrives[0]
      }
      await loadDriveSummary(selectedDrive.value, { forceScan: false, startup: true })
    })
    .catch(e => {
      error.value = e?.message ?? 'Impossible de charger la liste des lecteurs.'
    })
    .finally(() => {
      if (!loading.value) {
        initialLoadPending.value = false
      }
    })
})

watch(activeTypeFilter, async () => {
  await refreshCurrentLevel()
})

watch(selectedDrive, async (nextDrive, previousDrive) => {
  if (!nextDrive || nextDrive === previousDrive) return
  currentPathSegments.value = []
  clearFilters()
  await loadDriveSummary(nextDrive, { forceScan: false, startup: false })
})

onBeforeUnmount(() => {
  clearDashboardHideTimer()
  window.removeEventListener('click', closeContextMenu)
  window.removeEventListener('blur', closeContextMenu)
  removeProgressListener?.()
  removeProgressListener = null
  removeCacheUpdatedListener?.()
  removeCacheUpdatedListener = null
})
</script>

<style scoped>
.disk-tree-shell {
  position: relative;
  min-height: 100vh;
  padding: 24px;
  color: #e8edf7;
}

.startup-screen {
  position: absolute;
  inset: 0;
  z-index: 5;
  overflow: auto;
  border-radius: 28px;
  padding: 40px 28px;
  background:
    linear-gradient(180deg, rgba(21, 21, 21, 0.98), rgba(18, 18, 18, 0.96)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 34%);
  backdrop-filter: blur(18px);
}

.startup-screen__halo {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 999px;
  filter: blur(80px);
  opacity: 0.45;
  pointer-events: none;
}

.startup-screen__halo--left {
  top: -80px;
  left: -40px;
  background: rgba(255, 255, 255, 0.05);
}

.startup-screen__halo--right {
  right: -60px;
  bottom: -120px;
  background: rgba(255, 255, 255, 0.03);
}

.startup-screen__content {
  position: relative;
  max-width: 1180px;
  margin: 0 auto;
}

.startup-screen__eyebrow {
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.8rem;
  color: rgba(198, 212, 235, 0.72);
}

.startup-screen__title {
  margin: 12px 0 8px;
  font-size: clamp(2rem, 3vw, 3.5rem);
  line-height: 1.05;
}

.startup-screen__subtitle {
  max-width: 760px;
  margin: 0;
  font-size: 1rem;
  color: rgba(225, 233, 244, 0.82);
}

.startup-screen__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.startup-screen__bar {
  margin-top: 22px;
  animation: loading-bar-enter 0.6s ease;
}

.startup-screen__stats,
.startup-screen__stages,
.stage-card-grid {
  display: grid;
  gap: 16px;
}

.startup-screen__stats {
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  margin-top: 24px;
}

.startup-screen__stages,
.stage-card-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.startup-screen__stages {
  margin-top: 28px;
}

.startup-screen__highlights,
.highlight-grid,
.startup-screen__distribution {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.startup-screen__highlights {
  margin-top: 28px;
}

.startup-screen__distribution {
  margin-top: 20px;
}

.startup-screen__journal {
  margin-top: 28px;
  border-color: rgba(170, 191, 218, 0.16) !important;
  background: rgba(24, 24, 24, 0.82);
  animation: fade-up 0.55s ease;
}

.startup-metric-card,
.stage-card {
  border: 1px solid rgba(170, 191, 218, 0.16);
  border-radius: 20px;
  background: rgba(24, 24, 24, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.startup-metric-card {
  padding: 18px;
  animation: fade-up 0.45s ease both;
}

.startup-metric-card__label {
  display: block;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(198, 212, 235, 0.66);
}

.startup-metric-card__value {
  display: block;
  margin-top: 10px;
  font-size: 1.15rem;
  color: #ffffff;
}

.startup-metric-card__value--small {
  font-size: 0.98rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stage-card {
  padding: 16px;
  transition: transform 0.24s ease, border-color 0.24s ease, box-shadow 0.24s ease, background 0.24s ease;
}

.stage-card:hover {
  transform: translateY(-2px);
}

.stage-card--active {
  border-color: rgba(83, 164, 255, 0.38);
  box-shadow: 0 0 0 1px rgba(83, 164, 255, 0.08), 0 14px 40px rgba(0, 0, 0, 0.18);
  background: rgba(15, 34, 58, 0.92);
}

.stage-card--done {
  border-color: rgba(57, 191, 153, 0.28);
  background: rgba(12, 32, 31, 0.88);
}

.stage-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.stage-card__title {
  font-size: 0.95rem;
  font-weight: 600;
}

.stage-card__percent {
  font-size: 0.85rem;
  color: rgba(198, 212, 235, 0.82);
}

.stage-card__message {
  margin-top: 12px;
  font-size: 0.9rem;
  color: rgba(245, 248, 252, 0.94);
}

.stage-card__meta {
  margin-top: 6px;
  font-size: 0.8rem;
  color: rgba(198, 212, 235, 0.64);
}

.stage-card__eta {
  margin-top: 10px;
  font-size: 0.78rem;
  color: rgba(148, 214, 247, 0.82);
}

.highlight-card {
  border-color: rgba(170, 191, 218, 0.16) !important;
  background: rgba(24, 24, 24, 0.84);
  animation: fade-up 0.55s ease both;
}

.distribution-card {
  border-color: rgba(170, 191, 218, 0.16) !important;
  background: rgba(24, 24, 24, 0.84);
  animation: fade-up 0.55s ease both;
}

.highlight-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.distribution-card__controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.highlight-list {
  max-height: 280px;
  overflow: auto;
}

.highlight-card__actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-chart {
  display: grid;
  gap: 12px;
}

.mini-chart__row {
  display: grid;
  grid-template-columns: minmax(92px, 140px) 1fr auto;
  gap: 12px;
  align-items: center;
}

.mini-chart__row--interactive {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.mini-chart__row--interactive:hover .mini-chart__bar-wrap,
.mini-chart__row--active .mini-chart__bar-wrap {
  box-shadow: 0 0 0 1px rgba(135, 193, 255, 0.22), 0 8px 20px rgba(0, 0, 0, 0.14);
}

.mini-chart__label,
.mini-chart__value {
  font-size: 0.84rem;
}

.mini-chart__label {
  color: rgba(240, 244, 249, 0.92);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-chart__value {
  color: rgba(198, 212, 235, 0.76);
}

.mini-chart__bar-wrap {
  position: relative;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.mini-chart__bar {
  height: 100%;
  border-radius: inherit;
  min-width: 8px;
  transition: width 0.35s ease;
}

.mini-chart__bar--folder {
  background: linear-gradient(90deg, rgba(250, 180, 52, 0.88), rgba(255, 120, 72, 0.9));
}

.mini-chart__bar--type {
  background: linear-gradient(90deg, rgba(58, 154, 255, 0.9), rgba(34, 212, 167, 0.9));
}

.progress-timeline {
  max-height: 320px;
  overflow: auto;
}

.explorer-shell {
  min-height: 0;
}

.tree-surface {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: calc(100vh - 180px);
  max-height: calc(100vh - 180px);
  padding: 18px 18px 14px;
  border-color: rgba(170, 191, 218, 0.16) !important;
  background: rgba(8, 17, 31, 0.52);
  overflow: hidden;
}

.explorer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 4px 2px 0;
}

.explorer-breadcrumb {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
  min-width: 0;
}

.explorer-breadcrumb__sep {
  color: rgba(214, 224, 238, 0.4);
}

.explorer-breadcrumb__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(214, 224, 238, 0.78);
  font-size: 0.86rem;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.explorer-breadcrumb__item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #edf3fb;
}

.explorer-breadcrumb__item--active {
  color: #edf3fb;
  font-weight: 600;
}

.explorer-toolbar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.explorer-toolbar__select {
  width: 118px;
}

.explorer-toolbar__select--wide {
  width: 170px;
}

.explorer-toolbar__scan {
  white-space: nowrap;
}

.explorer-loading,
.explorer-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 16px;
  color: rgba(214, 224, 238, 0.68);
}

.explorer-loading {
  flex-direction: row;
}

.explorer-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 6px 2px 10px;
}

.explorer-content--table {
  padding-top: 0;
}

.explorer-table {
  width: 100%;
  border-collapse: collapse;
}

.explorer-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(8, 17, 31, 0.92);
  text-align: left;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: rgba(214, 224, 238, 0.72);
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}

.explorer-table thead th:hover {
  color: #edf3fb;
}

.explorer-table__col-type {
  width: 220px;
}

.explorer-table__col-size {
  width: 140px;
}

.explorer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 6px;
  padding-right: 4px;
}

.preview-text {
  margin: 0;
  padding: 16px;
  max-height: 62vh;
  overflow: auto;
  border-radius: 16px;
  background: rgba(8, 17, 31, 0.92);
  color: #dce8f6;
  font-size: 0.86rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-image-wrap {
  display: flex;
  justify-content: center;
  padding: 12px;
  border-radius: 18px;
  background: rgba(8, 17, 31, 0.92);
}

.preview-image {
  max-width: 100%;
  max-height: 68vh;
  object-fit: contain;
  border-radius: 14px;
}

.context-menu {
  position: fixed;
  z-index: 30;
  min-width: 220px;
  padding: 8px;
  border: 1px solid rgba(170, 191, 218, 0.18);
  border-radius: 16px;
  background: rgba(7, 15, 28, 0.96);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(14px);
}

.context-menu__item {
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #edf3fb;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.context-menu__item:hover {
  background: rgba(83, 164, 255, 0.16);
}

.context-menu__item--danger {
  color: #ff9d9d;
}

.recent-files-list {
  max-height: 220px;
  overflow: auto;
}

.recent-files-list--startup {
  max-height: 240px;
}

.stage-card-move,
.stage-card-enter-active,
.stage-card-leave-active {
  transition: all 0.3s ease;
}

.stage-card-enter-from,
.stage-card-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes loading-bar-enter {
  from {
    opacity: 0;
    transform: scaleX(0.92);
  }
  to {
    opacity: 1;
    transform: scaleX(1);
  }
}

@media (max-width: 960px) {
  .disk-tree-shell {
    padding: 16px;
  }

  .startup-screen {
    padding: 28px 18px;
    border-radius: 22px;
  }

  .mini-chart__row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .explorer-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .tree-surface {
    min-height: calc(100vh - 156px);
    max-height: calc(100vh - 156px);
    padding: 16px 14px 12px;
  }
}
</style>
