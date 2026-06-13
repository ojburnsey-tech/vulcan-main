# /process Endpoint Audit - Quick Reference

## What Was Added

Comprehensive diagnostic logging at **every stage** of the PDF upload → BoQ generation pipeline. **No business logic was changed.**

## 8 Critical Stages Now Instrumented

| Stage | Logging | Catches |
|-------|---------|---------|
| **PDF Parse** | START/END + file size, page count, text length | Corrupt PDFs, extraction failures |
| **AI Call** | START/END + processing time, stop reason, all API errors | Claude API issues, timeouts, truncation |
| **JSON Parse** | START/END + line/col errors, first 500 chars preview | Malformed JSON from Claude |
| **Schema Valid** | START/END + validation errors | Output doesn't match expected structure |
| **Rate Enrich** | START/END + enrichment errors | Rate lookup failures |
| **Auto-Save** | Detailed save steps, user ID, project ID | Database errors (non-fatal) |
| **Response Build** | START/END + JSON serialization | BoQ serialization failures |
| **Error Handler** | Method, path, exception type, full stack trace | Any unhandled exceptions |

## Every Exception Includes

✅ Exception type (e.g., `JSONDecodeError`, `ValueError`)  
✅ Exception message  
✅ Full Python stack trace  
✅ Contextual details (file sizes, counts, previews)  

## How to Debug

1. **Deploy** updated `app.py` to Railway
2. **Upload** PDF via frontend
3. **Watch** Railway logs in real-time:
   ```bash
   railway logs --follow
   ```
4. **Look for** these markers in order:
   ```
   PROCESS_PDF_START
   → START PDF PARSE → END PDF PARSE
   → START AI CALL → END AI CALL
   → START JSON EXTRACTION → END JSON EXTRACTION
   → START SCHEMA VALIDATION → END SCHEMA VALIDATION
   → START RATE ENRICHMENT → END RATE ENRICHMENT
   → START AUTO-SAVE → END AUTO-SAVE
   → START RESPONSE BUILD → END RESPONSE BUILD
   → PROCESS_PDF_SUCCESS
   ```

5. **If a stage has no END marker**, look for `[STAGE]_FAILED` log immediately after
6. **Report the failure stage** with the exception type and message

## Files Modified

- ✅ `api/app.py` - Comprehensive logging added throughout `/process` endpoint and `_run_boq_pipeline()`

## Files Created

- ✅ `PROCESS_ENDPOINT_AUDIT.md` - Full audit documentation with examples

## Key Changes in app.py

### Enhanced Error Handler (lines ~78-97)
Now logs: `method`, `path`, `exception_type`, `exception_message` + full stack trace

### PDF Parse (lines ~1406-1420)
- `START PDF PARSE: filename={name} file_size_bytes={size}`
- `END PDF PARSE: extracted_text_length={len} approx_words={count}`
- `START PDF PARSE FAILED` on error with full exception details

### Claude Call (lines ~1426-1463)
- `START AI CALL` / `END AI CALL` with processing time
- Separate logging for API errors: `APIStatusError`, `APITimeoutError`, `APIConnectionError`
- `AI_OUTPUT_TRUNCATED` / `AI_OUTPUT_REFUSED` if stop_reason indicates problem

### JSON Extraction (lines ~1494-1502)
- `START JSON EXTRACTION` / `END JSON EXTRACTION`
- On error: `JSONDecodeError at line {line} col {col}` + first 500 chars of raw text
- Shows exactly where Claude output is malformed

### Schema Validation (lines ~1504-1512)
- `START SCHEMA VALIDATION` / `END SCHEMA VALIDATION`
- Logs any validation errors with full exception details

### Rate Enrichment (lines ~1514-1521)
- `START RATE ENRICHMENT` / `END RATE ENRICHMENT`
- Logs any enrichment errors

### process_pdf() (lines ~1528-1600)
- `PROCESS_PDF_START` → auth check → pipeline call → auto-save → response build → `PROCESS_PDF_SUCCESS`
- Auto-save errors logged but don't fail response (best-effort)
- Response serialization errors caught and logged

## Expected Behavior After Deployment

### Success Case (HTTP 200)
```
PROCESS_PDF_SUCCESS: returning response to client
```
Followed by JSON BoQ in response body.

### Failure Case (HTTP 422/502/504)
```
[STAGE]_FAILED: exception_type=... message=...
[Full stack trace]
```
Followed by JSON error response readable in browser.

## CORS Always Works

✅ All error responses include CORS headers  
✅ `@app.after_request` hook applied after every response  
✅ Error handler explicitly sets CORS headers for unhandled exceptions  
✅ Browser can always read error body (no silent "CORS error" opaque failures)

---

**Next Step:** Deploy to Railway and upload a test PDF to see exactly where the pipeline is failing.
