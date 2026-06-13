# /process Endpoint Audit & Diagnostic Logging

**Date:** 2026-06-13  
**Status:** ✅ Complete  
**Changes:** Diagnostic logging only — no business logic changes

---

## Problem Summary

The `/process` endpoint was exhibiting these symptoms:
- Frontend uploads PDF → pages processed in Railway logs
- AI API credits consumed (Claude API call successful)
- Browser receives CORS error
- No successful response reaches frontend

**Hypothesis:** Exception occurring AFTER PDF processing begins, but response either:
1. Not being returned (causing browser timeout)
2. Being returned without CORS headers (appearing as CORS error)
3. Being caught by unhandled exception handler before reaching frontend

---

## Audit & Changes Made

All changes are **diagnostic logging only** — no business logic altered.

### 1. Error Handler Enhancement

**File:** `app.py` (lines ~78-97)  
**What Changed:** Enhanced `handle_unhandled_exception()` to log full diagnostic details

```python
@app.errorhandler(Exception)
def handle_unhandled_exception(exc):
    app.logger.exception(
        "UNHANDLED_EXCEPTION in request: method=%s path=%s exception_type=%s exception_message=%s",
        request.method,
        request.path,
        type(exc).__name__,
        str(exc)
    )
    # CORS headers still applied below
```

**Why:** Catches any unhandled exceptions before they reach WSGI and still apply CORS headers

---

### 2. PDF Parsing Stage

**File:** `app.py` `_run_boq_pipeline()` function (lines ~1406-1420)

**Logging Added:**
```
START PDF PARSE: filename={name} file_size_bytes={size}
  PDF opened: page_count={num_pages}
END PDF PARSE: extracted_text_length={len} approx_words={count}

[On Error]
START PDF PARSE FAILED: exception_type={type} exception_message={msg}
  [Full stack trace included]

[On Empty]
PDF_PARSE_EMPTY_TEXT: no text extracted from {page_count} pages
```

**Why:** Confirms PDF reading completes and text extraction succeeds before Claude call

---

### 3. AI (Claude) Call Stage

**File:** `app.py` `_run_boq_pipeline()` function (lines ~1426-1463)

**Logging Added:**
```
START AI CALL: model=claude-sonnet-4-6 pdf_text_length={length}
  [Existing: Claude structured output call details]
END AI CALL: processing_time_seconds={sec} stop_reason={reason}

[On API Errors - with full stack trace]
AI CALL FAILED (APIStatusError): status_code={code} message={msg}
AI CALL FAILED (APITimeoutError): {msg}
AI CALL FAILED (APIConnectionError): {msg}

[On Response Issues]
AI_OUTPUT_TRUNCATED: stop_reason=max_tokens
AI_OUTPUT_REFUSED: stop_reason=refusal
```

**Why:** Confirms Claude API call succeeds and response is valid before JSON parsing

---

### 4. JSON Extraction Stage

**File:** `app.py` `_run_boq_pipeline()` function (lines ~1494-1502)

**Logging Added:**
```
START JSON EXTRACTION: raw_text_length={length}
END JSON EXTRACTION: boq_data_keys={keys}

[On JSON Error - with full diagnostic info]
JSON_EXTRACTION_FAILED: JSONDecodeError at line {line} col {col}: {msg}
  First 500 chars of raw_text: {preview}

[On Unexpected Error]
JSON_EXTRACTION_FAILED: Unexpected exception_type={type}: {msg}
  [Full stack trace included]
```

**Why:** Identifies if Claude output is malformed JSON before validation

---

### 5. Schema Validation Stage

**File:** `app.py` `_run_boq_pipeline()` function (lines ~1504-1512)

**Logging Added:**
```
START SCHEMA VALIDATION
END SCHEMA VALIDATION: validation_passed=true

[On Validation Failure - with full stack trace]
SCHEMA_VALIDATION_FAILED: ValueError: {msg}
SCHEMA_VALIDATION_FAILED: Unexpected exception_type={type}: {msg}
```

**Why:** Confirms Claude output matches BOQ_OUTPUT_SCHEMA before rate enrichment

---

### 6. Rate Enrichment Stage

**File:** `app.py` `_run_boq_pipeline()` function (lines ~1514-1521)

