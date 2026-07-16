import { defineConfig } from 'astro/config';

// Static-first. All pages are prerendered to plain HTML; interactivity and
// auth checks happen client-side via Alpine.js talking to the FastAPI backend.
// This keeps the frontend maximally static and trivial to host.
export default defineConfig({
  output: 'static',
  server: {
    port: 4321,
  },
});
