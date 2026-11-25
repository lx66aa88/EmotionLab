import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
export default defineConfig({
  plugins:[react()],
  resolve:{alias:{'./App.jsx':fileURLToPath(new URL('./src/AppT53.jsx',import.meta.url))}},
  server:{host:'127.0.0.1',proxy:{'/api':'http://127.0.0.1:8773'}},
  build:{outDir:'dist-t53',target:'es2020',sourcemap:false}
});
