# Code Review Findings — Three Critical Issues

**Review Date:** 2026-05-25  
**Reviewer:** Kiro (Claude Code)  
**Scope:** File upload, parsing time display, knowledge graph synchronization, and multi-file upload capability

---

## Executive Summary

✅ **Issue #1 (Hardcoded Time Display):** RESOLVED  
✅ **Issue #2 (Knowledge Graph Not Syncing):** RESOLVED  
❌ **Issue #3 (No Second File Upload):** PARTIALLY RESOLVED — UI exists but has UX issues

---

## Issue #1: Hardcoded/Incorrect Time Display During File Parsing

### Status: ✅ RESOLVED

### Findings:
The time display is **NOT hardcoded**. The system correctly calculates actual elapsed time:

**Backend (`backend/routes/ingest.py:169`):**
```python
duration_seconds=int((task["updated_at"] - task["created_at"]).total_seconds())
```

**How it works:**
1. Task creation timestamp: `created_at = datetime.now(timezone.utc)` (line 135)
2. Each progress update: `updated_at = datetime.now(timezone.utc)` (line 33)
3. Duration calculated as difference between these timestamps
4. Frontend polls every 2 seconds (`frontend/src/pages/UploadPage.tsx:50`)

**Verification:**
- No hardcoded `setTimeout` delays in the pipeline
- No fake time values
- Real pipeline execution in `backend/worker.py` with actual processing steps
- Time reflects actual MinerU API calls, LangExtract processing, and KG building

**Possible confusion source:**
The `estimated_duration_seconds: 60` (line 115, 149) is only an **estimate** shown initially, not the actual duration. The actual duration updates in real-time based on `updated_at` timestamps.

---

## Issue #2: Knowledge Graph Not Synchronizing After File Upload

### Status: ✅ RESOLVED

### Findings:
The knowledge graph **DOES synchronize** correctly. The full pipeline is implemented:

**Complete Flow:**

1. **File Upload** → `POST /api/v1/ingest` (`backend/routes/ingest.py:87`)
2. **Background Processing** → `_run_indexing()` (line 23)
3. **Real Pipeline Execution** → `worker.run_real_pipeline()` (`backend/worker.py:34`)
   - Stage 1: MinerU document parsing (line 44-91)
   - Stage 2: Format Bridge segmentation (line 94-109)
   - Stage 3: LangExtract entity extraction (line 112-118)
   - Stage 4: Grounding resolution (line 121-128)
   - Stage 5: KG building (line 130-138)
4. **KG Serialization** → `serialize_kg()` saves to `output/kg/doc_{task_id}/` (line 134)
5. **Document Registration** → `add_doc()` adds to document list (line 67-77)
6. **Hot Reload** → `reload_kg()` refreshes query endpoint (line 80-84)

**Graph Endpoint (`backend/routes/graph.py:22`):**
- `GET /api/v1/graph/{document_id}` aggregates all indexed documents
- Reads from `output/kg/doc_{task_id}/nodes.json` and `edges.json`
- Auto-polls every 10 seconds on frontend (`frontend/src/pages/GraphPage.tsx:26`)

**Verification:**
- KG files are written to disk: `backend/kg_builder.py` → `serialize_kg()`
- Documents are tracked: `backend/routes/__init__.py` → `add_doc()`
- Graph endpoint reads from correct paths (line 57-68)
- Frontend auto-refreshes graph data every 10 seconds

**Why it might appear broken:**
- If MinerU API fails (no token, network issue), pipeline stops at stage 1
- If `output/kg/` directory doesn't exist, KG won't be saved
- Graph page needs vis.js CDN to load (10s timeout, line 34-38)

---

## Issue #3: No Way to Upload a Second File

### Status: ❌ PARTIALLY RESOLVED — UI exists but has UX issues

### Findings:

**Good News:**
The "Continue Upload" button **DOES exist** in the success state:

**Location:** `frontend/src/pages/UploadPage.tsx:196`
```tsx
<button onClick={reset} className="py-2.5 px-10 bg-accent text-white rounded-full text-sm font-semibold hover:bg-accent-light transition-all">
  📤 继续上传
</button>
```

**How it works:**
1. After successful upload, status becomes `'done'` (line 42)
2. Success UI shows 4 buttons (line 192-197):
   - 📄 查看文档列表
   - 💬 知识问答
   - 🔮 知识图谱
   - **📤 继续上传** ← This resets the form
3. `reset()` function clears state and returns to upload form (line 47-48)

**Problems Identified:**

### Problem 3A: Auto-redirect Interferes with "Continue Upload"
**Location:** `frontend/src/pages/UploadPage.tsx:19-25`
```tsx
// Auto-redirect to documents page when indexing completes
useEffect(() => {
  if (status === 'done') {
    const t = setTimeout(() => navigate('/documents'), 3000)
    return () => clearTimeout(t)
  }
}, [status, navigate])
```

