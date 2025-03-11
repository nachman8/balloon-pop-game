import cv2
import numpy as np
import os
import time
from datetime import datetime
import keyboard 

# Constants
MIN_BALL_SIZE = 5
MAX_BALL_SIZE = 50
AREA_THRESHOLD = 200

# Color samples from your input
color_samples = {
    "blue": [
        [[100, 158, 87], [120, 255, 255]],
        [[99, 128, 115], [119, 255, 255]],
        [[99, 162, 63], [119, 255, 255]],
        [[98, 164, 50], [118, 255, 255]],
        [[100, 154, 75], [120, 255, 255]]
    ],
    "yellow": [
        [[9, 166, 101], [29, 255, 255]],
        [[7, 152, 108], [27, 255, 255]],
        [[9, 121, 162], [29, 255, 255]],
        [[8, 168, 103], [28, 255, 255]],
        [[10, 180, 84], [30, 255, 255]]
    ]
}

def create_output_directory():
    """Create a directory on the desktop to save all visualization images."""
    # Get the desktop path
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    
    # Create a timestamped folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"ball_detection_{timestamp}"
    
    # Create the full path
    output_dir = os.path.join(desktop, folder_name)
    
    # Create the directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create subdirectories for each color
    os.makedirs(os.path.join(output_dir, "blue"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "yellow"), exist_ok=True)
    
    print(f"Created output directory: {output_dir}")
    return output_dir

