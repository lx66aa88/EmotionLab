import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
export default defineConfig(({mode}) => {
  const photo = mode === 't52';
  return {
    plugins: [react()],
    resolve: {alias: photo ? {'./App.jsx': fileURLToPath(new URL('./src/AppT52.jsx', import.meta.url))} : {}},
    server: {host: '127.0.0.1', proxy: {'/api': `http://127.0.0.1:${photo ? 8772 : 8765}`}},
    build: {outDir: photo ? 'dist-t52' : 'dist', target: 'es2020', sourcemap: false}
  };
});
