<template>
  <v-app class="app-shell">
    <header class="app-topbar">
      <div class="app-topbar__drag" />
      <button type="button" class="app-topbar__menu" aria-label="Menu principal">
        <span class="app-topbar__menu-line" />
        <span class="app-topbar__menu-line" />
        <span class="app-topbar__menu-line" />
      </button>
      <div class="app-topbar__brand-wrap">
        <div class="app-topbar__brand-dot" />
        <div class="app-topbar__brand">StorageAnalyse</div>
      </div>
      <div class="app-topbar__spacer" />
      <div v-if="diskUsage?.drive" class="app-topbar__usage" :title="`${diskUsage.drive}: ${diskUsage.usedDisplay} / ${diskUsage.totalDisplay}`">
        <div class="app-topbar__usage-meta">
          <span class="app-topbar__usage-drive">{{ diskUsage.drive }}:</span>
          <span class="app-topbar__usage-percent">{{ diskUsage.usedPercent }}%</span>
          <span class="app-topbar__usage-capacity">{{ diskUsage.usedDisplay }} / {{ diskUsage.totalDisplay }}</span>
        </div>
        <div class="app-topbar__usage-bar">
          <div class="app-topbar__usage-bar-fill" :style="{ width: `${diskUsage.usedPercent}%` }" />
        </div>
      </div>
      <div class="app-window-controls">
        <button type="button" class="app-window-controls__button" aria-label="Minimiser" @click="minimizeWindow">
          <span class="app-window-controls__glyph app-window-controls__glyph--minimize" />
        </button>
        <button type="button" class="app-window-controls__button" :aria-label="isMaximized ? 'Restaurer' : 'Maximiser'" @click="toggleMaximizeWindow">
          <span :class="['app-window-controls__glyph', isMaximized ? 'app-window-controls__glyph--restore' : 'app-window-controls__glyph--maximize']" />
        </button>
        <button type="button" class="app-window-controls__button app-window-controls__button--close" aria-label="Fermer" @click="closeWindow">
          <span class="app-window-controls__glyph app-window-controls__glyph--close" />
        </button>
      </div>
    </header>
    <v-main class="app-main">
      <DiskTree @disk-usage-change="updateDiskUsage" />
    </v-main>
  </v-app>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import DiskTree from '@/components/DiskTree.vue'

const isMaximized = ref(false)
const diskUsage = ref(null)
let removeWindowStateListener = null

function updateDiskUsage(payload) {
  diskUsage.value = payload?.drive ? payload : null
}

async function minimizeWindow() {
  await window.mftAPI.minimizeWindow()
}

async function toggleMaximizeWindow() {
  const result = await window.mftAPI.toggleMaximizeWindow()
  isMaximized.value = Boolean(result?.isMaximized)
}

async function closeWindow() {
  await window.mftAPI.closeWindow()
}

onMounted(async () => {
  removeWindowStateListener = window.mftAPI.onWindowState(payload => {
    isMaximized.value = Boolean(payload?.isMaximized)
  })
  const state = await window.mftAPI.getWindowState()
  isMaximized.value = Boolean(state?.isMaximized)
})

onBeforeUnmount(() => {
  removeWindowStateListener?.()
  removeWindowStateListener = null
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #151515;
  color: #f4f7fb;
}

.app-main {
  min-height: 100vh;
  background: transparent;
}

.app-topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 48px;
  padding: 0 0 0 14px;
  background: rgba(21, 21, 21, 0.92);
  backdrop-filter: blur(16px);
  -webkit-app-region: drag;
}

.app-topbar__drag {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.app-topbar__menu {
  display: inline-flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  cursor: default;
  position: relative;
  z-index: 1;
  -webkit-app-region: no-drag;
}

.app-topbar__menu-line {
  display: block;
  width: 14px;
  height: 2px;
  margin: 0 auto;
  border-radius: 999px;
  background: rgba(244, 247, 251, 0.92);
}

.app-topbar__brand-wrap {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  -webkit-app-region: no-drag;
}

.app-topbar__brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #67b7ff, #39d5a8);
  box-shadow: 0 0 18px rgba(86, 181, 255, 0.45);
}

.app-topbar__brand {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #f4f7fb;
}

.app-topbar__spacer {
  flex: 1;
}

.app-topbar__usage {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 220px;
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  -webkit-app-region: no-drag;
}

.app-topbar__usage-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 0.74rem;
  color: rgba(233, 239, 248, 0.82);
}

.app-topbar__usage-drive,
.app-topbar__usage-percent {
  font-weight: 700;
  color: #f4f7fb;
}

.app-topbar__usage-capacity {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-topbar__usage-bar {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.app-topbar__usage-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ffb347, #ffd166);
}

.app-window-controls {
  position: relative;
  z-index: 1;
  display: flex;
  align-self: stretch;
  margin-left: auto;
  -webkit-app-region: no-drag;
}

.app-window-controls__button {
  width: 46px;
  height: 48px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #eef4fb;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.18s ease;
}

.app-window-controls__button:hover {
  background: rgba(255, 255, 255, 0.08);
}

.app-window-controls__button--close:hover {
  background: #db4d4d;
}

.app-window-controls__glyph {
  position: relative;
  display: inline-block;
  width: 12px;
  height: 12px;
}

.app-window-controls__glyph--minimize::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 2px;
  height: 1.5px;
  background: currentColor;
}

.app-window-controls__glyph--maximize {
  border: 1.5px solid currentColor;
}

.app-window-controls__glyph--restore::before,
.app-window-controls__glyph--restore::after {
  content: '';
  position: absolute;
  border: 1.5px solid currentColor;
  background: transparent;
}

.app-window-controls__glyph--restore::before {
  top: 0;
  right: 0;
  width: 8px;
  height: 8px;
}

.app-window-controls__glyph--restore::after {
  left: 0;
  bottom: 0;
  width: 8px;
  height: 8px;
  background: linear-gradient(180deg, rgba(6, 11, 20, 0.98), rgba(9, 17, 30, 0.9));
}

.app-window-controls__glyph--close::before,
.app-window-controls__glyph--close::after {
  content: '';
  position: absolute;
  top: 5px;
  left: 0;
  width: 12px;
  height: 1.5px;
  background: currentColor;
}

.app-window-controls__glyph--close::before {
  transform: rotate(45deg);
}

.app-window-controls__glyph--close::after {
  transform: rotate(-45deg);
}
</style>
