import { copyFileSync } from 'node:fs'
import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// GitHub Pages has no server-side routing: for a path with no matching
// static file (every deep client-side route, e.g.
// /raidian/readings/<id>/result, on refresh or direct load) it serves the
// site's 404.html directly at the requested URL -- no HTTP redirect, so
// the address bar keeps the real route. Copying the already-built
// index.html (which already has correct /raidian/-prefixed asset URLs) to
// 404.html after the build lets that fallback load the same SPA shell;
// BrowserRouter then reads the still-correct window.location and renders
// the matching route client-side. Must run after `vite build` writes the
// final index.html -- copying the unprocessed source index.html instead
// would carry unresolved asset paths and break CSS/JS loading.
function githubPagesSpaFallback(): Plugin {
  let outDir = 'dist'
  let root = process.cwd()
  return {
    name: 'github-pages-spa-fallback',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir
      root = config.root
    },
    closeBundle() {
      const distDir = resolve(root, outDir)
      copyFileSync(resolve(distDir, 'index.html'), resolve(distDir, '404.html'))
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), githubPagesSpaFallback()],
  // Step 76: GitHub Pages project-site base path. ADR-0004 (docs/DECISIONS.md,
  // Accepted) names GitHub Pages as the frontend's intended host, and this
  // repository's own git remote (origin -> github.com/RaidianHQ/raidian.git)
  // confirms the actual repo name is "raidian" -- absent a custom domain (no
  // CNAME file exists anywhere in this repository), GitHub's own Pages
  // platform serves a project repository at
  // https://<org>.github.io/<repo-name>/, i.e. "/raidian/" here.
  //
  // Deliberately NOT hard-coded as the default: this only applies when a
  // future deploy step explicitly sets VITE_BASE_PATH. Local development
  // (`npm run dev`) and any build run without it keep defaulting to root
  // "/" -- correct for local dev, and for a possible future custom-domain
  // deployment, which nothing in this repository currently rules out.
  base: process.env.VITE_BASE_PATH ?? '/',
})
