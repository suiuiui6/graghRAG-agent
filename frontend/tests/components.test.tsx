import { expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react'
import { EntityCard } from '../src/components/EntityCard'
import { StructuredView } from '../src/components/StructuredView'
import { EntityDetailPanel } from '../src/components/EntityDetailPanel'
import { EntityGroupList } from '../src/components/EntityGroupList'
import { LineageGraph } from '../src/components/LineageGraph'
import ChatWidget from '../src/components/ChatWidget'
import { AppShell } from '../src/components/layout/AppShell'
import { GraphPage } from '../src/pages/GraphPage'
import { api } from '../src/lib/api'
import { useAppStore } from '../src/stores/useAppStore'
import { graph, node, mount, user, deferred } from './helpers'
it('entity cards use label/id fallback and only expose three properties with a remaining count', () => {
  const click=vi.fn(); const { rerender }=render(<EntityCard entity={{ ...node, properties:{ a:1,b:2,c:3,d:4 } }} color="red" icon={null} onClick={click} />)
  fireEvent.click(screen.getByText('收入')); expect(click).toHaveBeenCalledOnce(); expect(screen.getByText('+1 更多属性')).toBeInTheDocument(); expect(screen.getByText('✓ 已溯源')).toBeInTheDocument()
  rerender(<EntityCard entity={{ ...node, label:'', properties:undefined, page_idx:null, grounding_status:'missing' } as never} color="red" icon={()=><i>icon</i>} />)
  expect(screen.getByText('n1')).toBeInTheDocument(); expect(screen.queryByText('✓ 已溯源')).toBeNull()
})
it('structured view searches label/properties and opens/closes and navigates entity details', () => {
  const f=vi.fn(); render(<StructuredView data={graph as never} onViewInNetwork={f} />)
  fireEvent.click(screen.getByText('收入')); expect(screen.getByText('关系 (1)')).toBeInTheDocument(); fireEvent.click(screen.getByText('🔮 在网络图谱中查看')); expect(f).toHaveBeenCalledWith('n1')
  fireEvent.click(screen.getByText('成本')); fireEvent.click(screen.getByText('✕')); expect(screen.queryByText('详情')).toBeNull()
  const search=screen.getByPlaceholderText('🔍 搜索实体...'); fireEvent.change(search,{target:{value:'10'}}); expect(screen.getByText('收入')).toBeInTheDocument(); fireEvent.change(search,{target:{value:'absent'}}); expect(screen.getByText('未找到匹配的实体')).toBeInTheDocument()
})
it('groups unknown types, missing neighbors, reverse edges and search fallbacks without crashing', () => {
  const data={...graph,nodes:[node,{...node,id:'unknown',label:'',properties:undefined,entity_type:'other'}],edges:[{from:'n1',to:'unknown'}, {from:'absent',to:'n1'}, {from:'n1',to:'absent'}]}; const f=vi.fn()
  const {rerender}=render(<EntityGroupList data={data as never} searchQuery="" onEntityClick={f} />)
  fireEvent.click(screen.getByRole('button',{name:/metric/})); expect(screen.queryByText('收入')).toBeNull(); fireEvent.click(screen.getByRole('button',{name:/metric/})); fireEvent.click(screen.getByText('收入')); expect(f.mock.calls[0][0].neighbors[0].label).toBe('unknown')
  fireEvent.click(screen.getByText('other')); fireEvent.click(screen.getByText('unknown')); expect(f.mock.calls[1][0].neighbors[0].label).toBe('收入')
  rerender(<EntityGroupList data={data as never} searchQuery="missing" />); expect(screen.getByText('未找到匹配的实体')).toBeInTheDocument()
})
it('detail panel shows unknown/un-grounded fallbacks and switches lineage back to details', async () => {
  vi.spyOn(api,'lineageEntity').mockResolvedValue({entity_id:'n1',trace:[{node_id:'x',node_type:'entity',label:'链'}]} as never)
  render(<EntityDetailPanel entity={{...node,label:'',entity_type:'unknown',properties:undefined,bbox_norm:null,page_idx:null,grounding_status:'missing'} as never} neighbors={[]} onClose={()=>{}} onViewInNetwork={()=>{}} />)
  expect(screen.getByText('✗ 未溯源')).toBeInTheDocument(); expect(screen.getByText('暂无关系节点')).toBeInTheDocument(); fireEvent.click(screen.getByText('🧬 血缘追踪')); expect(await screen.findByText('链')).toBeInTheDocument(); fireEvent.click(screen.getAllByText('✕')[1]); expect(screen.getByText('暂无关系节点')).toBeInTheDocument()
})
it.each(['empty','null','error','full'])('lineage displays loading and %s result', async mode => {
  const p=deferred<any>(); vi.spyOn(api,'lineageEntity').mockReturnValue(p.promise); const close=vi.fn(); render(<LineageGraph entityId="n" onClose={close} />); expect(screen.getByText('⏳ 加载血缘链路...')).toBeInTheDocument()
  await act(async()=>mode==='error'?p.reject(new Error('offline')):p.resolve(mode==='null'?null:{entity_id:'n',trace:mode==='empty'?[]:[{node_type:'document',node_id:'d',label:'文档来源',timestamp:'2026-01-01',metadata:{x:1},domain_terms:['term']},{node_type:'unknown',label:'未知来源',metadata:{},domain_terms:[]}]}))
  if(mode==='full'){expect(screen.getByText('文档来源')).toBeInTheDocument();expect(screen.getByText('term')).toBeInTheDocument();fireEvent.click(screen.getByText('✕'));expect(close).toHaveBeenCalledOnce()}else expect(screen.getByText(mode==='error'?'⚠ offline':'暂无血缘数据')).toBeInTheDocument()
})
it('shell supports anonymous to authenticated to anonymous state changes without hook-order errors', async () => {
  useAppStore.setState({user:null,stats:null}); vi.spyOn(api,'getStats').mockResolvedValue({total_docs:0,total_kg_nodes:2,total_kg_edges:1,queries_today:3})
  mount(<AppShell>内容</AppShell>); await act(async()=>{}); await act(async()=>useAppStore.getState().setUser(user)); expect(screen.getByText('用户甲')).toBeInTheDocument(); await act(async()=>useAppStore.getState().setUser(null)); expect(screen.queryByText('用户甲')).toBeNull()
})
it('network initializes after engine readiness and recreates on return from structured view', async () => {
  const destroy=vi.fn(); const focus=vi.fn(); const selectNodes=vi.fn(); const network=vi.fn(function(){return {destroy,focus,selectNodes}}); (window as any).vis={DataSet: class { constructor(public data:any){} },Network:network}
  vi.spyOn(api,'getGraphAll').mockResolvedValue(graph as never); const view=mount(<GraphPage />)
  await screen.findByText('📋 结构化视图'); await waitFor(()=>expect(network).toHaveBeenCalledOnce()); fireEvent.click(screen.getByText('📋 结构化视图')); expect(destroy).toHaveBeenCalledOnce(); fireEvent.click(screen.getByText('收入')); fireEvent.click(screen.getByText('🔮 在网络图谱中查看')); await waitFor(()=>expect(network).toHaveBeenCalledTimes(2)); expect(focus).toHaveBeenCalledWith('n1',expect.anything()); expect(selectNodes).toHaveBeenCalledWith(['n1']); view.unmount(); expect(destroy).toHaveBeenCalledTimes(2); delete (window as any).vis
})
it('chat assistant escapes HTML, displays sources, sends feedback once and retains conversation on close', async () => {
  const f=vi.fn().mockImplementation((url:string)=>Promise.resolve(new Response(JSON.stringify(url.endsWith('feedback')?{}:{answer:'# 标题\n**粗体** *强调* `code`\n<script>x</script> & >\n\n[citation:1]',sources:[{label:'源文档',entity_type:'metric',relevance_score:.8}]})))); vi.stubGlobal('fetch',f); localStorage.setItem('access_token','test')
  const {container}=render(<ChatWidget/>); fireEvent.click(screen.getByTitle('AI 助手')); expect(screen.getByText(/你好！我是 AI/)).toBeInTheDocument(); const input=screen.getByPlaceholderText('输入你的问题...'); fireEvent.change(input,{target:{value:'问题'}}); fireEvent.keyDown(input,{key:'Enter',shiftKey:true}); expect(f).not.toHaveBeenCalled(); fireEvent.keyDown(input,{key:'Enter'}); expect(await screen.findByText('粗体')).toBeInTheDocument(); expect(container.querySelector('script')).toBeNull()
  fireEvent.click(screen.getByText('查看 1 条引用')); expect(screen.getByText('[1] 源文档')).toBeInTheDocument(); fireEvent.click(screen.getByText('收起 1 条引用')); expect(screen.queryByText('[1] 源文档')).toBeNull()
  const feedback=container.querySelectorAll('button svg.lucide-thumbs-up')[0]?.parentElement as HTMLElement; fireEvent.click(feedback); await waitFor(()=>expect(f).toHaveBeenCalledTimes(2)); expect(feedback).toBeDisabled(); expect(JSON.parse(f.mock.calls[1][1].body).rating).toBe('positive')
  fireEvent.click(container.querySelector('button svg.lucide-x')!.parentElement!); fireEvent.click(screen.getByTitle('AI 助手')); expect(screen.getByText('粗体')).toBeInTheDocument()
})
it.each(['detail','invalid','status','network','empty'])('chat recovers from %s responses without losing input history', async mode => {
  vi.stubGlobal('fetch',vi.fn().mockImplementation(()=>mode==='network'?Promise.reject({}):Promise.resolve(new Response(mode==='invalid'?'invalid':JSON.stringify(mode==='detail'?{detail:'denied'}:mode==='empty'?{answer:''}:{}),{status:mode==='empty'?200:500,statusText:mode==='invalid'?'Gateway':''}))))
  render(<ChatWidget/>); fireEvent.click(screen.getByTitle('AI 助手')); fireEvent.change(screen.getByPlaceholderText('输入你的问题...'),{target:{value:'问题'}}); fireEvent.click(screen.getByText('发送')); await waitFor(()=>expect(screen.getByText('发送')).toBeDisabled()); if(mode!=='empty') expect(await screen.findByText(mode==='detail'?'denied':mode==='network'?'请求失败':mode==='invalid'?'Gateway':'HTTP 500')).toBeInTheDocument()
})