def detect_ball_visualization(frame, color_name, color_samples, output_dir):
    """
    Process a frame through all steps of ball detection and save visualizations.
    
    Args:
        frame: The input camera frame
        color_name: Either "blue" or "yellow"
        color_samples: List of HSV color ranges for the specified color
        output_dir: Directory to save visualization images
    """
    color_dir = os.path.join(output_dir, color_name)
    
    # Step 1: Save the original frame
    original_path = os.path.join(color_dir, "01_original_frame.jpg")
    cv2.imwrite(original_path, frame)
    print(f"Saved original frame: {original_path}")
    
    # Step 2: Convert to HSV and save
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hsv_path = os.path.join(color_dir, "02_hsv_conversion.jpg")
    
    # Create a visualization of HSV channels
    h, s, v = cv2.split(hsv)
    hsv_vis = np.concatenate([
        cv2.cvtColor(h, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(s, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(v, cv2.COLOR_GRAY2BGR)
    ], axis=1)
    cv2.imwrite(hsv_path, hsv_vis)
    print(f"Saved HSV conversion: {hsv_path}")
    
    # Step 3: Apply Gaussian blur and save
    hsv_blurred = cv2.GaussianBlur(hsv, (7, 7), 0)
    blur_path = os.path.join(color_dir, "03_gaussian_blur.jpg")
    
    # Create visualization of blurred HSV channels
    h_blur, s_blur, v_blur = cv2.split(hsv_blurred)
    blur_vis = np.concatenate([
        cv2.cvtColor(h_blur, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(s_blur, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(v_blur, cv2.COLOR_GRAY2BGR)
    ], axis=1)
    cv2.imwrite(blur_path, blur_vis)
    print(f"Saved Gaussian blur: {blur_path}")
    
    # Step 4: Create masks for each color sample and save
    all_masks = []
    combined_mask = None
    
    for i, sample in enumerate(color_samples):
        lower_bound = np.array(sample[0], dtype=np.uint8)
        upper_bound = np.array(sample[1], dtype=np.uint8)
        
        # Create mask for this sample
        temp_mask = cv2.inRange(hsv_blurred, lower_bound, upper_bound)
        
        # Save individual mask
        mask_path = os.path.join(color_dir, f"04_mask_sample_{i+1}.jpg")
        cv2.imwrite(mask_path, temp_mask)
        print(f"Saved mask for sample {i+1}: {mask_path}")
        
        # Add to visualization list
        all_masks.append(temp_mask)
        
        # Combine with overall mask
        if combined_mask is None:
            combined_mask = temp_mask
        else:
            combined_mask = cv2.bitwise_or(combined_mask, temp_mask)
    
    # Save the combined mask
    if combined_mask is not None:
        combined_path = os.path.join(color_dir, "05_combined_mask.jpg")
        cv2.imwrite(combined_path, combined_mask)
        print(f"Saved combined mask: {combined_path}")
    
    # Step 5: Apply morphological operations and save
    if combined_mask is not None:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        # Apply opening
        opened_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel, iterations=2)
        opened_path = os.path.join(color_dir, "06_morphology_open.jpg")
        cv2.imwrite(opened_path, opened_mask)
        print(f"Saved morphology opening: {opened_path}")
        
        # Apply closing
        closed_mask = cv2.morphologyEx(opened_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        closed_path = os.path.join(color_dir, "07_morphology_close.jpg")
        cv2.imwrite(closed_path, closed_mask)
        print(f"Saved morphology closing: {closed_path}")
        
        # Step 6: Find contours
        contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Draw all contours
        contour_image = frame.copy()
        cv2.drawContours(contour_image, contours, -1, (0, 255, 0), 2)
        contour_path = os.path.join(color_dir, "08_all_contours.jpg")
        cv2.imwrite(contour_path, contour_image)
        print(f"Saved all contours: {contour_path}")
        
        # Step 7: Filter contours and find the ball
        ball_found = False
        if contours:
            # Sort contours by area, largest first
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            
            ball_image = frame.copy()
            for i, c in enumerate(contours[:3]):  # Only check the three largest contours
                area = cv2.contourArea(c)
                
                # Draw this contour with its area
                contour_center = np.mean(c, axis=0)[0].astype(int)
                cv2.drawContours(ball_image, [c], -1, (0, 255, 0), 2)
                cv2.putText(ball_image, f"Area: {area:.1f}", 
                           (contour_center[0], contour_center[1]), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Check if area is large enough
                if area > AREA_THRESHOLD:
                    # Find the minimum enclosing circle
                    (x, y), radius = cv2.minEnclosingCircle(c)
                    
                    # Check if radius is within expected range
                    if MIN_BALL_SIZE <= radius <= MAX_BALL_SIZE:
                        ball_found = True
                        center = (int(x), int(y))
                        radius = int(radius)
                        
                        # Draw the circle
                        cv2.circle(ball_image, center, radius, (0, 0, 255), 2)
                        cv2.putText(ball_image, f"Ball: {radius}px", 
                                   (center[0], center[1] + 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        
            # Save the result
            result_path = os.path.join(color_dir, "09_ball_detection.jpg")
            cv2.imwrite(result_path, ball_image)
            
            if ball_found:
                print(f"Ball detected and saved: {result_path}")
            else:
                print(f"No ball detected: {result_path}")
    
    return combined_mask


def main():
    """Main function to run the ball detection visualization."""
    print("Ball Detection Visualization Tool")
    print("--------------------------------")
    print("This program will capture a frame and show all steps of ball detection.")
    print("Press 'space' to capture a frame and start visualization.")
    print("Press 'q' to quit.")
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return
    
    # Create window
    cv2.namedWindow("Camera Feed", cv2.WINDOW_NORMAL)
    
    capturing = False
    countdown = 0
    countdown_start = 0
    output_dir = None
    
    while True:
        # Capture frame-by-frame
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
        
        display_frame = frame.copy()
        
        # Check for key press
        key = cv2.waitKey(1) & 0xFF
        
        # Also check for keyboard module events
        if keyboard.is_pressed('space') and not capturing:
            capturing = True
            countdown = 3
            countdown_start = time.time()
            output_dir = create_output_directory()
        
        if key == ord('q'):
            break
        
        # Handle countdown
        if capturing:
            elapsed = time.time() - countdown_start
            
            if elapsed < 3:
                # Still counting down
                remaining = 3 - int(elapsed)
                cv2.putText(display_frame, f"Capturing in {remaining}...", 
                           (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                # Countdown complete, capture and process
                if output_dir:
                    # Display "Processing..." message
                    processing_frame = frame.copy()
                    cv2.putText(processing_frame, "Processing... Please wait", 
                               (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.imshow("Camera Feed", processing_frame)
                    cv2.waitKey(1)
                    
                    # Process blue color samples
                    print("\nProcessing blue color samples...")
                    blue_mask = detect_ball_visualization(frame, "blue", color_samples["blue"], output_dir)
                    
                    # Process yellow color samples
                    print("\nProcessing yellow color samples...")
                    yellow_mask = detect_ball_visualization(frame, "yellow", color_samples["yellow"], output_dir)
                    
                    # Create a final visualization showing both colors
                    if blue_mask is not None and yellow_mask is not None:
                        final_image = frame.copy()
                        
                        # Colorize the masks
                        blue_overlay = np.zeros_like(frame)
                        yellow_overlay = np.zeros_like(frame)
                        
                        blue_overlay[blue_mask > 0] = [255, 0, 0]  # Blue
                        yellow_overlay[yellow_mask > 0] = [0, 255, 255]  # Yellow
                        
                        # Blend with original
                        alpha = 0.5
                        final_image = cv2.addWeighted(final_image, 1.0, blue_overlay, alpha, 0)
                        final_image = cv2.addWeighted(final_image, 1.0, yellow_overlay, alpha, 0)
                        
                        # Save combined visualization
                        final_path = os.path.join(output_dir, "final_visualization.jpg")
                        cv2.imwrite(final_path, final_image)
                        print(f"Saved final visualization: {final_path}")
                        
                        # Show the final result
                        cv2.imshow("Final Visualization", final_image)
                    
                    print("\nAll processing complete!")
                    print(f"Results saved to: {output_dir}")
                    
                capturing = False
        
        # Display the frame
        cv2.putText(display_frame, "Press SPACE to capture, Q to quit", 
                   (10, display_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (255, 255, 255), 2)
        cv2.imshow("Camera Feed", display_frame)
    
    # Release the capture and close windows
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
