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
TOKEN_FILE = os.path.abspath('tokens.json')

@app.route('/stream_audio', methods=['POST'])
def stream_audio():
    logger.info("Received streaming request")
    
    data = request.get_json()
    url = data.get("url")
    visitor_data = data.get("visitorData")
    po_token = data.get("po_token")

    logger.debug(f"Received URL: {url}")
    logger.debug(f"Received visitorData: {visitor_data}")
    logger.debug(f"Received po_token length: {len(po_token) if po_token else 0}")

    if not url or not visitor_data or not po_token:
        logger.error("Missing required parameters")
        return jsonify({"error": "URL, visitorData, and po_token must be provided"}), 400

    try:
        # Save tokens to file with the exact structure expected by InnerTube
        token_data = {
            "access_token": None,
            "refresh_token": None,
            "expires": None,
            "visitorData": visitor_data,
            "po_token": po_token
        }
        
        logger.debug(f"Writing token file to: {TOKEN_FILE}")
        logger.debug(f"Token data: {json.dumps(token_data, indent=2)}")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)

        # Initialize YouTube with correct parameters
        logger.info("Initializing YouTube object")
        yt = YouTube(
            url,
            token_file=TOKEN_FILE,
            use_oauth=False,
            use_po_token=True,
            allow_cache=True,
            client='WEB'  # Use WEB client instead of default ANDROID
        )
        
        logger.info("Fetching video info...")
        title = yt.title
        logger.info(f"Video title: {title}")

        # Get the audio stream
        logger.info("Getting audio stream...")
        audio_stream = yt.streams.get_audio_only()
        if not audio_stream:
            raise Exception("No audio stream found")
            
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

