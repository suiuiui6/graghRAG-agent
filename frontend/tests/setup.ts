import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

Object.defineProperty(Element.prototype, 'scrollIntoView', { value: vi.fn(), configurable: true })
Object.defineProperty(Element.prototype, 'scrollTo', { value: vi.fn(), configurable: true })
afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })
