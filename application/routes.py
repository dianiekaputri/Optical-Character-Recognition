from application import app
from flask import redirect, render_template, url_for, request, session
from application.forms import MyForm
from application import utils
from gtts import gTTS
import secrets
import os
import io
import ffmpeg
import subprocess as sp

# OCR
import cv2
import pytesseract
from PIL import Image
import numpy as np


# Function to compress image using PIL library
def compress_image(file_location):
    # Open the image
    img = Image.open(file_location)

    # Compress the image
    img = img.convert("RGB")
    img_io = io.BytesIO()
    img.save(img_io, "JPEG", quality=50)

    # Save the compressed image to a new file
    compressed_file_location = file_location.split(".")[0] + "_compressed.jpeg"
    with open(compressed_file_location, "wb") as f:
        f.write(img_io.getvalue())

    # Return the location of the compressed image
    return compressed_file_location


@app.route("/")
def index():
    return render_template("index.html", title="Home Page")


@app.route("/upload", methods=["POST", "GET"])
def upload():
    if request.method == "POST":

        # set a session value
        sentence = ""

        f = request.files.get("file")
        # something.jpg >> ["something", "jpg"]
        filename = f.filename.split(".")
        filename = filename[0]
        extension = filename [-1]
        generated_filename = secrets.token_hex(20) + f".{extension}"

        file_location = os.path.join(app.config["UPLOADED_PATH"], generated_filename)

        f.save(file_location)

        # Compress the image before OCR
        compressed_file_location = compress_image(file_location)

        # OCR here
        pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

        img = cv2.imread(compressed_file_location)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        boxes = pytesseract.image_to_data(img)

        for i, box in enumerate(boxes.splitlines()):
            if i == 0:
                continue

            box = box.split()

            # only deal with boxes with word in it.
            if len(box) == 12:
                sentence += box[11] + " "

        session["sentence"] = sentence

        # Remove the files after you are done working with them
        # os.remove(file_location)
        # os.remove(compressed_file_location)

        return redirect("/decoded/")

    else:
        return render_template("upload.html", title="Upload")


@app.route("/decoded", methods=["POST", "GET"])
def decoded():

    sentence = session.get("sentence")

    form = MyForm()

    if request.method == "POST":

        generated_audio_filename = secrets.token_hex(10) + ".wav"

        text_data = form.text_field.data
        translate_to = form.language_field.data

        translated_text = utils.translate_text(text_data, translate_to)
        form.text_field.data = translated_text

        tts = gTTS(translated_text, lang=translate_to)

        file_location = os.path.join(app.config["AUDIO_FILE_UPLOAD"], generated_audio_filename)

        tts.save(file_location)

        # Compress the audio before rendering
        # compressed_file_location = compress_audio(file_location)

        # Compress the audio using AAC compression
        compressed_audio_filename = generated_audio_filename.split(".")[0] + "_compressed.m4a"
        compressed_file_location = os.path.join(app.config["AUDIO_FILE_UPLOAD"], compressed_audio_filename)

        # Run FFmpeg command for compression
        command = 'ffmpeg -i {} -c:a aac -b:a 24k {}'.format(file_location, compressed_file_location)
        sp.run(command, shell=True)
        
        # Generate slow audio
        slow_audio_filename = compressed_audio_filename.split(".")[0] + "_slow.m4a"
        slow_file_location = os.path.join(app.config["AUDIO_FILE_UPLOAD"], slow_audio_filename)
        slow_command = 'ffmpeg -i {} -filter:a "atempo=0.7" {}'.format(compressed_file_location, slow_file_location)
        sp.run(slow_command, shell=True)
        
        # Apply equalizer to the slow audio
        equalized_audio_filename = slow_audio_filename.split(".")[0] + "_equalized.m4a"
        equalized_file_location = os.path.join(app.config["AUDIO_FILE_UPLOAD"], equalized_audio_filename)

        # Run FFmpeg command for equalization
        equalizer_command = 'ffmpeg -i {} -af "equalizer=f=1200:width_type=o:width=50:g=4" {}'.format(slow_file_location, equalized_file_location)
        sp.run(equalizer_command, shell=True)
        
        # Apply pitch shift to the audio
        pitch_shifted_audio_filename = equalized_audio_filename.split(".")[0] + "_pitch_shifted.m4a"
        pitch_shifted_file_location = os.path.join(app.config["AUDIO_FILE_UPLOAD"], pitch_shifted_audio_filename)

        # Run FFmpeg command for pitch shift
        pitch_shift_command = 'ffmpeg -i {} -af "rubberband=pitch=2" {}'.format(equalized_file_location, pitch_shifted_file_location)
        sp.run(pitch_shift_command, shell=True)


            
        return render_template(
            "decoded.html",
            title="Translations",
            form=form,
            audio=True,
            file=compressed_audio_filename,
            slow_file=slow_audio_filename,
            equalized_file=pitch_shifted_audio_filename
        )

    else:
        form.text_field.data = sentence
        session["sentence"] = ""
        return render_template("decoded.html", form=form, audio=False)
