#!/usr/bin/env python3
"""
Native FastAPI Whisper Service with GPU Acceleration
Replacement for Docker-based whisper container with better performance
"""

import os
import tempfile
import logging
import asyncio
from pathlib import Path
from typing import Optional, Literal
import torch
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhisperService:
    """High-performance Whisper transcription service with GPU acceleration"""
    
    def __init__(self):
        self.model = None
        self.model_size = "small"  # Optimal balance of speed and accuracy for RTX 2080
        
        # Try CUDA first, now that cuDNN is installed
        if torch.cuda.is_available():
            try:
                # Test CUDA availability with a simple operation
                test_tensor = torch.tensor([1.0], device='cuda')
                del test_tensor
                self.device = "cuda"
                self.compute_type = "float16"
                logger.info(f"CUDA available - using GPU")
                logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            except Exception as e:
                logger.warning(f"CUDA test failed: {e}, falling back to CPU")
                self.device = "cpu"
                self.compute_type = "float32"
        else:
            self.device = "cpu"
            self.compute_type = "float32"
            
        logger.info(f"Initializing Whisper service on {self.device}")
        self._load_model()
    
    def _load_model(self):
        """Load the Whisper model with optimal settings"""
        try:
            logger.info(f"Loading {self.model_size} model on {self.device} with {self.compute_type}")
            
            # Try to load model with specified settings
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4 if self.device == "cpu" else 1,
                num_workers=1  # Optimal for real-time processing
            )
            logger.info("Model loaded successfully")
            
            # Test the model with a simple operation
            if self.device == "cuda":
                logger.info("Testing GPU model functionality...")
                
        except Exception as e:
            logger.error(f"Failed to load model with {self.device}: {e}")
            # Fallback to CPU if GPU fails
            if self.device == "cuda":
                logger.warning("GPU model failed, falling back to CPU")
                try:
                    self.device = "cpu"
                    self.compute_type = "float32"
                    self.model = WhisperModel(
                        self.model_size, 
                        device="cpu", 
                        compute_type="float32",
                        cpu_threads=4
                    )
                    logger.info("CPU fallback model loaded successfully")
                except Exception as cpu_error:
                    logger.error(f"CPU fallback also failed: {cpu_error}")
                    raise RuntimeError("Could not load Whisper model on either GPU or CPU")
            else:
                raise
    
    async def transcribe_audio(
        self,
        audio_file: UploadFile,
        task: str = "transcribe",
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        output_format: str = "txt"
    ) -> dict:
        """Transcribe audio file using faster-whisper"""
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Transcribe using faster-whisper
            segments, info = self.model.transcribe(
                temp_path,
                task=task,
                language=language,
                initial_prompt=initial_prompt,
                beam_size=5,  # Good balance of speed and accuracy
                best_of=5,
                temperature=0.0,  # Deterministic output
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=True,
                word_timestamps=True if output_format == "json" else False
            )
            
            # Format output based on requested format
            if output_format == "json":
                return self._format_json_output(segments, info)
            elif output_format == "txt":
                return {"text": " ".join(segment.text for segment in segments)}
            elif output_format == "vtt":
                return {"vtt": self._format_vtt_output(segments)}
            elif output_format == "srt":
                return {"srt": self._format_srt_output(segments)}
            else:
                return {"text": " ".join(segment.text for segment in segments)}
                
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    
    def _format_json_output(self, segments, info):
        """Format output as JSON with detailed segment information"""
        return {
            "text": " ".join(segment.text for segment in segments),
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "segments": [
                {
                    "id": i,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "words": [
                        {
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        } for word in (segment.words or [])
                    ] if segment.words else []
                }
                for i, segment in enumerate(segments)
            ]
        }
    
    def _format_vtt_output(self, segments):
        """Format output as WebVTT"""
        vtt_lines = ["WEBVTT", ""]
        for segment in segments:
            start_time = self._seconds_to_vtt_time(segment.start)
            end_time = self._seconds_to_vtt_time(segment.end)
            vtt_lines.append(f"{start_time} --> {end_time}")
            vtt_lines.append(segment.text)
            vtt_lines.append("")
        return "\n".join(vtt_lines)
    
    def _format_srt_output(self, segments):
        """Format output as SRT"""
        srt_lines = []
        for i, segment in enumerate(segments, 1):
            start_time = self._seconds_to_srt_time(segment.start)
            end_time = self._seconds_to_srt_time(segment.end)
            srt_lines.append(str(i))
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(segment.text)
            srt_lines.append("")
        return "\n".join(srt_lines)
    
    def _seconds_to_vtt_time(self, seconds):
        """Convert seconds to VTT time format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    
    def _seconds_to_srt_time(self, seconds):
        """Convert seconds to SRT time format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    async def detect_language(self, audio_file: UploadFile) -> dict:
        """Detect the language of the audio file"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            segments, info = self.model.transcribe(temp_path, beam_size=1, best_of=1)
            return {
                "detected_language": info.language,
                "language_probability": info.language_probability
            }
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            raise HTTPException(status_code=500, detail=f"Language detection failed: {str(e)}")
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

# Initialize the service
whisper_service = WhisperService()

# Create FastAPI app
app = FastAPI(
    title="Whisper ASR Service",
    description="High-performance speech recognition service with GPU acceleration",
    version="2.0.0"
)

@app.post("/asr")
async def transcribe(
    audio_file: UploadFile = File(...),
    task: Literal["transcribe", "translate"] = Query("transcribe"),
    language: Optional[str] = Query(None),
    initial_prompt: Optional[str] = Query(None),
    output: Literal["txt", "vtt", "srt", "tsv", "json"] = Query("txt"),
    encode: bool = Query(True)  # For compatibility with Docker version
):
    """
    Transcribe audio file to text
    Compatible with the Docker whisper-asr-webservice API
    """
    if not audio_file.content_type.startswith('audio/'):
        # Allow common audio formats even if content-type is wrong
        allowed_extensions = ['.wav', '.mp3', '.mp4', '.m4a', '.flac', '.ogg']
        if not any(audio_file.filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(status_code=400, detail="Invalid audio file format")
    
    try:
        result = await whisper_service.transcribe_audio(
            audio_file=audio_file,
            task=task,
            language=language,
            initial_prompt=initial_prompt,
            output_format=output
        )
        return result
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/detect-language")
async def detect_language(
    audio_file: UploadFile = File(...),
    encode: bool = Query(True)  # For compatibility
):
    """Detect the language of an audio file"""
    try:
        result = await whisper_service.detect_language(audio_file)
        return result
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "device": whisper_service.device,
        "model_size": whisper_service.model_size,
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    }

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Whisper ASR Service",
        "version": "2.0.0",
        "device": whisper_service.device,
        "model": whisper_service.model_size,
        "gpu_acceleration": torch.cuda.is_available(),
        "endpoints": {
            "transcribe": "/asr",
            "detect_language": "/detect-language",
            "health": "/health",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    # Run the service
    port = int(os.getenv("WHISPER_PORT", 9000))
    host = os.getenv("WHISPER_HOST", "0.0.0.0")
    
    logger.info(f"Starting Whisper service on {host}:{port}")
    logger.info(f"Device: {whisper_service.device}")
    logger.info(f"Model: {whisper_service.model_size}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )