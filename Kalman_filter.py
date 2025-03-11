import cv2
import numpy as np
import logging
import math
from typing import Tuple, Optional, Dict, List, Any, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='kalman.log'
)
logger = logging.getLogger('KalmanFilter')

# Kalman filter settings
SAMPLE_RATE = 30
DT = 1.0 / SAMPLE_RATE

# Direction change detection thresholds
DIRECTION_CHANGE_THRESHOLD_X = 1.0
DIRECTION_CHANGE_THRESHOLD_Y = 1.0
MIN_BOUNCE_VELOCITY = 3.0

# New adaptive settings
USE_ADAPTIVE_PROCESS_NOISE = True
PROCESS_NOISE_ADAPTATION_RATE = 0.05


class KalmanFilterState:
    """Stores the state of a Kalman filter for a ball"""
    def __init__(self):
        self.filter = kalman_filter()
        self.last_vx = 1.0
        self.last_vy = 1.0
        self.last_position = None
        self.last_radius = None
        self.position_history = []
        self.max_history_length = 30
        self.bounce_count = 0
        self.confidence = 1.0  # 0.0 to 1.0
        self.adaptive_process_noise = {
            'position': 1e-1,
            'velocity': 5e-1,
            'radius': 2e-2,
            'acceleration': 1.0
        }
        
    def add_position(self, position: Tuple[int, int]) -> None:
        """Add a position to the history"""
        self.position_history.append(position)
        if len(self.position_history) > self.max_history_length:
            self.position_history.pop(0)
            
    def clear_history(self) -> None:
        """Clear position history"""
        self.position_history.clear()
        
    def get_velocity(self) -> Tuple[float, float]:
        """Get current velocity"""
        return (self.last_vx, self.last_vy)
        
    def get_speed(self) -> float:
        """Get current speed (magnitude of velocity)"""
        return math.sqrt(self.last_vx**2 + self.last_vy**2)


def kalman_filter():
    """
    The function defines a Kalman filter that tracks eight state variables:
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
        return  # Skip adaptation if no filter instance is provided
    if not USE_ADAPTIVE_PROCESS_NOISE:
        return
        
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
        np.ndarray: The predicted state for the next frame
    """
    # If this is the first measurement, initialize the state directly
    is_first_update = np.all(kalman_filter.statePost[:3] == 0)
    
    if is_first_update:
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
    
    # Create measurement vector from current detection
    measurement = np.array([
        [np.float32(center[0])],
        [np.float32(center[1])],
        [np.float32(radius)]
    ])
    
    # If not first update, predict first, then correct
    if not is_first_update:
        kalman_filter.predict()
    
    # Correct the state estimate with the measurement
    kalman_filter.correct(measurement)
    
    # Predict the next state
    predicted = kalman_filter.predict() if is_first_update else kalman_filter.statePost
    
    return predicted


