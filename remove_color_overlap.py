import cv2
import numpy as np
import yaml
import os
import pygame
import time
import logging
import argparse
from typing import List, Dict, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('CalibrationCleaner')

# Constants - SAME AS IN GAME.PY
WIDTH = 1920
HEIGHT = 1080
BALLOON_SIZE = 200
WHITE = (255, 255, 255)
RED = (255, 0, 0)
SAMPLE_COUNT = 5

def load_calibration(filename="calibration.yaml") -> Dict:
    """Load color calibration data from YAML file."""
    try:
        with open(filename, "r") as f:
            data = yaml.safe_load(f)
        logger.info(f"Loaded calibration data from {filename}")
        return data
    except Exception as e:
        logger.error(f"Failed to load calibration data: {e}")
        return {"blue": [], "yellow": []}

def save_calibration(data: Dict, filename="calibration.yaml") -> bool:
    """Save color calibration data to YAML file."""
    try:
        with open(filename, "w") as f:
            yaml.dump(data, f)
        logger.info(f"Saved calibration data to {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save calibration data: {e}")
        return False

def load_projector_calibration(filename="projector_calibration.yaml"):
    """Load the projector coordinates from calibration file."""
    try:
        with open(filename, "r") as f:
            data = yaml.safe_load(f)
        points = data.get("projector_points")
        if points is None:
            raise ValueError("Key 'projector_points' not found.")
        return np.array(points, dtype=np.float32)
    except Exception as e:
        logger.error(f"Error loading projector calibration: {e}")
        # Fallback to default screen coordinates
        return np.array([
            [0, 0], [WIDTH, 0], 
            [WIDTH, HEIGHT], [0, HEIGHT]
        ], dtype=np.float32)

def init_camera():
    """
    Initialize the camera by checking indices 0-4 with enhanced error handling and backend selection.
    
    Returns:
        cv2.VideoCapture or None: Initialized camera capture object, or None if no camera found
    """
    # Possible camera backends to try
    backends = [
        cv2.CAP_DSHOW,    # DirectShow (Windows)
        cv2.CAP_MSMF,     # Microsoft Media Foundation
        cv2.CAP_V4L2,     # Video4Linux (Linux)
        cv2.CAP_ANY       # Any available backend
    ]
    
    # Try multiple camera indices and backends
    for camera_index in range(5):  # Check indices 0-4
        for backend in backends:
            try:
                # Attempt to open camera with specific backend
                cap = cv2.VideoCapture(camera_index, backend)
                
                # Check if camera is opened
                if not cap.isOpened():
                    logger.debug(f"Camera {camera_index} with backend {backend} failed to open")
                    cap.release()
                    continue
                
                # Try to read a frame
                ret, frame = cap.read()
                
                if not ret or frame is None or frame.size == 0:
                    logger.debug(f"Camera {camera_index} with backend {backend} could not capture a frame")
                    cap.release()
                    continue
                
                # Set camera properties for optimal performance
                try:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                except Exception as prop_e:
                    logger.warning(f"Could not set camera properties: {prop_e}")
                
                # Verify camera properties
                actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                actual_fps = cap.get(cv2.CAP_PROP_FPS)
                
                logger.info(f"Camera initialized: Index {camera_index}, Backend {backend}")
                logger.info(f"Camera resolution: {actual_width}x{actual_height} @ {actual_fps} FPS")
                
                return cap
            
            except Exception as e:
                logger.error(f"Error with camera {camera_index}, backend {backend}: {e}")
                continue
    
    # If no camera found after all attempts
    logger.critical("Could not initialize any camera. Please check camera connection.")
    return None

def init_pygame_display():
    """Initialize the pygame display on the projector - using same settings as game.py."""
    pygame.init()
    
    # Set SDL window position to the projector monitor (same as in game.py)
    if os.name == 'nt':  # Windows
        os.environ['SDL_VIDEO_WINDOW_POS'] = "2000,0"  # Same as in game.py
        
    # Create a full-screen window on the projector - same as in game.py
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        pygame.display.set_caption("Balloon Color Sampling")
        logger.info(f"Created fullscreen display: {WIDTH}x{HEIGHT}")
        return screen
    except pygame.error as e:
        logger.error(f"Failed to initialize display: {e}")
        # Fallback to windowed mode if fullscreen fails
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Balloon Color Sampling (Windowed Fallback)")
        logger.info("Falling back to windowed mode")
        return screen

