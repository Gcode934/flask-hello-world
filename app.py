from flask import Flask, request, jsonify, Response
from pytubefix import YouTube
from pytubefix.cli import on_progress
from pydub import AudioSegment
import io
import os
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Specify the path for the token file
TOKEN_FILE = 'tokens.json'

def create_innertube_context(visitor_data, po_token):
    return {
        "context": {
            "client": {
                "visitorData": visitor_data,
                "clientName": "WEB",
                "clientVersion": "2.20240103.01.00"
            }
        },
        "po_token": po_token
    }

@app.route('/stream_audio', methods=['POST'])
def stream_audio():
    logger.info("Received streaming request")
    
    data = request.get_json()
    url = data.get("url")
    visitor_data = data.get("visitorData")
    po_token = data.get("po_token")

    logger.debug(f"Received URL: {url}")
    logger.debug(f"Received visitorData: {visitor_data}")
    logger.debug(f"Received po_token: {po_token[:20]}...") # Log only first 20 chars for security

    if not url or not visitor_data or not po_token:
        logger.error("Missing required parameters")
        return jsonify({"error": "URL, visitorData, and po_token must be provided"}), 400

    try:
        # Create innertube context
        innertube_context = create_innertube_context(visitor_data, po_token)
        
        # Save context to file
        with open(TOKEN_FILE, 'w') as f:
            json.dump(innertube_context, f, indent=2)
            logger.info(f"Token file created at: {os.path.abspath(TOKEN_FILE)}")
        
        # Verify file contents
        with open(TOKEN_FILE, 'r') as f:
            saved_data = json.load(f)
            logger.debug("Token file contents:")
            logger.debug(json.dumps(saved_data, indent=2))

        # Initialize YouTube object with proper configuration
        logger.info("Initializing YouTube object")
        yt = YouTube(
            url,
            token_file=TOKEN_FILE,
            use_oauth=False,
            use_po_token=True,
            allow_oauth_cache=False
        )
        
        logger.info(f"YouTube object initialized. Video title: {yt.title}")

        # Get the audio stream
        audio_stream = yt.streams.get_audio_only()
        logger.info(f"Selected audio stream: {str(audio_stream)}")

        # Download audio directly to a BytesIO object
        logger.info("Starting audio download")
        audio_data = io.BytesIO()
        audio_stream.download(output_path=None, filename=None, stream=audio_data)
        logger.info(f"Audio download complete. Size: {audio_data.tell()} bytes")

        # Convert audio to MP3 format in-memory
        logger.info("Converting audio to MP3")
        audio_data.seek(0)
        audio = AudioSegment.from_file(audio_data)
        
        mp3_io = io.BytesIO()
        audio.export(mp3_io, format="mp3")
        mp3_size = mp3_io.tell()
        mp3_io.seek(0)
        
        logger.info(f"MP3 conversion complete. Final size: {mp3_size} bytes")

        return Response(mp3_io, mimetype="audio/mpeg")

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
