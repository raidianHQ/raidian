import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
