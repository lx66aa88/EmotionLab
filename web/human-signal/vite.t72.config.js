import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [
    react(),
    {
      name: 'human-signal-t72-entry',
      transformIndexHtml: () => [
        { tag: 'meta', attrs: { name: 'emotionlab-release', content: 'human-signal-t72' }, injectTo: 'head' },
      ],
    },
  ],
  resolve: { alias: { './App.jsx': fileURLToPath(new URL('./src/AppT72.jsx', import.meta.url)) } },
  build: { outDir: 'dist-t72', emptyOutDir: false, target: 'es2020', sourcemap: false },
});
