import cv2
import numpy as np
import threading
import time
import os
import yaml
import pygame
import logging
from queue import Queue
import gc  # Added for garbage collection
import random

from game import Game, WIDTH, HEIGHT, RED, GREEN, SCREEN_COORDS
from video_recorder import VideoRecorder
from Kalman_filter import kalman_filter, Kalman_update, detect_direction_change

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='camera.log'
)
logger = logging.getLogger('CameraProcessor')

# Global variables
latest_frame = None
frame_lock = threading.Lock()
frame_number = 0

# Camera settings
AREA_THRESHOLD = 200
MIN_BALL_SIZE = 5
MAX_BALL_SIZE = 50
USE_FRAME_SKIP = False
FRAME_SKIP_COUNT = 1
SHOW_DEBUG_INFO = True
USE_ROI_TRACKING = True  # Enable ROI tracking for better performance
ROI_SIZE = 250  # Size of Region of Interest for tracking
USE_BACKGROUND_SUBTRACTION = True  # Enable background subtraction for better detection


# Add trajectory data structures for better visualization
blue_trajectory = []
yellow_trajectory = []
MAX_TRAJECTORY_LENGTH = 30


class BallTracker:
    """Enhanced ball tracking with ROI and background subtraction"""
    def __init__(self, color_samples, initial_frame=None, roi_size=ROI_SIZE):
        self.color_samples = color_samples
        self.roi_size = roi_size
        self.last_position = None
        self.kalman = kalman_filter()
        self.last_vx = 1
        self.last_vy = 1
        self.tracking_quality = 1.0  # 0.0 to 1.0
        self.trajectory = []
        
        # Initialize background subtractor if enabled
        self.bg_subtractor = None
        if USE_BACKGROUND_SUBTRACTION and initial_frame is not None:
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=16,
                detectShadows=False
            )
            # Train on initial frame
            self.bg_subtractor.apply(initial_frame)
    
    def update(self, frame, frame_number):
        """Track the ball in the current frame using ROI if possible"""
        # Full frame dimensions
        frame_height, frame_width = frame.shape[:2]
        
        # Determine if we should use ROI
        use_roi = USE_ROI_TRACKING and (self.last_position is not None and 
                  self.tracking_quality > 0.5)
        
        if use_roi:
            # Calculate ROI bounds
            roi_half = self.roi_size // 2
            roi_x = max(0, min(frame_width - self.roi_size, self.last_position[0] - roi_half))
            roi_y = max(0, min(frame_height - self.roi_size, self.last_position[1] - roi_half))
            roi_x_end = min(frame_width, roi_x + self.roi_size)
            roi_y_end = min(frame_height, roi_y + self.roi_size)
            
            # Extract ROI
            roi = frame[roi_y:roi_y_end, roi_x:roi_x_end]
            
            # Apply background subtraction if available
            fg_mask = None
            if self.bg_subtractor is not None:
                fg_mask = self.bg_subtractor.apply(roi)
            
            # Detect ball in ROI
            center, radius = detect_ball(
                roi, 
                self.color_samples, 
                params={"min_size": MIN_BALL_SIZE, "max_size": MAX_BALL_SIZE},
                foreground_mask=fg_mask
            )
            
            if center is not None:
                # Translate ROI coordinates to full frame coordinates
                center = (center[0] + roi_x, center[1] + roi_y)
                self.tracking_quality = min(1.0, self.tracking_quality + 0.1)
            else:
                # Ball left the ROI, search in full frame
                # But reduce the tracking quality
                self.tracking_quality *= 0.8
                center, radius = detect_ball(
                    frame, 
                    self.color_samples,
                    params={"min_size": MIN_BALL_SIZE, "max_size": MAX_BALL_SIZE}
                )
        else:
            # Search in full frame
            center, radius = detect_ball(
                frame, 
                self.color_samples,
                params={"min_size": MIN_BALL_SIZE, "max_size": MAX_BALL_SIZE}
            )
            
            if center is not None:
                self.tracking_quality = min(1.0, self.tracking_quality + 0.2)
            else:
                self.tracking_quality *= 0.9
        
        # Apply Kalman filter if ball was detected
        if center is not None and radius is not None:
            # Update trajectory
            self.trajectory.append(center)
            if len(self.trajectory) > MAX_TRAJECTORY_LENGTH:
                self.trajectory.pop(0)
                
            # Update Kalman filter
            predicted = Kalman_update(self.kalman, center, radius)
            is_back, self.last_vx, self.last_vy = detect_direction_change(
                predicted, self.last_vx, self.last_vy
            )
            
            # Fix the deprecation warnings by extracting single elements
            self.last_position = (int(predicted[0][0]), int(predicted[1][0]))
            
            # Return processed results
            return {
                'center': self.last_position,
                'radius': float(predicted[2][0]),  # Extract the first element
                'is_back': is_back,
                'velocity': (self.last_vx, self.last_vy),
                'frame_number': frame_number,
                'quality': self.tracking_quality,
                'trajectory': self.trajectory.copy()
            }
        
        # No ball detected
        return None