def detect_direction_change(predicted, last_vx, last_vy, threshold_x=None, threshold_y=None):
    """
    Detect if the ball has changed direction, indicating a bounce or collision.
    Uses separate thresholds for horizontal and vertical direction changes.
    
    Args:
        predicted: State vector from Kalman filter
        last_vx: Previous x velocity
        last_vy: Previous y velocity
        threshold_x: Minimum x velocity to consider significant (default from config)
        threshold_y: Minimum y velocity to consider significant (default from config)
        
    Returns:
        Tuple: (is_direction_changed, new_vx, new_vy)
    """
    # Use default thresholds if not specified
    if threshold_x is None:
        threshold_x = DIRECTION_CHANGE_THRESHOLD_X
    if threshold_y is None:
        threshold_y = DIRECTION_CHANGE_THRESHOLD_Y
    
    # Extract current velocities from predicted state
    current_vx = predicted[3][0]  # vx is at index 3
    current_vy = predicted[4][0]  # vy is at index 4
    
    # Check if vertical velocity changed sign (y direction bounce)
    is_vertical_change = (current_vy * last_vy < 0) and (abs(current_vy) > threshold_y) and (abs(last_vy) > threshold_y)
    
    # Check if horizontal velocity changed sign (x direction bounce)
    is_horizontal_change = (current_vx * last_vx < 0) and (abs(current_vx) > threshold_x) and (abs(last_vx) > threshold_x)
    
    # Calculate the velocity angle change
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
    else:
        large_angle_change = False
    
    # Consider any significant direction change
    is_direction_changed = is_vertical_change or is_horizontal_change or large_angle_change
    
    # Calculate the change in velocity magnitude
    last_vel_mag = math.sqrt(last_vx**2 + last_vy**2)
    current_vel_mag = math.sqrt(current_vx**2 + current_vy**2)
    vel_change_ratio = abs(current_vel_mag - last_vel_mag) / max(last_vel_mag, 0.1)
    
    # Sudden large changes in velocity magnitude can also indicate a bounce
    big_velocity_change = vel_change_ratio > 0.5 and current_vel_mag > MIN_BOUNCE_VELOCITY
    is_direction_changed = is_direction_changed or big_velocity_change
    
    if is_direction_changed:
        bounce_type = "vertical" if is_vertical_change else "horizontal" if is_horizontal_change else "angle"
        logger.debug(
            f"Direction change ({bounce_type}): vx={current_vx:.2f} (was {last_vx:.2f}), "
            f"vy={current_vy:.2f} (was {last_vy:.2f})"
        )
        
        # Adapt process noise after bounce detection to be more responsive
        if USE_ADAPTIVE_PROCESS_NOISE:
            # We're passing None for the kalman filter here since we don't have it
            # in this function. In a real implementation, you'd want to pass it or refactor.
            adapt_process_noise(None, current_vel_mag)
    
    return is_direction_changed, current_vx, current_vy


def visualize_kalman_state(frame, predicted, color=(0, 255, 255), draw_velocity=True, 
                          position_history=None):
    """
    Visualize the Kalman filter state on a frame, including velocity vector.
    
    Args:
        frame: Image to draw on
        predicted: Predicted state from Kalman filter
        color: Color for visualization
        draw_velocity: Whether to draw the velocity vector
        position_history: List of previous positions for drawing trajectory
        
    Returns:
        Frame with visualization elements added
    """
    # Extract state components
    x, y = int(predicted[0][0]), int(predicted[1][0])
    vx, vy = predicted[3][0], predicted[4][0]
    ax, ay = predicted[6][0], predicted[7][0]
    radius = int(predicted[2][0])
    
    # Draw current position
    cv2.circle(frame, (x, y), radius, color, 2)
    
    # Draw historical trajectory
    if position_history:
        for i in range(1, len(position_history)):
            prev_pos = position_history[i-1]
            curr_pos = position_history[i]
            
            if prev_pos is None or curr_pos is None:
                continue
                
            # Calculate opacity based on age (older points are more transparent)
            opacity = i / len(position_history)
            thickness = max(1, int(opacity * 4))
            
            # Draw line segment
            cv2.line(frame, prev_pos, curr_pos, color, thickness)
    
    # Draw velocity vector
    if draw_velocity:
        vel_mag = math.sqrt(vx*vx + vy*vy)
        scale = 3.0
        end_x = int(x + vx * scale)
        end_y = int(y + vy * scale)
        cv2.arrowedLine(frame, (x, y), (end_x, end_y), (0, 255, 0), 2)
    
    # Add text for velocity magnitude
    velocity = np.sqrt(vx*vx + vy*vy)
    cv2.putText(
        frame,
        f"v={velocity:.1f}", 
        (x + radius + 5, y),
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.5, 
        (255, 255, 255), 
        1
    )
    
    # Draw acceleration vector if significant
    acc_mag = math.sqrt(ax*ax + ay*ay)
    if acc_mag > 0.5:
        scale = 3.0
        # Use a different color for acceleration
        acc_color = (255, 165, 0)  # Orange
        end_x = int(x + ax * scale)
        end_y = int(y + ay * scale)
        cv2.arrowedLine(frame, (x, y), (end_x, end_y), acc_color, 1)
        
        # Add text for acceleration magnitude
        cv2.putText(
            frame,
            f"a={acc_mag:.1f}", 
            (x + radius + 5, y + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.5, 
            (255, 255, 255), 
            1
        )
    
    return frame


# For backward compatibility
IsBallIsBack = detect_direction_change