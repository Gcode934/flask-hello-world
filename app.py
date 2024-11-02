# app.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess
from youtube_transcript_api import YouTubeTranscriptApi
import json
import os
from pathlib import Path
import uuid

app = Flask(__name__)
CORS(app)

# Create directory for storing audio files
AUDIO_DIR = Path("audio_files")
AUDIO_DIR.mkdir(exist_ok=True)

def download_audio(url, output_filename):
    """
    Download audio from YouTube video using yt-dlp
    """
    try:
        # Download audio using yt-dlp
        process = subprocess.run([
            'yt-dlp',
            '-f', 'bestaudio/best',     # Download best audio format
            '--extract-audio',           # Extract audio only
            '--audio-format', 'mp3',     # Convert to mp3
            '--audio-quality', '0',      # Best quality
            '-o', output_filename,       # Output filename
            url
        ], capture_output=True, text=True)
        
        # Check if the process was successful
        if process.returncode != 0:
            raise Exception(f"yt-dlp error: {process.stderr}")
            
        return True
            
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return False

def get_transcript(video_url, language='en'):
    """
    Get transcription from YouTube video
    """
    try:
        # Extract video ID from URL
        if "youtu.be" in video_url:
            video_id = video_url.split("/")[-1]
        else:
            video_id = video_url.split("v=")[1].split("&")[0]
        
        # Get transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
        
        # Process transcript
        segments = []
        for item in transcript_list:
            # Split text into words
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
        print(f"Error getting transcript: {str(e)}")
        return None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

@app.route('/process-video', methods=['POST'])
def process_video():
    """Process YouTube video: download audio and get transcript"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
            
        video_url = data['url']
        language = data.get('language', 'en')  # Default to English if not specified
        
        # Generate unique ID for this request
        job_id = str(uuid.uuid4())
        output_filename = AUDIO_DIR / f"{job_id}.mp3"
        
        # Download audio
        audio_success = download_audio(video_url, str(output_filename))
        if not audio_success:
            return jsonify({'error': 'Failed to download audio'}), 500
            
        # Get transcript
        transcript = get_transcript(video_url, language)
        if transcript is None:
            return jsonify({'error': 'Failed to get transcript'}), 500
            
        return jsonify({
            'job_id': job_id,
            'message': 'Processing completed successfully',
            'audio_url': f'/audio/{job_id}',
            'transcript': transcript
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/audio/<job_id>', methods=['GET'])
def get_audio(job_id):
    """Serve audio file"""
    try:
        # Validate job_id format
        if not job_id or not job_id.replace('-', '').isalnum():
            return jsonify({'error': 'Invalid job ID'}), 400
            
        audio_path = AUDIO_DIR / f"{job_id}.mp3"
        
        if not audio_path.exists():
            return jsonify({'error': 'Audio file not found'}), 404
            
        return send_file(str(audio_path), mimetype='audio/mpeg')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Optional: Cleanup endpoint to remove old files
@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Remove old audio files"""
    try:
        # Remove files older than 24 hours
        cleanup_age = 24 * 3600  # 24 hours in seconds
        current_time = time.time()
        deleted_count = 0
        
        for file in AUDIO_DIR.glob('*.mp3'):
            if current_time - file.stat().st_mtime > cleanup_age:
                file.unlink()
                deleted_count += 1
                
        return jsonify({
            'message': f'Cleanup completed. Removed {deleted_count} files.',
            'files_removed': deleted_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

