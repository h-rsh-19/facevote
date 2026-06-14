# FaceVote

Facial-recognition based online voting system built with Flask, OpenCV, face_recognition, and SQLite.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

Note: webcam access and a working `face_recognition`/`dlib` installation are required for the full voting flow.

