import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig(({mode})=>{const env=loadEnv(mode,process.cwd(),'');return {plugins:[vue()],server:{strictPort:true,proxy:{'/api':{target:env.VITE_BACKEND_TARGET||'http://127.0.0.1:8200',changeOrigin:false}}},build:{rollupOptions:{output:{manualChunks:{charts:['echarts/core','echarts/charts','echarts/components','echarts/renderers'],map:['leaflet','leaflet.heat']}}}}}})
