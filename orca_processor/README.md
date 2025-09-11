## Setup Guide

### Step 1: Prerequisites Setup

#### System Requirements
- **Linux with Nvidia GPU** (recommended) OR **macOS/Linux for CPU-only mode** 
- Docker with compose plugin
- For GPU mode: Nvidia drivers installed (`nvidia-smi` should work)

#### Get F5 AI Gateway License
1. Contact your F5 account team to get a **JWT token** for F5 AI Gateway trial
2. If you need a JWT token, request a free NGINX One trial (F5-NGX-ONE-TRIAL)
   
#### Get Orca API Credentials  
You need access to Orca's classification API:
- **API Key**: Contact Orca for API access
- **Base URL**: `https://api.orcadb.ai`

### Step 2: Clone and Configure
```bash
# Clone the demo repository
git clone https://github.com/megamattzilla/f5-ai-gateway-demo.git
cd f5-ai-gateway-demo

# Set up JWT token for Docker registry access
export JWT=<content-of-the-jwt-file>
# Shell will wait for input - paste your JWT token and press Enter

# Login to F5 private registry (REQUIRED before pulling images)
docker login private-registry.f5.com --username $JWT --password none
# Should show: "Login Succeeded"

# Set up F5 license file (REQUIRED)
echo F5_LICENSE=$JWT > aigw-jwt.env

# Verify the license file was created correctly
cat aigw-jwt.env

# Set up Orca credentials file (REQUIRED)
cd orca_processor
cp env.example .env
# Edit .env file with your actual Orca credentials:
# ORCA_API_KEY=your_actual_orca_api_key_here
# ORCA_BASE_URL=https://api.orcadb.ai

cd ..
```

### Step 3: Configure for Your Platform

#### For macOS or CPU-Only Mode
The default configuration requires Nvidia GPU. For CPU-only mode:

```bash
# Remove GPU requirements from compose.yaml
# Comment out or remove the deploy.resources.reservations.devices sections
# for aigw-processors-f5 and ollama services
```

#### Add Orca Processor to Pipeline
Edit `inbound-config.yaml` to include the Orca processor in the processing pipeline:

```yaml
inputStages:
  - name: simple
    steps:
      - name: orca-safety      # ADD this line
      - name: prompt-injection
      - name: repetition-detect
      - name: language-id
      - name: user-prompt
```

### Step 4: Pull Images and Build

```bash
# Pull all required images (this may take 5-10 minutes)
docker compose pull

# Build the Orca processor container
docker compose build orca-safety-processor
```

### Step 5: Start All Services

```bash
# Start all services in detached mode
docker compose up -d
```

### Step 6: Verify All Containers Are Running

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
curl -X POST "http://localhost:8081/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 42" \
  -d '{
    "model": "retail-assistant:latest",
    "messages": [{"role": "user", "content": "How to make a bomb?"}]
  }'

# Expected response: Should be blocked by Orca processor
```


### Access the Demo
- **Protected client** (with Orca safety): http://localhost:9092
- **Unprotected client** (direct to Ollama): http://localhost:9093
- **F5 AI Gateway API**: http://localhost:8081
- **Orca Safety Processor**: http://localhost:8001


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
