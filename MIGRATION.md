# Migration to GapGPT API

## Overview
This document describes the migration from using OpenAI API to GapGPT API.

## Changes Made

### 1. Configuration Update (`backend/app/core/config.py`)
- Added new settings for GapGPT:
  - `gapgpt_api_key`
  - `gapgpt_base_url` (default: `https://api.gapgpt.app/v1`)
  - `gapgpt_model` (default: `gapgpt-qwen-3.5`)

### 2. LLM Service Update (`backend/app/services/llm_service.py`)
- Added support for "gapgpt" as an LLM provider
- Updated client initialization to use OpenAI client with GapGPT base URL
- Updated error handling to work with GapGPT

### 3. Medical Extractor Update (`backend/app/services/medical_extractor.py`)
- Updated to support GapGPT provider
- Now checks `llm_provider` setting to decide which client to use

### 4. SOAP Note Generator Update (`backend/app/services/soap_generator.py`)
- Added GapGPT to LLMProvider enum
- Added `gapgpt_client` initialization
- Added `_generate_with_gapgpt` method
- Updated provider selection logic

### 5. Medical File Analyzer Update (`backend/app/services/medical_file_analyzer.py`)
- Added `gapgpt_api_key` and `gapgpt_base_url` parameters to constructor
- Added `gapgpt_client` initialization
- Added `_analyze_with_gapgpt` method
- Updated provider selection logic

### 6. Environment Variables Update
- Updated `backend/.env` to use GapGPT
- Updated `backend/.env.example` to show new variables

### 7. Test Script
- Created `backend/test_gapgpt.py` to test GapGPT connection

## New Environment Variables
```env
GAPGPT_API_KEY=<GAPGPT_API_KEY>
GAPGPT_BASE_URL=https://api.gapgpt.app/v1
LLM_PROVIDER=gapgpt
GAPGPT_MODEL=gapgpt-qwen-3.5
```

## Notes
- GapGPT uses the same OpenAI client library, so no need to install new packages
- All parameters (temperature, max_tokens, etc.) should work the same
- Response format is the same as OpenAI
- You can still switch back to OpenAI by setting `LLM_PROVIDER=openai` in .env
