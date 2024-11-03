from flask import Flask, request, jsonify, Response
from pytubefix import YouTube
from pytubefix.cli import on_progress
from pydub import AudioSegment
import io

app = Flask(__name__)

@app.route('/stream_audio', methods=['POST'])
def stream_audio():
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # Initialize YouTube object
        yt = YouTube(url, on_progress_callback=on_progress)

        # Get the audio stream and download it as raw data
        audio_stream = yt.streams.get_audio_only()
        audio_data = audio_stream.download(filename="temp_audio")

        # Convert audio to MP3 format in-memory
        audio = AudioSegment.from_file(audio_data)
        mp3_io = io.BytesIO()
        audio.export(mp3_io, format="mp3")
        mp3_io.seek(0)  # Rewind the file-like object

        # Stream the MP3 audio back to the client
        return Response(mp3_io, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

