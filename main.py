import os
import time
import random
import requests
import concurrent.futures
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import statistics
from PIL import Image

# Configuration
API_ENDPOINT = "http://server950.freeconvert.com:8501/upload/"
#API_ENDPOINT = "http://localhost:8501/upload/"
INPUT_DIR = "test_images"
OUTPUT_DIR = "output"
SUMMARY_DIR = "summary"
FOLDERS = ["w512", "w1080", "w1920", "w2560", "w3840"]
MAX_CONCURRENT = 10

# Create output and summary directories if they don't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

# Create output subdirectories for each resolution
for folder in FOLDERS:
    os.makedirs(os.path.join(OUTPUT_DIR, folder), exist_ok=True)


def get_image_resolution(image_path):
    """Get image width and height"""
    with Image.open(image_path) as img:
        return img.size  # Returns (width, height)


def process_image(image_path):
    """Process a single image through the API and save the result"""
    # Get relative path for output directory structure
    rel_path = os.path.relpath(os.path.dirname(image_path), INPUT_DIR)
    image_filename = os.path.basename(image_path)

    # Create output path maintaining folder structure
    output_filename = os.path.splitext(image_filename)[0] + ".png"
    output_folder = os.path.join(OUTPUT_DIR, rel_path)
    output_path = os.path.join(output_folder, output_filename)

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Get file size in MB
    file_size = os.path.getsize(image_path) / (1024 * 1024)

    # Get image resolution
    try:
        width, height = get_image_resolution(image_path)
        resolution = f"{width}x{height}"
    except Exception as e:
        resolution = "Unknown"

    print(f"\n➡️ Processing {image_path} - Size: {file_size:.2f}MB - Resolution: {resolution}")

    with open(image_path, 'rb') as f:
        files = {'file': (image_filename, f, 'image/jpeg')}
        try:
            start_time = time.time()
            response = requests.post(API_ENDPOINT, files=files)
            response.raise_for_status()
            processing_time = time.time() - start_time

            # Save the processed image
            with open(output_path, 'wb') as output_file:
                output_file.write(response.content)

            print(f"✅ Completed in {processing_time:.2f}s: {os.path.basename(image_path)}")

            return {
                'folder': os.path.basename(os.path.dirname(image_path)),
                'filename': image_filename,
                'status': 'success',
                'processing_time': processing_time,
                'file_size': file_size,
                'resolution': resolution,
                'width': width,
                'height': height
            }
        except requests.exceptions.RequestException as e:
            processing_time = time.time() - start_time
            print(f"❌ Error processing {image_filename}: {str(e)}")
            return {
                'folder': os.path.basename(os.path.dirname(image_path)),
                'filename': image_filename,
                'status': 'error',
                'error': str(e),
                'processing_time': processing_time,
                'file_size': file_size,
                'resolution': resolution,
                'width': width if 'width' in locals() else 0,
                'height': height if 'height' in locals() else 0
            }


def run_sequential_test():
    """Test sequential processing for each folder"""
    print("\n" + "=" * 80)
    print("Running Sequential Test - Processing each image one by one for every folder")
    print("=" * 80)

    results = []

    for folder in FOLDERS:
        folder_path = os.path.join(INPUT_DIR, folder)
        if not os.path.exists(folder_path):
            print(f"Warning: Folder {folder_path} not found, skipping...")
            continue

        print(f"\n🔹 Processing folder: {folder}")
        images = [f"img{i}.jpg" for i in range(10)]

        for image in tqdm(images, desc=folder):
            image_path = os.path.join(folder_path, image)
            if os.path.exists(image_path):
                result = process_image(image_path)
                results.append(result)
            else:
                print(f"Warning: Image {image_path} not found, skipping...")

    return results


def run_concurrent_test():
    """Run concurrent tests with incrementing number of workers for each folder"""
    print("\n" + "=" * 80)
    print("Running Concurrent Tests - Processing with incrementing concurrency")
    print("=" * 80)

    all_results = []

    for folder in FOLDERS:
        folder_path = os.path.join(INPUT_DIR, folder)
        if not os.path.exists(folder_path):
            print(f"Warning: Folder {folder_path} not found, skipping...")
            continue

        # Get list of images in the folder
        images = [os.path.join(folder_path, f"img{i}.jpg") for i in range(10)]
        images = [img for img in images if os.path.exists(img)]

        if not images:
            print(f"No images found in {folder_path}, skipping...")
            continue

        # Run with incrementing concurrency levels starting from 2
        for workers in range(2, MAX_CONCURRENT + 1):
            print(f"\n🔹 Processing folder {folder} with {workers} concurrent workers")
            results = []

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_image = {executor.submit(process_image, image): image for image in images}
                for future in tqdm(concurrent.futures.as_completed(future_to_image), total=len(images),
                                   desc=f"{folder}-{workers}w"):
                    try:
                        result = future.result()
                        result['concurrency'] = workers  # Add concurrency level to results
                        results.append(result)
                    except Exception as e:
                        print(f"Executor error: {str(e)}")

            # Save results for this concurrency level
            df = pd.DataFrame(results)
            df.to_csv(os.path.join(SUMMARY_DIR, f"concurrent_{folder}_w{workers}.csv"), index=False)
            all_results.extend(results)

            # Pause briefly between tests to allow system to stabilize
            time.sleep(1)

    return all_results


