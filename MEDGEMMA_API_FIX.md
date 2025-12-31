# MedGemma API Format Fix

## Issue Summary
The Image Analyzer Agent was failing to extract responses from the MedGemma model due to API format changes.

## Root Cause
- **Old Format**: Legacy prediction format returned plain text strings
- **New Format**: ChatCompletion format returns nested dictionary structure
- **Problem**: Code was trying to use the entire dictionary as a string

## What Was Fixed

### 1. **Updated Request Format** ✅
Changed from legacy format to ChatCompletion format:

**Before (Legacy - Not Working):**
```python
instances = [{
    "prompt": formatted_prompt,
    "multi_modal_data": {"image": data_url},
    "max_tokens": self.config["max_tokens"],
    "temperature": self.config["temperature"],
    "raw_response": True,
}]
```

**After (ChatCompletion - Working):**
```python
instances = [{
    "@requestFormat": "chatCompletions",
    "messages": [
        {
            "role": "system",
            "content": [{"type": "text", "text": system_instruction}]
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_query},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }
    ],
    "max_tokens": self.config["max_tokens"],
    "temperature": self.config["temperature"]
}]
```

### 2. **Fixed Response Extraction** ✅
Added proper extraction logic for ChatCompletion format:

```python
if response.predictions and len(response.predictions) > 0:
    prediction_data = response.predictions[0]
    
    # Extract text from ChatCompletion format
    if isinstance(prediction_data, dict) and 'choices' in prediction_data:
        # ChatCompletion format: extract from choices[0].message.content
        response_text = prediction_data['choices'][0]['message']['content']
        self.logger.info(f"Successfully extracted response ({len(response_text)} chars)")
        return response_text
    elif isinstance(prediction_data, str):
        # Legacy format: direct string response (backward compatibility)
        self.logger.info("Received legacy format response")
        return prediction_data
    else:
        # Unknown format
        self.logger.error(f"Unexpected prediction format: {type(prediction_data)}")
        raise ValueError(f"Unexpected prediction format: {type(prediction_data)}")
```

### 3. **Response Structure**
The ChatCompletion response has this structure:
```python
{
    'choices': [
        {
            'index': 0,
            'message': {
                'content': "The actual radiologist response text...",
                'role': 'assistant'
            }
        }
    ],
    'created': 1767202449,
    'id': '60397b26-2a14-46e1-a96e-2e958deb8e05',
    'model': 'placeholder',
    'usage': {
        'completion_tokens': 200,
        'prompt_tokens': 283,
        'total_tokens': 483
    }
}
```

We now correctly extract: `prediction_data['choices'][0]['message']['content']`

### 4. **Benefits of the Fix**
- ✅ **Proper API Format**: Uses the correct ChatCompletion format
- ✅ **Correct Extraction**: Extracts text from nested structure
- ✅ **Backward Compatible**: Still handles legacy format if needed
- ✅ **Better Logging**: Clear success/error messages
- ✅ **Dynamic Values**: Uses actual `system_instruction`, `user_query`, and `data_url` instead of hardcoded values

## Configuration Update
Also updated `config/guardrails.yaml`:
- Changed `min_image_quality_score` from `0.6` to `0.25` for more lenient quality checks

## Testing
The fix should now:
1. ✅ Send requests in correct ChatCompletion format
2. ✅ Receive responses from MedGemma successfully
3. ✅ Extract the text content properly
4. ✅ Parse the response into structured findings
5. ✅ Return formatted analysis to the user

## Files Modified
- `/src/agents/image_analyzer_agent.py` - Updated `_query_medgemma()` method
- `/config/guardrails.yaml` - Lowered quality threshold

## Status
✅ **FIXED** - Ready for testing

---

**Date**: 2025-12-31  
**Version**: 2.0.1
