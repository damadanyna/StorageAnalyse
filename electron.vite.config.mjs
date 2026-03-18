import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import Fonts from 'unplugin-fonts/vite'
import Layouts from 'vite-plugin-vue-layouts-next'
import Vue from '@vitejs/plugin-vue'
import VueRouter from 'unplugin-vue-router/vite'
import { VueRouterAutoImports } from 'unplugin-vue-router'
import Vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname  = path.dirname(__filename)

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: { external: ['fsevents'] }
    }
  },

  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: 'out/preload',
      rollupOptions: {
        external: ['fsevents'],
        input: {
          index: path.resolve(__dirname, 'src/preload/index.js')
        },
        output: {
          format: 'cjs',
          entryFileNames: '[name].js'  // ← index.js au lieu de index.mjs
        }
      }
    }
  },

  renderer: {
    root: path.resolve(__dirname, 'src/renderer'),
    plugins: [
      VueRouter({
        routesFolder: 'src/renderer/pages',
        dts: false,
      }),
      Layouts({
        layoutsDirs: 'src/renderer/layouts',
      }),
      Vue({ template: { transformAssetUrls } }),
      Vuetify({
        autoImport: true,
        styles: {
          configFile: path.resolve(__dirname, 'src/renderer/styles/settings.scss'),
        },
      }),
      Components({
        dirs: ['src/renderer/components'],
      }),
      Fonts({
        google: {
          families: [{ name: 'Roboto', styles: 'wght@100;300;400;500;700;900' }],
        },
      }),
      AutoImport({
        imports: [
          'vue',
          VueRouterAutoImports,
          { pinia: ['defineStore', 'storeToRefs'] },
        ],
        eslintrc: { enabled: true },
        vueTemplate: true,
      }),
    ],
    css: {
      preprocessorOptions: {
        scss: { api: 'modern-embedded' }
      }
    },
    optimizeDeps: {
      exclude: [
        'vuetify',
        'vue-router',
        'unplugin-vue-router/runtime',
        'unplugin-vue-router/data-loaders',
        'unplugin-vue-router/data-loaders/basic',
        'fsevents',
      ],
    },
    define: { 'process.env': {} },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src/renderer'),
      },
      extensions: ['.js', '.json', '.jsx', '.mjs', '.ts', '.tsx', '.vue'],
    },
    server: { port: 3000 },
    base: './'
  }
})