def draw_balloon(screen, position):
    """Draw a balloon at the specified position - with same size as in game."""
    try:
        # Try to load the same balloon image used in the game
        balloon_img = pygame.image.load('red_balloon.png')
        balloon_img = pygame.transform.scale(balloon_img, (BALLOON_SIZE, BALLOON_SIZE))
        rect = balloon_img.get_rect(center=position)
        screen.blit(balloon_img, rect)
        return rect  # Return the rect for click detection
    except pygame.error:
        # Fallback to basic circle if image not found
        pygame.draw.circle(screen, RED, position, BALLOON_SIZE//2)
        logger.warning("Could not load red_balloon.png, using circle fallback")
        # Return a circle rect
        return pygame.Rect(
            position[0] - BALLOON_SIZE//2,
            position[1] - BALLOON_SIZE//2,
            BALLOON_SIZE,
            BALLOON_SIZE
        )

def apply_perspective_transform(pt, M):
    """Apply perspective transformation to a point."""
    src_pt = np.array([[[pt[0], pt[1]]]], dtype=np.float32)
    dst_pt = cv2.perspectiveTransform(src_pt, M)
    return (int(dst_pt[0][0][0]), int(dst_pt[0][0][1]))

def calculate_transform_matrix():
    """Calculate transformation matrix from camera to screen coordinates."""
    # This is a placeholder for a proper perspective transform
    # In a complete solution, you would need to calibrate the camera to the screen
    return np.array([
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1]
    ], dtype=np.float32)

def sample_color_from_balloon(frame, balloon_center, radius=BALLOON_SIZE//4):
    """Sample color specifically from the balloon region in the frame."""
    height, width = frame.shape[:2]
    
    # Ensure coordinates are within frame
    x, y = balloon_center
    x = max(0, min(x, width-1))
    y = max(0, min(y, height-1))
    
    # Create a circular mask for sampling the balloon
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask, (x, y), radius, 255, -1)
    
    # Convert frame to HSV
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Extract HSV values from the masked region
    h_values = hsv_frame[:,:,0][mask > 0]
    s_values = hsv_frame[:,:,1][mask > 0]
    v_values = hsv_frame[:,:,2][mask > 0]
    
    if len(h_values) == 0:
        logger.warning(f"No pixels found in sampling region at {balloon_center}")
        return None
    
    # Calculate histogram to find the dominant color
    h_hist = cv2.calcHist([hsv_frame], [0], mask, [180], [0, 180])
    s_hist = cv2.calcHist([hsv_frame], [1], mask, [256], [0, 256])
    v_hist = cv2.calcHist([hsv_frame], [2], mask, [256], [0, 256])
    
    # Find the most frequent values
    h_dominant = np.argmax(h_hist)
    s_dominant = np.argmax(s_hist)
    v_dominant = np.argmax(v_hist)
    
    # Calculate ranges around dominant values (±15 for hue, ±30 for saturation and value)
    h_min = max(0, int(h_dominant - 15))
    h_max = min(180, int(h_dominant + 15))
    s_min = max(0, int(s_dominant - 30))
    s_max = min(255, int(s_dominant + 30))
    v_min = max(0, int(v_dominant - 30))
    v_max = min(255, int(v_dominant + 30))
    
    # For red color, which wraps around hue 0/180
    if h_dominant < 15 or h_dominant > 165:
        # Create a range that wraps around
        if h_min < 15 and h_max > 165:
            # Two separate ranges needed
            range1 = [[0, s_min, v_min], [h_max % 180, s_max, v_max]]
            range2 = [[h_min, s_min, v_min], [180, s_max, v_max]]
            return [range1, range2]
        
    # Return a single range for non-red colors or non-wrapping red
    return [[h_min, s_min, v_min], [h_max, s_max, v_max]]

