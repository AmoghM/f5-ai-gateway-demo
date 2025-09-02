"""
Orca Safety Processor for F5 AI Gateway

This processor integrates Orca's classification capabilities with F5 AI Gateway
to provide content safety analysis for incoming prompts.
"""

import os
import logging
from typing import Optional

from f5_ai_gateway_sdk.parameters import Parameters
from f5_ai_gateway_sdk.processor import Processor
from f5_ai_gateway_sdk.processor_routes import ProcessorRoutes
from f5_ai_gateway_sdk.request_input import Message, MessageRole
from f5_ai_gateway_sdk.result import Result, Reject, RejectCode
from f5_ai_gateway_sdk.signature import INPUT_ONLY_SIGNATURE
from f5_ai_gateway_sdk.tags import Tags
from f5_ai_gateway_sdk.type_hints import Metadata
from starlette.applications import Starlette

logger = logging.getLogger(__name__)


class OrcaSafetyParameters(Parameters):
    """Parameters for Orca Safety Processor"""
    
    # Confidence threshold for safety classification
    safety_threshold: float = 0.7
    
    # Model name to use for classification (can be overridden)
    model_name: str = "orca-safety-demo"
    
    # Whether to add safety instructions when unsafe content is detected but not rejected
    add_safety_instructions: bool = True
    
    # Safety instruction to add
    safety_instruction: str = "Please provide helpful, harmless, and honest responses. Avoid generating harmful, unsafe, or inappropriate content."


class OrcaSafetyProcessor(Processor):
    """
    A processor that uses Orca classification to detect unsafe content in prompts
    """
    
    def __init__(self):
        super().__init__(
            name="orca-safety",
            version="v1",
            namespace="orca",
            signature=INPUT_ONLY_SIGNATURE,
            parameters_class=OrcaSafetyParameters,
        )
        
        self.orca_model: Optional[ClassificationModel] = None
        self._init_orca_model()
    
    def _init_orca_model(self):
        if not ORCA_AVAILABLE:
            raise RuntimeError("Orca SDK is required but not available. Please install orca_sdk.")
            
        # Check if credentials are available
        api_key = os.getenv("ORCA_API_KEY")
        base_url = os.getenv("ORCA_BASE_URL")
        
        if not api_key or not base_url:
            raise RuntimeError("Orca credentials not found. Please set ORCA_API_KEY and ORCA_BASE_URL environment variables.")
            
        # Initialize credentials
        try:
            OrcaCredentials.set_api_key(api_key)
            OrcaCredentials.set_base_url(base_url)
            logger.info("Orca credentials set successfully")
        except Exception as cred_error:
            raise RuntimeError(f"Could not set Orca credentials: {cred_error}")
                
        # Initialize Orca classification model
        # Try security/safety models first, then fall back to any available
        preferred_models = [
            "f5_api_sec_requests_ots",  # F5 API security requests (better for safety)
            "f5_api_sec_requests_ft",   # F5 API security requests (fine-tuned)
            "Screenshots"               # Jailbreak classifier (fallback)
        ]
        
        # First, try preferred security models
        model_loaded = False
        for model_name in preferred_models:
            try:
                if ClassificationModel.exists(model_name):
                    self.orca_model = ClassificationModel.open(model_name)
                    logger.info(f"Loaded Orca security model: {model_name}")
                    model_loaded = True
                    break
            except Exception as e:
                logger.warning(f"Failed to load model {model_name}: {e}")
                continue
        
        # If no preferred models work, try any available model
        if not model_loaded:
            try:
                available_models = ClassificationModel.all()
                if available_models:
                    first_model = available_models[0]
                    self.orca_model = ClassificationModel.open(first_model.name)
                    logger.warning(f"Using fallback Orca model: {first_model.name} (may not be suitable for safety)")
                    model_loaded = True
            except Exception as e:
                logger.warning(f"Failed to load any model: {e}")
        
        if not model_loaded:
            raise RuntimeError("No suitable Orca models available for safety classification.")
    
    def _classify_safety_with_orca(self, text: str) -> tuple[bool, float]:
        """Use Orca to classify safety of text"""
        if self.orca_model is None:
            raise RuntimeError("Orca model not initialized. Cannot process safety classification.")
        
        try:
            prediction = self.orca_model.predict(text)
            # Assuming binary classification: 0 = safe, 1 = unsafe
            is_unsafe = prediction.label == 1
            confidence = prediction.confidence
            logger.debug(f"Orca classification: text_length={len(text)}, is_unsafe={is_unsafe}, confidence={confidence}")
            return is_unsafe, confidence
        except Exception as e:
            logger.error(f"Orca classification failed: {e}")
            raise RuntimeError(f"Orca classification failed: {e}")
    
    
    
    def process_input(self, prompt, metadata, parameters: OrcaSafetyParameters, request):
        """Process incoming prompt for safety"""
        
        my_tags = Tags()
        
        # Combine all message content for analysis
        combined_text = " ".join(
            message.content for message in prompt.messages 
            if message.content and message.role != MessageRole.SYSTEM
        )
        
        # Classify safety using Orca
        try:
            is_unsafe, confidence = self._classify_safety_with_orca(combined_text)
        except Exception as e:
            logger.error(f"Safety classification failed: {e}")
            return Reject(
                code=RejectCode.POLICY_VIOLATION,
                detail=f"Safety classification service unavailable: {e}"
            )
        
        # Create metadata about the safety check
        result_metadata = Metadata({
            "safety_checked": True,
            "is_unsafe": is_unsafe,
            "confidence": confidence,
            "used_orca": self.orca_model is not None,
            "text_length": len(combined_text)
        })
        
        # Add tags if annotation is enabled
        if parameters.annotate:
            if is_unsafe:
                my_tags.add_tag("safety", "unsafe")
                my_tags.add_tag("confidence", str(round(confidence, 2)))
            else:
                my_tags.add_tag("safety", "safe")
        
        # Reject if unsafe content detected and confidence is above threshold
        if parameters.reject and is_unsafe and confidence >= parameters.safety_threshold:
            return Reject(
                code=RejectCode.POLICY_VIOLATION,
                detail=f"Unsafe content detected with {confidence:.2f} confidence"
            )
        
        # Optionally modify prompt to add safety instructions for borderline content
        modified_prompt = prompt
        if (parameters.modify and parameters.add_safety_instructions and 
            is_unsafe and confidence >= parameters.safety_threshold * 0.5):
            
            # Add safety instruction as system message
            prompt.messages.append(
                Message(
                    content=parameters.safety_instruction,
                    role=MessageRole.SYSTEM,
                )
            )
            modified_prompt = prompt
        
        return Result(
            processor_result=result_metadata,
            tags=my_tags,
            modified_prompt=modified_prompt
        )


# Create Starlette app
app = Starlette(
    routes=ProcessorRoutes([OrcaSafetyProcessor()]),
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
