import cv2
import numpy as np
import os
import time
import math
import logging
import keyboard
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='kalman_visualization.log'
)
logger = logging.getLogger('KalmanVisualization')

# Constants for Kalman filter
SAMPLE_RATE = 30
DT = 1.0 / SAMPLE_RATE
DIRECTION_CHANGE_THRESHOLD_X = 1.0
DIRECTION_CHANGE_THRESHOLD_Y = 1.0
MIN_BOUNCE_VELOCITY = 3.0
USE_ADAPTIVE_PROCESS_NOISE = True
PROCESS_NOISE_ADAPTATION_RATE = 0.05

# Constants for ball detection
MIN_BALL_SIZE = 5
MAX_BALL_SIZE = 50
AREA_THRESHOLD = 200

# Color samples for ball detection (blue and yellow balls)
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
    folder_name = f"kalman_filter_{timestamp}"
    
    # Create the full path
    output_dir = os.path.join(desktop, folder_name)
    
    # Create the directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Created output directory: {output_dir}")
    return output_dir

def kalman_filter():
    """
    Initialize a Kalman filter that tracks eight state variables:
    - x, y: Position of the ball
    - r: Radius of the ball
    - vx, vy: Velocity of the ball
    - vr: Rate of change of radius
    - ax, ay: Acceleration of the ball
    
    Returns:
        cv2.KalmanFilter: Initialized Kalman filter for ball tracking
    """
    # Create Kalman filter with 8 state variables and 3 measurement inputs (x, y, r)
    kalman = cv2.KalmanFilter(8, 3)

    # Measurement matrix - how state maps to measurement
    # We only directly measure position (x,y) and radius (r)
    kalman.measurementMatrix = np.array([
        [1, 0, 0, 0, 0, 0, 0, 0],  # x measurement
        [0, 1, 0, 0, 0, 0, 0, 0],  # y measurement
        [0, 0, 1, 0, 0, 0, 0, 0]   # r measurement
    ], dtype=np.float32)

    # Time step between frames
    dt = DT

    # State transition matrix - describes how state evolves over time
    # This implements the physical model (kinematics)
    kalman.transitionMatrix = np.array([
        # Position equations: position = previous_position + velocity*time + 0.5*acceleration*time^2
        [1, 0, 0, dt, 0, 0, 0.5 * dt**2, 0],  # x' = x + vx*dt + 0.5*ax*dt^2
        [0, 1, 0, 0, dt, 0, 0, 0.5 * dt**2],  # y' = y + vy*dt + 0.5*ay*dt^2
        [0, 0, 1, 0, 0, dt, 0, 0],            # r' = r + vr*dt
        
        # Velocity equations: velocity = previous_velocity + acceleration*time
        [0, 0, 0, 1, 0, 0, dt, 0],            # vx' = vx + ax*dt
        [0, 0, 0, 0, 1, 0, 0, dt],            # vy' = vy + ay*dt
        [0, 0, 0, 0, 0, 1, 0, 0],             # vr' = vr (radius velocity stays constant)
        
        # Acceleration remains constant
        [0, 0, 0, 0, 0, 0, 1, 0],             # ax' = ax
        [0, 0, 0, 0, 0, 0, 0, 1]              # ay' = ay
    ], dtype=np.float32)

    # Process noise covariance matrix
    # Represents the uncertainty in the process model
    # Higher values cause the filter to rely more on measurements than predictions
    process_noise_cov = np.eye(8, dtype=np.float32) * 1e-1
    
    # Fine-tune process noise for different state variables
    process_noise_cov[0, 0] = 1e-1  # x position noise
    process_noise_cov[1, 1] = 1e-1  # y position noise
    process_noise_cov[2, 2] = 2e-2  # radius noise
    process_noise_cov[3, 3] = 5e-1  # vx noise
    process_noise_cov[4, 4] = 5e-1  # vy noise
    process_noise_cov[5, 5] = 2e-2  # vr noise
    process_noise_cov[6, 6] = 1.0   # ax noise
    process_noise_cov[7, 7] = 1.0   # ay noise
    kalman.processNoiseCov = process_noise_cov

    # Measurement noise covariance matrix
    # Represents noise in the measurements
    # Lower values cause the filter to rely more on measurements
    measurement_noise_cov = np.eye(3, dtype=np.float32)
    measurement_noise_cov[0, 0] = 1e-2  # x measurement noise
    measurement_noise_cov[1, 1] = 1e-2  # y measurement noise
    measurement_noise_cov[2, 2] = 1e-3  # radius measurement noise
    kalman.measurementNoiseCov = measurement_noise_cov

    # Error covariance matrix post-prediction
    # Represents uncertainty in the current state estimate
    kalman.errorCovPost = np.eye(8, dtype=np.float32)

    # Initial state (will be set with first measurement)
    kalman.statePost = np.zeros((8, 1), dtype=np.float32)

    return kalman