**Issue:** User only has 3 seconds to click "继续上传" before being redirected away. This is too short and creates a poor UX.

**Recommendation:** 
- Increase timeout to 10 seconds, OR
- Remove auto-redirect entirely (let user choose), OR
- Add a "Cancel redirect" button

### Problem 3B: Auto-reset on Mount Clears Success State
**Location:** `frontend/src/pages/UploadPage.tsx:16-17`
```tsx
// Auto-reset on mount if previous upload completed/failed — user sees fresh upload page
useEffect(() => { if (status === 'done' || status === 'failed') reset() }, [])
```

**Issue:** If user navigates away and comes back to `/upload`, the success state is immediately cleared. They never see the success message or stats.

**Recommendation:**
- Remove this auto-reset, OR
- Only reset if user explicitly clicks "继续上传"

### Problem 3C: No Upload Button in Failed State
**Location:** `frontend/src/pages/UploadPage.tsx:201-207`
```tsx
{status === 'failed' && (
  <div className="mt-7 p-6 bg-red/5 border border-red/30 rounded-card text-center">
    <p className="text-red font-semibold mb-2">解析失败</p>
    <p className="text-text-muted text-sm mb-3">{error}</p>
    <button onClick={reset} className="py-2 px-6 bg-accent text-white rounded-full text-sm font-semibold">重试</button>
  </div>
)}
```

**Issue:** The "重试" button only resets the form. If the file was removed or the error was due to file content, user has no way to upload a different file without manually removing the current one.

**Recommendation:**
- Add a "上传其他文件" button alongside "重试"

---

## Detailed Code Paths

### Upload Flow (Success Case)
```
1. User drops file → setFile() → status: 'idle'
2. User clicks "开始解析文档" → handleUpload()
3. POST /api/v1/ingest → returns task_id
4. startUpload() → status: 'indexing'
5. pollTask() every 2s → updateFromStatus()
6. Backend completes → status: 'done'
7. Success UI shows with "继续上传" button
8. [PROBLEM] After 3s → auto-redirect to /documents
9. User clicks "继续上传" → reset() → status: 'idle', file: null
10. User can upload again ✓
```

### Upload Flow (Navigation Case)
```
1. User completes upload → status: 'done'
2. User clicks "查看文档列表" → navigate('/documents')
3. User clicks "Upload" in nav → navigate('/upload')
4. [PROBLEM] useEffect auto-reset fires → status: 'idle' immediately
5. User never sees success stats
```

---

## Recommendations

### High Priority
1. **Fix auto-redirect timing** (Issue 3A)
   - Change timeout from 3s to 10s, or remove entirely
   - Add visual countdown or cancel button

2. **Remove auto-reset on mount** (Issue 3B)
   - Let success state persist until user explicitly clicks "继续上传"
   - Or store success state in sessionStorage to survive navigation

### Medium Priority
3. **Improve failed state UX** (Issue 3C)
   - Add "上传其他文件" button in failed state
   - Distinguish between "retry same file" vs "upload different file"

### Low Priority
4. **Add upload queue UI**
   - Allow multiple files to be queued
   - Show progress for each file
   - This is a feature enhancement, not a bug fix

---

## Code Locations Reference

| Issue | File | Lines | Description |
|-------|------|-------|-------------|
| 1 (Time) | `backend/routes/ingest.py` | 169 | Duration calculation |
| 1 (Time) | `backend/worker.py` | 34-149 | Real pipeline execution |
| 2 (KG Sync) | `backend/routes/ingest.py` | 80-84 | KG hot reload |
| 2 (KG Sync) | `backend/routes/graph.py` | 22-143 | Graph aggregation endpoint |
| 2 (KG Sync) | `frontend/src/pages/GraphPage.tsx` | 19-28 | Auto-poll every 10s |
| 3A (Auto-redirect) | `frontend/src/pages/UploadPage.tsx` | 19-25 | 3s redirect timer |
| 3B (Auto-reset) | `frontend/src/pages/UploadPage.tsx` | 16-17 | Mount reset effect |
| 3C (Failed state) | `frontend/src/pages/UploadPage.tsx` | 201-207 | Failed state UI |
| 3 (Continue button) | `frontend/src/pages/UploadPage.tsx` | 196 | "继续上传" button |

---

## Conclusion

**Issues #1 and #2 are fully resolved.** The time display is accurate and the knowledge graph synchronizes correctly through the complete pipeline.

**Issue #3 has a working solution** (the "继续上传" button exists), but **UX problems** make it hard to use:
- Auto-redirect gives only 3 seconds to click the button
- Auto-reset on mount clears success state when navigating back
- Failed state lacks clear "upload different file" option

The core functionality works; the problems are in the user experience flow.
