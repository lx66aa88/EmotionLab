import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig(({ mode }) => {
  const release = mode === 't621' ? 't621' : 't62';
  const app = release === 't621' ? 'AppT621' : 'AppT62';
  return {
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [
    react(),
    {
      name: 'human-signal-t62-entry',
      transformIndexHtml: () => [
        { tag: 'meta', attrs: { name: 'emotionlab-release', content: `human-signal-${release}` }, injectTo: 'head' },
      ],
    },
  ],
  resolve: { alias: { './App.jsx': fileURLToPath(new URL(`./src/${app}.jsx`, import.meta.url)) } },
  build: { outDir: `dist-${release}`, target: 'es2020', sourcemap: false },
  };
});