def adapt_process_noise(kalman_filter, velocity_magnitude, predicted=None):
    """
    Adapt the process noise covariance based on observed velocity
    for more robust tracking during bounces.
    
    Args:
        kalman_filter: The Kalman filter to update
        velocity_magnitude: Current speed of the ball
        predicted: Optional predicted state to extract more information
    """
    if kalman_filter is None:
        return None  # Skip adaptation if no filter instance is provided
    if not USE_ADAPTIVE_PROCESS_NOISE:
        return None
        
    # Base process noise values
    base_pos_noise = 1e-1
    base_vel_noise = 5e-1
    base_acc_noise = 1.0
    
    # Scale noise based on velocity
    vel_factor = min(3.0, 1.0 + velocity_magnitude / 10.0)
    
    # Get current process noise values
    current_noise = {}
    current_noise['position'] = kalman_filter.processNoiseCov[0, 0]
    current_noise['velocity'] = kalman_filter.processNoiseCov[3, 3]
    current_noise['acceleration'] = kalman_filter.processNoiseCov[6, 6]
    
    # Calculate target values
    target_noise = {}
    target_noise['position'] = base_pos_noise * vel_factor
    target_noise['velocity'] = base_vel_noise * vel_factor
    target_noise['acceleration'] = base_acc_noise * vel_factor
    
    # Smoothly adapt values
    rate = PROCESS_NOISE_ADAPTATION_RATE
    for key in target_noise:
        current_noise[key] = current_noise[key] * (1-rate) + target_noise[key] * rate
    
    # Update Kalman filter's process noise covariance
    kalman_filter.processNoiseCov[0, 0] = current_noise['position']  # x position
    kalman_filter.processNoiseCov[1, 1] = current_noise['position']  # y position
    kalman_filter.processNoiseCov[3, 3] = current_noise['velocity']  # vx
    kalman_filter.processNoiseCov[4, 4] = current_noise['velocity']  # vy
    kalman_filter.processNoiseCov[6, 6] = current_noise['acceleration']  # ax
    kalman_filter.processNoiseCov[7, 7] = current_noise['acceleration']  # ay
    
    return current_noise

def Kalman_update(kalman_filter, center, radius):
    """
    Update the Kalman filter with a new measurement and get prediction.
    
    Args:
        kalman_filter: The Kalman filter to update
        center: Tuple (x, y) of the ball center
        radius: Measured radius of the ball
        
    Returns:
        Dictionary with all states and intermediate values for visualization
    """
    # Create a result dictionary to store all states for visualization
    result = {
        'is_first_update': False,
        'center': center,
        'radius': radius,
        'raw_measurement': None,
        'pre_predict_state': None,
        'post_predict_state': None, 
        'pre_correct_state': None,
        'post_correct_state': None,
        'final_prediction': None
    }
    
    # If this is the first measurement, initialize the state directly
    is_first_update = np.all(kalman_filter.statePost[:3] == 0)
    result['is_first_update'] = is_first_update
    
    # Create measurement vector from current detection
    measurement = np.array([
        [np.float32(center[0])],
        [np.float32(center[1])],
        [np.float32(radius)]
    ])
    result['raw_measurement'] = measurement.copy()
    
    # Store the pre-predict state
    result['pre_predict_state'] = kalman_filter.statePost.copy()
    
    if is_first_update:
        # For the first update, directly set the state
        kalman_filter.statePost[:3] = np.array([
            [center[0]], [center[1]], [radius]
        ], dtype=np.float32)
        
        # For first update, set error covariance to high values for position
        # and low values for velocity and acceleration
        kalman_filter.errorCovPost = np.eye(8, dtype=np.float32)
        kalman_filter.errorCovPost[0, 0] = 1.0  # x uncertainty
        kalman_filter.errorCovPost[1, 1] = 1.0  # y uncertainty
        kalman_filter.errorCovPost[2, 2] = 1.0  # r uncertainty
        kalman_filter.errorCovPost[3:, 3:] = 0.1  # Lower uncertainty for velocity and acceleration
        
        # Store the post-initialization state
        result['post_correct_state'] = kalman_filter.statePost.copy()
        
        # Make a prediction for the next frame
        prediction = kalman_filter.predict()
        result['final_prediction'] = prediction.copy()
    else:
        # For subsequent updates, first predict
        prediction = kalman_filter.predict()
        result['post_predict_state'] = prediction.copy()
        
        # Store pre-correction state
        result['pre_correct_state'] = kalman_filter.statePre.copy()
        
        # Then correct with measurement
        kalman_filter.correct(measurement)
        result['post_correct_state'] = kalman_filter.statePost.copy()
        
        # The final prediction is the corrected state
        result['final_prediction'] = kalman_filter.statePost.copy()
    
    return result

