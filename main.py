import os
import time
import requests
import concurrent.futures
import csv
import random
from PIL import Image

# API endpoint for background removal
API_ENDPOINT = "http://localhost:8501/upload/"

def process_image(image_path, output_folder, test_type):
    """
    Process an image file by sending it to the API, then save the returned PNG.
    Logs file name, file size, resolution and processing time.
    Returns a tuple for CSV summary.
    """
    file_name = os.path.basename(image_path)
    # Get file size (in bytes)
    file_size = os.path.getsize(image_path)
    # Get image resolution (width, height)
    with Image.open(image_path) as img:
        width, height = img.size

    start_time = time.time()
    # Send the image file via POST request
    with open(image_path, 'rb') as f:
        files = {'file': (file_name, f, 'image/jpeg')}
        response = requests.post(API_ENDPOINT, files=files)
    processing_time = time.time() - start_time

    # Save the processed image to the output folder (convert file extension to png)
    output_path = os.path.join(output_folder, file_name.rsplit('.', 1)[0] + '.png')
    with open(output_path, 'wb') as f:
        f.write(response.content)

    # Log details to console
    print(f"[{test_type}] Processed {file_name}: Size {file_size} bytes, "
          f"Resolution {width}x{height}, Time {processing_time:.3f}s")

    # Return summary details with test type first (matching the CSV header)
    return (test_type, file_name, file_size, width, height, processing_time)

def sequential_test(input_root, output_root, csv_writer):
    """
    Process all images sequentially in each subfolder.
    """
    test_type = "sequential"
    for folder in os.listdir(input_root):
        folder_path = os.path.join(input_root, folder)
        if os.path.isdir(folder_path):
            # Create corresponding output subfolder
            out_folder = os.path.join(output_root, folder)
            os.makedirs(out_folder, exist_ok=True)
            # List all image files (jpg, jpeg, or png)
            image_files = sorted(f for f in os.listdir(folder_path)
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png')))
            for img in image_files:
                image_path = os.path.join(folder_path, img)
                result = process_image(image_path, out_folder, test_type)
                csv_writer.writerow(result)

def concurrent_test(input_root, output_root, csv_writer):
    """
    For each folder, process images concurrently in batches.
    The first batch processes 2 images concurrently and then increases the concurrency by 1 each batch,
    up to a maximum default value of 10.
    """
    test_type = "concurrent_increasing"
    for folder in os.listdir(input_root):
        folder_path = os.path.join(input_root, folder)
        if os.path.isdir(folder_path):
            out_folder = os.path.join(output_root, folder)
            os.makedirs(out_folder, exist_ok=True)
            image_files = sorted(f for f in os.listdir(folder_path)
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png')))
            image_paths = [os.path.join(folder_path, f) for f in image_files]

            concurrency = 2  # start with 2 concurrent images
            index = 0
            while index < len(image_paths):
                batch_size = min(concurrency, len(image_paths) - index)
                with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                    # Submit a batch of images concurrently
                    futures = {executor.submit(process_image, image_paths[i], out_folder, test_type): image_paths[i]
                               for i in range(index, index + batch_size)}
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        csv_writer.writerow(result)
                index += batch_size
                if concurrency < 10:
                    concurrency += 1  # increment concurrency count up to default max of 10

def random_test(input_root, output_root, csv_writer):
    """
    Randomly select 5 images from any folder and process them concurrently.
    """
    test_type = "random_selection"
    all_images = []
    for folder in os.listdir(input_root):
        folder_path = os.path.join(input_root, folder)
        if os.path.isdir(folder_path):
            image_files = sorted(f for f in os.listdir(folder_path)
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png')))
            for img in image_files:
                all_images.append((folder, os.path.join(folder_path, img)))
    # Randomly choose 5 images
    selected = random.sample(all_images, 5)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_img = {}
        for folder, image_path in selected:
            out_folder = os.path.join(output_root, folder)
            os.makedirs(out_folder, exist_ok=True)
            future = executor.submit(process_image, image_path, out_folder, test_type)
            future_to_img[future] = image_path
        for future in concurrent.futures.as_completed(future_to_img):
            result = future.result()
            csv_writer.writerow(result)

def main():
    input_root = "test_images"
    output_root = "output"
    summary_folder = "summary"

    # Create necessary directories if they do not exist
    os.makedirs(output_root, exist_ok=True)
    os.makedirs(summary_folder, exist_ok=True)

    summary_csv = os.path.join(summary_folder, "benchmark_summary.csv")
    with open(summary_csv, mode="w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        # Write CSV header: test_type, file_name, file_size_bytes, width, height, processing_time_seconds
        csv_writer.writerow(["test_type", "file_name", "file_size_bytes", "width", "height", "processing_time_seconds"])

        # Run sequential test on all folders
        sequential_test(input_root, output_root, csv_writer)
        # Run concurrent test on each folder with increasing concurrency
        concurrent_test(input_root, output_root, csv_writer)
        # Run random selection test (5 random images from any folder)
        random_test(input_root, output_root, csv_writer)

if __name__ == "__main__":
    main()
