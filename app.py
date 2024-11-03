from flask import Flask, request, jsonify, Response
from pytubefix import YouTube
from pytubefix.innertube import InnerTube
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

class CustomInnerTube(InnerTube):
    def __init__(self, visitor_data, po_token, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._visitor_data = visitor_data
        self._po_token = po_token
        
    def fetch_po_token(self):
        logger.debug("Using provided tokens instead of interactive input")
        self.access_visitorData = self._visitor_data
        self.access_po_token = self._po_token
        return self._visitor_data, self._po_token

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
        # Create custom innertube instance
        innertube = CustomInnerTube(
            visitor_data=visitor_data,
            po_token=po_token,
            client='WEB',
            use_oauth=False,
            allow_cache=False
        )

        # Initialize YouTube with custom innertube
        logger.info("Initializing YouTube object")
        yt = YouTube(url)
        yt.innertube_client = innertube
        
        logger.info("Fetching video details...")
        title = yt.title  # This will use our custom token handling
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
