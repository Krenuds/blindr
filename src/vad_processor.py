"""
Voice Activity Detection (VAD) Processor
Handles speech segment detection before sending to Whisper
"""

import logging
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
import time

logger = logging.getLogger(__name__)

class VADProcessor:
    """
    Voice Activity Detection processor for segmenting audio streams.
    Replaces time-based chunking with speech-aware segmentation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize VAD processor.
        
        Args:
            config: VAD configuration parameters
        """
        # Default VAD configuration
        self.config = {
            'energy_threshold': 50,          # Energy threshold for speech detection
            'min_speech_duration': 0.3,      # Minimum speech segment duration (seconds)
            'min_silence_duration': 0.5,     # Minimum silence to end segment (seconds)
            'max_segment_duration': 30.0,    # Maximum segment duration (seconds)
            'sample_rate': 48000,            # Audio sample rate
            'window_size': 0.02,             # Analysis window size (seconds)
            'hop_size': 0.01                 # Window hop size (seconds)
        }
        
        if config:
            self.config.update(config)
        
        # State for each user
        self.user_segments: Dict[int, List[bytes]] = {}
        self.user_speech_start: Dict[int, Optional[float]] = {}
        self.user_last_activity: Dict[int, float] = {}
        self.user_energy_history: Dict[int, List[float]] = {}
        
        logger.info(f"VADProcessor initialized with config: {self.config}")
    
    def calculate_energy(self, audio_data: bytes) -> float:
        """
        Calculate RMS energy of audio segment.
        
        Args:
            audio_data: Raw PCM audio data
            
        Returns:
            RMS energy value
        """
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array) == 0:
                return 0.0
            
            # Calculate RMS energy
            energy = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            return float(energy)
        
        except Exception as e:
            logger.debug(f"Energy calculation error: {e}")
            return 0.0
    
    def is_speech(self, audio_data: bytes, user_id: int) -> bool:
        """
        Determine if audio segment contains speech.
        
        Args:
            audio_data: Raw PCM audio data
            user_id: User identifier for state tracking
            
        Returns:
            True if speech is detected
        """
        energy = self.calculate_energy(audio_data)
        
        # Initialize user history if needed
        if user_id not in self.user_energy_history:
            self.user_energy_history[user_id] = []
        
        # Store energy history for adaptive thresholding
        self.user_energy_history[user_id].append(energy)
        if len(self.user_energy_history[user_id]) > 50:  # Keep last 50 samples
            self.user_energy_history[user_id].pop(0)
        
        # Simple threshold-based detection
        # TODO: Implement more sophisticated VAD (WebRTC VAD, deep learning models)
        threshold = self.config['energy_threshold']
        is_speech = energy > threshold
        
        if is_speech:
            logger.debug(f"Speech detected for user {user_id}: energy={energy:.2f} > {threshold}")
        
        return is_speech
    
    def process_audio_chunk(self, user_id: int, audio_data: bytes, timestamp: float) -> List[Tuple[bytes, float, float]]:
        """
        Process incoming audio chunk and return completed speech segments.
        
        Args:
            user_id: User identifier
            audio_data: Raw PCM audio data
            timestamp: Timestamp of audio chunk
            
        Returns:
            List of (segment_audio, start_time, end_time) tuples for completed segments
        """
        completed_segments = []
        current_time = time.time()
        
        # Initialize user state if needed
        if user_id not in self.user_segments:
            self.user_segments[user_id] = []
            self.user_speech_start[user_id] = None
            self.user_last_activity[user_id] = current_time
        
        # Check if this chunk contains speech
        has_speech = self.is_speech(audio_data, user_id)
        
        if has_speech:
            # Start new segment if not already started
            if self.user_speech_start[user_id] is None:
                self.user_speech_start[user_id] = timestamp
                logger.debug(f"Starting new speech segment for user {user_id}")
            
            # Add to current segment
            self.user_segments[user_id].append(audio_data)
            self.user_last_activity[user_id] = current_time
            
            # Check for maximum segment duration
            segment_start = self.user_speech_start[user_id]
            segment_duration = timestamp - segment_start
            
            if segment_duration >= self.config['max_segment_duration']:
                # Force segment completion
                segment_audio = b''.join(self.user_segments[user_id])
                completed_segments.append((segment_audio, segment_start, timestamp))
                
                # Reset state
                self.user_segments[user_id] = []
                self.user_speech_start[user_id] = None
                
                logger.info(f"Completed segment for user {user_id} (max duration): {segment_duration:.2f}s")
        
        else:
            # No speech in this chunk
            if self.user_speech_start[user_id] is not None:
                # We were in a speech segment, check if silence is long enough
                silence_duration = current_time - self.user_last_activity[user_id]
                
                if silence_duration >= self.config['min_silence_duration']:
                    # Complete the segment
                    segment_start = self.user_speech_start[user_id]
                    segment_duration = timestamp - segment_start
                    
                    if segment_duration >= self.config['min_speech_duration']:
                        segment_audio = b''.join(self.user_segments[user_id])
                        completed_segments.append((segment_audio, segment_start, timestamp))
                        
                        logger.info(f"Completed segment for user {user_id} (silence): {segment_duration:.2f}s")
                    else:
                        logger.debug(f"Discarding short segment for user {user_id}: {segment_duration:.2f}s")
                    
                    # Reset state
                    self.user_segments[user_id] = []
                    self.user_speech_start[user_id] = None
        
        return completed_segments
    
    def force_segment_completion(self, user_id: int, timestamp: float) -> Optional[Tuple[bytes, float, float]]:
        """
        Force completion of current segment for a user.
        
        Args:
            user_id: User identifier
            timestamp: Current timestamp
            
        Returns:
            Completed segment tuple or None if no active segment
        """
        if (user_id in self.user_segments and 
            len(self.user_segments[user_id]) > 0 and 
            self.user_speech_start[user_id] is not None):
            
            segment_start = self.user_speech_start[user_id]
            segment_duration = timestamp - segment_start
            
            if segment_duration >= self.config['min_speech_duration']:
                segment_audio = b''.join(self.user_segments[user_id])
                
                # Reset state
                self.user_segments[user_id] = []
                self.user_speech_start[user_id] = None
                
                logger.info(f"Force completed segment for user {user_id}: {segment_duration:.2f}s")
                return (segment_audio, segment_start, timestamp)
        
        return None
    
    def cleanup_user(self, user_id: int):
        """
        Clean up state for a user.
        
        Args:
            user_id: User identifier
        """
        if user_id in self.user_segments:
            del self.user_segments[user_id]
        if user_id in self.user_speech_start:
            del self.user_speech_start[user_id]
        if user_id in self.user_last_activity:
            del self.user_last_activity[user_id]
        if user_id in self.user_energy_history:
            del self.user_energy_history[user_id]
        
        logger.debug(f"Cleaned up VAD state for user {user_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current VAD processor status.
        
        Returns:
            Status dictionary
        """
        status = {
            'active_users': len(self.user_segments),
            'config': self.config,
            'users': {}
        }
        
        current_time = time.time()
        for user_id in self.user_segments:
            segment_count = len(self.user_segments[user_id])
            speech_start = self.user_speech_start[user_id]
            last_activity = self.user_last_activity.get(user_id, 0)
            
            status['users'][user_id] = {
                'active_segment': speech_start is not None,
                'segment_chunks': segment_count,
                'last_activity_ago': round(current_time - last_activity, 2) if last_activity else None,
                'current_segment_duration': round(current_time - speech_start, 2) if speech_start else None
            }
        
        return status