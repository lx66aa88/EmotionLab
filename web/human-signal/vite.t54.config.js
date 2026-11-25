import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
export default defineConfig({
  plugins:[react()],
  resolve:{alias:{'./App.jsx':fileURLToPath(new URL('./src/AppT54.jsx',import.meta.url))}},
  server:{host:'127.0.0.1',proxy:{'/api':'http://127.0.0.1:8774'}},
  build:{outDir:'dist-t54',target:'es2020',sourcemap:false}
});
