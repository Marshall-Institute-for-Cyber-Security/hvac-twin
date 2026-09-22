import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Independent single-page entries, not routes in one app: the room picker
// (index.html), each twin's HMI (closet.html, office.html), and the
// red-team attack console (attack.html) are meant to run as their own
// pages against their own backends (hvac_twin.hmi for a given twin, or
// hvac_twin.console) -- keeping them as separate HTML entries (rather
// than client-side routes) means any one can be opened on its own with no
// shared state or accidental coupling.
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        home: resolve(import.meta.dirname, 'index.html'),
        closet: resolve(import.meta.dirname, 'closet.html'),
        attack: resolve(import.meta.dirname, 'attack.html'),
        office: resolve(import.meta.dirname, 'office.html'),
        defenses: resolve(import.meta.dirname, 'defenses.html'),
      },
    },
  },
})