**Logging Added:**
```
START RATE ENRICHMENT
END RATE ENRICHMENT: enrichment_complete=true

[On Enrichment Failure - with full stack trace]
RATE_ENRICHMENT_FAILED: exception_type={type}: {msg}
  [Full stack trace included]

[Final Success]
PIPELINE_SUCCESS: returning_to_process_pdf
```

**Why:** Confirms BoQ is enriched with rates before returning to process_pdf

---

### 7. Process PDF Handler

**File:** `app.py` `process_pdf()` function (lines ~1528-1600)

**Logging Added:**
```
PROCESS_PDF_START: method=POST path=/process

[Auth Check]
PROCESS_PDF_AUTH_OK: calling _run_boq_pipeline
  OR
PROCESS_PDF_AUTH_FAILED: no bearer token in Authorization header

[Pipeline Results]
PROCESS_PDF_PIPELINE_SUCCESS: pages={num} boq_trades={num}
  OR
PROCESS_PDF_PIPELINE_ERROR: pipeline_returned_error

[Auto-Save Stage]
START AUTO-SAVE
AUTO_SAVE: authenticated user_id={id}
AUTO_SAVE: updating existing project_id={id}
  OR
AUTO_SAVE: creating new project name={name} pages={num}
AUTO_SAVE: new project created successfully
  OR
AUTO_SAVE: no authenticated user, skipping save
  OR (Best-effort - doesn't fail response)
AUTO_SAVE_FAILED: exception_type={type} message={msg}
  [Full stack trace included]

[Response Build Stage]
START RESPONSE BUILD: serializing boq_data to JSON
END RESPONSE BUILD: jsonify successful status_code=200
PROCESS_PDF_SUCCESS: returning response to client

[Response Build Failure - with full stack trace]
RESPONSE_BUILD_FAILED: exception_type={type} message={msg}
```

**Why:** Traces entire request flow from auth through auto-save to final response

---

## How to Use This Logging

### 1. **Check Railway Logs**

All logs are output via `app.logger` which goes to Railway's stdout:

```bash
railway logs --follow
```

Or via Railway dashboard:
1. Go to railway.app
2. Select your deployment
3. View Logs tab in real-time

### 2. **Trace Execution Flow**

Look for these markers in order:
```
PROCESS_PDF_START
  ↓
PROCESS_PDF_AUTH_OK
  ↓
START PDF PARSE → END PDF PARSE
  ↓
START AI CALL → END AI CALL
  ↓
START JSON EXTRACTION → END JSON EXTRACTION
  ↓
START SCHEMA VALIDATION → END SCHEMA VALIDATION
  ↓
START RATE ENRICHMENT → END RATE ENRICHMENT
  ↓
PIPELINE_SUCCESS
  ↓
START AUTO-SAVE → [Auto-save logs] → END AUTO-SAVE (or AUTO_SAVE_FAILED)
  ↓
START RESPONSE BUILD → END RESPONSE BUILD
  ↓
PROCESS_PDF_SUCCESS
```

**If you see a stage marker but no END marker**, execution stopped there → look at exception logs that follow.

### 3. **Find the Exact Failure Point**

Search logs for any of these error prefixes to locate failures:
- `START PDF PARSE FAILED`
- `AI CALL FAILED`
- `AI_OUTPUT_TRUNCATED` or `AI_OUTPUT_REFUSED`
- `JSON_EXTRACTION_FAILED`
- `SCHEMA_VALIDATION_FAILED`
- `RATE_ENRICHMENT_FAILED`
- `AUTO_SAVE_FAILED`
- `RESPONSE_BUILD_FAILED`
- `UNHANDLED_EXCEPTION`

Each includes:
- Full exception type
- Full exception message
- Complete Python stack trace

### 4. **Common Failure Scenarios**

