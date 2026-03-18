
// Plugins
import { registerPlugins } from '@/plugins'
import '@/styles/style.css'
import 'vuetify/styles'
import api from './plugins/api'
import pinia from './stores/index'

// Components
import App from './App.vue'

// Composables
import { createApp } from 'vue'

// Styles
import 'unfonts.css'

const app = createApp(App)

registerPlugins(app)
app.use(api) // Assure-toi que le plugin est utilisé
app.use(pinia) // Assure-toi que le plugin est utilisé
app.mount('#app')
