# /process Endpoint - Execution Flow with Logging

## Complete Request Flow

```
┌─ HTTP POST /process (multipart/form-data with PDF file)
│
├─ PROCESS_PDF_START
│  └─ Check Authorization header
│     ├─ PROCESS_PDF_AUTH_OK ──────────────┐
│     │                                      │
│     └─ PROCESS_PDF_AUTH_FAILED (401)      │
│                                            │
│  ┌────────────────────────────────────────┘
│  │
│  └─ Call _run_boq_pipeline()
│
│     ┌─ START PDF PARSE
│     │  ├─ filename={name}
│     │  ├─ file_size_bytes={bytes}
│     │  │
│     │  ├─ Validate file extension
│     │  │
│     │  ├─ Read PDF into BytesIO buffer
│     │  │
│     │  ├─ Open with pdfplumber
│     │  │  └─ PDF opened: page_count={num}
│     │  │
│     │  ├─ Extract text from each page
│     │  │
│     │  ├─ Join pages with \n\n
│     │  │
│     │  └─ END PDF PARSE
│     │     ├─ extracted_text_length={len}
│     │     └─ approx_words={count}
│     │
│     ├─ [ERROR] START PDF PARSE FAILED
│     │  ├─ exception_type={type}
│     │  ├─ exception_message={msg}
│     │  ├─ Full stack trace
│     │  └─ Return 422 Unprocessable Entity
│     │
│     ├─ [EMPTY] PDF_PARSE_EMPTY_TEXT
│     │  └─ Return 422 (scanned image)
│     │
│     ┌─ START AI CALL
│     │  ├─ model=claude-sonnet-4-6
│     │  ├─ pdf_text_length={len}
│     │  │
│     │  ├─ Build Anthropic client
│     │  │
│     │  ├─ Call client.messages.create()
│     │  │  ├─ system=SYSTEM_PROMPT
│     │  │  ├─ messages=[{role:user, content:full_text}]
│     │  │  ├─ max_tokens=16000
│     │  │  └─ model=claude-sonnet-4-6
│     │  │
│     │  ├─ Record processing_time
│     │  │
│     │  └─ END AI CALL
│     │     ├─ processing_time_seconds={sec}
│     │     └─ stop_reason={reason}
│     │
│     ├─ [ERROR] AI CALL FAILED (APIStatusError)
│     │  ├─ status_code={code}
│     │  ├─ message={msg}
│     │  ├─ Full stack trace
│     │  └─ Return 502 Bad Gateway
│     │
│     ├─ [ERROR] AI CALL FAILED (APITimeoutError)
│     │  └─ Return 504 Gateway Timeout
│     │
│     ├─ [ERROR] AI CALL FAILED (APIConnectionError)
│     │  ├─ exception={details}
│     │  ├─ Full stack trace
│     │  └─ Return 503 Service Unavailable
│     │
│     ├─ [ERROR] AI_OUTPUT_TRUNCATED
│     │  ├─ stop_reason=max_tokens
│     │  └─ Return 502
│     │
│     ├─ [ERROR] AI_OUTPUT_REFUSED
│     │  ├─ stop_reason=refusal
│     │  └─ Return 502
│     │
│     ├─ Extract Claude response text
│     │  └─ Claude response extracted: raw_text_length={len}
│     │
│     ├─ Persist usage tokens to Supabase (best-effort)
│     │
│     ┌─ START JSON EXTRACTION
│     │  ├─ raw_text_length={len}
│     │  │
│     │  ├─ json.loads(raw_text)
│     │  │
│     │  └─ END JSON EXTRACTION
│     │     └─ boq_data_keys={keys}
│     │
│     ├─ [ERROR] JSON_EXTRACTION_FAILED (JSONDecodeError)
│     │  ├─ JSONDecodeError at line {line} col {col}
│     │  ├─ Error message: {msg}
│     │  ├─ First 500 chars of raw_text: {preview}
│     │  ├─ Full stack trace
│     │  └─ Return 502
│     │
│     ├─ [ERROR] JSON_EXTRACTION_FAILED (Unexpected)
│     │  ├─ exception_type={type}
│     │  ├─ exception_message={msg}
│     │  ├─ Full stack trace
│     │  └─ Return 502
│     │
│     ┌─ START SCHEMA VALIDATION
│     │  ├─ _validate_boq_output(boq_data)
│     │  │
│     │  └─ END SCHEMA VALIDATION
│     │     └─ validation_passed=true
│     │
│     ├─ [ERROR] SCHEMA_VALIDATION_FAILED
│     │  ├─ ValueError: {path}: {msg}
│     │  ├─ Full stack trace
│     │  └─ Return 502
│     │
│     ┌─ START RATE ENRICHMENT
│     │  ├─ _enrich_boq(boq_data)
│     │  │  ├─ Walk each trade group
│     │  │  ├─ Walk each line item
│     │  │  ├─ Lookup or fuzzy-match rate_key
│     │  │  ├─ Add material_rate, labour_rate, rate, line_total
│     │  │  └─ Sort trades by NRM2 section order
│     │  │
│     │  └─ END RATE ENRICHMENT
│     │     └─ enrichment_complete=true
│     │
│     ├─ [ERROR] RATE_ENRICHMENT_FAILED
│     │  ├─ exception_type={type}
│     │  ├─ exception_message={msg}
│     │  ├─ Full stack trace
│     │  └─ Return 502
│     │
│     └─ PIPELINE_SUCCESS: returning_to_process_pdf
│        └─ Return (boq_data, pages_text, uploaded_file, None)
│
├─ Back in process_pdf()
│
├─ PROCESS_PDF_PIPELINE_SUCCESS
│  ├─ pages={num}
│  └─ boq_trades={num}
│
├─ START AUTO-SAVE
│  ├─ Get authenticated user from Bearer token
│  │
│  ├─ [NO USER] AUTO_SAVE: no authenticated user, skipping save
│  │
│  ├─ [WITH USER] AUTO_SAVE: authenticated user_id={id}
│  │
│  ├─ Check for project_id in form data
│  │
│  ├─ [UPDATE] AUTO_SAVE: updating existing project_id={id}
│  │  ├─ db.table("projects").update({...}).execute()
│  │  └─ AUTO_SAVE: project update completed for project_id={id}
│  │
│  ├─ [CREATE] AUTO_SAVE: creating new project name={name} pages={num}
│  │  ├─ _insert_project(...)
│  │  └─ AUTO_SAVE: new project created successfully
│  │
│  └─ [ERROR] AUTO_SAVE_FAILED (best-effort - doesn't fail response!)
│     ├─ exception_type={type}
│     ├─ exception_message={msg}
│     ├─ Full stack trace
│     └─ Continue to build response anyway
│
├─ START RESPONSE BUILD
│  ├─ jsonify(boq_data)
│  ├─ Set status_code = 200
│  │
│  └─ END RESPONSE BUILD
│     └─ jsonify successful status_code=200
│
├─ [ERROR] RESPONSE_BUILD_FAILED
│  ├─ exception_type={type}
│  ├─ exception_message={msg}
│  ├─ Full stack trace
│  └─ Return 502 error response
│
├─ PROCESS_PDF_SUCCESS: returning response to client
│
└─ HTTP 200 + JSON BoQ
   ↓
   @app.after_request adds CORS headers
   ↓
   Browser receives response + can read body
```

