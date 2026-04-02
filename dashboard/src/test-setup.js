import '@testing-library/jest-dom/vitest';

// Stub EventSource for tests (SSE is not available in jsdom)
if (typeof globalThis.EventSource === 'undefined') {
  globalThis.EventSource = class EventSource {
    constructor() {
      this.readyState = 0;
    }
    addEventListener() {}
    removeEventListener() {}
    close() {}
  };
}
