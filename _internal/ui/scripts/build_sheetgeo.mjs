// Optional lockfile-verified icon package lives in the task tree, never the shared junction.
import { build } from 'vite';
await build({ configFile: 'vite.gallery.config.ts', ...(process.env.SHEETGEO_LUCIDE ? {
  resolve: { dedupe: ['react', 'react-dom'], alias: [{ find: /^lucide-react$/, replacement: process.env.SHEETGEO_LUCIDE }] },
} : {}) });
