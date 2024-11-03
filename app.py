from flask import Flask, request, jsonify, Response
from pytubefix import YouTube
from pytubefix.cli import on_progress
from pydub import AudioSegment
import io
import os
import json

app = Flask(__name__)

# Specify the path for the token file
TOKEN_FILE = 'tokens.json'

@app.route('/stream_audio', methods=['POST'])
def stream_audio():
    data = request.get_json()
    url = data.get("url")
    visitor_data = data.get("visitorData")
    po_token = data.get("po_token")

    if not url or not visitor_data or not po_token:
        return jsonify({"error": "URL, visitorData, and po_token must be provided"}), 400

    # Save visitorData and po_token to file
    with open(TOKEN_FILE, 'w') as f:
        json.dump({
            'visitorData': visitor_data,
            'po_token': po_token
        }, f)

    try:
        # Initialize YouTube object with token file path
        yt = YouTube(url, token_file=TOKEN_FILE, use_po_token=True, on_progress_callback=on_progress)

        # Get the audio stream
        audio_stream = yt.streams.get_audio_only()

        # Download audio directly to a BytesIO object
        audio_data = io.BytesIO()
        audio_stream.download(output_path=None, filename=None, stream=audio_data)

        # Convert audio to MP3 format in-memory
        audio_data.seek(0)  # Rewind the BytesIO object
        audio = AudioSegment.from_file(audio_data)
        
        mp3_io = io.BytesIO()
        audio.export(mp3_io, format="mp3")
        mp3_io.seek(0)  # Rewind the file-like object

        # Stream the MP3 audio back to the client
        return Response(mp3_io, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

