# app.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import re
import os
import tempfile
import uuid
import logging
from pydub import AudioSegment
from pathlib import Path
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create temporary directories for storing files
TEMP_DIR = Path(tempfile.gettempdir()) / "language_learning_app"
AUDIO_DIR = TEMP_DIR / "audio"

# Create directories if they don't exist
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

class ProcessingError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code

def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ProcessingError("Invalid YouTube URL", 400)

def extract_audio_from_youtube(url, output_path):
    """Extract audio from YouTube video"""
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        if not audio_stream:
            raise ProcessingError("No audio stream available", 400)
        
        # Download audio
        downloaded_file = audio_stream.download(output_path=str(TEMP_DIR))
        temp_path = Path(downloaded_file)
        
        # Convert to mp3
        audio = AudioSegment.from_file(temp_path)
        audio.export(output_path, format="mp3")
        
        # Clean up temporary file
        temp_path.unlink(missing_ok=True)
        
        return True
    except Exception as e:
        logger.error(f"Error extracting audio: {str(e)}")
        raise ProcessingError(f"Failed to extract audio: {str(e)}", 500)

def get_youtube_transcription(video_id):
    """Get transcription from YouTube"""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=['en']  # You can modify this to support other languages
        )
        
        # Process transcript into segments
        segments = []
        for item in transcript_list:
            # Split text into words and calculate approximate word timings
            words = item['text'].split()
            duration = item['duration']
            start = item['start']
            
            # Calculate approximate time per word
            word_duration = duration / len(words) if words else 0
            
            # Create word-level timing data
            word_data = []
            current_time = start
            
            for word in words:
                word_info = {
                    'word': word,
                    'start': round(current_time, 2),
                    'end': round(current_time + word_duration, 2)
                }
                word_data.append(word_info)
                current_time += word_duration
            
            segment = {
                'start': round(start, 2),
                'end': round(start + duration, 2),
                'text': item['text'],
                'words': word_data
            }
            segments.append(segment)
        
        return segments
    except Exception as e:
        logger.error(f"Error getting transcription: {str(e)}")
        raise ProcessingError(f"Failed to get transcription: {str(e)}", 500)

# Error handlers
@app.errorhandler(ProcessingError)
def handle_processing_error(error):
    response = jsonify({'error': str(error)})
    response.status_code = error.status_code
    return response

@app.errorhandler(HTTPException)
def handle_http_error(error):
    response = jsonify({'error': error.description})
    response.status_code = error.code
    return response

@app.errorhandler(Exception)
def handle_generic_error(error):
    logger.error(f"Unexpected error: {str(error)}")
    response = jsonify({'error': 'Internal server error'})
    response.status_code = 500
    return response

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/process-video', methods=['POST'])
def process_video():
    try:
        data = request.get_json()
        if not data:
            raise ProcessingError("No JSON data provided", 400)
        
        video_url = data.get('url')
        if not video_url:
            raise ProcessingError("No URL provided", 400)
        
        # Extract video ID
        video_id = extract_video_id(video_url)
        
        # Generate unique ID for this processing job
        job_id = str(uuid.uuid4())
        
        # Create path for audio file
        audio_path = AUDIO_DIR / f"{job_id}.mp3"
        
        # Get transcription from YouTube
        segments = get_youtube_transcription(video_id)
        
        # Extract audio from YouTube
        extract_audio_from_youtube(video_url, str(audio_path))
        
        return jsonify({
            'job_id': job_id,
            'message': 'Processing completed',
            'audio_url': f'/audio/{job_id}',
            'transcription': segments
        })
        
    except ProcessingError as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_video: {str(e)}")
        raise ProcessingError("Internal server error", 500)

@app.route('/audio/<job_id>', methods=['GET'])
def get_audio(job_id):
    try:
        if not re.match(r'^[0-9a-f-]+$', job_id):
            raise ProcessingError("Invalid job ID format", 400)
            
        audio_path = AUDIO_DIR / f"{job_id}.mp3"
        if not audio_path.exists():
            raise ProcessingError("Audio file not found", 404)
            
        return send_file(str(audio_path), mimetype='audio/mpeg')
    except ProcessingError as e:
        raise
    except Exception as e:
        logger.error(f"Error serving audio: {str(e)}")
        raise ProcessingError("Internal server error", 500)

# if __name__ == '__main__':
#     app.run(debug=True)