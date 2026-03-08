import { createApp } from 'vue'
import App from './App.vue'
import router from './router.ts'
import '@carbon/styles/css/styles.css'
import './style.css'

const app = createApp(App)
app.use(router)
app.mount('#app')
