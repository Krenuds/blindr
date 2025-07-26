#!/usr/bin/env python3
"""
Whisper HTTP Client for Discord Bot Integration
Async HTTP client for communicating with the Whisper ASR service
"""

import aiohttp
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
import json

logger = logging.getLogger(__name__)

class WhisperClient:
    """Async HTTP client for Whisper ASR service"""
    
    def __init__(self, base_url: str = "http://localhost:9000"):
        """
        Initialize Whisper client
        
        Args:
            base_url: Whisper service URL (default: http://localhost:9000)
        """
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def connect(self):
        """Initialize the HTTP session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes for large audio files
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check if Whisper service is healthy
        
        Returns:
            Health status dictionary
            
        Raises:
            aiohttp.ClientError: If service is unreachable
            Exception: If service returns error
        """
        await self.connect()
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Health check failed: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Whisper service unreachable: {e}")
            raise
    
    async def transcribe_file(
        self,
        audio_file_path: Union[str, Path],
        task: str = "transcribe",
        language: Optional[str] = None,
        output_format: str = "txt",
        initial_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file
        
        Args:
            audio_file_path: Path to audio file
            task: "transcribe" or "translate" 
            language: Language code (e.g., "en", "es") or None for auto-detection
            output_format: "txt", "json", "vtt", "srt"
            initial_prompt: Optional prompt to guide transcription
            
        Returns:
            Transcription result dictionary
            
        Raises:
            FileNotFoundError: If audio file doesn't exist
            aiohttp.ClientError: If service is unreachable
            Exception: If transcription fails
        """
        await self.connect()
        
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Prepare form data
        data = aiohttp.FormData()
        
        # Add audio file
        with open(audio_path, 'rb') as f:
            data.add_field('audio_file', f, filename=audio_path.name, 
                          content_type='audio/wav')
            
            # Add parameters
            params = {
                'task': task,
                'output': output_format,
                'encode': 'true'
            }
            
            if language:
                params['language'] = language
            if initial_prompt:
                params['initial_prompt'] = initial_prompt
            
            try:
                async with self.session.post(
                    f"{self.base_url}/asr",
                    data=data,
                    params=params
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Transcription successful for {audio_path.name}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Transcription failed: {response.status} - {error_text}")
                        raise Exception(f"Transcription failed: {response.status} - {error_text}")
                        
            except aiohttp.ClientError as e:
                logger.error(f"HTTP error during transcription: {e}")
                raise Exception(f"Service communication error: {e}")
    
    async def transcribe_bytes(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        task: str = "transcribe",
        language: Optional[str] = None,
        output_format: str = "txt",
        initial_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio from bytes data
        
        Args:
            audio_data: Raw audio file bytes
            filename: Filename for the upload
            task: "transcribe" or "translate"
            language: Language code or None for auto-detection
            output_format: "txt", "json", "vtt", "srt" 
            initial_prompt: Optional prompt to guide transcription
            
        Returns:
            Transcription result dictionary
            
        Raises:
            aiohttp.ClientError: If service is unreachable
            Exception: If transcription fails
        """
        await self.connect()
        
        # Prepare form data
        data = aiohttp.FormData()
        data.add_field('audio_file', audio_data, filename=filename, 
                      content_type='audio/wav')
        
        # Add parameters
        params = {
            'task': task,
            'output': output_format,
            'encode': 'true'
        }
        
        if language:
            params['language'] = language
        if initial_prompt:
            params['initial_prompt'] = initial_prompt
        
        try:
            async with self.session.post(
                f"{self.base_url}/asr",
                data=data,
                params=params
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Transcription successful for {filename}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Transcription failed: {response.status} - {error_text}")
                    raise Exception(f"Transcription failed: {response.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during transcription: {e}")
            raise Exception(f"Service communication error: {e}")
    
    async def detect_language(
        self,
        audio_file_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Detect language of an audio file
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Language detection result
            
        Raises:
            FileNotFoundError: If audio file doesn't exist
            aiohttp.ClientError: If service is unreachable
            Exception: If detection fails
        """
        await self.connect()
        
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        data = aiohttp.FormData()
        with open(audio_path, 'rb') as f:
            data.add_field('audio_file', f, filename=audio_path.name,
                          content_type='audio/wav')
            
            try:
                async with self.session.post(
                    f"{self.base_url}/detect-language",
                    data=data,
                    params={'encode': 'true'}
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Language detection successful for {audio_path.name}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Language detection failed: {response.status} - {error_text}")
                        raise Exception(f"Language detection failed: {response.status} - {error_text}")
                        
            except aiohttp.ClientError as e:
                logger.error(f"HTTP error during language detection: {e}")
                raise Exception(f"Service communication error: {e}")

# Convenience functions for quick usage
async def transcribe_audio_file(
    file_path: Union[str, Path],
    whisper_url: str = "http://localhost:9000",
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to transcribe a single audio file
    
    Args:
        file_path: Path to audio file
        whisper_url: Whisper service URL
        **kwargs: Additional arguments for transcribe_file
        
    Returns:
        Transcription result
    """
    async with WhisperClient(whisper_url) as client:
        return await client.transcribe_file(file_path, **kwargs)

async def check_whisper_health(whisper_url: str = "http://localhost:9000") -> Dict[str, Any]:
    """
    Convenience function to check Whisper service health
    
    Args:
        whisper_url: Whisper service URL
        
    Returns:
        Health status
    """
    async with WhisperClient(whisper_url) as client:
        return await client.health_check()

# Example usage for testing
if __name__ == "__main__":
    async def test_client():
        """Test the Whisper client"""
        try:
            # Test health check
            health = await check_whisper_health()
            print(f"Whisper service health: {health}")
            
            # Test with a sample audio file if it exists
            test_file = Path("recorded_audio/test.wav")
            if test_file.exists():
                result = await transcribe_audio_file(test_file)
                print(f"Transcription: {result}")
            else:
                print("No test audio file found, skipping transcription test")
                
        except Exception as e:
            print(f"Test failed: {e}")
    
    # Run test
    asyncio.run(test_client())