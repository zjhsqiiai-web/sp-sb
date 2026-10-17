FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

WORKDIR /app

# Install xvfb for virtual display (needed for headless=False)
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Use xvfb-run to provide a virtual display
CMD ["xvfb-run", "-a", "--server-args=-screen 0 1280x900x24", "python", "bot.py"]
