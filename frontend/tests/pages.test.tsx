import { beforeEach, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { api } from '../src/lib/api'
import { HealthPage } from '../src/pages/HealthPage'
import { QualityDashboard } from '../src/pages/QualityDashboard'
import { CatalogPage } from '../src/pages/CatalogPage'
import { DocumentsPage } from '../src/pages/DocumentsPage'
import { QueryPage } from '../src/pages/QueryPage'
import { UploadPage } from '../src/pages/UploadPage'
import { useAppStore, useUploadStore } from '../src/stores/useAppStore'
import { mount, graph, node, deferred } from './helpers'
beforeEach(()=>{useUploadStore.getState().reset();useAppStore.setState({documents:[],totalDocs:0})})
it.each(['healthy','degraded','null','error'])('health renders loading then %s', async mode=>{
  const p=deferred<any>();vi.spyOn(api,'health').mockReturnValue(p.promise);mount(<HealthPage/>);expect(screen.getByText('⏳ 加载中...')).toBeInTheDocument()
  await act(async()=>mode==='error'?p.reject(new Error('offline')):p.resolve(mode==='null'?null:{status:mode,version:'1',uptime_seconds:125,components:{api_server:'ok'},stats:{total_kg_nodes:2,total_queries_served:4}}))
  if(mode==='null')expect(screen.queryByText('系统状态')).toBeNull();else expect(screen.getByText(mode==='error'?'⚠ 无法连接后端: offline':'系统状态')).toBeInTheDocument()
})
it.each([85,50,20,null,'error'])('quality reports %s and all threshold/alert/freshness states',async score=>{
  vi.spyOn(api,'qualityReport').mockImplementation(()=>score==='error'?Promise.reject(new Error('offline')):Promise.resolve(score===null?null:{overall_score:score,generated_at:'2026-01-01',alerts:score===85?[]:[{severity:'critical',metric:'low',value:.2,threshold:.5},{severity:'warn',metric:'missing',value:'none',threshold:1}],extraction_quality:{grounding_rate:score===85?.9:.2,confidence_avg:score===85?.9:.2,extraction_error_rate:score===85?.01:.2,total_entities:5,grounded_entities:2},feedback_quality:{positive_ratio:score===85?.9:.2,positive:4,negative:score===85?1:5,negative_clusters:score===85?[]:['bad query']},retrieval_quality:score===85?{path_covers_avg:3,zero_result_total:1}:undefined,data_freshness:{days_since_last_ingest:score===85?1:999,stale_entities:score===85?0:500,conversation_active_today:1}} as never));mount(<QualityDashboard/>);await act(async()=>{})
  if(score===null)expect(screen.queryByText('数据质量监控')).toBeNull();else expect(screen.getByText(score==='error'?'⚠ 加载失败: offline':'数据质量监控')).toBeInTheDocument();if(score===50)expect(screen.getByText('从未')).toBeInTheDocument()
})
it.each(['full','empty','null','error'])('catalog displays %s inventory and quality signals',async mode=>{
  vi.spyOn(api,'catalogLowQuality').mockResolvedValue({items:mode==='full'?[{doc_id:'lowdoc',issue:'low confidence',value:.2,entities_grounded:1,entities_total:10}]:[]} as never)
  vi.spyOn(api,'catalog').mockImplementation(()=>mode==='error'?Promise.reject(new Error('offline')):Promise.resolve(mode==='null'?null:{last_updated:'2026-01-01',summary:{total_documents:2,total_entities:10,total_edges:1,total_chunks:3,total_conversations:1,total_feedback:2,domain_terms:5,by_entity_type:mode==='full'?{metric:8,other:2}:{}},quality_metrics:mode==='full'?{grounded_rate:.2,orphan_entities:20,low_quality_docs:['d']}:null,domain_dict:mode==='full'?{by_category:{safety:1,equipment:1,ppe:1,regulation:1,other:1}}:null,feedback:mode==='full'?{positive_ratio:.5,positive:1,negative:1}:null} as never));mount(<CatalogPage/>);await act(async()=>{})
  if(mode==='null')expect(screen.queryByText('数据资产目录')).toBeNull();else expect(screen.getByText(mode==='error'?'⚠ 加载失败: offline':'数据资产目录')).toBeInTheDocument();if(mode==='full')expect(screen.getByText('lowdoc')).toBeInTheDocument();if(mode==='empty')expect(screen.getByText('暂无质量数据')).toBeInTheDocument()
})
it('documents retain status/null fields, delete and refresh the rendered listing',async()=>{
  const docs=[{document_id:'d',filename:'report.pdf',status:'indexed',kg_nodes:2,kg_edges:1,pages:3,indexed_at:'2026-01-01',file_size_mb:1},{document_id:'d2',filename:'pending.pdf',status:'pending',kg_nodes:null,pages:null,indexed_at:null}]
  vi.spyOn(api,'listDocuments').mockResolvedValueOnce({documents:docs,total:2} as never).mockResolvedValue({documents:[],total:0});vi.spyOn(api,'deleteDocument').mockResolvedValue({} as never);mount(<DocumentsPage/>);expect(await screen.findByText('report.pdf')).toBeInTheDocument();expect(screen.getAllByTitle('问答')[0]).toHaveAttribute('href','/query/d');fireEvent.click(screen.getAllByTitle('删除')[0]);expect(await screen.findByText('暂无已索引文档')).toBeInTheDocument()
})
it('documents stop automatic refresh after five consecutive failures',async()=>{
  vi.useFakeTimers();const f=vi.spyOn(api,'listDocuments').mockRejectedValue(new Error('offline'));mount(<DocumentsPage/>);await act(async()=>{});await act(async()=>vi.advanceTimersByTimeAsync(25000));expect(f).toHaveBeenCalledTimes(5);expect(screen.getByText(/刷新文档列表失败/)).toBeInTheDocument()
})
it('query forwards optional document and session scopes and renders markdown evidence diagnostics',async()=>{
  vi.spyOn(api,'getGraphAll').mockResolvedValue(graph as never);const ask=vi.spyOn(api,'ask').mockResolvedValue({answer:'**答案**\n\n|字段|值|\n|---|---|\n|a|b|',sources:[{...node,node_id:'n1',source:'kg',relevance_score:.8}],metadata:{duration_ms:1200,query_mode:'hybrid',degraded_mode:'trim',rewrite_reason:'followup',rewritten_query:'改写问题',final_context_chunk_ids:['c1','c2']}} as never)
  mount(<QueryPage/>,'/query/doc','/query/:docId?');await screen.findByText('你好！');const input=screen.getByPlaceholderText('输入你的问题，Enter 发送...');fireEvent.change(input,{target:{value:'问题'}});fireEvent.keyDown(input,{key:'Enter',shiftKey:true});expect(ask).not.toHaveBeenCalled();fireEvent.keyDown(input,{key:'Enter'});expect(await screen.findByText('答案')).toBeInTheDocument();expect(screen.getByRole('table')).toBeInTheDocument();expect(ask).toHaveBeenCalledWith('问题','doc',expect.objectContaining({sessionId:expect.any(String)}));expect(screen.getByText('响应 1.2s')).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:/n1/}));expect(screen.getByText('答案溯源')).toBeInTheDocument();expect(screen.getByText('[1, 2, 3, 4]')).toBeInTheDocument()
})
it.each([500,12000,NaN,undefined])('query handles empty evidence and duration %s',async duration=>{
  vi.spyOn(api,'getGraphAll').mockRejectedValue(new Error('offline'));vi.spyOn(api,'ask').mockResolvedValue({answer:'无来源答案',sources:null,metadata:{duration_ms:duration,final_context_chunk_ids:[]}} as never);mount(<QueryPage/>);await act(async()=>{});fireEvent.click(screen.getByText('→'));expect(api.ask).not.toHaveBeenCalled();fireEvent.change(screen.getByPlaceholderText('输入你的问题，Enter 发送...'),{target:{value:'q'}});fireEvent.click(screen.getByText('→'));expect(await screen.findByText('无来源答案')).toBeInTheDocument();expect(screen.getByText(/本次回答未返回/)).toBeInTheDocument();expect(screen.getByText(/本次最终上下文证据较少/)).toBeInTheDocument()
})
it.each([new Error('offline'),'unknown'])('query displays recoverable failure %s',async err=>{
  vi.spyOn(api,'getGraphAll').mockResolvedValue(graph as never);vi.spyOn(api,'ask').mockRejectedValue(err);mount(<QueryPage/>);await act(async()=>{});fireEvent.change(screen.getByPlaceholderText('输入你的问题，Enter 发送...'),{target:{value:'q'}});fireEvent.click(screen.getByText('→'));expect(await screen.findByText(err instanceof Error?'❌ 查询失败: offline':'❌ 查询失败: 未知错误')).toBeInTheDocument();expect(screen.getByPlaceholderText('输入你的问题，Enter 发送...')).toBeEnabled()
})
it('file upload polls stages to completion and redirects after showing results',async()=>{
  vi.useFakeTimers();vi.spyOn(api,'ingest').mockResolvedValue({task_id:'t',estimated_duration_seconds:10} as never);vi.spyOn(api,'getStatus').mockResolvedValueOnce({status:'running',progress:{current_step:2}} as never).mockResolvedValue({status:'done',result:{kg_nodes:2,kg_edges:1,entity_types:1,pages_parsed:3,grounded_entities:2},progress:{current_step:5}} as never)
  mount(<UploadPage/>,'/upload','/upload');const file=new File(['data'],'a.pdf');fireEvent.change(document.getElementById('fileInput')!,{target:{files:[file]}});expect(screen.getByText('a.pdf')).toBeInTheDocument();fireEvent.click(screen.getByText('🚀 开始解析文档'));await act(async()=>{});expect((api.ingest as any).mock.calls[0][0].get('file')).toBe(file);await act(async()=>vi.advanceTimersByTimeAsync(4000));expect(screen.getByText('解析结果')).toBeInTheDocument();await act(async()=>vi.advanceTimersByTimeAsync(10000));expect(screen.getByTestId('location')).toHaveTextContent('/documents')
})
it.each([new Error('bad upload'),'bad'])('URL upload failure and retry restore idle %s',async err=>{
  vi.spyOn(api,'ingest').mockRejectedValue(err);mount(<UploadPage/>);fireEvent.click(screen.getByText('解析链接'));expect(api.ingest).not.toHaveBeenCalled();fireEvent.change(document.getElementById('urlInput')!,{target:{value:'https://example.test/'}});fireEvent.click(screen.getByText('解析链接'));expect(await screen.findByText('解析失败')).toBeInTheDocument();expect((api.ingest as any).mock.calls[0][0].get('url')).toBe('https://example.test/');fireEvent.click(screen.getByText('重试'));expect(screen.getByText('拖拽文件到此处，或点击选择文件')).toBeInTheDocument()
})
it('resumes pending upload, caps polling failures and clears timer after failure',async()=>{
  vi.useFakeTimers();useUploadStore.setState({status:'indexing',taskId:'t'});const f=vi.spyOn(api,'getStatus').mockRejectedValue(new Error('offline'));mount(<UploadPage/>);await act(async()=>vi.advanceTimersByTimeAsync(22000));expect(f).toHaveBeenCalledTimes(10);expect(screen.getByText(/轮询状态失败/)).toBeInTheDocument();fireEvent.click(screen.getByText('上传其他文件'));expect(useUploadStore.getState().status).toBe('idle')
})
it('leaving upload stops polling and remount creates exactly one independent timer',async()=>{
  vi.useFakeTimers();useUploadStore.setState({status:'indexing',taskId:'t'});const f=vi.spyOn(api,'getStatus').mockResolvedValue({status:'running'} as never);const view=mount(<UploadPage/>);await act(async()=>vi.advanceTimersByTimeAsync(2000));expect(f).toHaveBeenCalledTimes(1);view.unmount();await act(async()=>vi.advanceTimersByTimeAsync(4000));expect(f).toHaveBeenCalledTimes(1);const next=mount(<UploadPage/>);await act(async()=>vi.advanceTimersByTimeAsync(2000));expect(f).toHaveBeenCalledTimes(2);next.unmount()
})
it('drag and input selection tolerate absent files and allow removal',()=>{
  mount(<UploadPage/>);const drop=screen.getByText('拖拽文件到此处，或点击选择文件').closest('[class*="border-dashed"]')!;fireEvent.dragOver(drop);fireEvent.drop(drop,{dataTransfer:{files:[]}});fireEvent.drop(drop,{dataTransfer:{files:[new File(['x'],'drag.pdf')]}});expect(screen.getByText('drag.pdf')).toBeInTheDocument();fireEvent.click(screen.getByText('移除'));expect(useUploadStore.getState().file).toBeNull();fireEvent.change(document.getElementById('fileInput')!,{target:{files:[]}})
})