def initialize_camera():
    """Attempts to find and initialize an available camera with error handling and retries."""
    max_attempts = 3
    
    for read_attempt in range(1, max_attempts + 1):
        logger.info(f"Camera initialization attempt {read_attempt}/{max_attempts}")
        
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            logger.warning(f"Camera 0 with backend CAP_DSHOW failed to open")
            cap.release()
            continue
        # Verify frame capture with multiple attempts
        frame_read_attempts = 5
        for attempt in range(frame_read_attempts):
            try:
                ret, frame = cap.read()
                
                if ret and frame is not None and frame.size > 0:
                    logger.info(f"Successfully opened camera at index 0 with backend CAP_DSHOW")
                    
                    # Get actual properties
                    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    logger.info(f"Camera resolution: {actual_width}x{actual_height} @ {actual_fps} FPS")
                    return cap, 0
                
                time.sleep(0.1)
            except Exception as read_e:
                logger.warning(f"Frame read attempt {attempt+1} failed: {read_e}")
                time.sleep(0.1)
        # If no camera was found, wait before retrying
        logger.warning("No suitable camera found, retrying in 2 seconds...")
        time.sleep(2)
    
    # If all attempts failed
    logger.error("Failed to initialize camera after multiple attempts")
    return None, -1


def load_color_calibration(calib_file="calibration.yaml"):
    """
    Loads the color calibration data from a YAML file with error handling.
    """
    try:
        with open(calib_file, "r") as f:
            calib_data = yaml.safe_load(f)
        logger.info("Color calibration data loaded.")
        return calib_data
    except FileNotFoundError:
        logger.error(f"Calibration file '{calib_file}' not found, using defaults")
        # Fallback defaults if file loading fails
        return {
            "blue": [[[97, 141, 146], [117, 255, 255]]],
            "yellow": [[[14, 197, 152], [34, 255, 255]]]
        }
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in calibration file: {e}")
        return {
            "blue": [[[97, 141, 146], [117, 255, 255]]],
            "yellow": [[[14, 197, 152], [34, 255, 255]]]
        }
    except Exception as e:
        logger.error(f"Unexpected error loading calibration: {e}")
        # Fallback defaults if file loading fails
        return {
            "blue": [[[97, 141, 146], [117, 255, 255]]],
            "yellow": [[[14, 197, 152], [34, 255, 255]]]
        }


