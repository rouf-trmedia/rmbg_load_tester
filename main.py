import os
import time
import requests
import concurrent.futures
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import statistics

# Configuration
API_ENDPOINT = "http://server950.freeconvert.com:8501/upload/"
INPUT_DIR = "test_images"
OUTPUT_DIR = "output"
NORMAL_IMAGES = [f"img{i}.jpg" for i in range(50)]
LARGE_IMAGE = "large_image.jpg"

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)


def process_image(image_filename):
    """Process a single image through the API and save the result"""

    input_path = os.path.join(INPUT_DIR, image_filename)
    output_filename = os.path.splitext(image_filename)[0] + ".png"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print(f"\n➡️ Processing file ...{image_filename}")

    with open(input_path, 'rb') as f:
        files = {'file': (image_filename, f, 'image/jpeg')}
        try:
            start_time = time.time()
            response = requests.post(API_ENDPOINT, files=files)
            response.raise_for_status()
            processing_time = time.time() - start_time

            # Save the processed image
            with open(output_path, 'wb') as output_file:
                output_file.write(response.content)

            return {
                'filename': image_filename,
                'status': 'success',
                'processing_time': processing_time,
                'file_size': os.path.getsize(input_path) / (1024 * 1024)  # Size in MB
            }
        except requests.exceptions.RequestException as e:
            processing_time = time.time() - start_time
            return {
                'filename': image_filename,
                'status': 'error',
                'error': str(e),
                'processing_time': processing_time,
                'file_size': os.path.getsize(input_path) / (1024 * 1024)  # Size in MB
            }


def run_large_image_test():
    """Test processing of the large image"""
    print("\n➡️ Running large image processing test...")
    result = process_image(LARGE_IMAGE)
    return [result]


def run_large_image_batch_test(batch_size=5):
    """Test batch processing of the large image multiple times"""
    print(f"\n➡️ Running large image batch processing test ({batch_size} batch size)...")
    results = []
    for i in tqdm(range(batch_size)):
        result = process_image(LARGE_IMAGE)
        results.append(result)
    return results


def run_large_image_concurrent_test(workers=5):
    """Test concurrent processing of the large image"""
    print(f"\n➡️ Running large image concurrent processing test ({workers} workers)...")
    tasks = [LARGE_IMAGE] * workers
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_image = {executor.submit(process_image, image): image for image in tasks}
        for future in tqdm(concurrent.futures.as_completed(future_to_image), total=len(tasks)):
            result = future.result()
            results.append(result)

    return results


def run_normal_image_batch_test():
    """Test batch processing of all normal images sequentially"""
    print("\n➡️ Running normal image batch processing test...")
    results = []
    for image in tqdm(NORMAL_IMAGES):
        result = process_image(image)
        results.append(result)
    return results


def run_normal_image_concurrent_test(workers=10):
    """Test concurrent processing of normal images"""
    print(f"\n➡️ Running normal image concurrent processing test ({workers} workers)...")
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_image = {executor.submit(process_image, image): image for image in NORMAL_IMAGES}
        for future in tqdm(concurrent.futures.as_completed(future_to_image), total=len(NORMAL_IMAGES)):
            result = future.result()
            results.append(result)

    return results


def run_continuous_stress_test(total_requests=500):
    """Run continuous processing with normal images to reach at least 500 requests"""
    print(f"\n➡️ Running continuous stress test ({total_requests} requests)...")
    results = []

    # Calculate how many rounds needed to reach the target
    cycles_needed = total_requests // len(NORMAL_IMAGES) + 1

    for cycle in range(cycles_needed):
        print(f"Cycle {cycle + 1}/{cycles_needed}")
        for image in tqdm(NORMAL_IMAGES, leave=False):
            if len(results) >= total_requests:
                break
            result = process_image(image)
            results.append(result)

            # Add a small delay to prevent overwhelming the server
            time.sleep(0.1)

        if len(results) >= total_requests:
            break

    return results[:total_requests]


def generate_summary(all_results):
    """Generate summary statistics from all test results"""
    summary = {}

    # Overall stats
    all_times = [r['processing_time'] for r in all_results if r['status'] == 'success']
    success_count = len(all_times)
    error_count = len(all_results) - success_count

    summary['overall'] = {
        'total_requests': len(all_results),
        'successful_requests': success_count,
        'failed_requests': error_count,
        'success_rate': success_count / len(all_results) * 100,
        'avg_processing_time': statistics.mean(all_times) if all_times else 0,
        'min_processing_time': min(all_times) if all_times else 0,
        'max_processing_time': max(all_times) if all_times else 0,
        'median_processing_time': statistics.median(all_times) if all_times else 0
    }

    # Create a DataFrame for detailed analysis
    df = pd.DataFrame(all_results)

    # Group by test type
    test_groups = {
        'large_image_test': df[df['filename'] == LARGE_IMAGE],
        'normal_images_test': df[df['filename'] != LARGE_IMAGE]
    }

    for test_name, test_data in test_groups.items():
        if not test_data.empty:
            successful_tests = test_data[test_data['status'] == 'success']
            if not successful_tests.empty:
                summary[test_name] = {
                    'count': len(test_data),
                    'success_count': len(successful_tests),
                    'avg_time': successful_tests['processing_time'].mean(),
                    'min_time': successful_tests['processing_time'].min(),
                    'max_time': successful_tests['processing_time'].max(),
                    'median_time': successful_tests['processing_time'].median(),
                    'avg_size_mb': test_data['file_size'].mean()
                }

    return summary


