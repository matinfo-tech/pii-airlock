import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import SetupPicker from './components/SetupPicker.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('SetupPicker', SetupPicker)
  },
} satisfies Theme
