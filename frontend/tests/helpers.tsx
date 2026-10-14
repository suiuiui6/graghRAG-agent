import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
export const user = { user_id: 'u', username: 'user', email: 'u@example.test', display_name: '用户甲', roles: [], department: null, last_login: null }
export const node = { id: 'n1', label: '收入', entity_type: 'metric', properties: { value: 10 }, page_idx: 0, bbox_norm: [1, 2, 3, 4], grounding_status: 'grounded' }
export const graph = { nodes: [node, { ...node, id: 'n2', label: '成本' }], edges: [{ id: 'e', from: 'n1', to: 'n2', relation: 'depends' }], stats: { total_nodes: 2, total_edges: 1, entity_types: { metric: 2 }, grounded_nodes: 2 }, documents: ['d'] }
function Location() { const loc = useLocation(); return <output data-testid="location">{loc.pathname}{loc.search}</output> }
export function mount(element: ReactNode, path = '/', route = '*') { return render(<MemoryRouter initialEntries={[path]}><Location /><Routes><Route path={route} element={element} /><Route path="*" element={<p>目的页面</p>} /></Routes></MemoryRouter>) }
export function deferred<T>() { let resolve!: (value: T) => void; let reject!: (err: unknown) => void; const promise = new Promise<T>((a,b) => { resolve=a; reject=b }); return { promise, resolve, reject } }
