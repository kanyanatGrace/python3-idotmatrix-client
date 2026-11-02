# Virtual 32x32 Emotion Face

## Requirements
- Windows
- Python environment created by the project setup script

## Run the virtual display

```powershell
.\venv_windows\Scripts\python.exe .\virtual_face.py

## Send an emotion to the display

The virtual display listens for local UDP messages on
127.0.0.1, port 5005.

Supported emotion labels:
- neutral
- joy
- sadness
- anger
- fear
- surprise
- disgust

Each message contains one lowercase emotion label.

The virtual face displays the matching expression and
plays a short transition.