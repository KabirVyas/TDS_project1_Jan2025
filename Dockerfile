# Use a lightweight Python image
FROM python:3.12-slim-bookworm

# Set the working directory
WORKDIR /app

# Install curl & SSL certificates (needed for `uv`)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install `uv`
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure `uv` is available in the system PATH
ENV PATH="/root/.local/bin/:$PATH"

# Copy project files into the container
COPY . /app

# ✅ Install dependencies using `pip`
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for FastAPI/Flask
EXPOSE 8000

# Run the application using `uv`
CMD ["uv", "run", "app.py"]
