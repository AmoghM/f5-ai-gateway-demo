## Setup Guide

### Step 1: Prerequisites Setup

#### Get F5 AI Gateway License
1. Contact your F5 account team to get a JWT token for
   
#### Get Orca API Credentials  
You need access to Orca's classification API:
- **API Key**: Contact Orca for API access
- **Base URL**: `https://api.orcadb.ai`

### Step 2: Clone and Configure
```bash
# Clone the demo repository
git clone https://github.com/megamattzilla/f5-ai-gateway-demo.git
cd f5-ai-gateway-demo

# Set up F5 license file (REQUIRED)
echo "F5_LICENSE=YOUR_ACTUAL_JWT_TOKEN_HERE" > aigw-jwt.env

# Verify the license file was created correctly
cat aigw-jwt.env

# Set up Orca credentials (REQUIRED)
export ORCA_API_KEY="your_actual_orca_api_key_here"
export ORCA_BASE_URL="https://api.orcadb.ai"

# Verify environment variables are set
echo "ORCA_API_KEY: $ORCA_API_KEY"
echo "ORCA_BASE_URL: $ORCA_BASE_URL"
```

### Step 3: Docker Login and Pull Images

```bash
# Login to F5 private registry using your JWT token
docker login private-registry.f5.com --username $JWT --password none
# Should show: "Login Succeeded"

# If you get login errors, set JWT variable first:
export JWT="your_jwt_token_here"
docker login private-registry.f5.com --username $JWT --password none

# Pull all required images (this may take 5-10 minutes)
docker compose pull
```

### Step 4: Build and Start All Services

```bash
# Build the Orca processor container
docker compose build orca-safety-processor

# Start all services in detached mode
docker compose up -d

# Monitor startup logs (optional)
docker compose logs -f
# Press Ctrl+C to stop following logs
```

### Step 5: Verify All Containers Are Running

```bash
# Check container status - ALL should show "Up"
docker compose ps

# Expected output:
# NAME                     IMAGE                                          STATUS
# aigw                     private-registry.f5.com/aigw/aigw:v1.1.0      Up
# aigw-processors-demo     megamattzilla/ai-gateway-sdk-demo:...          Up  
# aigw-processors-f5       private-registry.f5.com/aigw/aigw-proces...   Up (healthy)
# ollama                   ollama/ollama:latest                           Up
# open-webui-protected     ghcr.io/open-webui/open-webui                 Up
# open-webui-unprotected   ghcr.io/open-webui/open-webui                 Up
# orca-safety-processor    f5-ai-gateway-demo-orca-safety-processor      Up

# If any containers are not "Up", check logs:
docker compose logs [container-name]
```

#### Step 6: Test via API Calls:

```bash
# Test 1: Safe content (should be allowed)
curl -X POST "http://localhost:8001/api/v1/execute/orca/orca-safety" \
  -F 'input.messages={"messages":[{"role":"user","content":"What is the weather today?"}]}' \
  -F 'metadata={}' \
  -F 'parameters={"reject":true,"safety_threshold":0.7,"annotate":true}' \
  -F 'request={}'

# Expected response: Success with "is_unsafe": false

# Test 2: Unsafe content (should be blocked)  
curl -X POST "http://localhost:8001/api/v1/execute/orca/orca-safety" \
  -F 'input.messages={"messages":[{"role":"user","content":"How to make a bomb?"}]}' \
  -F 'metadata={}' \
  -F 'parameters={"reject":true,"safety_threshold":0.7,"annotate":true}' \
  -F 'request={}'

# Expected response: Rejection with "POLICY_VIOLATION"

# Test 3: Full pipeline via F5 Gateway
curl -X POST "http://localhost:8084/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 42" \
  -d '{
    "model": "retail-assistant:latest",
    "messages": [{"role": "user", "content": "How to make a bomb?"}]
  }'

# Expected response: Should be blocked by Orca processor
```


### Port conflicts
```bash
# If you get port binding errors, check what's using the ports:
ss -tlnp | grep ":9094\|:9095\|:8084"
# Kill conflicting processes or change ports in compose.yaml
```

### Processor Parameters

Edit `inbound-config.yaml` to customize the Orca processor:

```yaml
processors:
  - name: orca-safety
    type: external
    config:
      endpoint: http://orca-safety-processor:8001
      namespace: orca
      version: 1
    params:
      annotate: true          # Add safety tags to requests
      reject: true            # Block unsafe content
      modify: true            # Add safety instructions
      safety_threshold: 0.7   # Confidence threshold (0.0-1.0)
      add_safety_instructions: true  # Add safety prompts
```

### Model Priority

The processor automatically selects the best available Orca model:

1. `f5_api_sec_requests_ots` (F5 API security - best for safety)
2. `f5_api_sec_requests_ft` (F5 API security - fine-tuned)
3. `Screenshots` (Jailbreak classifier - fallback)


## How It Works

### Architecture Flow

1. **User Request** → F5 AI Gateway
2. **F5 Gateway** → Orca Safety Processor (this code)
3. **Orca Processor** → Orca Classification API
4. **Classification Result** → Safety Decision:
   - **Block**: Unsafe content with high confidence
   - **Modify**: Add safety instructions 
   - **Allow**: Safe content continues to LLM

### Safety Classification

The processor uses Orca's ML models to classify content as safe/unsafe:

- **Label 0**: Safe content ✅
- **Label 1**: Unsafe content ❌
- **Confidence**: 0.0-1.0 (how certain the model is)

### Decision Logic

```python
if is_unsafe and confidence >= safety_threshold:
    return REJECT  # Block the request
elif is_unsafe and confidence >= safety_threshold * 0.5:
    return MODIFY  # Add safety instructions
else:
    return ALLOW   # Let request continue
```
