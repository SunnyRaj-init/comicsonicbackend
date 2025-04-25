#the prompt
prompt="""You are given a document in which each page is made up of one image \n 
these images consist of characters/speakers and their dialogues encapsulated in bubbles or boxes \n 
Dialogue Flow is from Top to Bottom and left to right i.e. dialogues flow row wise left to right \n 
\n the dialogue in a bubble belongs to a speaker its closest to or above or below
\n let say in an image there is a male and female character if the buble is above or below the female character then the dialogue is said by the female character else its said by the male character
\n speakers can be male or female use your vision to classify teh gender of the speaker
you have provide me the output in this form:\nen-US-Standard-D:That creature is called a &quot;dog&quot;.\nen-US-Standard-F:Hmmm,I didn&apos;t know they were so loyal\n and so on \n 
you have to maintain the conversation flow between the speakers/characters \n 
\n NOTE use "en-US-Standard-D" when the dialogue is said by a male character/speaker and use "en-US-Standard-F" when the dialogue is said by  female character/speaker
\n carefully evaluate the gender fo the speaker do not make rushed decisions; if the character in the image who speaks the dialogue is a female use en-US-Standard-F and if its male use en-US-Standard-D
\n ONLY ASSIGN A GENDER TO THE DIALOGUE WHEN YOU ARE ABSOLUTELY SURE; DO NOT IDENTIFY THE CHARACTERS DIALOGUE WITH A WRONG GENDER THIS IS A CRUCIAL STEP!
Replace special characters in input text: &, ", ', <, > with HTML Ampersand Character Codes For example, '<' --> '&lt;' and '&' --> '&amp;'
\n DO NOT  forget to replace the special characters in the text to their HTML Ampersand Character Codes; only use HTML Apmersand Codes dont use Unicodes
\n Do not forget spaces between words and parse the whole word do not provide incomplete words\n
Carefully analyze the whole image and extract all the text present in it parse it into sequential dialogues preceeded by "en-US-Standard-D" when speaker is male and "en-US-Standard-F" when speaker is female
and then move on to next image DO NOT MISS OUT ANY DIALOGUES AND MAINTAIN THE CONVERSATION SEQUENCE \n 
Do not get confused between the characters and their dialogues proceed to the next image only when you are absolutely sure; 
only parse the next image if the you are done parsing the previous image\n
IGNORE ANY SYMBOLS OR CHARACTERS FROM ANOTHER LANGUAGE\noutput should look like:\nen-US-Standard-D:That creature is called a &quot;dog&quot;.\nen-US-Standard-F:Hmmm,I didn&apos;t know they were so loyal\n and so on \n; 
only provide the required output; do not specify the page numbers and present the output in lower-cased
\n DO NOT USE SHORT HAND NOTATIONS FOR en-US-Standard-D or en-US-Standard-F; you have to represent them fully as mentioned dont use en-US-F or en-US-D
"""
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import base64
import google.generativeai as genai
from google.cloud import texttospeech
from pydub import AudioSegment
import os
import time

load_dotenv("./.env.local")

# TEXT TO SPEECH INITIALIZATION BLOCK
client = texttospeech.TextToSpeechClient()
AudioSegment.converter = "/usr/bin/ffmpeg"
AudioSegment.ffmpeg = "/usr/bin/ffmpeg"
AudioSegment.ffprobe = "/usr/bin/ffprobe"
audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
audio_files = []

# HITTING GEMINI
genai.configure(api_key=os.getenv("API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# SETTING UP FLASK
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://comicsonicfrontend.vercel.app/"}})

@app.after_request
def add_cors_headers(response):
    """Add necessary CORS headers to every response."""
    response.headers.add("Access-Control-Allow-Origin", "https://comicsonicfrontend.vercel.app/")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    # Handle OPTIONS preflight requests
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "https://comicsonicfrontend.vercel.app/")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response, 204

    # Handle POST requests for file upload
    if 'file' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No file selected'}), 400
    
    # Save the file to a specific location
    file_path = 'uploads/' + file.filename
    file.save(file_path)
    doc_path = file_path

    # Read and encode the local file
    with open(doc_path, "rb") as doc_file:
        doc_data = base64.standard_b64encode(doc_file.read()).decode("utf-8")
    
    # Generating transcriptions
    response = model.generate_content([{'mime_type': 'application/pdf', 'data': doc_data}, prompt])
    out = response.text.replace("xml", "")
    out = out.replace("en-US-F", "en-US-Standard-F")
    out = out.replace("en-US-D", "en-US-Standard-D")
    out_parsed = out.replace("\"", "\\\"")

    # Generating segmented speech files
    i = 0
    for line in out_parsed.split("\n"):
        if i % 5 == 0:
            time.sleep(15)
        if len(line) > 0:
            synthesis_input = texttospeech.SynthesisInput(text=line[17:])

            if line[0:17] == "en-US-Standard-F:":
                voice_name = "en-US-Standard-F"
            else:
                voice_name = "en-US-Standard-D"

            print(voice_name, line)

            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=voice_name,
            )

            # Generate audio using the Text-to-Speech API
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            # Save the generated audio to an MP3 file
            filename = f"part-{str(i)}.mp3"
            audio_files.append(filename)
            with open(filename, "wb") as out:
                out.write(response.audio_content)
                print(f"Audio content written to file {filename}")
            i += 1

    # Creating the combined audio file
    full_audio = AudioSegment.silent(duration=1000)
    for file in audio_files:  # Use 'set()' to ensure files are unique
        if os.path.exists(file):  # Check if the file exists before processing
            sound = AudioSegment.from_mp3(file)
            silence = AudioSegment.silent(duration=1000)
            full_audio += sound + silence
            os.remove(file)  # Delete the file after processing
            print(f"File {file} removed")
        else:
            print(f"File {file} does not exist, skipping...")

    
    podcast_filename = "audiofile.mp3"
    full_audio.export(podcast_filename)
    print(f"Podcast content written to file {podcast_filename}")

    # # Deleting the uploaded file
    # try:
    #     os.remove(file_path)
    #     print(f"Uploaded file {file.filename} deleted successfully.")
    # except Exception as e:
    #     print(f"Error deleting file {file.filename}: {e}")

    return send_file(podcast_filename, mimetype='audio/mpeg', as_attachment=True), 200

if __name__ == '__main__':
    app.run(debug=True)