def save_results_to_csv(results, filename):
    """Save test results to a CSV file"""
    df = pd.DataFrame(results)
    df.to_csv(filename, index=False)
    print(f"Results saved to {filename}")


def main():
    start_time = time.time()
    all_results = []

    # Check if input directory exists
    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' not found.")
        return

    # Verify that test images exist
    large_image_path = os.path.join(INPUT_DIR, LARGE_IMAGE)
    if not os.path.exists(large_image_path):
        print(f"Warning: Large image '{LARGE_IMAGE}' not found.")

    missing_normal = []
    for img in NORMAL_IMAGES:
        if not os.path.exists(os.path.join(INPUT_DIR, img)):
            missing_normal.append(img)

    if missing_normal:
        print(f"Warning: {len(missing_normal)} normal images not found.")
        print(f"First few missing: {missing_normal[:5]}")

    # Run tests and collect results
    print("Starting API load testing...")

    # Test 1: Large image processing
    results = run_large_image_test()
    all_results.extend(results)
    save_results_to_csv(results, "large_image_test_results.csv")

    # Test 2: Large image batch processing
    results = run_large_image_batch_test(batch_size=5)
    all_results.extend(results)
    save_results_to_csv(results, "large_image_batch_test_results.csv")

    # Test 3: Large image concurrent processing
    results = run_large_image_concurrent_test(workers=5)
    all_results.extend(results)
    save_results_to_csv(results, "large_image_concurrent_test_results.csv")

    # Test 4: Normal image batch processing
    results = run_normal_image_batch_test()
    all_results.extend(results)
    save_results_to_csv(results, "normal_image_batch_test_results.csv")

    # Test 5: Normal image concurrent processing
    results = run_normal_image_concurrent_test(workers=10)
    all_results.extend(results)
    save_results_to_csv(results, "normal_image_concurrent_test_results.csv")

    # Test 6: Continuous stress test
    results = run_continuous_stress_test(total_requests=500)
    all_results.extend(results)
    save_results_to_csv(results, "continuous_stress_test_results.csv")

    # Save all results
    save_results_to_csv(all_results, "all_test_results.csv")

    # Generate and display summary
    summary = generate_summary(all_results)

    print("\n" + "=" * 80)
    print("BACKGROUND REMOVAL API LOAD TESTING SUMMARY")
    print("=" * 80)

    print("\n🔹 OVERALL STATISTICS:")
    overall = summary['overall']
    print(f"Total Requests: {overall['total_requests']}")
    print(f"Successful Requests: {overall['successful_requests']} ({overall['success_rate']:.2f}%)")
    print(f"Failed Requests: {overall['failed_requests']}")
    print(f"Average Processing Time: {overall['avg_processing_time']:.2f}s")
    print(f"Min/Max Processing Time: {overall['min_processing_time']:.2f}s / {overall['max_processing_time']:.2f}s")
    print(f"Median Processing Time: {overall['median_processing_time']:.2f}s")

    if 'large_image_test' in summary:
        print("\n🔹 LARGE IMAGE STATISTICS:")
        large = summary['large_image_test']
        print(f"Tests: {large['count']}")
        print(f"Successful: {large['success_count']}")
        print(f"Average Time: {large['avg_time']:.2f}s")
        print(f"Min/Max Time: {large['min_time']:.2f}s / {large['max_time']:.2f}s")
        print(f"Median Time: {large['median_time']:.2f}s")
        print(f"Average File Size: {large['avg_size_mb']:.2f} MB")

    if 'normal_images_test' in summary:
        print("\n🔹 NORMAL IMAGES STATISTICS:")
        normal = summary['normal_images_test']
        print(f"Tests: {normal['count']}")
        print(f"Successful: {normal['success_count']}")
        print(f"Average Time: {normal['avg_time']:.2f}s")
        print(f"Min/Max Time: {normal['min_time']:.2f}s / {normal['max_time']:.2f}s")
        print(f"Median Time: {normal['median_time']:.2f}s")
        print(f"Average File Size: {normal['avg_size_mb']:.2f} MB")

    total_duration = time.time() - start_time
    print(f"\nTotal Testing Duration: {total_duration:.2f} seconds ({total_duration / 60:.2f} minutes)")

    print("\n" + "=" * 80)
    print("Test completed. All results saved to CSV files.")
    print("=" * 80)


if __name__ == "__main__":
    main()