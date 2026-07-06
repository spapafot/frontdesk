import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// This Node/jsdom combo ships a native localStorage that throws without a
// backing file. Replace it with a deterministic in-memory Storage.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear() {
    this.store.clear();
  }
  getItem(key: string) {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }
  key(index: number) {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value));
  }
}
const memoryStorage = new MemoryStorage();
Object.defineProperty(window, "localStorage", { value: memoryStorage, configurable: true });
Object.defineProperty(globalThis, "localStorage", { value: memoryStorage, configurable: true });

// jsdom doesn't implement these; components call them on mount.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