def detect_direction_change(predicted, last_vx, last_vy, threshold_x=None, threshold_y=None):
    """
    Detect if the ball has changed direction, indicating a bounce or collision.
    Uses separate thresholds for horizontal and vertical direction changes.
    
    Args:
        predicted: State vector from Kalman filter
        last_vx: Previous x velocity
        last_vy: Previous y velocity
        threshold_x: Minimum x velocity to consider significant
        threshold_y: Minimum y velocity to consider significant
        
    Returns:
        Dictionary with bounce detection results
    """
    # Create a result dictionary for consistent return format
    result = {
        'is_direction_changed': False,
        'bounce_type': None,
        'current_vx': 0,
        'current_vy': 0,
        'last_vx': last_vx,
        'last_vy': last_vy,
        'is_vertical_change': False,
        'is_horizontal_change': False,
        'large_angle_change': False,
        'big_velocity_change': False,
        'angle_diff': 0,
        'vel_change_ratio': 0,
        'last_vel_mag': 0,
        'current_vel_mag': 0,
        'is_back': False
    }
    
    # Use default thresholds if not specified
    if threshold_x is None:
        threshold_x = DIRECTION_CHANGE_THRESHOLD_X
    if threshold_y is None:
        threshold_y = DIRECTION_CHANGE_THRESHOLD_Y
    
    # Extract current velocities from predicted state
    current_vx = predicted[3][0]  # vx is at index 3
    current_vy = predicted[4][0]  # vy is at index 4
    
    result['current_vx'] = current_vx
    result['current_vy'] = current_vy
    
    # Static frame counter for warmup period
    if not hasattr(detect_direction_change, "frame_count"):
        detect_direction_change.frame_count = 0
    detect_direction_change.frame_count += 1
    
    # Skip bounce detection during first 5 frames while filter stabilizes
    if detect_direction_change.frame_count < 5:
        return result
    
    # Check if vertical velocity changed sign (y direction bounce)
    is_vertical_change = (current_vy * last_vy < 0) and (abs(current_vy) > threshold_y) and (abs(last_vy) > threshold_y)
    result['is_vertical_change'] = is_vertical_change
    
    # Check if horizontal velocity changed sign (x direction bounce)
    is_horizontal_change = (current_vx * last_vx < 0) and (abs(current_vx) > threshold_x) and (abs(last_vx) > threshold_x)
    result['is_horizontal_change'] = is_horizontal_change
    
    # Calculate the velocity angle change
    angle_diff = 0
    large_angle_change = False
    if abs(last_vx) > 0.1 and abs(last_vy) > 0.1 and abs(current_vx) > 0.1 and abs(current_vy) > 0.1:
        last_angle = math.atan2(last_vy, last_vx)
        current_angle = math.atan2(current_vy, current_vx)
        angle_diff = abs(math.degrees(current_angle - last_angle)) % 360
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
            
        # Large angle changes also indicate bounces
        large_angle_change = angle_diff > 90 and (
            abs(current_vx) > threshold_x or abs(current_vy) > threshold_y
        )
    
    result['angle_diff'] = angle_diff
    result['large_angle_change'] = large_angle_change
    
    # Calculate the change in velocity magnitude
    last_vel_mag = math.sqrt(last_vx**2 + last_vy**2)
    current_vel_mag = math.sqrt(current_vx**2 + current_vy**2)
    vel_change_ratio = abs(current_vel_mag - last_vel_mag) / max(last_vel_mag, 0.1)
    
    result['last_vel_mag'] = last_vel_mag
    result['current_vel_mag'] = current_vel_mag
    result['vel_change_ratio'] = vel_change_ratio
    
    # Ignore changes when velocity is very low (initial frames)
    if last_vel_mag < MIN_BOUNCE_VELOCITY:
        is_direction_changed = False
    else:
        # Consider any significant direction change
        is_direction_changed = is_vertical_change or is_horizontal_change or large_angle_change
        
        # Sudden large changes in velocity magnitude can also indicate a bounce
        # But only if the current velocity is significant
        big_velocity_change = vel_change_ratio > 0.7 and current_vel_mag > MIN_BOUNCE_VELOCITY
        result['big_velocity_change'] = big_velocity_change
        
        is_direction_changed = is_direction_changed or big_velocity_change
    
    result['is_direction_changed'] = is_direction_changed
    
    # Determine bounce type
    if is_direction_changed:
        if is_vertical_change:
            result['bounce_type'] = 'vertical'
        elif is_horizontal_change:
            result['bounce_type'] = 'horizontal'
        elif large_angle_change:
            result['bounce_type'] = 'angle'
        elif big_velocity_change:
            result['bounce_type'] = 'velocity'
        
        # Mark as coming back from wall
        result['is_back'] = True
    
    return result

