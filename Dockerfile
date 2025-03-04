FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the test script
COPY load_test.py .

# Create directories for images and results
RUN mkdir -p test_images output

# Set the entrypoint to run the tests
ENTRYPOINT ["python", "main.py"]