| Error | Cause | Solution |
|-------|-------|----------|
| `START PDF PARSE FAILED` | PDF unreadable (corrupt, password-protected, scanned image) | Validate PDF with pdfplumber locally |
| `PDF_PARSE_EMPTY_TEXT` | Scanned image without OCR layer | Add OCR or use PDF with text layer |
| `AI CALL FAILED (APIStatusError)` | Claude API error (invalid key, rate limit, etc.) | Check `ANTHROPIC_API_KEY` env var |
| `AI_OUTPUT_TRUNCATED` | Response too large for token limit | Reduce system prompt or increase `max_tokens` |
| `JSON_EXTRACTION_FAILED` | Claude output is not valid JSON | Claude sometimes adds markdown wrappers—check raw_text preview |
| `SCHEMA_VALIDATION_FAILED` | Output doesn't match BOQ_OUTPUT_SCHEMA | Check Claude system prompt and response structure |
| `AUTO_SAVE_FAILED` | Database error during project save | Check Supabase connection and permissions (best-effort—doesn't fail response) |
| `RESPONSE_BUILD_FAILED` | Cannot serialize BoQ to JSON | Check for circular references or non-JSON-serializable objects in boq_data |
| `UNHANDLED_EXCEPTION` | Unknown exception in request | Look at method/path/exception_type in log |

### 5. **Example Log Session**

A successful request looks like:
```
PROCESS_PDF_START: method=POST path=/process
PROCESS_PDF_AUTH_OK: calling _run_boq_pipeline
START PDF PARSE: filename=drawing.pdf file_size_bytes=2457823
PDF opened: page_count=12
END PDF PARSE: extracted_text_length=45678 approx_words=8234
START AI CALL: model=claude-sonnet-4-6 pdf_text_length=45678
END AI CALL: processing_time_seconds=18.5 stop_reason=end_turn
Claude response extracted: raw_text_length=12456
END JSON EXTRACTION: boq_data_keys=['revision', 'bill_of_quantities', 'assumptions_register']
END SCHEMA VALIDATION: validation_passed=true
END RATE ENRICHMENT: enrichment_complete=true
PIPELINE_SUCCESS: returning_to_process_pdf
PROCESS_PDF_PIPELINE_SUCCESS: pages=12 boq_trades=8
START AUTO-SAVE
AUTO_SAVE: authenticated user_id=abc-def-123
AUTO_SAVE: creating new project name=drawing pages=12
AUTO_SAVE: new project created successfully
START RESPONSE BUILD: serializing boq_data to JSON
END RESPONSE BUILD: jsonify successful status_code=200
PROCESS_PDF_SUCCESS: returning response to client
```

A failed request shows where it stops, e.g.:
```
PROCESS_PDF_START: method=POST path=/process
PROCESS_PDF_AUTH_OK: calling _run_boq_pipeline
START PDF PARSE: filename=drawing.pdf file_size_bytes=2457823
PDF opened: page_count=12
END PDF PARSE: extracted_text_length=45678 approx_words=8234
START AI CALL: model=claude-sonnet-4-6 pdf_text_length=45678
END AI CALL: processing_time_seconds=18.5 stop_reason=end_turn
Claude response extracted: raw_text_length=12456
START JSON EXTRACTION: raw_text_length=12456
JSON_EXTRACTION_FAILED: JSONDecodeError at line 1 col 142: Invalid \escape
  First 500 chars of raw_text: {"revision": "A", "issue_status": "Tender Issue", ... \N ...
  [Full stack trace follows]
```

---

## CORS Headers on All Error Paths

**Verified:** All error responses include CORS headers via:
1. `@app.after_request` hook runs after every response
2. `@app.errorhandler(Exception)` explicitly sets CORS headers even for unhandled exceptions
3. Each early return in `_run_boq_pipeline()` returns via `_fail` tuple which `process_pdf()` then returns

**Result:** Browser can always read error response body; "CORS error" in browser console (if seen) means headers weren't sent, which now triggers diagnostic logging in error handler.

---

## Full Stack Traces in Logs

**Every exception** logged via `app.logger.exception()` which includes:
```
[Timestamp] [LOG_LEVEL] [Module] Message
Traceback (most recent call last):
  File "...", line X, in function_name
    code line
  ...
ExceptionType: exception message
```

All exception details captured for debugging.

---

## No Business Logic Changes

✅ **Verified:** Only logging statements added — no changes to:
- PDF parsing logic
- Claude API calls
- JSON parsing
- Schema validation
- Rate enrichment
- Auto-save logic
- Response generation

---

## Next Steps

1. **Deploy** updated `app.py` to Railway
2. **Reproduce** the issue by uploading a PDF
3. **Check Railway logs** for failure point using markers above
4. **Report** the exact failure stage and exception details
5. **Iterate** based on which stage is failing

The logs will now show exactly where execution stops and why.
