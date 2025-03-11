import cv2
import numpy as np
import pygame
import time
import yaml
import os
import logging
from typing import Dict, List, Tuple, Optional, Any



class CalibrationWizard:
    """A user-friendly guided calibration system for the Balloon Pop game"""
    
    def __init__(self):
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='calibration.log'
        )
        self.logger = logging.getLogger('CalibrationWizard')
        
        # Initialize pygame for UI
        pygame.init()
        # Get the display info for fullscreen
        info = pygame.display.Info()
        self.width, self.height = info.current_w, info.current_h
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Balloon Pop Game - Calibration Wizard")
        
        # Fonts
        self.title_font = pygame.font.Font(None, 48)
        self.text_font = pygame.font.Font(None, 36)
        self.button_font = pygame.font.Font(None, 32)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.BLUE = (100, 100, 255)
        self.GREEN = (100, 255, 100)
        self.RED = (255, 100, 100)
        self.GRAY = (150, 150, 150)
        
        # Camera
        self.camera = None
        self.camera_index = 0

        # Frozen frame for color sampling
        self.frozen_frame = None
        self.is_frame_frozen = False
        
        # Calibration data
        self.projector_points = None
        self.color_ranges = {
            "blue": [],
            "yellow": []
        }
        self.ball_sizes = {
            "blue": {},
            "yellow": {}
        }
        
        # Calibration state
        self.current_step = "welcome"
        self.substep = 0
        self.calibration_complete = False
        
        # Warm up the camera early
        camera_result = self.initialize_camera()
        if isinstance(camera_result, tuple) and len(camera_result) == 2:
            self.camera, self.camera_index = camera_result
        time.sleep(2)  # Give camera time to wake up
        
        
    def initialize_camera(self) -> bool:
        """Attempts to find and initialize an available camera with error handling and retries."""
        max_attempts = 3
        
        for read_attempt in range(1, max_attempts + 1):
            self.logger.info(f"Camera initialization attempt {read_attempt}/{max_attempts}")
            
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                self.logger.warning(f"Camera 0 with backend CAP_DSHOW failed to open")
                cap.release()
                continue
            # Verify frame capture with multiple attempts
            frame_read_attempts = 5
            for attempt in range(frame_read_attempts):
                try:
                    ret, frame = cap.read()
                    
                    if ret and frame is not None and frame.size > 0:
                        self.logger.info(f"Successfully opened camera at index 0 with backend CAP_DSHOW")
                        
                        # Get actual properties
                        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        actual_fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        self.logger.info(f"Camera resolution: {actual_width}x{actual_height} @ {actual_fps} FPS")
                        return cap, 0
                    
                    time.sleep(0.1)
                except Exception as read_e:
                    self.logger.warning(f"Frame read attempt {attempt+1} failed: {read_e}")
                    time.sleep(0.1)
            # If no camera was found, wait before retrying
            self.logger.warning("No suitable camera found, retrying in 2 seconds...")
            time.sleep(2)
        
        # If all attempts failed
        self.logger.error("Failed to initialize camera after multiple attempts")
        return None, -1
        
    def release_camera(self):
        """Release the camera if it's open"""
        try:
            if self.camera is not None:
                # Explicitly release the camera
                self.camera.release()
                # Set to None to prevent multiple release attempts
                self.camera = None
                self.logger.info("Camera resources released")
        except Exception as e:
            self.logger.error(f"Error releasing camera: {e}")
        finally:
            # Ensure pygame display is released
            pygame.display.quit()
            
    def get_camera_frame(self) -> Optional[np.ndarray]:
        """Get a frame from the camera with error handling"""
        if self.camera is None:
            # Retry initializing camera
            self.initialize_camera()
            
        if self.camera is None:
            return None
            
        try:
            ret, frame = self.camera.read()
            if ret and frame is not None and frame.size > 0:
                return frame
            return None
        except Exception as e:
            self.logger.error(f"Error getting camera frame: {e}")
            return None
    
    def show_camera_preview(self, frame: np.ndarray, position: Tuple[int, int], size: Tuple[int, int]) -> None:
        """Display camera preview on the pygame screen"""
        if frame is None:
            # Draw placeholder if no frame
            pygame.draw.rect(self.screen, self.GRAY, (*position, *size))
            text = self.text_font.render("No Camera Feed", True, self.WHITE)
            text_pos = (position[0] + size[0]//2 - text.get_width()//2, 
                         position[1] + size[1]//2 - text.get_height()//2)
            self.screen.blit(text, text_pos)
            return
            
        try:
            # Resize frame to fit the display area
            frame_resized = cv2.resize(frame, size)
            
            # Convert from BGR to RGB for pygame
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            
            # Transpose to match pygame surface requirements
            frame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
            
            # Blit to screen
            self.screen.blit(frame_surface, position)
            
        except Exception as e:
            self.logger.error(f"Error showing camera preview: {e}")
            # Fallback to drawing an error rectangle
            pygame.draw.rect(self.screen, self.RED, (*position, *size))
            text = self.text_font.render("Camera Error", True, self.WHITE)
            text_pos = (position[0] + size[0]//2 - text.get_width()//2, 
                         position[1] + size[1]//2 - text.get_height()//2)
            self.screen.blit(text, text_pos)
        
    def draw_button(self, rect: pygame.Rect, text: str, active: bool = True) -> bool:
        """Draw a button and return whether it was clicked"""
        mouse_pos = pygame.mouse.get_pos()
        clicked = False
        
        # Check if mouse is over button
        hover = rect.collidepoint(mouse_pos)
        
        # Check for click
        if hover and pygame.mouse.get_pressed()[0] and active:
            clicked = True
            
        # Draw button
        if not active:
            color = self.GRAY
        elif hover:
            color = self.GREEN
        else:
            color = self.BLUE
            
        pygame.draw.rect(self.screen, color, rect, border_radius=8)
        pygame.draw.rect(self.screen, self.WHITE, rect, 2, border_radius=8)
        
        # Draw text
        text_surf = self.button_font.render(text, True, self.WHITE)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)
        
        return clicked

    def sample_color(self, frame, x, y, color_name):
        """Sample HSV color at the given coordinates"""
        try:
            # Convert to HSV
            hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Sample the pixel
            pixel = hsv_frame[y, x]
            h, s, v = int(pixel[0]), int(pixel[1]), int(pixel[2])
            
            # Create tolerance range
            lower_bound = [max(0, h - 10), max(50, s - 50), max(50, v - 50)]
            upper_bound = [min(180, h + 10), 255, 255]
            
            # Add to color ranges
            if len(self.color_ranges[color_name]) < 5:  # Limit to 5 samples
                self.color_ranges[color_name].append((lower_bound, upper_bound))
                
            self.logger.info(f"Sampled {color_name} color: HSV=({h},{s},{v})")
            self.logger.info(f"Range: Lower={lower_bound}, Upper={upper_bound}")
            
        except Exception as e:
            self.logger.error(f"Error sampling color: {e}")

    def detect_ball(self, frame, color_samples, params):
        """Detect a ball in the frame using the provided color samples"""
        try:
            # Convert to HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv = cv2.GaussianBlur(hsv, (7, 7), 0)
            
            # Create mask from color samples
            mask = None
            for sample in color_samples:
                lower_bound = np.array(sample[0], dtype=np.uint8)
                upper_bound = np.array(sample[1], dtype=np.uint8)
                
                temp_mask = cv2.inRange(hsv, lower_bound, upper_bound)
                
                if mask is None:
                    mask = temp_mask
                else:
                    mask = cv2.bitwise_or(mask, temp_mask)
                    
            # Clean up mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                c = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(c)
                
                # Check area
                if area > 200:  # Minimum area
                    (x, y), radius = cv2.minEnclosingCircle(c)
                    
                    # Check radius
                    min_size = params.get("min_size", 5)
                    max_size = params.get("max_size", 100)
                    
                    if min_size <= radius <= max_size:
                        return (int(x), int(y)), radius
                        
            return None, None
        except Exception as e:
            self.logger.error(f"Error detecting ball: {e}")
            return None, None

    def draw_welcome_screen(self):
        """Draw the welcome screen with instructions"""
        # Clear screen
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.title_font.render("Balloon Pop Game - Calibration Wizard", True, self.WHITE)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 100))
        
        # Description
        descriptions = [
            "Welcome to the calibration wizard!",
            "This will guide you through setting up your game for optimal play.",
            "",
            "You will need:",
            "- A projector connected to this computer",
            "- A camera that can see the projection area",
            "- Blue and yellow balls for gameplay"
        ]
        
        y = 200
        for line in descriptions:
            text = self.text_font.render(line, True, self.WHITE)
            self.screen.blit(text, (self.width//2 - text.get_width()//2, y))
            y += 40
            
        # Start button
        start_rect = pygame.Rect(self.width//2 - 100, self.height - 150, 200, 60)
        if self.draw_button(start_rect, "Start Calibration"):
            self.current_step = "camera_setup"
            
        # Update screen
        pygame.display.flip()

    def draw_camera_setup(self):
        """Draw the camera setup screen"""
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.title_font.render("Step 1: Camera Setup", True, self.WHITE)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 50))
        
        # Status text
        if self.camera is None:
            status = self.text_font.render("No camera detected. Please connect a camera.", True, self.RED)
        else:
            status = self.text_font.render(f"Using camera {self.camera_index}", True, self.GREEN)
        self.screen.blit(status, (self.width//2 - status.get_width()//2, 100))
        
        # Camera preview
        frame = self.get_camera_frame()
        # Camera preview - make it larger (around 70% of screen width)
        preview_width = int(self.width * 0.7)
        preview_height = int(preview_width * 9/16)  # Maintain aspect ratio
        preview_x = (self.width - preview_width) // 2
        preview_y = (self.height - preview_height) // 2 - 50
        self.show_camera_preview(frame, (preview_x, preview_y), (preview_width, preview_height))
                
        # Test camera button
        test_rect = pygame.Rect(self.width//2 - 220, self.height - 100, 200, 60)
        if self.draw_button(test_rect, "Test Camera", active=True):
            self.initialize_camera()
            
        # Next button
        next_rect = pygame.Rect(self.width//2 + 20, self.height - 100, 200, 60)
        next_active = self.camera is not None
        if self.draw_button(next_rect, "Next Step", active=next_active):
            self.current_step = "projector_calibration"
            self.substep = 0
        
        # Update screen
        pygame.display.flip()

    def save_projector_calibration(self):
        """Save projector calibration data to file"""
        if self.projector_points is None or len(self.projector_points) != 4:
            return
            
        try:
            # Convert points to correct format
            points = np.array(self.projector_points, dtype=np.float32).tolist()
            
            # Save to YAML
            data = {"projector_points": points}
            with open("projector_calibration.yaml", "w") as f:
                yaml.dump(data, f)
                
            self.logger.info("Saved projector calibration")
        except Exception as e:
            self.logger.error(f"Error saving projector calibration: {e}")

    def save_color_calibration(self):
        """Save color calibration data to file"""
        try:
            # Convert calibration data to the required format
            data_to_save = {}
            
            for color in self.color_ranges:
                data_to_save[color] = [
                    [list(lower), list(upper)] 
                    for lower, upper in self.color_ranges[color]
                ]
                
            # Save to YAML
            with open("calibration.yaml", "w") as f:
                yaml.dump(data_to_save, f)
                
            self.logger.info("Saved color calibration")
        except Exception as e:
            self.logger.error(f"Error saving color calibration: {e}")

    def save_ball_calibration(self):
        """Save ball calibration data to file"""
        try:
            with open("ball_calibration.yaml", "w") as f:
                yaml.dump(self.ball_sizes, f)
            self.logger.info("Saved ball calibration")
        except Exception as e:
            self.logger.error(f"Error saving ball calibration: {e}")

    def get_calibration_position(self, position_name):
        """Get screen coordinates for a calibration position"""
        if self.projector_points is None or len(self.projector_points) != 4:
            return None
            
        points = np.array(self.projector_points)
    
        # Calculate dimensions of the projection area
        width = max(points[:, 0]) - min(points[:, 0])
        height = max(points[:, 1]) - min(points[:, 1])
        
        # Determine offset based on screen size (20% of the smaller dimension)
        offset = min(width, height) * 0.2
        
        # Center point
        center = tuple(np.mean(points, axis=0).astype(int))
        
        if position_name == "top_left":
            return int(points[0][0] + offset), int(points[0][1] + offset)
        elif position_name == "top_right":
            return int(points[1][0] - offset), int(points[1][1] + offset)
        elif position_name == "bottom_right":
            return int(points[2][0] - offset), int(points[2][1] - offset)
        elif position_name == "bottom_left":
            return int(points[3][0] + offset), int(points[3][1] - offset)
        elif position_name == "center":
            return center
        
        return None

    def calibrate_ball_position(self, ball_color, position_name):
        """Calibrate ball size at the current position"""
        frame = self.get_camera_frame()
        if frame is None:
            return
            
        # Get calibration position
        position = self.get_calibration_position(position_name)
        if position is None:
            return
            
        # Detect ball
        color_samples = self.color_ranges.get(ball_color, [])
        if not color_samples:
            return
            
        ball_center, ball_radius = self.detect_ball(
            frame, 
            color_samples, 
            {"min_size": 5, "max_size": 100}
        )
        
        if ball_center is None or ball_radius is None:
            return
            
        # Calculate distance from expected position
        dist = np.linalg.norm(np.array(ball_center) - np.array(position))
        if dist > 50:  # Too far from expected position
            return
            
        # Record the ball size
        self.ball_sizes[ball_color][position_name] = ball_radius
        self.logger.info(f"Calibrated {ball_color} ball at {position_name}: radius={ball_radius}")
        
        # Increment substep
        self.substep += 1

    def draw_projector_calibration(self):
        """Draw the projector calibration screen"""
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.title_font.render("Step 2: Projector Calibration", True, self.WHITE)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 50))
        
        # Instructions
        instructions = [
            "Point your camera at the projection area",
            "Click on the four corners of the projected area:",
            "Top-left, top-right, bottom-right, bottom-left"
        ]
        
        y = 100
        for line in instructions:
            text = self.text_font.render(line, True, self.WHITE)
            self.screen.blit(text, (self.width//2 - text.get_width()//2, y))
            y += 40
            
        # Camera preview with calibration overlay
        frame = self.get_camera_frame()
        
        # Draw calibration points on frame if available
        if frame is not None and self.projector_points is not None:
            for i, point in enumerate(self.projector_points):
                cv2.circle(frame, (int(point[0]), int(point[1])), 5, (0, 255, 0), -1)
                cv2.putText(
                    frame,
                    f"{i+1}",
                    (int(point[0]) + 10, int(point[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
        
        # Camera preview - make it larger (around 70% of screen width)
        preview_width = int(self.width * 0.7)
        preview_height = int(preview_width * 9/16)  # Maintain aspect ratio
        preview_x = (self.width - preview_width) // 2
        preview_y = (self.height - preview_height) // 2 - 50
        self.show_camera_preview(frame, (preview_x, preview_y), (preview_width, preview_height))
                
        # Reset button
        reset_rect = pygame.Rect(self.width//2 - 320, self.height - 80, 200, 60)
        if self.draw_button(reset_rect, "Reset Points"):
            self.projector_points = []
            self.substep = 0
            
        # Next button
        next_rect = pygame.Rect(self.width//2 + 120, self.height - 80, 200, 60)
        next_active = self.projector_points is not None and len(self.projector_points) == 4
        if self.draw_button(next_rect, "Next Step", active=next_active):
            # Save projector calibration
            self.save_projector_calibration()
            self.current_step = "color_calibration"
            self.substep = 0
            
        # Handle point selection
        if frame is not None and pygame.mouse.get_pressed()[0]:
            mouse_pos = pygame.mouse.get_pos()
            
            # Define camera preview area - using the same calculations as when displaying
            preview_width = int(self.width * 0.7)
            preview_height = int(preview_width * 9/16)
            preview_x = (self.width - preview_width) // 2
            preview_y = (self.height - preview_height) // 2 - 50
            
            # Check if mouse is within preview area
            if (preview_x <= mouse_pos[0] < preview_x + preview_width and 
                preview_y <= mouse_pos[1] < preview_y + preview_height):
                
                # Convert mouse position to frame coordinates using the correct preview dimensions
                frame_x = int((mouse_pos[0] - preview_x) * (frame.shape[1] / preview_width))
                frame_y = int((mouse_pos[1] - preview_y) * (frame.shape[0] / preview_height))
                
                # Check if coordinates are valid
                if (0 <= frame_x < frame.shape[1] and 
                    0 <= frame_y < frame.shape[0] and
                    self.substep < 4):
                    
                    # Initialize points list if needed
                    if self.projector_points is None:
                        self.projector_points = []
                        
                    # Add point if we have fewer than 4
                    if len(self.projector_points) < 4:
                        self.projector_points.append((frame_x, frame_y))
                        self.substep += 1
                        # Add delay to avoid multiple clicks
                        pygame.time.delay(300)
        
        # Update screen
        pygame.display.flip()

    def draw_color_calibration(self):
        """Draw the color calibration screen"""
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.title_font.render("Step 3: Color Calibration", True, self.WHITE)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 50))
        
        # Current ball color
        current_color = "blue" if self.substep < 5 else "yellow"
        color_text = self.text_font.render(f"Current Ball: {current_color.upper()}", True, 
                                          self.BLUE if current_color == "blue" else (255, 255, 0))
        self.screen.blit(color_text, (self.width//2 - color_text.get_width()//2, 100))
        
        # Instructions
        instructions = [
            f"Place the {current_color} ball in the camera view",
            f"Click on the ball to sample its color ({len(self.color_ranges[current_color])}/5 samples)"
        ]
        
        y = 140
        for line in instructions:
            text = self.text_font.render(line, True, self.WHITE)
            self.screen.blit(text, (self.width//2 - text.get_width()//2, y))
            y += 40

        # Freeze/unfreeze button
        freeze_rect = pygame.Rect(self.width//2 - 320, self.height - 80, 200, 60)
        freeze_text = "Unfreeze Camera" if self.is_frame_frozen else "Freeze Camera"
        freeze_color = self.GREEN if self.is_frame_frozen else self.BLUE

        if self.draw_button(freeze_rect, freeze_text, active=True):
            if self.is_frame_frozen:
                # Unfreeze
                self.is_frame_frozen = False
                self.frozen_frame = None
            else:
                # Freeze current frame
                self.is_frame_frozen = True
                current_frame = self.get_camera_frame()
                if current_frame is not None:
                    self.frozen_frame = current_frame.copy()
            
        # Camera preview
        if self.is_frame_frozen:
            # Use the stored frozen frame
            display_frame = self.frozen_frame
        else:
            # Get a new frame from the camera
            display_frame = self.get_camera_frame()

        preview_width = int(self.width * 0.7)
        preview_height = int(preview_width * 9/16)
        preview_x = (self.width - preview_width) // 2
        preview_y = (self.height - preview_height) // 2 - 50
        self.show_camera_preview(display_frame, (preview_x, preview_y), (preview_width, preview_height))

        # Add a "FROZEN" indicator if frame is frozen
        if self.is_frame_frozen:
            frozen_text = self.text_font.render("CAMERA FROZEN", True, self.RED)
            self.screen.blit(frozen_text, (preview_x + 20, preview_y + 20))
        # Show color samples if any
        if self.color_ranges[current_color]:
            # Display the current color ranges
            sample_text = self.text_font.render("Color Samples:", True, self.WHITE)
            self.screen.blit(sample_text, (100, 580))
            
            for i, (lower, upper) in enumerate(self.color_ranges[current_color]):
                # Draw color sample box
                color = tuple([(l+u)//2 for l, u in zip(lower, upper)])
                # Convert HSV to RGB for display
                color_rgb = cv2.cvtColor(
                    np.uint8([[[color[0], color[1], color[2]]]]), 
                    cv2.COLOR_HSV2RGB
                )[0][0].tolist()
                
                pygame.draw.rect(
                    self.screen, 
                    color_rgb, 
                    (160 + i*100, 580, 60, 40)
                )
        
        # Next button
        next_rect = pygame.Rect(self.width//2 + 120, self.height - 80, 200, 60)
        if current_color == "blue":
            next_active = len(self.color_ranges[current_color]) > 0
            next_text = "Next Color"
        else:
            next_active = len(self.color_ranges[current_color]) > 0
            next_text = "Next Step"
            
        if self.draw_button(next_rect, next_text, active=next_active):
            if current_color == "blue":
                self.substep = 5  # Move to yellow ball
            else:
                # Save color calibration
                self.save_color_calibration()
                self.current_step = "ball_calibration"
                self.substep = 0
        
        # Handle color sampling
        if pygame.mouse.get_pressed()[0]:
            mouse_pos = pygame.mouse.get_pos()
            
            # Define camera preview area
            preview_width = int(self.width * 0.7)
            preview_height = int(preview_width * 9/16)
            preview_x = (self.width - preview_width) // 2
            preview_y = (self.height - preview_height) // 2 - 50
            
            # Check if click is within camera preview area
            if (preview_x <= mouse_pos[0] < preview_x + preview_width and 
                preview_y <= mouse_pos[1] < preview_y + preview_height):
                
                # Get the frame we should sample from
                sampling_frame = self.frozen_frame if self.is_frame_frozen else display_frame
                
                if sampling_frame is not None:
                    # Convert mouse position to frame coordinates
                    frame_x = int((mouse_pos[0] - preview_x) * (sampling_frame.shape[1] / preview_width))
                    frame_y = int((mouse_pos[1] - preview_y) * (sampling_frame.shape[0] / preview_height))
                    
                    if 0 <= frame_x < sampling_frame.shape[1] and 0 <= frame_y < sampling_frame.shape[0]:
                        self.sample_color(sampling_frame, frame_x, frame_y, current_color)
                        # Add delay to avoid multiple clicks
                        pygame.time.delay(300)
        
        # Update screen
        pygame.display.flip()

    def draw_ball_calibration(self):
        """Draw the ball size calibration screen"""
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.title_font.render("Step 4: Ball Size Calibration", True, self.WHITE)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 50))
        
        # Determine current calibration point
        calibration_positions = ["top_left", "top_right", "bottom_right", "bottom_left", "center"]
        position_idx = self.substep % 5
        position_name = calibration_positions[position_idx]
        ball_color = "blue" if self.substep < 5 else "yellow"
        
        # Instructions
        instructions = [
            f"Place the {ball_color} ball at the {position_name.replace('_', ' ')} of the projection area",
            "Hold it there and press the Calibrate button"
        ]
        
        y = 100
        for line in instructions:
            text = self.text_font.render(line, True, self.WHITE)
            self.screen.blit(text, (self.width//2 - text.get_width()//2, y))
            y += 40
            
        # Progress
        progress = self.text_font.render(
            f"Progress: {self.substep}/10 positions calibrated", 
            True, 
            self.WHITE
        )
        self.screen.blit(progress, (self.width//2 - progress.get_width()//2, y + 20))
        
        # Camera preview with marker for current position
        frame = self.get_camera_frame()
        
        if frame is not None and self.projector_points is not None:
            # Draw current position marker
            position = self.get_calibration_position(position_name)
            if position:
                cv2.circle(frame, position, 10, (0, 0, 255), -1)
                
            # Draw already calibrated positions
            for pos_name in calibration_positions:
                if ball_color == "blue" and pos_name in self.ball_sizes["blue"]:
                    pos = self.get_calibration_position(pos_name)
                    radius = self.ball_sizes["blue"][pos_name]
                    cv2.circle(frame, pos, int(radius), (255, 0, 0), 2)
                elif ball_color == "yellow" and pos_name in self.ball_sizes["yellow"]:
                    pos = self.get_calibration_position(pos_name)
                    radius = self.ball_sizes["yellow"][pos_name]
                    cv2.circle(frame, pos, int(radius), (0, 255, 255), 2)
        
        # Camera preview - make it larger (around 70% of screen width)
        preview_width = int(self.width * 0.7)
        preview_height = int(preview_width * 9/16)  # Maintain aspect ratio
        preview_x = (self.width - preview_width) // 2
        preview_y = (self.height - preview_height) // 2 - 50
        self.show_camera_preview(frame, (preview_x, preview_y), (preview_width, preview_height))
                
        # Calibrate button
        calibrate_rect = pygame.Rect(self.width//2 - 100, self.height - 140, 200, 60)
        if self.draw_button(calibrate_rect, "Calibrate Position"):
            self.calibrate_ball_position(ball_color, position_name)
            
        # Next button
        next_rect = pygame.Rect(self.width//2 + 120, self.height - 80, 200, 60)
        next_active = self.substep >= 10  # All positions calibrated
        if self.draw_button(next_rect, "Finish", active=next_active):
            # Save ball calibration
            self.save_ball_calibration()
            self.current_step = "complete"
            
        # Update screen
        pygame.display.flip()

    def draw_complete_screen(self):
        """Draw the completion screen"""
        self.screen.fill(self.BLACK)
        
        # Title
        title = self.title_font.render("Calibration Complete!", True, self.GREEN)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 150))
        
        # Message
        message = self.text_font.render("Your game is now calibrated and ready to play!", True, self.WHITE)
        self.screen.blit(message, (self.width//2 - message.get_width()//2, 250))
        
        # Details
        details = [
            "Calibration data saved to:",
            "- projector_calibration.yaml",
            "- calibration.yaml",
            "- ball_calibration.yaml"
        ]
        
        y = 350
        for line in details:
            text = self.text_font.render(line, True, self.WHITE)
            self.screen.blit(text, (self.width//2 - text.get_width()//2, y))
            y += 40
            
        # Finish button
        finish_rect = pygame.Rect(self.width//2 - 100, self.height - 150, 200, 60)
        if self.draw_button(finish_rect, "Start Game!"):
            self.calibration_complete = True
            
        # Update screen
        pygame.display.flip()
        
    def run(self):
        """Run the calibration wizard"""
        running = True
        clock = pygame.time.Clock()
        
        try:
            while running and not self.calibration_complete:
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                
                # Draw current step
                if self.current_step == "welcome":
                    self.draw_welcome_screen()
                elif self.current_step == "camera_setup":
                    self.draw_camera_setup()
                elif self.current_step == "projector_calibration":
                    self.draw_projector_calibration()
                elif self.current_step == "color_calibration":
                    self.draw_color_calibration()
                elif self.current_step == "ball_calibration":
                    self.draw_ball_calibration()
                elif self.current_step == "complete":
                    self.draw_complete_screen()
                    
                # Cap framerate
                clock.tick(30)
                
        finally:
            # Ensure camera is always released, even if an exception occurs
            self.release_camera()
            pygame.quit()
            
        return self.calibration_complete

# Usage
if __name__ == "__main__":
    wizard = CalibrationWizard()
    success = wizard.run()
    
    if success:
        print("Calibration completed successfully!")
        # Start the game
        import main
        main.start_game_and_camera()
    else:
        print("Calibration was cancelled or failed.")