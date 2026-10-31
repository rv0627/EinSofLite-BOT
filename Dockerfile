# Base image - Python 3.11
FROM python:3.11-slim

# working directory set 
WORKDIR /app

# Packages install ක
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copying project files to the container
COPY . .