def detect_ball(frame, color_samples, params=None):
    """
    Detect a ball in an image using color-based filtering.
    
    Args:
        frame: The image frame to process
        color_samples: List of HSV color ranges to detect
        params: Dictionary of detection parameters
        
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

def main():
    """
    Main function to run the Kalman filter visualization.
    Captures frames, detects balls, applies Kalman filtering, and saves visualizations.
    """
    print("Kalman Filter Visualization Tool")
    print("--------------------------------")
    print("This program will capture frames and demonstrate all steps of Kalman filtering.")
    print("Press 'space' to start capture with a 3-second countdown.")
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
    
    # Initialize Kalman filter state
    kalman_state = None
    kalman_filter_obj = None
    position_history = []
    MAX_HISTORY_LENGTH = 30
    last_vx = 1.0
    last_vy = 1.0
    recording_active = False
    frame_counter = 0
    
    # For recording consecutive frames - CHANGED FROM 300 TO 60
    MAX_RECORD_FRAMES = 60
    recorded_frames = []
    
    # To track bounce status
    is_coming_back = False
    coming_back_frames = []  # List to store frame numbers where ball is detected as coming back
    
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
        if capturing and not recording_active:
            elapsed = time.time() - countdown_start
            
            if elapsed < 3:
                # Still counting down
                remaining = 3 - int(elapsed)
                cv2.putText(display_frame, f"Capturing in {remaining}...", 
                           (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                # Countdown complete, start recording
                recording_active = True
                kalman_filter_obj = kalman_filter()
                position_history = []
                frame_counter = 0
                recorded_frames = []
                coming_back_frames = []
                print("Recording active! Processing frames with Kalman filter...")
        
        # Process frames with Kalman filter when recording is active
        if recording_active:
            frame_counter += 1
            
            # Detect the ball (either blue or yellow)
            ball_center, ball_radius = detect_ball(frame, color_samples["yellow"])
            if ball_center is None:
                ball_center, ball_radius = detect_ball(frame, color_samples["blue"])
            
            # Store the original frame
            recorded_frames.append(frame.copy())
            
            # Apply Kalman filter if ball is detected
            if ball_center is not None:
                # Update Kalman filter
                kalman_result = Kalman_update(kalman_filter_obj, ball_center, ball_radius)
                
                # Extract states
                final_prediction = kalman_result['final_prediction']
                
                # Check for direction change (bounce)
                bounce_result = detect_direction_change(final_prediction, last_vx, last_vy)
                last_vx = bounce_result['current_vx'] 
                last_vy = bounce_result['current_vy']
                
                # Update "is coming back" status
                is_coming_back = bounce_result['is_direction_changed']
                if is_coming_back:
                    coming_back_frames.append(frame_counter)
                
                # Update position history
                predicted_center = (int(final_prediction[0][0]), int(final_prediction[1][0]))
                position_history.append(predicted_center)
                if len(position_history) > MAX_HISTORY_LENGTH:
                    position_history.pop(0)
                
                # Create a combined visualization for this frame
                combined_vis = frame.copy()
                
                # Draw trajectory
                if position_history:
                    for i in range(1, len(position_history)):
                        prev_pos = position_history[i-1]
                        curr_pos = position_history[i]
                        opacity = i / len(position_history)
                        thickness = max(1, int(opacity * 4))
                        cv2.line(combined_vis, prev_pos, curr_pos, (0, 255, 255), thickness)
                
                # Draw measurement
                cv2.circle(combined_vis, ball_center, int(ball_radius), (0, 0, 255), 2)
                
                # Draw prediction with different color if coming back from wall
                predicted_x = int(final_prediction[0][0])
                predicted_y = int(final_prediction[1][0])
                predicted_radius = int(final_prediction[2][0])
                
                # Use a special highlight color if the ball is detected as coming back from wall
                prediction_color = (0, 0, 255) if is_coming_back else (0, 255, 0)
                cv2.circle(combined_vis, (predicted_x, predicted_y), predicted_radius, prediction_color, 3)
                
                # Draw velocity vector
                vx, vy = final_prediction[3][0], final_prediction[4][0]
                vel_mag = math.sqrt(vx*vx + vy*vy)
                scale = 10.0
                end_x = int(predicted_x + vx * scale)
                end_y = int(predicted_y + vy * scale)
                cv2.arrowedLine(combined_vis, (predicted_x, predicted_y), (end_x, end_y), (0, 255, 0), 2)
                
                # Add status text
                info_text = [
                    f"Frame: {frame_counter}",
                    f"Position: ({predicted_x}, {predicted_y})",
                    f"Velocity: {vel_mag:.2f} px/frame",
                    f"Direction: vx={vx:.2f}, vy={vy:.2f}"
                ]
                
                # Highlight when ball is coming back from wall (z coordinate change)
                if is_coming_back:
                    # Add a highlighted BACK FROM WALL indicator
                    bounce_type = bounce_result.get('bounce_type', 'unknown')
                    back_text = f"BACK FROM WALL - {bounce_type} bounce"
                    cv2.putText(combined_vis, back_text, 
                               (predicted_x - 100, predicted_y - 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    
                    # Add to main info text
                    info_text.append(f"BACK FROM WALL: {bounce_type} bounce")
                
                # Add bounce detection to info text
                if bounce_result['is_direction_changed']:
                    info_text.append(f"Bounce detected: {bounce_result['bounce_type']}")
                
                for i, text in enumerate(info_text):
                    cv2.putText(combined_vis, text, (10, 30 + 30*i), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Add frame border when coming back from wall
                if is_coming_back:
                    # Add a red border to the frame
                    border_thickness = 20
                    h, w = combined_vis.shape[:2]
                    # Top border
                    combined_vis[0:border_thickness, 0:w] = [0, 0, 255]
                    # Bottom border
                    combined_vis[h-border_thickness:h, 0:w] = [0, 0, 255]
                    # Left border
                    combined_vis[0:h, 0:border_thickness] = [0, 0, 255]
                    # Right border
                    combined_vis[0:h, w-border_thickness:w] = [0, 0, 255]
                
                # Save only the combined visualization
                os.makedirs(output_dir, exist_ok=True)
                cv2.imwrite(os.path.join(output_dir, f"frame_{frame_counter:03d}_combined.jpg"), combined_vis)
                
                # Use this for display
                display_frame = combined_vis
            
            # Add recording indicator
            cv2.putText(display_frame, f"RECORDING: Frame {frame_counter}/{MAX_RECORD_FRAMES}", 
                       (10, display_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (0, 0, 255), 2)
            
            # End recording after MAX_RECORD_FRAMES
            if frame_counter >= MAX_RECORD_FRAMES:
                recording_active = False
                capturing = False
                print(f"Recording complete. {frame_counter} frames processed.")
                print(f"Results saved to: {output_dir}")
                
                # Save the full trajectory visualization
                if position_history:
                    full_trajectory = frame.copy()
                    # Draw position history
                    for i in range(1, len(position_history)):
                        prev_pos = position_history[i-1]
                        curr_pos = position_history[i]
                        # Use a color gradient from red to green
                        progress = i / len(position_history)
                        color = (
                            int((1-progress) * 255),  # B
                            int(progress * 255),      # G
                            int((1-progress) * 128)   # R
                        )
                        cv2.line(full_trajectory, prev_pos, curr_pos, color, 2)
                    
                    # Mark points with circles
                    for i, pos in enumerate(position_history):
                        progress = i / len(position_history)
                        color = (
                            int((1-progress) * 255),  # B
                            int(progress * 255),      # G
                            int((1-progress) * 128)   # R
                        )
                        cv2.circle(full_trajectory, pos, 3, color, -1)
                    
                    # Add annotations
                    cv2.putText(full_trajectory, "Full Trajectory", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(full_trajectory, "Red = Start, Green = End", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
                    # Add annotations for bounce frames
                    if coming_back_frames:
                        cv2.putText(full_trajectory, "Back from Wall Frames:", (10, 90), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        frames_text = ", ".join([str(f) for f in coming_back_frames[:5]])
                        if len(coming_back_frames) > 5:
                            frames_text += f"... (+{len(coming_back_frames)-5} more)"
                        cv2.putText(full_trajectory, frames_text, (10, 120), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    cv2.imwrite(os.path.join(output_dir, "full_trajectory.jpg"), full_trajectory)
        
        # Display the frame
        cv2.putText(display_frame, "Press SPACE to capture, Q to quit", 
                   (10, display_frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (255, 255, 255), 2)
        cv2.imshow("Camera Feed", display_frame)
    
    # Release the capture and close windows
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()