def detect_ball(frame, color_samples, screen_top_left=None, screen_bottom_right=None, 
               params=None, foreground_mask=None):
    """
    Detect a ball in an image using color-based filtering with optional foreground mask.
    
    Args:
        frame: The image frame to process
        color_samples: List of HSV color ranges to detect
        screen_top_left: Optional top-left corner to limit detection area
        screen_bottom_right: Optional bottom-right corner to limit detection area
        params: Dictionary of detection parameters
        foreground_mask: Optional foreground mask from background subtraction
        
    Returns:
        Tuple of (center, radius) if ball detected, or (None, None) if not
    """
    # Convert to HSV color space for better color detection
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Apply Gaussian blur to reduce noise
    hsv = cv2.GaussianBlur(hsv, (7, 7), 0)

    # Create a mask by combining all the provided color sample ranges
    mask = None
    for sample in color_samples:
        lower_bound = np.array(sample[0], dtype=np.uint8)
        upper_bound = np.array(sample[1], dtype=np.uint8)
                
        temp_mask = cv2.inRange(hsv, lower_bound, upper_bound)
        
        # Combine masks using logical OR
        if mask is None:
            mask = temp_mask
        else:
            mask = cv2.bitwise_or(mask, temp_mask)
    #show mask
    #cv2.imshow("Blue Mask", mask)
    # If foreground mask is provided, combine with color mask
    if foreground_mask is not None:
        mask = cv2.bitwise_and(mask, foreground_mask)
    
    # If screen boundaries are provided, limit detection to that area
    if screen_top_left and screen_bottom_right:
        screen_mask = np.zeros_like(mask)
        cv2.rectangle(screen_mask, screen_top_left, screen_bottom_right, 255, -1)
        mask = cv2.bitwise_and(mask, screen_mask)

    # Apply morphological operations to clean up the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract parameters or use defaults
    min_size = MIN_BALL_SIZE
    max_size = MAX_BALL_SIZE
    area_threshold = AREA_THRESHOLD
    if params:
        if params.get('min_size', 0) > 0:
            min_size = params['min_size']
        if params.get('max_size', 0) > 0:
            max_size = params['max_size']
        if params.get('area_threshold', 0) > 0:
            area_threshold = params['area_threshold']
    
    # If contours are found, find the largest one (likely to be the ball)
    if contours:
        # Sort contours by area, largest first
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        for c in contours:
            area = cv2.contourArea(c)
            
            # Check if area is large enough
            if area > area_threshold:
                # Find the minimum enclosing circle for the contour
                (x, y), radius = cv2.minEnclosingCircle(c)
                
                # Check if radius is within expected range
                if min_size <= radius <= max_size:
                    return (int(x), int(y)), radius
    
    # Ball not found
    return None, None


def capture_thread_func(cap, stop_event):
    """Thread function to continuously capture frames from camera."""
    global latest_frame
    
    # Track performance
    frame_count = 0
    start_time = time.time()
    fps = 0
    
    # Skip frame counter
    skip_counter = 0
    
    while not stop_event.is_set():
        # Read a frame from the camera
        ret, frame = cap.read()
        
        if not ret:
            # Failed to capture frame
            time.sleep(0.01)
            continue
            
        # Update FPS calculation
        frame_count += 1
        elapsed = time.time() - start_time
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            frame_count = 0
            start_time = time.time()
            
        # Frame skipping for performance
        if USE_FRAME_SKIP:
            skip_counter = (skip_counter + 1) % (FRAME_SKIP_COUNT + 1)
            if skip_counter != 0:
                continue
        
        # Store FPS on the frame for reference
        if SHOW_DEBUG_INFO:
            cv2.putText(
                frame,
                f"Camera: {fps:.1f} FPS",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                1
            )
        
        # Update the latest frame
        with frame_lock:
            latest_frame = frame.copy()
            
    logger.info("Capture thread ending.")


def get_projector_screen_transform(frame, width, height):
    """
    Calculates a perspective transformation matrix that will allow the screen identified 
    in the image to be mapped to a rectangular area of fixed size (width, height).
    We get the coordinate from calibration projector.
    """
    # Draw screen contour in blue to avoid interference with green detection
    if SCREEN_COORDS is None:
        logger.error("Screen coordinates not available for transform")
        return np.eye(3, dtype=np.float32)  # Identity transform as fallback
    screen_points = SCREEN_COORDS.astype(np.int32)
    cv2.polylines(frame, [screen_points], True, (255, 0, 0), 2)
    
    # Calculate transform for the fixed coordinates
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    try:
        M = cv2.getPerspectiveTransform(SCREEN_COORDS, dst)
        return M
    except Exception as e:
        logger.error(f"Error creating perspective transform: {e}")
        return np.eye(3, dtype=np.float32)  # Identity transform as fallback


def detect_red_balloon(frame):
    """
    Detect red balloons in the frame.
    Returns a list of tuples containing (center, radius) for each detected balloon.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    red_balloons = []
    for cnt in contours:
        if cv2.contourArea(cnt) > 100:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            red_balloons.append(((int(x), int(y)), float(radius)))
    return red_balloons


def detect_green_balloon(frame):
    """
    Detect green balloons in the frame.
    Returns a list of tuples containing (center, radius) for each detected balloon.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_green = np.array([40, 50, 50])
    upper_green = np.array([80, 255, 255])

    mask = cv2.inRange(hsv, lower_green, upper_green)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    green_balloons = []
    for cnt in contours:
        if cv2.contourArea(cnt) > 100:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            green_balloons.append(((int(x), int(y)), float(radius)))
    return green_balloons


