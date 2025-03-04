from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
import shutil
import uuid
import os
import logging
from io import BytesIO
from model_classes import BackgroundRemover

# Initialize FastAPI app
app = FastAPI()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory setup
OUTPUT_DIR = "processed_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load background remover model
model = BackgroundRemover()

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), rotation: int = 0):
    """ Upload an image, process it, and return the background-removed result. """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in ("jpg", "jpeg", "png"):
            raise HTTPException(status_code=400, detail="Unsupported file format. Use JPG or PNG.")

        # Read file into memory and convert to PIL Image
        contents = await file.read()
        image = Image.open(BytesIO(contents))

        logger.info(f"Image received: {file.filename}, format: {image.format}")

        # Process image using model.process_images()
        output_filename = f"result_{uuid.uuid4()}.png"
        output_filepath = os.path.join(OUTPUT_DIR, output_filename)

        processed_images = model.process_images([image], [rotation])  # ✅ Pass a list of images and rotations

        # Save processed image
        processed_images[0].save(output_filepath)

        logger.info(f"Processed image saved: {output_filepath}")

        return FileResponse(output_filepath, media_type="image/png", filename=output_filename)

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
 
