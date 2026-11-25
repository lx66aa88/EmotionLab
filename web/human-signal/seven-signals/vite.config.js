import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const root = fileURLToPath(new URL('.', import.meta.url));
const licenses = {
  'Archivo-OFL.txt': '../public/fonts/Archivo-OFL.txt',
  'IBMPlexMono-OFL.txt': '../public/fonts/IBMPlexMono-OFL.txt',
  'React-MIT.txt': '../node_modules/react/LICENSE',
  'ReactDOM-MIT.txt': '../node_modules/react-dom/LICENSE',
};

export default defineConfig({
  root,
  publicDir: false,
  appType: 'mpa',
  plugins: [react(), {
    name: 'seven-signals-licenses',
    generateBundle() {
      for (const [name, location] of Object.entries(licenses)) {
        this.emitFile({ type: 'asset', fileName: `licenses/${name}`,
          source: readFileSync(new URL(location, import.meta.url)) });
      }
    },
  }],
  build: { outDir: 'dist', target: 'es2020', assetsInlineLimit: 0 },
  preview: {
    host: '127.0.0.1', port: 8786, strictPort: true,
    headers: {
      'Content-Security-Policy': "default-src 'self'; connect-src 'none'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
      'Permissions-Policy': 'camera=(), microphone=()',
    },
  },
});