---

## Error Handler Catch-All

If ANY exception escapes before reaching the response handler:

```
UNHANDLED_EXCEPTION in request
  ├─ method={HTTP_METHOD}
  ├─ path={PATH}
  ├─ exception_type={TYPE}
  ├─ exception_message={MESSAGE}
  ├─ Full stack trace
  └─ HTTP 500 + CORS headers (so browser can read error)
```

---

## Logging Search Patterns

### To find success:
```
grep "PROCESS_PDF_SUCCESS" railway.log
```

### To find failures:
```
grep "FAILED\|FAILED" railway.log
grep "UNHANDLED_EXCEPTION" railway.log
```

### To trace complete request:
```
grep "PROCESS_PDF_START" -A 100 railway.log | head -50
```

### To find specific stage:
```
grep "START PDF PARSE\|END PDF PARSE" railway.log
grep "START AI CALL\|END AI CALL" railway.log
grep "START JSON EXTRACTION\|END JSON EXTRACTION" railway.log
# etc.
```

---

## Key Decision Points

| Decision | Logs | Action |
|----------|------|--------|
| Is PDF readable? | `END PDF PARSE` → ✅ or `START PDF PARSE FAILED` → ❌ | Fix PDF or adjust pdfplumber |
| Did Claude API work? | `END AI CALL` → ✅ or `AI CALL FAILED` → ❌ | Check API key, rate limits, model |
| Is response valid JSON? | `END JSON EXTRACTION` → ✅ or `JSON_EXTRACTION_FAILED` → ❌ | Claude output format issue |
| Does JSON match schema? | `END SCHEMA VALIDATION` → ✅ or `SCHEMA_VALIDATION_FAILED` → ❌ | Claude system prompt issue |
| Can rates be looked up? | `END RATE ENRICHMENT` → ✅ or `RATE_ENRICHMENT_FAILED` → ❌ | RATES_DB lookup issue |
| Can DB save project? | `AUTO_SAVE: ... created` → ✅ or `AUTO_SAVE_FAILED` → ⚠️ | Supabase permission issue (non-fatal) |
| Can JSON serialize? | `END RESPONSE BUILD` → ✅ or `RESPONSE_BUILD_FAILED` → ❌ | BoQ contains non-serializable object |

---

## Response Codes You'll See

| Code | Meaning | From | Likely Cause |
|------|---------|------|--------------|
| 200 | OK | `process_pdf()` return | Success ✅ |
| 401 | Unauthorized | Early return | No Bearer token |
| 400 | Bad Request | `_run_boq_pipeline()` | No file field, empty filename |
| 415 | Unsupported Media Type | `_run_boq_pipeline()` | Not a PDF |
| 422 | Unprocessable Entity | `_run_boq_pipeline()` | PDF unreadable or empty text |
| 429 | Rate Limited | `_run_boq_pipeline()` | Quota exceeded |
| 502 | Bad Gateway | Various | Claude API error, JSON parse error, schema validation error, enrichment error, response build error |
| 503 | Service Unavailable | `_run_boq_pipeline()` | Claude API connection error |
| 504 | Gateway Timeout | `_run_boq_pipeline()` | Claude API timeout |
| 500 | Internal Server Error | Error handler | Unhandled exception |
