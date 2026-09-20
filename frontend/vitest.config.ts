import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Deliberately separate from vite.config.ts. That file carries a dev-server
// proxy to the FastAPI backend, which tests do not use — every API call is
// mocked — and merging the two would mean one config serving two purposes.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // Tests live outside src/ so `tsc -b` during `pnpm build` never sees them.
    include: ['tests/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    // Restores the original implementation between tests, so a vi.spyOn in one
    // file cannot leak into another.
    restoreMocks: true,
  },
});
