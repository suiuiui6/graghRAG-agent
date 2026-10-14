import { expect, it, vi } from 'vitest'
import { act, screen, waitFor } from '@testing-library/react'
import ReactDOM from 'react-dom/client'
import App from '../src/App'
import { api } from '../src/lib/api'
import { useAppStore } from '../src/stores/useAppStore'
import { mount, graph } from './helpers'
it.each(['/query','/query/doc','/graph','/graph/doc','/missing','/'])('real application route resolves %s',async path=>{
  useAppStore.setState({user:null});vi.spyOn(api,'getStats').mockResolvedValue({total_docs:0,total_kg_nodes:0,total_kg_edges:0,queries_today:0});vi.spyOn(api,'getGraphAll').mockResolvedValue(graph as never);vi.spyOn(api,'getGraph').mockResolvedValue(graph as never)
  ;(window as any).vis={DataSet:class {},Network:class {destroy(){}}};mount(<App/>,path);await act(async()=>{});expect(screen.getAllByRole('navigation')).toHaveLength(2)
  if(path==='/')expect(screen.getByTestId('location')).toHaveTextContent('/upload');else if(path==='/missing')expect(screen.getByText('页面未找到')).toBeInTheDocument();else if(path.startsWith('/query'))expect(screen.getByPlaceholderText('输入你的问题，Enter 发送...')).toBeInTheDocument();else expect(screen.getByText('📋 结构化视图')).toBeInTheDocument();delete (window as any).vis
})
it('main bootstraps a real React root and declarative browser router',async()=>{
  useAppStore.setState({user:null});vi.spyOn(api,'getStats').mockResolvedValue({total_docs:0,total_kg_nodes:0,total_kg_edges:0,queries_today:0});window.history.replaceState({},'', '/upload')
  const container=document.createElement('div');container.id='root';document.body.append(container);let root:ReturnType<typeof ReactDOM.createRoot>|undefined;const create=ReactDOM.createRoot;vi.spyOn(ReactDOM,'createRoot').mockImplementation((...args)=>{root=create(...args);return root})
  await act(async()=>{await import('../src/main')});expect(screen.getByText('上传文档，构建知识图谱')).toBeInTheDocument();expect(container.querySelector('main')).toBeInTheDocument();await act(async()=>root?.unmount());container.remove()
})