def run_random_test():
    """Randomly pick 5 files from any folder and process them"""
    print("\n" + "=" * 80)
    print("Running Random Test - Processing 5 random images from any folder")
    print("=" * 80)

    all_image_paths = []

    # Collect all available image paths
    for folder in FOLDERS:
        folder_path = os.path.join(INPUT_DIR, folder)
        if os.path.exists(folder_path):
            for i in range(10):
                img_path = os.path.join(folder_path, f"img{i}.jpg")
                if os.path.exists(img_path):
                    all_image_paths.append(img_path)

    # Select 5 random images (or fewer if less than 5 are available)
    sample_size = min(5, len(all_image_paths))
    selected_images = random.sample(all_image_paths, sample_size)

    print(f"Selected {sample_size} random images for processing")

    results = []
    for image_path in tqdm(selected_images, desc="Random processing"):
        result = process_image(image_path)
        results.append(result)

    return results


def generate_summary(results):
    """Generate summary statistics from test results"""
    if not results:
        return None

    df = pd.DataFrame(results)

    # Skip summary if no successful results
    if not df[df['status'] == 'success'].empty:
        # Group by folder
        grouped = df.groupby('folder')

        summary = []
        # Overall stats
        overall = {
            'folder': 'All',
            'total_images': len(df),
            'successful': sum(df['status'] == 'success'),
            'failed': sum(df['status'] == 'error'),
            'avg_time': df[df['status'] == 'success']['processing_time'].mean(),
            'min_time': df[df['status'] == 'success']['processing_time'].min(),
            'max_time': df[df['status'] == 'success']['processing_time'].max(),
            'median_time': df[df['status'] == 'success']['processing_time'].median(),
            'avg_size_mb': df['file_size'].mean()
        }
        summary.append(overall)

        # Stats for each folder
        for folder, group in grouped:
            folder_summary = {
                'folder': folder,
                'total_images': len(group),
                'successful': sum(group['status'] == 'success'),
                'failed': sum(group['status'] == 'error'),
                'avg_time': group[group['status'] == 'success']['processing_time'].mean(),
                'min_time': group[group['status'] == 'success']['processing_time'].min(),
                'max_time': group[group['status'] == 'success']['processing_time'].max(),
                'median_time': group[group['status'] == 'success']['processing_time'].median(),
                'avg_size_mb': group['file_size'].mean()
            }
            summary.append(folder_summary)

        return pd.DataFrame(summary)

    return pd.DataFrame()


def main():
    start_time = time.time()
    all_results = []

    # Verify the input directory exists
    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' not found.")
        return

    # Check for existence of resolution folders
    missing_folders = []
    for folder in FOLDERS:
        folder_path = os.path.join(INPUT_DIR, folder)
        if not os.path.exists(folder_path):
            missing_folders.append(folder)

    if missing_folders:
        print(f"Warning: The following folders were not found: {', '.join(missing_folders)}")

    # 1. Sequential processing
    sequential_results = run_sequential_test()
    all_results.extend(sequential_results)

    # Save sequential results
    sequential_df = pd.DataFrame(sequential_results)
    sequential_df.to_csv(os.path.join(SUMMARY_DIR, "sequential_results.csv"), index=False)

    # 2. Concurrent processing
    concurrent_results = run_concurrent_test()
    all_results.extend(concurrent_results)

    # 3. Random processing
    random_results = run_random_test()
    all_results.extend(random_results)

    # Save random results
    random_df = pd.DataFrame(random_results)
    random_df.to_csv(os.path.join(SUMMARY_DIR, "random_results.csv"), index=False)

    # Generate and save overall results
    all_df = pd.DataFrame(all_results)
    all_df.to_csv(os.path.join(SUMMARY_DIR, "all_results.csv"), index=False)

    # Generate summary
    summary_df = generate_summary(all_results)
    if summary_df is not None and not summary_df.empty:
        summary_df.to_csv(os.path.join(SUMMARY_DIR, "summary.csv"), index=False)

        # Display summary
        print("\n" + "=" * 80)
        print("BACKGROUND REMOVAL API LOAD TESTING SUMMARY")
        print("=" * 80)

        for _, row in summary_df.iterrows():
            folder = row['folder']
            print(f"\n🔹 {folder} STATISTICS:")
            print(f"Total Images: {row['total_images']}")
            print(f"Successful: {row['successful']} ({row['successful'] / row['total_images'] * 100:.2f}%)")
            print(f"Failed: {row['failed']}")
            if not pd.isna(row['avg_time']):
                print(f"Average Time: {row['avg_time']:.2f}s")
                print(f"Min/Max Time: {row['min_time']:.2f}s / {row['max_time']:.2f}s")
                print(f"Median Time: {row['median_time']:.2f}s")
            print(f"Average File Size: {row['avg_size_mb']:.2f} MB")

    total_duration = time.time() - start_time
    print(f"\nTotal Testing Duration: {total_duration:.2f} seconds ({total_duration / 60:.2f} minutes)")

    print("\n" + "=" * 80)
    print("Test completed. All results and summary saved to CSV files.")
    print("=" * 80)


if __name__ == "__main__":
    main()