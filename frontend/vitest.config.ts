import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}', 'public/**/*.js'],
      exclude: ['src/**/*.test.{ts,tsx}'],
      reporter: ['text', 'json', 'json-summary', 'lcov'],
      thresholds: { lines: 90, branches: 90 },
    },
  },
})