def Handle_ballons(ballons, frame_display, color):
    """
    This function draws a circle on the balloon to help with debugging.
    """
    for center, radius in ballons:
        if color == "RED":
            cv2.circle(frame_display, center, int(radius), (0, 0, 255), 2)
            cv2.putText(frame_display, "Red Balloon", (center[0] + 10, center[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        else:
            cv2.circle(frame_display, center, int(radius), (0, 255, 0), 2)
            cv2.putText(frame_display, "Green Balloon", (center[0] + 10, center[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)


def camera_processing(game_instance, event_queue):
    """
    This function connects to the camera, detects balloons and balls, and shows the video in real time.
    """
    global latest_frame
    global frame_number
    global SHOW_DEBUG_INFO 

    # Initialize camera - use the improved initialization function
    try:
        cap, camera_index = initialize_camera()
        if cap is None:
            logger.critical("No camera could be initialized. Please check your camera connection.")
            return
    except Exception as init_e:
        logger.critical(f"Camera initialization failed: {init_e}")
        return

    # Get camera properties
    cam_fps = cap.get(cv2.CAP_PROP_FPS)
    if cam_fps <= 0 or cam_fps is None:
        cam_fps = 30
    logger.info(f"Camera FPS: {cam_fps}")

    # Start capture thread
    stop_event = threading.Event()
    cap_thread = threading.Thread(target=capture_thread_func, args=(cap, stop_event))
    cap_thread.daemon = True
    cap_thread.start()

    # Create display window
    cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Camera", 1280, 720)
    logger.info("Camera window is open. Starting processing...")

    # Performance tracking
    effective_frame_count = 0
    fps_timer = time.time()
    effective_fps = 0

    # Video recording options
    recording_enabled = False
    contour_recording_enabled = False
    video_recorder = None
    video_recorder_contour = None
    
    # Load color calibration data
    calibration_data = load_color_calibration()

    frame_number = 0  # Initialize frame counter

    # Initialize processing variables
    last_frame = None  # For motion detection
    
    # Wait for the first frame to initialize trackers
    while latest_frame is None:
        time.sleep(0.1)
        
    with frame_lock:
        init_frame = latest_frame.copy()
    
    # Initialize ball trackers with enhanced tracking
    blue_tracker = BallTracker(calibration_data["blue"], init_frame)
    yellow_tracker = BallTracker(calibration_data["yellow"], init_frame)

    try:
        logger.info("Starting main processing loop")
        last_gc_time = time.time()
        
        while True:
            # Update performance metrics
            effective_frame_count += 1
            frame_number += 1
            current_time = time.time()
            
            if current_time - fps_timer >= 1.0:
                effective_fps = effective_frame_count / (current_time - fps_timer)
                fps_timer = current_time
                effective_frame_count = 0
                
            # Periodic garbage collection to prevent memory leaks
            if current_time - last_gc_time > 30:  # Run GC every 30 seconds
                gc.collect()
                last_gc_time = current_time

            # Get the latest frame
            with frame_lock:
                if latest_frame is None:
                    continue
                frame = latest_frame.copy()
                frame_display = frame.copy()

            # Get transform matrix and draw screen contour
            M = get_projector_screen_transform(frame_display, WIDTH, HEIGHT)

            # Use the enhanced ball trackers
            blue_result = blue_tracker.update(frame, frame_number)
            yellow_result = yellow_tracker.update(frame, frame_number)
            
            # Process blue ball detection result
            if blue_result:
                # Extract tracked data
                blue_center = blue_result['center']
                blue_radius = blue_result['radius']
                is_back = blue_result['is_back']
                blue_trajectory = blue_result['trajectory']
                
                # Draw ball visualization
                cv2.circle(frame_display, blue_center, int(blue_radius), (255, 0, 0), 2)
                cv2.putText(
                    frame_display, 
                    "Blue Ball", 
                    (blue_center[0] + 10, blue_center[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, 
                    (255, 0, 0), 
                    2
                )
                
                # code to create trail effects:
                if frame_number % 3 == 0:  # Only add trails every 3rd frame to avoid too many particles
                    for _ in range(3):
                        trail_x = blue_center[0] + random.uniform(-5, 5)
                        trail_y = blue_center[1] + random.uniform(-5, 5)
                        # Draw a small blue circle for the trail
                        cv2.circle(frame_display, (int(trail_x), int(trail_y)), 
                                random.randint(1, 3), (255, 200, 100), -1)
                
                # Draw trajectory
                if len(blue_trajectory) > 1:
                    for i in range(1, len(blue_trajectory)):
                        # Calculate opacity based on age
                        alpha = i / len(blue_trajectory)
                        thickness = max(1, int(alpha * 4))
                        cv2.line(
                            frame_display,
                            blue_trajectory[i-1],
                            blue_trajectory[i],
                            (255, 0, 0),
                            thickness
                        )
                
                # Draw velocity vector
                if SHOW_DEBUG_INFO:
                    vx, vy = blue_result['velocity']
                    vel_mag = np.sqrt(vx*vx + vy*vy)
                    scale = 3.0
                    end_x = int(blue_center[0] + vx * scale)
                    end_y = int(blue_center[1] + vy * scale)
                    cv2.arrowedLine(frame_display, blue_center, (end_x, end_y), (0, 255, 0), 2)
                    
                    # Show velocity magnitude
                    cv2.putText(
                        frame_display,
                        f"v={vel_mag:.1f}, q={blue_result['quality']:.2f}", 
                        (blue_center[0] + int(blue_radius) + 5, blue_center[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, 
                        (255, 255, 255), 
                        1
                    )
                
                # Transform to projector coordinates
                src_pt = np.array([[[blue_center[0], blue_center[1]]]], dtype=np.float32)
                center_warped = cv2.perspectiveTransform(src_pt, M)[0][0]
                
                # Add to event queue
                event_queue.put((
                    "blue", 
                    int(center_warped[0]), 
                    int(center_warped[1]), 
                    blue_radius,
                    frame_number,
                    is_back
                ))
            
            # Process yellow ball detection result
            if yellow_result:
                # Extract tracked data
                yellow_center = yellow_result['center']
                yellow_radius = yellow_result['radius']
                is_back = yellow_result['is_back']
                yellow_trajectory = yellow_result['trajectory']
                
                # Draw ball visualization
                cv2.circle(frame_display, yellow_center, int(yellow_radius), (0, 255, 255), 2)
                cv2.putText(
                    frame_display, 
                    "Yellow Ball", 
                    (yellow_center[0] + 10, yellow_center[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, 
                    (0, 255, 255), 
                    2
                )

                # code to create trail effects for yellow ball:
                if frame_number % 3 == 0:  # Only add trails every 3rd frame to avoid too many particles
                    for _ in range(3):
                        trail_x = yellow_center[0] + random.uniform(-5, 5)
                        trail_y = yellow_center[1] + random.uniform(-5, 5)
                        # Draw a small yellow circle for the trail (or adjust color if needed)
                        cv2.circle(frame_display, (int(trail_x), int(trail_y)), 
                                random.randint(1, 3), (255, 200, 100), -1)
                
                # Draw trajectory
                if len(yellow_trajectory) > 1:
                    for i in range(1, len(yellow_trajectory)):
                        # Calculate opacity based on age
                        alpha = i / len(yellow_trajectory)
                        thickness = max(1, int(alpha * 4))
                        cv2.line(
                            frame_display,
                            yellow_trajectory[i-1],
                            yellow_trajectory[i],
                            (0, 255, 255),
                            thickness
                        )
                
                # Draw velocity vector
                if SHOW_DEBUG_INFO:
                    vx, vy = yellow_result['velocity']
                    vel_mag = np.sqrt(vx*vx + vy*vy)
                    scale = 3.0
                    end_x = int(yellow_center[0] + vx * scale)
                    end_y = int(yellow_center[1] + vy * scale)
                    cv2.arrowedLine(frame_display, yellow_center, (end_x, end_y), (0, 255, 0), 2)
                    
                    # Show velocity magnitude
                    cv2.putText(
                        frame_display,
                        f"v={vel_mag:.1f}, q={yellow_result['quality']:.2f}", 
                        (yellow_center[0] + int(yellow_radius) + 5, yellow_center[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, 
                        (255, 255, 255), 
                        1
                    )
                
                # Transform to projector coordinates
                src_pt = np.array([[[yellow_center[0], yellow_center[1]]]], dtype=np.float32)
                center_warped = cv2.perspectiveTransform(src_pt, M)[0][0]
                
                # Add to event queue
                event_queue.put((
                    "yellow", 
                    int(center_warped[0]), 
                    int(center_warped[1]), 
                    yellow_radius,
                    frame_number,
                    is_back
                ))

            # Add performance info
            if SHOW_DEBUG_INFO:
                cv2.putText(
                    frame_display,
                    f"Processing: {effective_fps:.1f} FPS",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    1
                )
                
                # Add frame number
                cv2.putText(
                    frame_display,
                    f"Frame: {frame_number}",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    1
                )
                
                # Add controls info
                cv2.putText(
                    frame_display,
                    "Controls: [r] Record raw, [c] Record processed, [d] Toggle debug, [q] Quit",
                    (10, frame_display.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (200, 200, 200),
                    1
                )

            # Show the frame
            cv2.imshow("Camera", frame_display)

            # Handle recording
            if recording_enabled and video_recorder is not None:
                video_recorder.record_frame(frame.copy())
            if contour_recording_enabled and video_recorder_contour is not None:
                video_recorder_contour.record_frame(frame_display.copy())

            # Process key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                recording_enabled = not recording_enabled
                if recording_enabled:
                    rec_fps = effective_fps if effective_fps >= 1 else 1
                    video_recorder = VideoRecorder(filename="clean_video.avi", fps=rec_fps)
                    logger.info(f"Raw recording started at {rec_fps:.2f} FPS")
                else:
                    if video_recorder is not None:
                        video_recorder.stop()
                        video_recorder = None
                    logger.info("Raw recording stopped")
            elif key == ord('c'):
                contour_recording_enabled = not contour_recording_enabled
                if contour_recording_enabled:
                    rec_fps = effective_fps if effective_fps >= 1 else 1
                    video_recorder_contour = VideoRecorder(filename="contour_video.avi", fps=rec_fps)
                    logger.info(f"Contour recording started at {rec_fps:.2f} FPS")
                else:
                    if video_recorder_contour is not None:
                        video_recorder_contour.stop()
                        video_recorder_contour = None
                    logger.info("Contour recording stopped")
            elif key == ord('d'):
                # Toggle debug info
                SHOW_DEBUG_INFO = not SHOW_DEBUG_INFO
                logger.info(f"Debug info display: {SHOW_DEBUG_INFO}")
    
    except KeyboardInterrupt:
        logger.info("Camera processing interrupted by user")
    except Exception as e:
        logger.error(f"Error in camera processing: {e}", exc_info=True)
    finally:
        # Clean up resources
        stop_event.set()
        cap_thread.join(timeout=1.0)
        cap.release()
        cv2.destroyAllWindows()
        
        if video_recorder is not None:
            video_recorder.stop()
        if video_recorder_contour is not None:
            video_recorder_contour.stop()
        
        logger.info("Camera resources released")

    # Run the game
    try:
        logger.info("Starting game in main thread")
        game_instance.run()
    except Exception as e:
        logger.error(f"Error running game: {e}", exc_info=True)


def start_game_and_camera():
    """Initialize and start both the game and camera processing."""
    try:
        # Force a complete Pygame reset
        pygame.quit()
        
        # Comprehensive Pygame initialization
        pygame.init()
        pygame.display.init()
        pygame.mixer.init()
        
        # Verify initialization
        if not pygame.get_init():
            logger.critical("Pygame failed to initialize")
            return
        
        if not pygame.display.get_init():
            logger.critical("Pygame display failed to initialize")
            return
        
        # Create display surface
        try:
            screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
            pygame.display.set_caption("Balloon Pop Game")
        except Exception as display_e:
            logger.critical(f"Failed to create display surface: {display_e}")
            return

        logger.info("Pygame initialized successfully")

        # Create event queue for communication between threads
        event_queue = Queue()
        
        # Initialize game
        try:
            game_instance = Game()
        except Exception as game_init_e:
            logger.critical(f"Game initialization failed: {game_init_e}")
            return

        game_instance.event_queue = event_queue
        
        # Create and start camera thread
        cam_thread = threading.Thread(
            target=camera_processing, 
            args=(game_instance, event_queue)
        )
        cam_thread.daemon = True
        cam_thread.start()
        
        # Run the game in the main thread
        try:
            game_instance.run()
        except Exception as game_run_e:
            logger.critical(f"Game run failed: {game_run_e}")
    
    except Exception as e:
        logger.critical(f"Failed to start game: {e}", exc_info=True)
        import sys
        sys.exit(1)


if __name__ == "__main__":
    start_game_and_camera()