def visualize_color_detection(frame, balloon_center, hsv_range, radius=BALLOON_SIZE//4):
    """
    Create a visualization showing the detected balloon color.
    Returns the visualization frame.
    """
    # Create a copy of the frame for visualization
    vis_frame = frame.copy()
    
    # Mark the balloon center with a green circle
    cv2.circle(vis_frame, balloon_center, radius, (0, 255, 0), 2)
    
    # Add text showing the HSV range being sampled
    if isinstance(hsv_range[0], list) and isinstance(hsv_range[0][0], list):
        # This is a wrapped range (for red color)
        for i, range_pair in enumerate(hsv_range):
            lower, upper = range_pair
            y_pos = 30 + i * 30
            text = f"Range {i+1}: H:{lower[0]}-{upper[0]} S:{lower[1]}-{upper[1]} V:{lower[2]}-{upper[2]}"
            cv2.putText(vis_frame, text, (10, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    else:
        # Standard single range
        lower, upper = hsv_range
        text = f"H:{lower[0]}-{upper[0]} S:{lower[1]}-{upper[1]} V:{lower[2]}-{upper[2]}"
        cv2.putText(vis_frame, text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Create a mask for showing what's being detected with this range
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.uint8)
    
    if isinstance(hsv_range[0], list) and isinstance(hsv_range[0][0], list):
        # Handle wrapped range
        for range_pair in hsv_range:
            lower, upper = range_pair
            temp_mask = cv2.inRange(hsv_frame, np.array(lower), np.array(upper))
            mask = cv2.bitwise_or(mask, temp_mask)
    else:
        # Handle standard range
        lower, upper = hsv_range
        mask = cv2.inRange(hsv_frame, np.array(lower), np.array(upper))
    
    # Create a colored overlay of the detected areas
    color_mask = np.zeros_like(frame)
    color_mask[mask > 0] = (0, 255, 0)  # Green highlight
    
    # Blend the highlight with the original frame
    highlight = cv2.addWeighted(vis_frame, 0.7, color_mask, 0.3, 0)
    
    # Draw contours around detected regions for better visibility
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(highlight, contours, -1, (0, 255, 0), 2)
    
    return highlight

def find_balloon_in_camera(frame, transform_matrix, previous_balloon_center=None):
    """
    Find the red balloon in the camera frame using enhanced color detection.
    
    Args:
        frame (numpy.ndarray): Input camera frame
        transform_matrix (numpy.ndarray): Perspective transform matrix
        previous_balloon_center (tuple, optional): Center of previously detected balloon
    
    Returns:
        tuple or None: Balloon center coordinates in camera space
    """
    # Convert to HSV for color detection
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Multiple red color ranges to handle different lighting conditions
    red_ranges = [
        # Classic red range
        (np.array([0, 100, 100]), np.array([10, 255, 255])),
        # Alternate red range for different lighting
        (np.array([160, 100, 100]), np.array([180, 255, 255])),
        # Broader red range for less saturated reds
        (np.array([0, 50, 50]), np.array([15, 255, 255])),
        # Very broad range for detection
        (np.array([0, 0, 100]), np.array([20, 255, 255]))
    ]
    
    # Combined mask to find red regions
    red_mask = np.zeros(hsv_frame.shape[:2], dtype=np.uint8)
    
    # Combine masks for different red ranges
    for lower, upper in red_ranges:
        temp_mask = cv2.inRange(hsv_frame, lower, upper)
        red_mask = cv2.bitwise_or(red_mask, temp_mask)
    
    # Morphological operations to clean up the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # Find contours in the mask
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter and rank contours
    valid_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        
        # Basic area filter
        if area < 100:  # Skip very small contours
            continue
        
        # Get contour properties
        M = cv2.moments(contour)
        if M["m00"] <= 0:
            continue
        
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        # Compute contour characteristics
        solidity = cv2.contourArea(contour) / cv2.convexHull(contour, returnPoints=False).size
        
        # Check for balloon-like shape (circular/elliptical)
        (x, y), (MA, ma), angle = cv2.fitEllipse(contour)
        aspect_ratio = MA / ma if MA > 0 else 1.0
        
        # Rank the contour based on multiple criteria
        rank_score = (
            area * 0.4 +  # Prefer larger balloons
            (1.0 / abs(aspect_ratio - 1.0)) * 0.3 +  # Prefer more circular shapes
            solidity * 0.3  # Prefer solid, filled contours
        )
        
        # Optional: proximity to previous balloon (if tracking)
        if previous_balloon_center:
            dist = np.sqrt((cx - previous_balloon_center[0])**2 + 
                           (cy - previous_balloon_center[1])**2)
            rank_score += max(0, 1000 - dist) * 0.1
        
        valid_contours.append((rank_score, contour))
    
    # Sort contours by rank
    if valid_contours:
        valid_contours.sort(key=lambda x: x[0], reverse=True)
        
        # Select the top-ranked contour
        best_contour = valid_contours[0][1]
        
        # Compute center
        M = cv2.moments(best_contour)
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        # Log debugging information
        logger.debug(f"Detected balloon at ({cx}, {cy})")
        logger.debug(f"Total valid contours: {len(valid_contours)}")
        logger.debug(f"Top contour area: {cv2.contourArea(best_contour)}")
        
        return (cx, cy)
    
    # No balloon detected
    logger.warning("No balloon detected in the frame")
    return None

def calculate_positions_from_calibration(projector_points):
    """
    Calculate optimal balloon positions inside the calibrated projector area.
    """
    # Convert to integer positions
    proj_points = projector_points.astype(int)
    
    # Calculate center of the calibrated area
    center_x = int(np.mean(proj_points[:, 0]))
    center_y = int(np.mean(proj_points[:, 1]))
    
    # Calculate an offset from the edges (20% of distance from center to edge)
    offset_x = int((proj_points[1, 0] - proj_points[0, 0]) * 0.2)
    offset_y = int((proj_points[2, 1] - proj_points[0, 1]) * 0.2)
    
    # Calculate positions for each corner and center with offset to stay within bounds
    top_left = (proj_points[0, 0] + offset_x, proj_points[0, 1] + offset_y)
    top_right = (proj_points[1, 0] - offset_x, proj_points[1, 1] + offset_y)
    bottom_right = (proj_points[2, 0] - offset_x, proj_points[2, 1] - offset_y)
    bottom_left = (proj_points[3, 0] + offset_x, proj_points[3, 1] - offset_y)
    center = (center_x, center_y)
    
    # Return all positions
    return [top_left, top_right, bottom_right, bottom_left, center]

def sample_balloon_colors():
    """
    Main function to sample balloon colors from the projected display.
    
    Displays red balloons at different positions on the screen and
    allows the user to click on them to sample their colors.
    """
    # Initialize camera
    cap = init_camera()
    if cap is None:
        logger.error("Camera initialization failed")
        return None
    
    # Initialize pygame display - using same settings as game.py
    screen = init_pygame_display()
    clock = pygame.time.Clock()
    
    # Load projector calibration
    projector_points = load_projector_calibration()
    
    # Calculate positions based on calibrated projector points
    positions = calculate_positions_from_calibration(projector_points)
    
    # Log the positions for debugging
    logger.info(f"Using balloon positions: {positions}")
    
    # Calculate transformation matrix
    transform_matrix = calculate_transform_matrix()
    
    # Initialize variables
    color_samples = []
    current_position_index = 0
    waiting_for_click = True
    sample_visualization = None
    balloon_rect = None
    previous_balloon_center = None
    
    font = pygame.font.Font(None, 36)
    
    try:
        while current_position_index < len(positions) and len(color_samples) < SAMPLE_COUNT:
            # Fill screen with white
            screen.fill(WHITE)
            
            # Draw calibrated projector area outline for reference
            pygame.draw.polygon(screen, (0, 0, 255), projector_points.astype(int), 2)
            
            # Draw the balloon at current position
            current_pos = positions[current_position_index]
            balloon_rect = draw_balloon(screen, current_pos)
            
            # Draw instructions
            text = font.render(f"Click on the red balloon to sample its color ({len(color_samples)+1}/{SAMPLE_COUNT})", 
                              True, (0, 0, 0))
            screen.blit(text, (20, 20))
            
            # Add ESC instruction
            esc_text = font.render("Press ESC to quit", True, (0, 0, 0))
            screen.blit(esc_text, (20, 60))
            
            # Add position label
            pos_names = ["Top Left", "Top Right", "Bottom Right", "Bottom Left", "Center"]
            pos_text = font.render(f"Current Position: {pos_names[current_position_index]}", True, (0, 0, 0))
            screen.blit(pos_text, (20, 100))
            
            # Update the display
            pygame.display.flip()
            
            # Process camera frame
            ret, frame = cap.read()
            if ret:
                # Try to find the balloon in the camera frame automatically
                balloon_cam_center = find_balloon_in_camera(
                    frame, transform_matrix, 
                    previous_balloon_center
                )
                
                # If balloon found, draw on debugging frame
                debug_frame = frame.copy()
                if balloon_cam_center:
                    cv2.circle(debug_frame, balloon_cam_center, 10, (0, 0, 255), -1)
                    cv2.putText(debug_frame, "Detected Balloon", balloon_cam_center, 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Show debugging frame with detected balloon
                cv2.imshow("Camera Feed - Balloon Detection", debug_frame)
                cv2.waitKey(1)
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return None
                
                if event.type == pygame.MOUSEBUTTONDOWN and waiting_for_click and balloon_rect:
                    mouse_pos = pygame.mouse.get_pos()
                    
                    # Check if click is inside the balloon rect
                    if balloon_rect.collidepoint(mouse_pos):
                        waiting_for_click = False
                        
                        # Capture a few frames to let the camera catch up
                        for _ in range(5):
                            ret, frame = cap.read()
                        
                        if ret:
                            # Try to find the balloon in the camera frame
                            balloon_cam_center = find_balloon_in_camera(
                                frame, transform_matrix, 
                                previous_balloon_center
                            )
                            
                            if balloon_cam_center:
                                # Update previous balloon center for next detection
                                previous_balloon_center = balloon_cam_center
                                
                                # Sample color from the detected balloon area
                                hsv_range = sample_color_from_balloon(frame, balloon_cam_center)
                                
                                if hsv_range:
                                    color_samples.append(hsv_range)
                                    logger.info(f"Sampled color at position {current_pos}: {hsv_range}")
                                    
                                    # Show the detected color with better visualization
                                    sample_visualization = visualize_color_detection(
                                        frame, balloon_cam_center, hsv_range
                                    )
                                    cv2.imshow("Sampled Color", sample_visualization)
                                    cv2.waitKey(100)  # Show for a bit longer
                                    
                                    # Move to next position
                                    current_position_index += 1
                                    if current_position_index >= len(positions):
                                        # If we've used all positions but need more samples, loop back
                                        if len(color_samples) < SAMPLE_COUNT:
                                            current_position_index = 0
                                else:
                                    logger.warning("Failed to sample color from balloon")
                            else:
                                logger.warning("Could not find balloon in camera frame - click again")
                        else:
                            logger.warning("Failed to capture frame from camera")
                        
                        # Wait a moment before accepting next click
                        time.sleep(0.5)
                        waiting_for_click = True
            
            clock.tick(30)
    
    finally:
        pygame.quit()
        cap.release()
        cv2.destroyAllWindows()
    
    return color_samples

def extract_red_hsv_ranges(color_samples):
    """Extract just the HSV ranges from the color samples."""
    all_ranges = []
    
    for sample in color_samples:
        if isinstance(sample, list):
            if isinstance(sample[0], list) and isinstance(sample[0][0], list):
                # This is a wrapped range (list of two ranges)
                for subrange in sample:
                    all_ranges.append(subrange)
            else:
                # Standard range
                all_ranges.append(sample)
    
    return all_ranges

def adjust_yellow_range(yellow_range, red_range):
    """
    Modify a yellow HSV range to exclude a red HSV range.
    Returns a single adjusted yellow range (wrapped in a list) or None if the overlap is too large.
    This version does not split the yellow range into two.
    """
    # Unpack ranges
    y_lower, y_upper = yellow_range
    r_lower, r_upper = red_range

    # Check for overlap in each HSV dimension
    h_overlap = not (y_lower[0] > r_upper[0] or y_upper[0] < r_lower[0])
    s_overlap = not (y_lower[1] > r_upper[1] or y_upper[1] < r_lower[1])
    v_overlap = not (y_lower[2] > r_upper[2] or y_upper[2] < r_lower[2])

    # If there is no significant overlap, return the yellow range as is.
    if not (h_overlap and s_overlap and v_overlap):
        return [yellow_range]

    # For this example, we focus on adjusting the hue dimension,
    # since that is typically where red and yellow differ.
    # Check if the red range lies completely inside the yellow range for hue.
    if y_lower[0] < r_lower[0] and y_upper[0] > r_upper[0]:
        # Calculate the available span on each side
        left_span = r_lower[0] - y_lower[0]
        right_span = y_upper[0] - r_upper[0]
        # Choose the larger segment
        if left_span >= right_span:
            new_upper = [r_lower[0], y_upper[1], y_upper[2]]
            adjusted = [y_lower, new_upper]
        else:
            new_lower = [r_upper[0], y_lower[1], y_lower[2]]
            adjusted = [new_lower, y_upper]
        return [adjusted]

    # If the red range overlaps on the left side of the yellow range:
    elif y_lower[0] < r_upper[0] <= y_upper[0]:
        new_lower = [r_upper[0], y_lower[1], y_lower[2]]
        return [[new_lower, y_upper]]

    # If the red range overlaps on the right side of the yellow range:
    elif y_lower[0] <= r_lower[0] < y_upper[0]:
        new_upper = [r_lower[0], y_upper[1], y_upper[2]]
        return [[y_lower, new_upper]]

    # Fallback: if none of the above conditions meet, return the original yellow range.
    return [yellow_range]

def adjust_calibration_data(calibration_data, red_samples):
    """
    Adjust yellow calibration ranges to exclude red balloon colors.
    """
    original_yellow_ranges = calibration_data.get("yellow", [])
    red_ranges = extract_red_hsv_ranges(red_samples)
    
    logger.info(f"Adjusting {len(original_yellow_ranges)} yellow ranges with {len(red_ranges)} red samples")
    
    # Start with original ranges
    adjusted_yellow_ranges = original_yellow_ranges.copy()
    
    # Process each red range
    for red_range in red_ranges:
        current_ranges = adjusted_yellow_ranges.copy()
        adjusted_yellow_ranges = []
        
        # Check each yellow range against this red range
        for yellow_range in current_ranges:
            # Try to adjust this yellow range
            adjusted = adjust_yellow_range(yellow_range, red_range)
            
            if adjusted is None:
                # This range should be completely removed
                logger.info(f"Removing yellow range {yellow_range} (overlaps too much with red)")
            else:
                # Add adjusted ranges
                adjusted_yellow_ranges.extend(adjusted)
    
    # Update the calibration data
    calibration_data["yellow"] = adjusted_yellow_ranges
    
    logger.info(f"Original yellow ranges: {len(original_yellow_ranges)}")
    logger.info(f"Final yellow ranges after adjustment: {len(adjusted_yellow_ranges)}")
    
    return calibration_data

def main():
    parser = argparse.ArgumentParser(description="Adjust yellow calibration to exclude red balloon colors")
    parser.add_argument("--calibration", default="calibration.yaml", 
                        help="Path to calibration YAML file")
    parser.add_argument("--output", default=None, 
                        help="Output calibration file (defaults to overwriting input)")
    args = parser.parse_args()
    
    output_file = args.output if args.output else args.calibration
    
    # Sample balloon colors
    logger.info("Starting balloon color sampling...")
    color_samples = sample_balloon_colors()
    print(color_samples)
    
    if not color_samples or len(color_samples) == 0:
        logger.error("Failed to collect color samples. Exiting.")
        return
    
    logger.info(f"Collected {len(color_samples)} color samples")
    
    # Load existing calibration
    calibration_data = load_calibration(args.calibration)
    
    # Adjust calibration data to exclude red balloon colors
    updated_calibration = adjust_calibration_data(calibration_data, color_samples)
    
    # Save updated calibration
    if save_calibration(updated_calibration, output_file):
        logger.info(f"Successfully updated calibration in {output_file}")
        
        # Print summary
        yellow_ranges = len(updated_calibration.get("yellow", []))
        blue_ranges = len(updated_calibration.get("blue", []))
        logger.info(f"Calibration now contains {yellow_ranges} yellow ranges and {blue_ranges} blue ranges")
    else:
        logger.error("Failed to save updated calibration")

if __name__ == "__main__":
    main()