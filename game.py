import pygame
import random
import sys
import os
import math
from time import time
import yaml
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any

from enhanced_effects import EffectsManager
from game_analytics import GameAnalytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='game.log'
)
logger = logging.getLogger('BalloonGame')

# Constants
WIDTH = 1920
HEIGHT = 1080
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GOLD = (255, 215, 0)
PURPLE = (128, 0, 128)
PINK = (255, 105, 180)
BALLOON_SIZE = 200
GAME_DURATION = 120  # seconds
POP_DURATION = 8  # frames

# Game settings
DIFFICULTY_SETTINGS = {
    'easy': {'spawn_rate': 210, 'speed_range': (1, 2), 'max_balloons': 4, 'special_chance': 0.1},
    'normal': {'spawn_rate': 180, 'speed_range': (2, 3), 'max_balloons': 6, 'special_chance': 0.15},
    'hard': {'spawn_rate': 150, 'speed_range': (2, 4), 'max_balloons': 8, 'special_chance': 0.2}
}

# Initialize pygame
pygame.init()
pygame.mixer.init()
# Set the SDL window position to the projector monitor (adjust as needed)
if os.name == 'nt':
    os.environ['SDL_VIDEO_WINDOW_POS'] = "2000,0"

# Load sound effects
try:
    POP_GREEN = pygame.mixer.Sound("sound/pop_balloon.wav")
    POP_RED = pygame.mixer.Sound("sound/pop_red_ballon.wav")
    BONUS_SOUND = pygame.mixer.Sound("sound/bonus_balloon.wav")  # Reuse existing sound
    POWERUP_SOUND = pygame.mixer.Sound("sound/pop_balloon.wav")  # Reuse existing sound
    COMBO_SOUND = pygame.mixer.Sound("sound/pop_red_ballon.wav")  # Reuse existing sound
    PENALTY_SOUND = pygame.mixer.Sound("sound/penalty_balloon.wav")  # Reuse existing sound
except pygame.error as e:
    logger.error(f"Failed to load sound: {e}")
    # Create silent sound as fallback
    POP_GREEN = pygame.mixer.Sound(buffer=bytearray(44100))  # 1 second of silence
    POP_RED = pygame.mixer.Sound(buffer=bytearray(44100))
    BONUS_SOUND = pygame.mixer.Sound(buffer=bytearray(44100))
    POWERUP_SOUND = pygame.mixer.Sound(buffer=bytearray(44100))
    COMBO_SOUND = pygame.mixer.Sound(buffer=bytearray(44100))


class SoundManager:
    """Manages game sound effects with volume control and caching"""
    
    def __init__(self, volume: float = 0.7):
        self.volume = volume
        self.enabled = True
        self.sounds = {}  # Cache for loaded sounds
        self.channels = {}  # Track channels for sound categories
        
        # Initialize channel groups
        for i, category in enumerate(['balloon', 'powerup', 'ui', 'ambient']):
            self.channels[category] = pygame.mixer.Channel(i)
            self.channels[category].set_volume(volume)
    
    def load_sound(self, sound_file: str) -> Optional[pygame.mixer.Sound]:
        """Load a sound file with caching"""
        if sound_file in self.sounds:
            return self.sounds[sound_file]
            
        try:
            sound = pygame.mixer.Sound(sound_file)
            self.sounds[sound_file] = sound
            return sound
        except pygame.error as e:
            logger.error(f"Could not load sound {sound_file}: {e}")
            # Create silent sound as fallback
            fallback = pygame.mixer.Sound(buffer=bytearray(22050))  # 0.5 seconds of silence
            self.sounds[sound_file] = fallback
            return fallback
    
    def play(self, sound_file: str, category: str = 'balloon', volume_scale: float = 1.0, 
             pitch_shift: float = 1.0) -> None:
        """Play a sound with effects"""
        if not self.enabled:
            return
            
        sound = self.load_sound(sound_file)
        
        # Apply volume scaling (allows for variations in volume)
        effective_volume = min(1.0, self.volume * volume_scale)
        
        # Get the appropriate channel
        channel = self.channels.get(category, self.channels['balloon'])
        
        # Set individual sound volume
        sound.set_volume(effective_volume)
        
        # Play on the channel
        channel.play(sound)
    
    def set_volume(self, volume: float, category: str = None) -> None:
        """Set volume for all sounds or a specific category"""
        self.volume = max(0.0, min(1.0, volume))
        
        if category and category in self.channels:
            self.channels[category].set_volume(self.volume)
        else:
            # Set for all channels
            for channel in self.channels.values():
                channel.set_volume(self.volume)
    
    def stop_all(self) -> None:
        """Stop all currently playing sounds"""
        for channel in self.channels.values():
            channel.stop()
            
    def enable(self, enabled: bool = True) -> None:
        """Enable or disable all sounds"""
        self.enabled = enabled
        if not enabled:
            self.stop_all()
            
    def play_powerup_sound(self, powerup_type=None):
        """Play sound for a powerup with pitch variation based on type"""
        if not self.enabled:
            return
            
        # Choose a default sound file that's likely to exist
        sound_file = "sound/pop_balloon.wav"
        
        # Map power-up types to sound files
        sound_files = {
            'slow': "sound/slow_powerup.wav",
            'double': "sound/double_powerup.wav", 
            'magnet': "sound/magnet_powerup.wav",
            'multiball': "sound/multiball_powerup.wav",
            'giant': "sound/giant_powerup.wav",
            'chain': "sound/chain_powerup.wav",
            'freeze': "sound/freeze_powerup.wav"
        }
        
        # Try to get the specific sound file for this power-up
        if powerup_type in sound_files:
            # Check if the file exists
            if os.path.exists(sound_files[powerup_type]):
                sound_file = sound_files[powerup_type]
            elif os.path.exists("sound/powerup_sound.wav"):
                # Fall back to generic power-up sound
                sound_file = "sound/powerup_sound.wav"
        
        try:
            # Load and play the sound, with proper error handling
            sound = self.load_sound(sound_file)
            sound.set_volume(min(1.0, self.volume * 0.8))
            self.channels['powerup'].play(sound)
        except Exception as e:
            # Log the error but don't crash
            print(f"Error playing power-up sound: {e}")


class Particle:
    def __init__(self, x, y, color, size_range=(3, 8), speed_range=(2, 8)):
        self.x = x
        self.y = y
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(*speed_range)
        self.dx = speed * math.cos(angle)
        self.dy = speed * math.sin(angle)
        # Convert size_range to integers if they're floats
        size_min = int(size_range[0])
        size_max = int(size_range[1])
        self.size = random.randint(size_min, size_max)


        self.life = POP_DURATION
        self.original_size = self.size
        
        # Add slight color variation
        r, g, b = color[:3]
        variation = 30
        self.color = (
            max(0, min(255, r + random.randint(-variation, variation))),
            max(0, min(255, g + random.randint(-variation, variation))),
            max(0, min(255, b + random.randint(-variation, variation)))
        )

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.dy += 0.2  # Gravity
        self.life -= 1
        life_ratio = self.life / POP_DURATION
        self.size = max(0, self.original_size * life_ratio)


class StarParticle(Particle):
    """Particle used for star/sparkle effects"""
    
    def __init__(self, x, y, color, size=3, lifetime=15):
        size_min = int(size)
        size_max = int(size * 2)
        super().__init__(x, y, color, (size_min, size_max), (1, 3))
        self.life = lifetime
        self.angle = random.uniform(0, 2 * math.pi)
        self.pulse_rate = random.uniform(0.1, 0.3)
    
    def update(self):
        """Update particle properties"""
        super().update()
        
        # Rotate and pulse
        self.angle += 0.1
        pulse = 0.7 + 0.3 * math.sin(self.life * self.pulse_rate)
        self.size = self.original_size * pulse * (self.life / POP_DURATION)


class TrailParticle(Particle):
    """Particle used for motion trails"""
    
    def __init__(self, x, y, color, size=5, lifetime=20):
        size_min = int(size)
        size_max = int(size)
        super().__init__(x, y, color, (size_min, size_max), (0.5, 1.5))
        
        self.life = lifetime
        self.dx *= 0.2  # Slower horizontal movement
        self.dy *= 0.2  # Slower vertical movement
    
    def update(self):
        """Update particle properties"""
        super().update()
        
        # Fade more rapidly
        life_ratio = (self.life / POP_DURATION) ** 2
        self.size = max(0, self.original_size * life_ratio)


class PopAnimation(pygame.sprite.Sprite):
    def __init__(self, x, y, color, particle_count=20, special=False):
        super().__init__()
        self.image = pygame.Surface((BALLOON_SIZE * 3, BALLOON_SIZE * 3), pygame.SRCALPHA)
        self.color = color
        self.frame = 0
        self.rect = self.image.get_rect(center=(x + BALLOON_SIZE // 2, y + BALLOON_SIZE // 2))
        
        # Create more particles and with bigger sizes for special balloons
        size_range = (4, 12) if special else (3, 8)
        speed_range = (3, 10) if special else (2, 8)
        count = particle_count * 2 if special else particle_count
        
        self.particles = [
            Particle(
                BALLOON_SIZE * 1.5, 
                BALLOON_SIZE * 1.5, 
                color,
                size_range,
                speed_range
            ) for _ in range(count)
        ]
        
        # Add special star particles for bonus balloons
        if special:
            star_color = GOLD if color == RED else GOLD
            self.particles.extend([
                StarParticle(
                    BALLOON_SIZE * 1.5 + random.uniform(-20, 20),
                    BALLOON_SIZE * 1.5 + random.uniform(-20, 20),
                    star_color,
                    size=random.uniform(3, 6),
                    lifetime=random.randint(10, 20)
                ) for _ in range(int(count * 0.3))
            ])
        
    def update(self):
        self.frame += 1
        if self.frame >= POP_DURATION:
            self.kill()
        else:
            self.image.fill((0, 0, 0, 0))
            for particle in self.particles:
                particle.update()
                if particle.size > 0:
                    # Add slight transparency based on lifetime
                    alpha = int(255 * particle.life / POP_DURATION)
                    pygame.draw.circle(
                        self.image, 
                        (*particle.color, alpha),
                        (int(particle.x), int(particle.y)),
                        int(particle.size)
                    )


class PowerUp(pygame.sprite.Sprite):
    """Power-up item that provides special abilities when collected"""
    TYPES = {
        'slow': {'color': (100, 100, 255), 'effect': 'Slow Motion', 'duration': 5, 'rarity': 'common'},
        'double': {'color': (255, 215, 0), 'effect': 'Double Points', 'duration': 7, 'rarity': 'common'},
        'magnet': {'color': (255, 100, 100), 'effect': 'Balloon Magnet', 'duration': 6, 'rarity': 'common'},
        'multiball': {'color': (255, 50, 255), 'effect': 'Multi-Ball', 'duration': 8, 'rarity': 'uncommon'},
        'giant': {'color': (200, 100, 50), 'effect': 'Giant Ball', 'duration': 10, 'rarity': 'uncommon'},
        'freeze': {'color': (0, 200, 255), 'effect': 'Freeze', 'duration': 3, 'rarity': 'rare'},
        'chain': {'color': (100, 255, 100), 'effect': 'Chain Reaction', 'duration': 5, 'rarity': 'rare'}
    }
    
    # Rarity weights for random selection
    RARITY_WEIGHTS = {
        'common': 0.7,
        'uncommon': 0.25,
        'rare': 0.05
    }
    
    def __init__(self, power_type=None):
        super().__init__()
        # If no type specified, randomly select one based on rarity
        if power_type is None:
            rarities = list(self.RARITY_WEIGHTS.keys())
            weights = [self.RARITY_WEIGHTS[r] for r in rarities]
            selected_rarity = random.choices(rarities, weights=weights, k=1)[0]
            
            # Find powerups of this rarity
            valid_types = [
                p for p, info in self.TYPES.items() 
                if info.get('rarity', 'common') == selected_rarity
            ]
            
            if valid_types:
                power_type = random.choice(valid_types)
            else:
                power_type = 'slow'  # Default fallback
        
        self.type = power_type
        info = self.TYPES.get(power_type, {})
        self.effect = info.get('effect', 'Unknown Effect')
        self.duration = info.get('duration', 5) * FPS
        self.color = info.get('color', (255, 255, 255))
        self.rarity = info.get('rarity', 'common')
        
        # Create power-up appearance
        self.size = BALLOON_SIZE // 2
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.original_image = self.image.copy()
        
        # Draw based on rarity
        self.draw_powerup()
        
        # Set initial position
        self.rect = self.image.get_rect()
        self.rect.centerx = random.randint(self.size, WIDTH - self.size)
        self.rect.y = -self.size  # Start above the screen
        
        # Movement
        self.speed = random.uniform(1.5, 3.0)
        self.wobble = random.randint(20, 50)
        self.wobble_speed = random.uniform(0.05, 0.1)
        self.start_x = self.rect.centerx
        self.time = random.uniform(0, 6.28)  # Random phase
        
        # Animation
        self.angle = 0
        self.pulse_factor = 1.0
        self.pulse_direction = 0.02
        self.particles = []
        
    def draw_powerup(self):
        """Draw the powerup with a unique shape and icon based on its type"""
        # Clear the surface
        self.image.fill((0, 0, 0, 0))
        
        # Draw based on powerup type instead of rarity
        if self.type == 'slow':
            self._draw_slow_powerup()
        elif self.type == 'double':
            self._draw_double_powerup()
        elif self.type == 'magnet':
            self._draw_magnet_powerup()
        elif self.type == 'multiball':
            self._draw_multiball_powerup()
        elif self.type == 'giant':
            self._draw_giant_powerup()
        elif self.type == 'freeze':
            self._draw_freeze_powerup()
        elif self.type == 'chain':
            self._draw_chain_powerup()
        else:
            # Fallback for any undefined powerup types
            self._draw_generic_powerup()
        
        # Store as original image for rotation and scaling
        self.original_image = self.image.copy()
        
    def _draw_slow_powerup(self):
        """Draw a clock-like shape for slow motion powerup"""
        center = (self.size // 2, self.size // 2)
        radius = self.size // 2
        
        # Draw circular clock face
        pygame.draw.circle(self.image, self.color, center, radius)
        
        # Add clock-like details
        pygame.draw.circle(self.image, (255, 255, 255), center, radius - 4, 2)
        
        try:
            # Try to load hourglass image
            hourglass_img = pygame.image.load('png/hourglass_icon.png').convert_alpha()
            icon_size = self.size // 2
            hourglass_img = pygame.transform.scale(hourglass_img, (icon_size, icon_size))
            icon_pos = (center[0] - icon_size // 2, center[1] - icon_size // 2)
            self.image.blit(hourglass_img, icon_pos)
        except pygame.error:
            # Fallback to drawing clock hands
            # Hour hand
            hour_angle = math.pi / 6  # 30 degrees
            hour_length = radius * 0.5
            hour_end = (
                center[0] + int(hour_length * math.sin(hour_angle)), 
                center[1] - int(hour_length * math.cos(hour_angle))
            )
            pygame.draw.line(self.image, (255, 255, 255), center, hour_end, 3)
            
            # Minute hand
            minute_angle = math.pi / 2  # 90 degrees
            minute_length = radius * 0.7
            minute_end = (
                center[0] + int(minute_length * math.sin(minute_angle)), 
                center[1] - int(minute_length * math.cos(minute_angle))
            )
            pygame.draw.line(self.image, (255, 255, 255), center, minute_end, 2)
            
            # Center dot
            pygame.draw.circle(self.image, (255, 255, 255), center, 3)

    def _draw_double_powerup(self):
        """Draw a coin with X2 for double points powerup"""
        center = (self.size // 2, self.size // 2)
        
        # Draw a circular coin shape
        pygame.draw.circle(self.image, self.color, center, self.size // 2)
        
        # Add a ring to make it look like a coin
        pygame.draw.circle(self.image, (255, 215, 0), center, self.size // 2 - 2, 3)  # Gold ring
        
        # Draw "×2" text
        font = pygame.font.Font(None, self.size // 2)
        text = font.render("×2", True, (255, 255, 255))
        text_rect = text.get_rect(center=center)
        self.image.blit(text, text_rect)
        
        # Add some coin-like details
        coin_detail_radius = self.size // 2 - 6
        pygame.draw.circle(self.image, (255, 215, 0), center, coin_detail_radius, 1)

    def _draw_magnet_powerup(self):
        """Draw a circle with magnet image for magnet powerup"""
        center = (self.size // 2, self.size // 2)
        
        # Draw a circular base
        pygame.draw.circle(self.image, self.color, center, self.size // 2)
        
        try:
            # Try to load magnet image
            magnet_img = pygame.image.load('png/magnet_icon.png').convert_alpha()
            icon_size = self.size // 2
            magnet_img = pygame.transform.scale(magnet_img, (icon_size, icon_size))
            icon_pos = (center[0] - icon_size // 2, center[1] - icon_size // 2)
            self.image.blit(magnet_img, icon_pos)
        except pygame.error:
            # Fallback to drawing a simple magnet
            # Draw magnet body
            magnet_width = self.size // 3
            magnet_height = self.size // 2
            magnet_x = center[0] - magnet_width // 2
            magnet_y = center[1] - magnet_height // 2
            
            # Draw the magnet body in white
            pygame.draw.rect(self.image, (255, 255, 255), 
                            (magnet_x, magnet_y, magnet_width, magnet_height))
            
            # North pole (red)
            pygame.draw.rect(self.image, (255, 0, 0), 
                            (magnet_x, magnet_y, magnet_width, magnet_height // 3))
            # South pole (blue)
            pygame.draw.rect(self.image, (0, 0, 255), 
                            (magnet_x, magnet_y + 2*magnet_height//3, 
                            magnet_width, magnet_height // 3))

    def _draw_multiball_powerup(self):
        """Draw three distinct stacked balls for multiball powerup"""
        center = (self.size // 2, self.size // 2)
        
        # Calculate ball parameters
        ball_radius = self.size // 4  # Slightly smaller for better visibility
        x_offset = ball_radius * 0.75  # Horizontal offset between balls
        y_offset = ball_radius * 0.75  # Vertical offset between balls
        
        # Positions for the three balls (bottom-left to top-right)
        positions = [
            (center[0] - x_offset, center[1] + y_offset),  # Bottom left
            (center[0], center[1]),                        # Center
            (center[0] + x_offset, center[1] - y_offset)   # Top right
        ]
        
        # Draw the balls from back to front
        for x, y in positions:
            # Fill ball with powerup color
            pygame.draw.circle(self.image, self.color, (int(x), int(y)), ball_radius)
            
            # Add black outline
            pygame.draw.circle(self.image, (0, 0, 0), (int(x), int(y)), ball_radius, 2)
    

    def _draw_giant_powerup(self):
        """Draw a red circle with white outward arrows for giant ball powerup"""
        center = (self.size // 2, self.size // 2)
        
        # Draw main circle in red
        pygame.draw.circle(self.image, (255, 0, 0), center, self.size // 2)  # Red circle
        
        # Draw expanding rings
        for i in range(1, 4):
            radius = self.size // 2 - i * 5
            pygame.draw.circle(self.image, (255, 255, 255), center, radius, 1)
        
        # Draw outward arrows in white
        arrow_length = self.size // 4
        head_size = self.size // 10
        arrow_color = (255, 255, 255)  # White arrows
        
        for angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
            # Arrow start and end points
            start_x = center[0] + int((self.size//4) * math.cos(angle))
            start_y = center[1] + int((self.size//4) * math.sin(angle))
            end_x = center[0] + int((self.size//2 - 2) * math.cos(angle))
            end_y = center[1] + int((self.size//2 - 2) * math.sin(angle))
            
            # Draw arrow line
            pygame.draw.line(self.image, arrow_color, 
                            (start_x, start_y), (end_x, end_y), 2)
            
            # Draw arrow head
            left_angle = angle + math.pi/4
            right_angle = angle - math.pi/4
            
            head_left_x = end_x - int(head_size * math.cos(left_angle))
            head_left_y = end_y - int(head_size * math.sin(left_angle))
            
            head_right_x = end_x - int(head_size * math.cos(right_angle))
            head_right_y = end_y - int(head_size * math.sin(right_angle))
            
            pygame.draw.line(self.image, arrow_color, 
                            (end_x, end_y), (head_left_x, head_left_y), 2)
            pygame.draw.line(self.image, arrow_color, 
                            (end_x, end_y), (head_right_x, head_right_y), 2)

    def _draw_freeze_powerup(self):
        """Draw a hexagon/snowflake shape for freeze powerup"""
        center = (self.size // 2, self.size // 2)
        radius = self.size // 2
        
        # Draw hexagon base
        points = []
        for i in range(6):
            angle = math.pi/2 + 2 * math.pi * i / 6
            points.append((
                center[0] + int(radius * math.cos(angle)),
                center[1] + int(radius * math.sin(angle))
            ))
        pygame.draw.polygon(self.image, self.color, points)
        
        try:
            # Try to load snowflake image
            snowflake_img = pygame.image.load('png/snowflake_icon.png').convert_alpha()
            icon_size = self.size // 2
            snowflake_img = pygame.transform.scale(snowflake_img, (icon_size, icon_size))
            icon_pos = (center[0] - icon_size // 2, center[1] - icon_size // 2)
            self.image.blit(snowflake_img, icon_pos)
        except pygame.error:
            # Fallback to drawing snowflake
            for i in range(6):
                angle = math.pi/3 * i
                
                # Main arm
                end_x = center[0] + int(radius * 0.8 * math.cos(angle))
                end_y = center[1] + int(radius * 0.8 * math.sin(angle))
                pygame.draw.line(self.image, (255, 255, 255), center, (end_x, end_y), 2)
                
                # Branch 1
                branch1_angle = angle + math.pi/6
                branch1_length = radius * 0.3
                branch1_x = end_x + int(branch1_length * math.cos(branch1_angle))
                branch1_y = end_y + int(branch1_length * math.sin(branch1_angle))
                pygame.draw.line(self.image, (255, 255, 255), (end_x, end_y), 
                                (branch1_x, branch1_y), 2)
                
                # Branch 2
                branch2_angle = angle - math.pi/6
                branch2_length = radius * 0.3
                branch2_x = end_x + int(branch2_length * math.cos(branch2_angle))
                branch2_y = end_y + int(branch2_length * math.sin(branch2_angle))
                pygame.draw.line(self.image, (255, 255, 255), (end_x, end_y), 
                                (branch2_x, branch2_y), 2)

    def _draw_chain_powerup(self):
        """Draw a circle with chain image for chain reaction powerup"""
        center = (self.size // 2, self.size // 2)
        
        # Draw circular base
        pygame.draw.circle(self.image, self.color, center, self.size // 2)
        
        try:
            # Try to load chain image
            chain_img = pygame.image.load('png/chain_icon.png').convert_alpha()
            icon_size = self.size // 2
            chain_img = pygame.transform.scale(chain_img, (icon_size, icon_size))
            icon_pos = (center[0] - icon_size // 2, center[1] - icon_size // 2)
            self.image.blit(chain_img, icon_pos)
        except pygame.error:
            # Fallback to drawing chain links
            # Draw two interlocking circles as chain links
            link1_rect = pygame.Rect(
                center[0] - self.size//4, 
                center[1] - self.size//8,
                self.size//4,
                self.size//4
            )
            link2_rect = pygame.Rect(
                center[0] - self.size//8, 
                center[1] - self.size//8,
                self.size//4,
                self.size//4
            )
            
            pygame.draw.ellipse(self.image, (255, 255, 255), link1_rect, 2)
            pygame.draw.ellipse(self.image, (255, 255, 255), link2_rect, 2)

    def _draw_generic_powerup(self):
        """Fallback drawing for any undefined powerup types"""
        center = (self.size // 2, self.size // 2)
        
        # Draw a basic circle
        pygame.draw.circle(self.image, self.color, center, self.size // 2)
        
        # Draw a question mark
        font = pygame.font.Font(None, self.size // 2)
        text = font.render("?", True, (255, 255, 255))
        text_rect = text.get_rect(center=center)
        self.image.blit(text, text_rect)
    
    def update(self):
        """Update powerup position and animation"""
        # Move down
        self.rect.y += self.speed
        
        # Wobble side to side
        self.time += self.wobble_speed
        self.rect.centerx = self.start_x + int(math.sin(self.time) * self.wobble)
        
        # Rotate and pulse
        self.angle = (self.angle + 2) % 360
        self.pulse_factor += self.pulse_direction
        if self.pulse_factor > 1.2 or self.pulse_factor < 0.8:
            self.pulse_direction *= -1
            
        # Apply rotation and scaling
        scaled_size = int(self.size * self.pulse_factor)
        self.image = pygame.transform.scale(self.original_image, (scaled_size, scaled_size))
        self.image = pygame.transform.rotate(self.image, self.angle)
        old_center = self.rect.center
        self.rect = self.image.get_rect()
        self.rect.center = old_center
        
        # Remove if it goes off screen
        if self.rect.top > HEIGHT:
            self.kill()


class Balloon(pygame.sprite.Sprite):
    """Standard balloon that moves upward"""
    def __init__(self, color, speed_range, balloon_type="normal"):
        super().__init__()
        self.color = color
        self.balloon_type = balloon_type
        self.points = 1  # Default points
        
        # Set properties based on balloon type
        if balloon_type == "bonus":
            self.points = 3
            glow_color = GOLD
        elif balloon_type == "penalty":
            self.points = -2
            glow_color = (100, 0, 0)  # Dark red
        else:
            glow_color = None
        
        # Load the appropriate balloon image
        try:
            if self.color == RED:
                self.image = pygame.image.load('png/red_balloon.png').convert_alpha()
            else:
                self.image = pygame.image.load('png/green_balloon.png').convert_alpha()
                
            self.image = pygame.transform.scale(
                self.image, 
                (BALLOON_SIZE, BALLOON_SIZE)
            )
        except pygame.error as e:
            logger.error(f"Failed to load balloon image: {e}")
            # Create a fallback balloon if image loading fails
            self.image = pygame.Surface(
                (BALLOON_SIZE, BALLOON_SIZE), 
                pygame.SRCALPHA
            )
            pygame.draw.circle(
                self.image, 
                color, 
                (BALLOON_SIZE//2, BALLOON_SIZE//2), 
                BALLOON_SIZE//2
            )
        

        # Add special effects for bonus/penalty balloons
        if glow_color:
            glow_surface = pygame.Surface((BALLOON_SIZE, BALLOON_SIZE), pygame.SRCALPHA)
            center_x = BALLOON_SIZE // 2
            center_y = BALLOON_SIZE // 2
            offset = BALLOON_SIZE // 4
            
            if balloon_type == "bonus":
                # Add a gold ring for bonus balloons
                shift_y_c = 15
                pygame.draw.circle(
                glow_surface, 
                glow_color, 
                (center_x, center_y - shift_y_c), 
                BALLOON_SIZE//2 - 20, 
                6  # Thickness
                )
                # Add a star in the center
                shift_y_s = 10 
                points = []
                for i in range(5):
                    angle = math.pi/2 + (2*math.pi/5) * i
                    points.append((
                        BALLOON_SIZE//2 + int(BALLOON_SIZE//5 * math.cos(angle)),
                        BALLOON_SIZE//2 - shift_y_s + int(BALLOON_SIZE//5 * math.sin(angle))
                    ))
                    angle += math.pi/5
                    points.append((
                        BALLOON_SIZE//2 + int(BALLOON_SIZE//10 * math.cos(angle)),
                        BALLOON_SIZE//2 - shift_y_s + int(BALLOON_SIZE//10 * math.sin(angle))
                    ))
                pygame.draw.polygon(glow_surface, GOLD, points)
                
            elif balloon_type == "penalty":
                # Add an X mark for penalty balloons
                line_width = 8
                shift_y = 13
                pygame.draw.line(
                    glow_surface, 
                    glow_color,
                    (center_x - offset, center_y - offset - shift_y), 
                    (center_x + offset, center_y + offset - shift_y), 
                    line_width
                )
                pygame.draw.line(
                    glow_surface, 
                    glow_color,
                    (center_x + offset, center_y - offset - shift_y), 
                    (center_x - offset, center_y + offset - shift_y),  
                    line_width
                )
            
            # Blend the glow onto the balloon image
            self.image.blit(glow_surface, (0, 0))
        
        self.rect = self.image.get_rect()
        
        # Set initial position
        if color == RED:
            # Red balloons on left side
            self.rect.x = random.randint(0, WIDTH // 2 - BALLOON_SIZE)
        else:
            # Green balloons on right side
            self.rect.x = random.randint(WIDTH // 2, WIDTH - BALLOON_SIZE)
            
        self.rect.y = HEIGHT
        
        # Movement properties
        base_speed = random.randint(*speed_range)
        if balloon_type == "bonus":
            # Bonus balloons move slightly faster
            self.speed = base_speed * 1.5
        elif balloon_type == "penalty":
            # Penalty balloons move slightly slower
            self.speed = base_speed * 0.8
        else:
            self.speed = base_speed
            
        self.wobble = random.randint(0, 40)  # How much it wobbles
        self.wobble_speed = random.uniform(0.02, 0.06)  # How fast it wobbles
        self.start_x = self.rect.x
        self.time = random.uniform(0, 6.28)  # Random starting phase
        
        # Animation properties
        self.pulse = 0
        self.pulse_speed = random.uniform(0.03, 0.07)
        self.pulse_size = random.randint(3, 8)
        
        # Frozen state for freeze powerup
        self.frozen = False
        self.original_speed = self.speed
        # Store a copy of the original image for scaling effects
        self.original_image = self.image.copy()
        
    def update(self, powerups=None):
        # Skip update if frozen
        if self.frozen:
            return True
            

        # Access active powerups from the game instance
        if powerups is None:
            powerups = {}
            
        # Apply slow motion effect if active
        slow_factor = 0.5 if 'slow' in powerups else 1.0
        
        # Update vertical position
        self.rect.y -= self.speed * slow_factor
        
        # Apply horizontal wobble
        self.time += self.wobble_speed * slow_factor
        self.rect.x = self.start_x + int(math.sin(self.time) * self.wobble)
        
        # Apply balloon magnet effect if active
        if powerups and 'magnet' in powerups:
            # Move toward center of screen with stronger attraction
            center_x = WIDTH // 2
            center_y = HEIGHT // 3
            
            # Calculate distance-based attraction strength (stronger pull when further away)
            dx = center_x - self.rect.centerx
            dy = center_y - self.rect.centery
            distance = max(1, math.sqrt(dx*dx + dy*dy))
            
            # EXTREME attraction (10-20 pixels per frame)
            base_strength = 10.0
            attraction_strength = base_strength + (distance / 100)
            
            # Normalize and apply
            if distance > 10:  # Only apply if not already at center
                # Calculate movement with dramatic pull
                move_x = dx / distance * attraction_strength
                move_y = dy / distance * attraction_strength
                
                # Apply movement - much stronger effect
                self.rect.x += int(move_x)
                self.rect.y += int(move_y)
                
                # Override normal wobble to create a direct path
                self.start_x = self.rect.x

        # ---  Apply giant effect to visually scale the balloon ---
        if 'giant' in powerups:
            scale = 1.5  # or a higher value if desired
            new_size = int(BALLOON_SIZE * scale)
            # Use the original image to avoid cumulative distortion
            self.image = pygame.transform.scale(self.original_image, (new_size, new_size))
            # Re-center the balloon so it doesn't jump around
            self.rect = self.image.get_rect(center=self.rect.center)
        else:
            # Optional: Reset to normal size if the giant powerup is not active.
            self.image = pygame.transform.scale(self.original_image, (BALLOON_SIZE, BALLOON_SIZE))
            self.rect = self.image.get_rect(center=self.rect.center)
    
        
        # Remove if it goes off screen
        if self.rect.bottom < 0:
            self.kill()
            return False
            
        return True


class SmartBalloon(Balloon):
    """A balloon with more advanced movement patterns"""
    def __init__(self, color, speed_range, balloon_type="smart"):
        super().__init__(color, speed_range, balloon_type)
        self.behavior = random.choice(["zigzag", "spiral", "bounce", "accelerate"])
        self.behavior_timer = 0
        self.points = 2  # Worth more points due to difficulty
        
        # Add a distinctive visual marker for smart balloons
        # Draw a small icon to indicate behavior
        indicator = pygame.Surface((BALLOON_SIZE, BALLOON_SIZE), pygame.SRCALPHA)
        icon_size = BALLOON_SIZE // 5
        icon_color = BLACK
        icon_pos = (BALLOON_SIZE // 2, BALLOON_SIZE // 2 - BALLOON_SIZE // 3)
        
        if self.behavior == "zigzag":
            # Draw zigzag pattern
            points = [(0, 0), (icon_size//2, -icon_size//2), 
                      (icon_size, 0), (icon_size*1.5, -icon_size//2), (icon_size*2, 0)]
            # Offset points
            points = [(x + icon_pos[0] - icon_size, y + icon_pos[1]) for x, y in points]
            pygame.draw.lines(indicator, icon_color, False, points, 2)
        elif self.behavior == "spiral":
            # Draw spiral
            pygame.draw.circle(indicator, icon_color, icon_pos, icon_size//2, 2)
            # Draw arrow inside
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0] - icon_size//4, icon_pos[1]),
                             (icon_pos[0] + icon_size//4, icon_pos[1]), 2)
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0] + icon_size//4, icon_pos[1]),
                             (icon_pos[0], icon_pos[1] - icon_size//4), 2)
        elif self.behavior == "bounce":
            # Draw bounce arrow
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0] - icon_size//2, icon_pos[1] - icon_size//2),
                             (icon_pos[0], icon_pos[1] + icon_size//2), 2)
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0], icon_pos[1] + icon_size//2),
                             (icon_pos[0] + icon_size//2, icon_pos[1] - icon_size//2), 2)
        elif self.behavior == "accelerate":
            # Draw acceleration arrows
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0] - icon_size//2, icon_pos[1]),
                             (icon_pos[0], icon_pos[1] - icon_size//2), 2)
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0], icon_pos[1] - icon_size//2),
                             (icon_pos[0] + icon_size//2, icon_pos[1]), 2)
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0] - icon_size//3, icon_pos[1] + icon_size//3),
                             (icon_pos[0], icon_pos[1] - icon_size//4), 2)
            pygame.draw.line(indicator, 
                             icon_color, 
                             (icon_pos[0], icon_pos[1] - icon_size//4),
                             (icon_pos[0] + icon_size//3, icon_pos[1] + icon_size//3), 2)
        
        # Add indicator to the balloon image
        self.image.blit(indicator, (0, 0))
        self.original_image = self.image.copy()  # Save the image with the behavior indicator

        
    def update(self, powerups=None):
        # First run the standard update
        if not super().update(powerups):
            return False
            
        # Skip special behavior if frozen
        if self.frozen:
            return True
            
        # Apply slow motion effect if active
        slow_factor = 0.5 if powerups and 'slow' in powerups else 1.0
        
        # Apply special behavior
        if self.behavior == "zigzag":
            self.behavior_timer += 0.05 * slow_factor
            self.rect.x = self.start_x + int(math.sin(self.behavior_timer * 2) * self.wobble * 2)
        elif self.behavior == "spiral":
            self.behavior_timer += 0.03 * slow_factor
            radius = min(100, self.behavior_timer * 10)
            self.rect.x = self.start_x + int(math.cos(self.behavior_timer) * radius)
        elif self.behavior == "bounce":
            if random.random() < 0.02 * slow_factor:  # Occasional direction change
                self.wobble = -self.wobble
        elif self.behavior == "accelerate":
            self.speed += 0.01 * slow_factor  # Gradually speed up
        
        return True


class GameMode:
    """Base class for different game modes"""
    def __init__(self, name, description):
        self.name = name
        self.description = description
        
    def initialize(self, game):
        """Set up the game for this mode"""
        pass
        
    def update(self, game):
        """Mode-specific update logic"""
        pass
        
    def check_victory(self, game):
        """Check if victory/end conditions are met"""
        return False


class StandardMode(GameMode):
    """Standard competitive mode where players compete for highest score"""
    def __init__(self):
        super().__init__(
            "Standard", 
            "Red vs Green: Compete for the highest score!"
        )
        
    def initialize(self, game):
        game.red_score = 0
        game.green_score = 0
        game.time_left = GAME_DURATION
        game.start_time = time()
        
    def update(self, game):
        # Standard update - already implemented in the game class
        pass
        
    def check_victory(self, game):
        # Game ends when time runs out
        if game.time_left <= 0:
            return True
        return False


class TimeAttackMode(GameMode):
    """Pop as many balloons as possible in a limited time"""
    def __init__(self):
        super().__init__(
            "Time Attack", 
            "Pop as many balloons as possible before time runs out!"
        )
        
    def initialize(self, game):
        game.red_score = 0
        game.green_score = 0
        game.time_left = 90  # 90 seconds
        game.start_time = time()
        
    def update(self, game):
        # Increase balloon spawn rate as time decreases
        time_factor = max(0.5, game.time_left / 90)
        settings = DIFFICULTY_SETTINGS[game.difficulty]
        game.spawn_rate = int(settings['spawn_rate'] * time_factor)
        
    def check_victory(self, game):
        if game.time_left <= 0:
            return True
        return False


class SurvivalMode(GameMode):
    """Balloons get progressively faster and more numerous"""
    def __init__(self):
        super().__init__(
            "Survival", 
            "Balloons get faster and more numerous. How long can you last?"
        )
        self.level = 1
        self.level_timer = 30 * FPS  # 30 seconds per level
        
    def initialize(self, game):
        game.red_score = 0
        game.green_score = 0
        game.elapsed_time = 0
        game.start_time = time()
        self.level = 1
        self.level_timer = 30 * FPS
        
    def update(self, game):
        # Update level timer
        self.level_timer -= 1
        if self.level_timer <= 0:
            self.level += 1
            self.level_timer = 30 * FPS
            # Add notification about level increase
            game.add_notification(f"Level {self.level}!", (255, 255, 0))
            
        # Adjust difficulty based on level
        settings = DIFFICULTY_SETTINGS[game.difficulty]
        level_factor = 1.0 + (self.level - 1) * 0.2  # 20% increase per level
        
        # Update spawn rates and speeds
        game.difficulty_factor = level_factor  # Store for use in spawn_balloons
        
    def check_victory(self, game):
        #Add a limit - when level 10 is reached, end the game
        if self.level >= 10:
            return True
        return False


class CooperativeMode(GameMode):
    """Players work together to reach a target score"""
    def __init__(self):
        super().__init__(
            "Cooperative", 
            "Work together to reach the target score before time runs out!"
        )
        self.target_score = 100
        
    def initialize(self, game):
        game.red_score = 0
        game.green_score = 0
        game.time_left = 120  # 2 minutes
        game.start_time = time()
        # Set target based on difficulty
        if game.difficulty == 'easy':
            self.target_score = 75
        elif game.difficulty == 'normal':
            self.target_score = 100
        else:
            self.target_score = 150
            
    def update(self, game):
        # Standard update
        pass
        
    def check_victory(self, game):
        # Win if combined score reaches target
        total_score = game.red_score + game.green_score
        if total_score >= self.target_score:
            return True
        # Lose if time runs out
        if game.time_left <= 0:
            return False
        # Continue playing
        return None


class PowerupManager:
    """Manages all powerup-related functionality"""
    
    def __init__(self):
        self.active_powerups = {}  # powerup_type -> expiry_time
        self.pending_powerups = []  # Powerups waiting to be activated
        
    def update(self, game):
        """Update powerup timers and spawn new powerups"""
        current_time = time()
        
        # Update active powerups
        expired_powerups = []
        for powerup_type, expiry_time in self.active_powerups.items():
            if current_time >= expiry_time:
                expired_powerups.append(powerup_type)
                
        # Remove expired powerups
        for powerup_type in expired_powerups:
            self.deactivate_powerup(powerup_type, game)
            
        # Check if we should spawn a new powerup
        if (random.random() < 0.005 * game.difficulty_factor and 
                len(game.powerups) < 1):
            self.spawn_powerup(game)
            
    def spawn_powerup(self, game):
        """Create a new powerup based on rarity"""
        new_powerup = PowerUp()
        game.powerups.add(new_powerup)
            
    def activate_powerup(self, powerup_type, game):
        """Activate a powerup and apply its effects"""
        info = PowerUp.TYPES.get(powerup_type)
        if not info:
            return
            
        # Set expiry time
        current_time = time()
        self.active_powerups[powerup_type] = current_time + info['duration']

        # IMPORTANT: Make sure this updates game.active_powerups correctly
        game.active_powerups[powerup_type] = info['duration'] * FPS  # Use FPS instead of game.FPS
        
        # Apply immediate effects
        if powerup_type == 'freeze':
            # Freeze all balloons
            for balloon in game.balloons:
                balloon.frozen = True
                balloon.original_speed = balloon.speed
                balloon.speed = 0
                
        elif powerup_type == 'giant':
            # Signal to camera processing to increase ball detection size
            # This would need to be implemented in the camera processing code
            pass
            
        # Show notification
        game.add_notification(
            f"{info['effect']} Activated!", 
            info['color']
        )
        
        # Play sound
        game.sound_manager.play_powerup_sound(powerup_type)
        
    def deactivate_powerup(self, powerup_type, game):
        """Remove a powerup and its effects"""
        if powerup_type not in self.active_powerups:
            return
            
        del self.active_powerups[powerup_type]

        if powerup_type in game.active_powerups:
            del game.active_powerups[powerup_type]

        info = PowerUp.TYPES.get(powerup_type)
        
        # Revert any specific effects
        if powerup_type == 'freeze':
            # Unfreeze all balloons
            for balloon in game.balloons:
                if hasattr(balloon, 'frozen') and balloon.frozen:
                    balloon.frozen = False
                    if hasattr(balloon, 'original_speed'):
                        balloon.speed = balloon.original_speed
                    
        elif powerup_type == 'giant':
            # Signal to camera processing to return to normal ball detection size
            pass
            
        # Show notification that powerup ended
        game.add_notification(
            f"{info['effect']} Ended", 
            (200, 200, 200)
        )
        
    def is_active(self, powerup_type):
        """Check if a powerup is currently active"""
        return powerup_type in self.active_powerups
        
    def get_active_powerups(self):
        """Get all currently active powerups"""
        current_time = time()
        active = {}
        
        for powerup_type, expiry_time in self.active_powerups.items():
            time_left = max(0, expiry_time - current_time)
            if time_left > 0:
                info = PowerUp.TYPES.get(powerup_type, {})
                active[powerup_type] = {
                    'time_left': time_left,
                    'effect': info.get('effect', 'Unknown'),
                    'color': info.get('color', (255, 255, 255))
                }
                
        return active


def load_projector_calibration(filename="projector_calibration.yaml"):
    """
    Load projector calibration data from a YAML file with error handling.
    
    The YAML file should contain a key "projector_points" with a list of four [x, y] points.
    
    Args:
        filename (str): Path to the calibration YAML file.
    
    Returns:
        np.ndarray: A 4x2 NumPy array (dtype=np.float32) containing the calibration points,
                    or None if loading fails.
    """
    try:
        with open(filename, "r") as f:
            data = yaml.safe_load(f)
        points = data.get("projector_points")
        if points is None:
            raise ValueError("Key 'projector_points' not found in the calibration file.")
        return np.array(points, dtype=np.float32)
    except FileNotFoundError:
        logger.error(f"Calibration file '{filename}' not found")
        return None
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in calibration file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading projector calibration: {e}")
        return None
    
SCREEN_COORDS = load_projector_calibration()
if SCREEN_COORDS is not None:
    logger.info("Loaded projector calibration points")
else:
    logger.critical("Failed to load projector calibration. Game may not function correctly.")
    # Default screen coordinates if loading fails
    SCREEN_COORDS = np.array([
        [0, 0], [WIDTH, 0], 
        [WIDTH, HEIGHT], [0, HEIGHT]
    ], dtype=np.float32)


# Define calibration points from SCREEN_COORDS:
calibration_points = {
    "top_left": tuple(SCREEN_COORDS[0].astype(int)),
    "top_right": tuple(SCREEN_COORDS[1].astype(int)),
    "bottom_right": tuple(SCREEN_COORDS[2].astype(int)),
    "bottom_left": tuple(SCREEN_COORDS[3].astype(int)),
    "center": tuple(np.mean(SCREEN_COORDS, axis=0).astype(int))
}

# Create a full-screen window on the projector
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Balloon Pop Game")
clock = pygame.time.Clock()


class Game:
    def __init__(self):
        # Force Pygame initialization
        if not pygame.get_init():
            pygame.init()
        
        # Ensure display module is initialized
        if not pygame.display.get_init():
            pygame.display.init()
        
        # Create display surface with error handling
        try:
            # Try fullscreen first
            self.actual_surface = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        except Exception as fullscreen_e:
            logger.warning(f"Fullscreen mode failed: {fullscreen_e}")
            try:
                # Fallback to windowed mode
                self.actual_surface = pygame.display.set_mode((WIDTH, HEIGHT))
            except Exception as window_e:
                logger.critical(f"Failed to create display surface: {window_e}")
                raise
        
        # Set window caption
        pygame.display.set_caption("Balloon Pop Game")
        
        # Reset the display
        pygame.display.update()
        
        # Ensure mixer is initialized for sound
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        # Reset clock
        global clock
        clock = pygame.time.Clock()

        # Game state and scoring
        self.red_score = 0
        self.green_score = 0
        self.balloons = pygame.sprite.Group()
        self.pop_animations = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.frame_count = 0
        self.game_state = "mode_select"  # Changed from "difficulty_select" to include mode selection
        self.difficulty = None
        self.selected_mode = None
        self.game_mode = None  # Will hold the GameMode instance
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 36)
        self.start_time = None
        self.time_left = GAME_DURATION
        self.event_queue = None  # This will be set externally

        # Initialize particles list
        self.particles = []

        
        
        # Initialize mode selection
        self.available_modes = [
            StandardMode(),
            TimeAttackMode(),
            SurvivalMode(),
            CooperativeMode()
        ]
        
        try:
            pygame.mixer.music.load("sound/background_sound.mp3")  # Use your audio file here
            pygame.mixer.music.set_volume(0.04)  # Adjust volume (0.0 to 1.0)
            pygame.mixer.music.play(-1)  # -1 means loop indefinitely
        except pygame.error as e:
            logger.error(f"Could not load background music: {e}")

        # Ball detection tracking
        self.COOLDOWN_FRAMES = 12
        self.REDLastEvent = 0
        self.GREENLastEvent = 0
        self.YELLOWCOUNTER = 0
        
        # Advanced game features
        self.sound_manager = SoundManager()
        self.powerup_manager = PowerupManager()
        self.active_powerups = {}  # type -> time remaining
        self.combo = {"red": 0, "green": 0}  # Player color combo counters
        self.combo_timer = {"red": 0, "green": 0}  # Timers for combo decay
        self.COMBO_DECAY_TIME = FPS * 2  # 2 seconds
        self.MAX_COMBO = 10  # Maximum combo multiplier
        
        # Visual effects
        self.notifications = []  # List of (text, color, time_left, position)
        self.effects_manager = EffectsManager()
        self.analytics = GameAnalytics()
        self.difficulty_factor = 1.0
        self.screen_shake = 0
        
        # Player statistics
        self.player_stats = {
            "red": {"hits": 0, "misses": 0, "combos": 0, "max_combo": 0},
            "green": {"hits": 0, "misses": 0, "combos": 0, "max_combo": 0}
        }
        
        # Visual background elements
        self.stars = []
        for _ in range(50):
            self.stars.append({
                'x': random.randint(0, WIDTH),
                'y': random.randint(0, HEIGHT),
                'size': random.uniform(0.5, 3),
                'speed': random.uniform(0.2, 1.0)
            })

        # Load ball calibration data
        self.load_ball_calibration()
        
        # Make the calibration points available to the class
        self.calibration_points = calibration_points
        
        # Dynamic difficulty adjustment
        self.difficulty_factor = 1.0
        
    def load_ball_calibration(self):
        """Load ball calibration data with error handling."""
        try:
            with open("ball_calibration.yaml", "r") as f:
                self.ball_calibration = yaml.safe_load(f)
            logger.info("Ball calibration data loaded.")
        except FileNotFoundError:
            logger.error("Ball calibration file not found")
            # Create empty calibration as fallback
            self.ball_calibration = {
                "blue": {k: 30.0 for k in calibration_points.keys()},
                "yellow": {k: 30.0 for k in calibration_points.keys()}
            }
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in ball calibration: {e}")
            # Create empty calibration as fallback
            self.ball_calibration = {
                "blue": {k: 30.0 for k in calibration_points.keys()},
                "yellow": {k: 30.0 for k in calibration_points.keys()}
            }
        except Exception as e:
            logger.error(f"Failed to load ball calibration data: {e}")
            # Create empty calibration as fallback
            self.ball_calibration = {
                "blue": {k: 30.0 for k in calibration_points.keys()},
                "yellow": {k: 30.0 for k in calibration_points.keys()}
            }

    def spawn_balloons(self):
        """
        Add balloons to the game according to the difficulty level.
        Includes special balloon types at random intervals.
        """
        settings = DIFFICULTY_SETTINGS[self.difficulty]
        
        # Progressive difficulty adjustment
        time_elapsed = GAME_DURATION - self.time_left
        if not hasattr(self, 'difficulty_factor'):
            self.difficulty_factor = 1.0
            
        # If game mode didn't set a difficulty factor, calculate it based on time
        if self.game_mode and not hasattr(self.game_mode, 'level'):
            self.difficulty_factor = 1.0 + (time_elapsed / GAME_DURATION) * 0.5  # Up to 50% harder
        
        adjusted_spawn_rate = max(50, int(settings['spawn_rate'] / self.difficulty_factor))
        
        # Only spawn on specific frames based on spawn rate
        if self.frame_count % adjusted_spawn_rate != 0:
            return
            
        # Count current balloons by color
        red_count = len([b for b in self.balloons if b.color == RED])
        green_count = len([b for b in self.balloons if b.color == GREEN])
        max_per_color = int(settings['max_balloons'] * self.difficulty_factor) // 2
        
        # Determine if we should spawn special balloons
        # Special chance increases with game time
        special_chance = settings['special_chance'] * self.difficulty_factor
        smart_chance = 0.2 * self.difficulty_factor  # Chance for smart balloons
        
        # Spawn red balloons if needed
        if red_count < max_per_color:
            if random.random() < smart_chance:
                # Create a smart balloon
                balloon = SmartBalloon(RED, settings['speed_range'])
            else:
                balloon_type = "normal"
                if random.random() < special_chance:
                    balloon_type = random.choices(
                        ["bonus", "penalty"], 
                        weights=[0.7, 0.3]
                    )[0]
                    
                # Adjust speed range based on difficulty progression
                min_speed, max_speed = settings['speed_range']
                adjusted_speed = (
                    min_speed, 
                    max_speed + int(self.difficulty_factor - 1) * 2
                )
                
                balloon = Balloon(RED, adjusted_speed, balloon_type)
                
            self.balloons.add(balloon)
                
        # Spawn green balloons if needed
        if green_count < max_per_color:
            if random.random() < smart_chance:
                # Create a smart balloon
                balloon = SmartBalloon(GREEN, settings['speed_range'])
            else:
                balloon_type = "normal"
                if random.random() < special_chance:
                    balloon_type = random.choices(
                        ["bonus", "penalty"], 
                        weights=[0.7, 0.3]
                    )[0]
                    
                # Adjust speed range based on difficulty progression
                min_speed, max_speed = settings['speed_range']
                adjusted_speed = (
                    min_speed, 
                    max_speed + int(self.difficulty_factor - 1) * 2
                )
                
                balloon = Balloon(GREEN, adjusted_speed, balloon_type)
                
            self.balloons.add(balloon)
            
        # Occasionally spawn powerups - managed by PowerupManager
        if self.powerup_manager:
            self.powerup_manager.update(self)

    def handle_events(self): 
        """
        Handle mouse clicking and other events
        """
        global pos
        # Ensure event system is initialized
        if not pygame.get_init():
            pygame.init()
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                return False
            
            # Pause event handling
            if event.type == pygame.KEYDOWN:
                # Pause toggle
                if event.key == pygame.K_p:
                    if self.game_state == "playing":
                        self.game_state = "paused"
                    elif self.game_state == "paused":
                        self.game_state = "playing"
                
                # Existing ESC handler for quitting game entirely
                if event.key == pygame.K_q and self.game_state == "playing" and isinstance(self.game_mode, SurvivalMode):
                    # End survival mode and go to results screen
                    self.game_state = "end"
                    if hasattr(self, 'analytics'):
                        self.analytics.end_game()
            
            # Mouse click events
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Convert the actual mouse position to the virtual resolution.
                actual_size = pygame.display.get_surface().get_size()
                raw_pos = pygame.mouse.get_pos()
                # Scale the mouse coordinates:
                pos = (raw_pos[0] * WIDTH / actual_size[0], raw_pos[1] * HEIGHT / actual_size[1])
                
                # Pause screen specific handling
                if self.game_state == "paused":
                    resume_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 - 50, 400, 80)
                    quit_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 + 50, 400, 80)
                    
                    # Resume button
                    if resume_rect.collidepoint(pos):
                        self.game_state = "playing"
                        self.sound_manager.play("sound/pop_balloon.wav", "ui")
                    
                    # End game button
                    if quit_rect.collidepoint(pos):
                        self.game_state = "end"
                        if hasattr(self, 'analytics'):
                            self.analytics.end_game()
                        self.sound_manager.play("sound/pop_balloon.wav", "ui")
                    
                    return True  # Prevent other click handlers from processing
                
                # Existing click handlers for other game states
                if self.game_state == "mode_select":
                    # Handle mode selection
                    for i, mode in enumerate(self.available_modes):
                        rect = pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 150 + i * 80, 400, 60)
                        if rect.collidepoint(pos):
                            self.selected_mode = i
                            self.game_mode = self.available_modes[i]
                            self.game_state = "difficulty_select"
                            # Play sound
                            self.sound_manager.play("sound/pop_balloon.wav", "ui")
                
                elif self.game_state == "difficulty_select":
                    # The difficulty buttons are defined in the virtual space.
                    for i, diff in enumerate(['easy', 'normal', 'hard']):
                        rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 50 + i * 80, 300, 60)
                        if rect.collidepoint(pos):
                            self.difficulty = diff
                            self.game_state = "start"
                            # Play sound
                            self.sound_manager.play("sound/pop_balloon.wav", "ui")
                            
                elif self.game_state == "start":
                    self.game_state = "playing"
                    self.start_time = time()

                    # code to track analytics:
                    if hasattr(self, 'analytics'):
                        mode_name = self.game_mode.name if self.game_mode else "Standard"
                        self.analytics.start_game(mode_name, self.difficulty)
                    
                    # Initialize the selected game mode
                    if self.game_mode:
                        self.game_mode.initialize(self)
                        
                    # Reset game state
                    self.balloons.empty()
                    self.powerups.empty()
                    self.pop_animations.empty()
                    self.active_powerups = {}
                    self.notifications = []
                    
                    # Play sound
                    self.sound_manager.play("sound/pop_balloon.wav", "ui")
                    
                elif self.game_state == "playing":
                    # Process clicks on balloons during play.
                    for balloon in self.balloons:
                        if balloon.rect.collidepoint(pos):
                            self.pop_balloon(balloon, "mouse")
                            break
                            
                    # Process clicks on powerups
                    for powerup in self.powerups:
                        if powerup.rect.collidepoint(pos):
                            self.collect_powerup(powerup)
                            break
                            
                elif self.game_state == "end":
                    # Check for restart button
                    restart_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 150, 300, 60)
                    if restart_rect.collidepoint(pos):
                        # Reset the game
                        self.__init__()
                        self.game_state = "mode_select"
                        # Play sound
                        self.sound_manager.play("sound/pop_balloon.wav", "ui")
        return True

    def update(self):
        # Process events from the camera thread
        if self.event_queue is not None:
            while not self.event_queue.empty():
                event = self.event_queue.get()
                # Now event is expected to be a tuple: (color, x, y, radius, frame_number, is_back)
                self.pop_balloon_at_point(event)

        if self.game_state == "playing":
            # Update timer based on game mode
            if isinstance(self.game_mode, SurvivalMode):
                # For survival, don't countdown - just track elapsed time
                self.elapsed_time = int(time() - self.start_time)
            elif isinstance(self.game_mode, TimeAttackMode):
                # For time attack, use 90 seconds
                self.time_left = max(0, 90 - int(time() - self.start_time))
            else:
                # Standard and Cooperative use GAME_DURATION (120 seconds)
                self.time_left = max(0, GAME_DURATION - int(time() - self.start_time))
            
            # Update game mode
            if self.game_mode:
                self.game_mode.update(self)
                
                # Check for game over
                game_over = self.game_mode.check_victory(self)
                if game_over:  # Not None means the game has ended
                    self.game_state = "end"
                    # Add this line to finalize analytics when game ends
                    if hasattr(self, 'analytics'):
                        self.analytics.end_game()
                    return
                
            # Update frame counter
            self.frame_count += 1
            
            # Update active powerups via PowerupManager
            if hasattr(self, 'powerup_manager') and self.powerup_manager:
                # PowerupManager handles powerup updates
                #  call update on the powerup manager
                self.powerup_manager.update(self)
                # Add this line to debug active powerups:
                if self.active_powerups:
                    logger.info(f"Active powerups: {list(self.active_powerups.keys())}")
        
            for powerup_type in list(self.active_powerups.keys()):
                self.active_powerups[powerup_type] -= 1
                if self.active_powerups[powerup_type] <= 0:
                    del self.active_powerups[powerup_type]
                    self.add_notification(f"{PowerUp.TYPES[powerup_type]['effect']} Ended", WHITE)
                
            # Update combo timers
            for color in self.combo_timer:
                if self.combo_timer[color] > 0:
                    self.combo_timer[color] -= 1
                    if self.combo_timer[color] <= 0 and self.combo[color] > 0:
                        # Combo ended
                        self.combo[color] = 0
                        
            # Spawn balloons based on difficulty
            self.spawn_balloons()
            
            # Update balloons
            for balloon in list(self.balloons):
                if hasattr(balloon, 'pop_at_frame') and self.frame_count >= balloon.pop_at_frame:
                    self.pop_balloon(balloon, "chain")
                else:
                    balloon.update(self.active_powerups)
                
            # Update powerups
            self.powerups.update()
            
            # Update animations
            self.pop_animations.update()

            # Update enhanced effects
            self.effects_manager.update()
            
            # Update notifications
            for i, notification in enumerate(self.notifications):
                text, color, time_left, position = notification
                self.notifications[i] = (text, color, time_left - 1, position)
            
            # Remove expired notifications
            self.notifications = [n for n in self.notifications if n[2] > 0]
            
            # Update screen shake
            if self.screen_shake > 0:
                self.screen_shake -= 1
                
            # Update stars
            for star in self.stars:
                star['y'] += star['speed']
                if star['y'] > HEIGHT:
                    star['y'] = 0
                    star['x'] = random.randint(0, WIDTH)
                    
            # Periodic cleanup - every 5 seconds
            if self.frame_count % (5 * FPS) == 0:
                # Force garbage collection for smoother performance
                import gc
                gc.collect()

            if hasattr(self, 'analytics'):
                self.analytics.update_game(
                    red_score=self.red_score,
                    green_score=self.green_score,
                    red_hits=self.player_stats["red"]["hits"],
                    green_hits=self.player_stats["green"]["hits"],
                    red_max_combo=self.player_stats["red"]["max_combo"],
                    green_max_combo=self.player_stats["green"]["max_combo"]
                )
            

    def add_notification(self, text, color, duration=60, position=None):
        """Add a temporary notification that fades out"""
        if position is None:
            position = (WIDTH // 2, HEIGHT // 3)
        
        if hasattr(self, 'effects_manager'):
            self.effects_manager.add_text_popup(text, position[0], position[1], color, duration=duration)
        else:
            # Fallback to old system
            self.notifications.append((text, color, duration, position))
        
    def add_score(self, points, color):
        """Add points to the appropriate team score"""
        # Apply double points powerup if active
        if 'double' in self.active_powerups:
            points *= 2
            
        # Apply combo multiplier if any
        player_color = "red" if color == RED else "green"
        combo_mult = min(self.combo[player_color], self.MAX_COMBO)
        if combo_mult > 1:
            points *= combo_mult
            
        if color == RED:
            self.red_score += points
        else:
            self.green_score += points
            
        # Show score popup
        prefix = ""
        if combo_mult > 1:
            prefix = f"{combo_mult}x "
        
        # Position the notification near where the balloon was popped
        if points > 0:
            self.add_notification(f"{prefix}+{points}", color)
        else:
            self.add_notification(f"{points}", color)
            
        return points

    def pop_balloon(self, balloon, source="camera"):
        """Pop a balloon and add appropriate effects"""
        is_special = balloon.balloon_type != "normal"

        # Always use enhanced effects system for explosion
        self.effects_manager.add_explosion(
            balloon.rect.centerx,
            balloon.rect.centery,
            balloon.color,
            special=is_special,
            count=30 if is_special else 20
        )
        
        """# Use enhanced effects system for explosion
        if hasattr(self, 'effects_manager'):
            self.effects_manager.add_explosion(
                balloon.rect.centerx,
                balloon.rect.centery,
                balloon.color,
                special=is_special,
                count=30 if is_special else 20
            )
        else:
            # Fallback to old system if effects manager isn't available
            self.pop_animations.add(
                PopAnimation(
                    balloon.rect.x, 
                    balloon.rect.y, 
                    balloon.color, 
                    particle_count=30 if is_special else 20,
                    special=is_special
                )
            )"""
        
        # Add score
        points = balloon.points
        
        # Correctly map balloon colors to player colors
        player_color = "red" if balloon.color == RED else "green"
        
        # Update combo
        if points > 0:
            # Increment combo for positive points
            self.combo[player_color] += 1
            self.combo_timer[player_color] = self.COMBO_DECAY_TIME
            
            # Record max combo
            if self.combo[player_color] > self.player_stats[player_color]["max_combo"]:
                self.player_stats[player_color]["max_combo"] = self.combo[player_color]
                
            # Play combo sound for milestones
            if self.combo[player_color] in [3, 5, 8, 10]:
                self.sound_manager.play("sound/pop_red_ballon.wav", "balloon", 
                                       volume_scale=1.2, pitch_shift=1.0 + self.combo[player_color] * 0.05)
        else:
            # Reset combo for negative points
            self.combo[player_color] = 0
        
        # Add score with multipliers
        actual_points = self.add_score(points, balloon.color)

        if hasattr(self, 'effects_manager'):
            self.effects_manager.add_score_popup(
                actual_points,
                balloon.rect.centerx,
                balloon.rect.centery - 50,
                balloon.color,
                combo=self.combo[player_color]
            )
        
        # Play appropriate sound
        if balloon.balloon_type == "bonus":
            self.sound_manager.play("sound/bonus_balloon.wav", "balloon", volume_scale=1.2)
            self.screen_shake = 10  # Add screen shake for bonus balloons
        elif balloon.balloon_type == "penalty":
            self.sound_manager.play("sound/penalty_balloon.wav", "balloon", volume_scale=1.3)
            self.screen_shake = 5  # Add screen shake for penalty balloons
        elif balloon.color == RED:
            self.sound_manager.play("sound/pop_red_ballon.wav", "balloon")
        else:
            self.sound_manager.play("sound/pop_balloon.wav", "balloon")
         
        # Add special effect for smart balloons
        if isinstance(balloon, SmartBalloon):
            # Add sparkle particles
            for _ in range(10):
                self.particles.append(
                    StarParticle(
                        balloon.rect.centerx + random.uniform(-20, 20),
                        balloon.rect.centery + random.uniform(-20, 20),
                        GOLD,
                        size=random.uniform(3, 6),
                        lifetime=random.randint(10, 20)
                    )
                )
            
        # Update player stats
        self.player_stats[player_color]["hits"] += 1
        
        # Chain reaction effect if powerup is active
        if 'chain' in self.active_powerups:
            # Find nearby balloons
            chain_radius = BALLOON_SIZE * 2
            for other_balloon in list(self.balloons):
                if other_balloon != balloon:
                    dx = other_balloon.rect.centerx - balloon.rect.centerx
                    dy = other_balloon.rect.centery - balloon.rect.centery
                    distance = math.sqrt(dx*dx + dy*dy)
                    if distance < chain_radius:
                        # Create chain reaction with slight delay
                        self.schedule_pop(other_balloon, 5)
        
        # Remove the balloon
        balloon.kill()
        
        return actual_points
        
    def schedule_pop(self, balloon, delay):
        """Schedule a balloon to pop after a short delay (used for chain reactions)"""
        # This could be implemented with a timer or a queue
        # For now, just store the frame count when it should pop
        if not hasattr(balloon, 'pop_at_frame'):
            balloon.pop_at_frame = self.frame_count + delay

    def collect_powerup(self, powerup):
        """Activate a powerup"""
        if hasattr(self, 'effects_manager'):
            self.effects_manager.add_explosion(
                powerup.rect.centerx,
                powerup.rect.centery,
                powerup.color,
                special=True,
                count=20
            )
            
            # Add sparkle effects
            for _ in range(20):
                self.effects_manager.add_sparkle(
                    powerup.rect.centerx + random.uniform(-30, 30),
                    powerup.rect.centery + random.uniform(-30, 30),
                    powerup.color
                )

        logger.info(f"Collecting {powerup.type} powerup")
        self.powerup_manager.activate_powerup(powerup.type, self)

        
        # Legacy implementation - directly add to active powerups
        """self.active_powerups[powerup.type] = powerup.duration
        
        # Show notification
        self.add_notification(
            f"{powerup.effect} Activated!", 
            powerup.color
        )
        
        # Play sound
        self.sound_manager.play("sound/pop_balloon.wav", "powerup", volume_scale=1.2)
        
        # Add visual effects
        self.screen_shake = 15
        
        # Add sparkle particles
        for _ in range(20):
            self.particles.append(
                StarParticle(
                    powerup.rect.centerx + random.uniform(-30, 30),
                    powerup.rect.centery + random.uniform(-30, 30),
                    powerup.color,
                    size=random.uniform(3, 8),
                    lifetime=random.randint(10, 30)
                )
            )"""
        
        # Remove the powerup
        powerup.kill()

    def Draw_mode_select_screen(self, surface):
        """Draw the game mode selection screen"""
        # Draw stars
        for star in self.stars:
            pygame.draw.circle(
                surface, 
                (200, 200, 255), 
                (int(star['x']), int(star['y'])), 
                int(star['size'])
            )
        
        # Draw title
        title_text = pygame.font.Font(None, 80).render("Balloon Pop Challenge", True, WHITE)
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 250))
        surface.blit(title_text, title_rect)
        
        # Draw subtitle
        subtitle = self.font.render("Select Game Mode", True, (200, 200, 255))
        subtitle_rect = subtitle.get_rect(center=(WIDTH//2, HEIGHT//2 - 180))
        surface.blit(subtitle, subtitle_rect)

        # Draw mode buttons
        for i, mode in enumerate(self.available_modes):
            # Create button
            button_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 - 120 + i*80, 400, 60)
            
            # Draw button shadow
            shadow_rect = button_rect.copy()
            shadow_rect.x += 5
            shadow_rect.y += 5
            pygame.draw.rect(surface, (0, 0, 40), shadow_rect, border_radius=10)
            
            # Draw button background
            colors = [
                (0, 180, 0),  # Standard - Green
                (180, 180, 0), # Time Attack - Yellow
                (180, 0, 0),   # Survival - Red
                (0, 0, 180)    # Cooperative - Blue
            ]
            pygame.draw.rect(surface, colors[i], button_rect, border_radius=10)
            pygame.draw.rect(surface, WHITE, button_rect, 2, border_radius=10)
            
            # Draw button text
            mode_text = self.font.render(mode.name, True, WHITE)
            text_rect = mode_text.get_rect(center=button_rect.center)
            surface.blit(mode_text, text_rect)
            
            # Draw mode description
            desc_text = self.small_font.render(mode.description, True, WHITE)
            desc_rect = desc_text.get_rect(center=(WIDTH//2, button_rect.bottom + 20))
            surface.blit(desc_text, desc_rect)
            
        # Draw footer text
        footer = self.small_font.render("Use physical balls to pop balloons", True, WHITE)
        footer_rect = footer.get_rect(center=(WIDTH//2, HEIGHT - 50))
        surface.blit(footer, footer_rect)

    def Draw_difficulty_screen_select(self, surface):
        """Design the difficulty game screen"""
        # Draw stars
        for star in self.stars:
            pygame.draw.circle(
                surface, 
                (200, 200, 255), 
                (int(star['x']), int(star['y'])), 
                int(star['size'])
            )
        
        # Draw title
        title_text = pygame.font.Font(None, 80).render(f"{self.game_mode.name} Mode", True, WHITE)
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 200))
        surface.blit(title_text, title_rect)
        
        # Draw subtitle
        subtitle = self.font.render("Select Difficulty", True, (200, 200, 255))
        subtitle_rect = subtitle.get_rect(center=(WIDTH//2, HEIGHT//2 - 120))
        surface.blit(subtitle, subtitle_rect)

        # Draw difficulty buttons
        for i, diff in enumerate(['easy', 'normal', 'hard']):
            # Create button
            button_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 50 + i*80, 300, 60)
            
            # Draw button shadow
            shadow_rect = button_rect.copy()
            shadow_rect.x += 5
            shadow_rect.y += 5
            pygame.draw.rect(surface, (0, 0, 40), shadow_rect, border_radius=10)
            
            # Draw button background
            colors = {
                'easy': (0, 180, 0),
                'normal': (180, 180, 0),
                'hard': (180, 0, 0)
            }
            pygame.draw.rect(surface, colors[diff], button_rect, border_radius=10)
            pygame.draw.rect(surface, WHITE, button_rect, 2, border_radius=10)
            
            # Draw button text
            diff_text = self.font.render(diff.title(), True, WHITE)
            text_rect = diff_text.get_rect(center=button_rect.center)
            surface.blit(diff_text, text_rect)
            
        # Draw footer text
        footer = self.small_font.render("Use physical balls to pop balloons", True, WHITE)
        footer_rect = footer.get_rect(center=(WIDTH//2, HEIGHT - 50))
        surface.blit(footer, footer_rect)

    def Draw_start_screen(self, surface):
        """Design the start game screen"""
        # Draw stars
        for star in self.stars:
            pygame.draw.circle(
                surface, 
                (200, 200, 255), 
                (int(star['x']), int(star['y'])), 
                int(star['size'])
            )
        
        # Draw title
        title_text = pygame.font.Font(None, 80).render(f"{self.game_mode.name} Mode - {self.difficulty.title()}", True, WHITE)
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 150))
        surface.blit(title_text, title_rect)
        
        # Draw start text
        start_text = self.font.render("Click to Start Game (ESC to quit)", True, WHITE)
        text_rect = start_text.get_rect(center=(WIDTH/2, HEIGHT/2 - 50))
        surface.blit(start_text, text_rect)
        
        # Draw mode-specific instructions
        if isinstance(self.game_mode, CooperativeMode):
            instructions = [
                "Red and Green work together to reach the target score!",
                f"Target Score: {self.game_mode.target_score} points",
                "Hit balloons with physical balls to score points",
                "Special balloons and power-ups will appear during the game!"
            ]
        elif isinstance(self.game_mode, SurvivalMode):
            instructions = [
                "Balloons get faster and more numerous over time",
                "How long can you survive?",
                "Hit balloons with physical balls to score points",
                "Watch out for special balloons and power-ups!"
            ]
        elif isinstance(self.game_mode, TimeAttackMode):
            instructions = [
                "Score as many points as possible in 90 seconds!",
                "Player 1 (Green) vs Player 2 (Red)",
                "Hit balloons with physical balls to score points",
                "Special balloons and power-ups will help you score more!"
            ]
        else:  # Standard mode
            instructions = [
                "Player 1 (Green) vs Player 2 (Red)", 
                f"{GAME_DURATION // 60} Minutes Competition", 
                "Hit balloons with physical balls to score points",
                "Special balloons and power-ups will appear during the game!"
            ]
        
        y_offset = HEIGHT/2 
        for text in instructions:
            inst_text = self.small_font.render(text, True, BLACK)
            inst_rect = inst_text.get_rect(center=(WIDTH/2, y_offset))
            surface.blit(inst_text, inst_rect)
            y_offset += 40
            
        # Draw sample balloons
        # Normal balloon
        normal = Balloon(RED, (1, 1))
        normal.rect.center = (WIDTH//2 - 300, HEIGHT//2 + 290)
        surface.blit(normal.image, normal.rect)
        normal_text = self.small_font.render("Normal: 1 point", True, BLACK)
        surface.blit(normal_text, (normal.rect.centerx - normal_text.get_width()//2, normal.rect.bottom + 10))
        
        # Bonus balloon
        bonus = Balloon(RED, (1, 1), "bonus")
        bonus.rect.center = (WIDTH//2, HEIGHT//2 + 290)
        surface.blit(bonus.image, bonus.rect)
        bonus_text = self.small_font.render("Bonus: 3 points", True, GOLD)
        surface.blit(bonus_text, (bonus.rect.centerx - bonus_text.get_width()//2, bonus.rect.bottom + 10))
        
        # Penalty balloon
        penalty = Balloon(RED, (1, 1), "penalty")
        penalty.rect.center = (WIDTH//2 + 300, HEIGHT//2 + 290)
        surface.blit(penalty.image, penalty.rect)
        penalty_text = self.small_font.render("Penalty: -2 points", True, (255, 100, 100))
        surface.blit(penalty_text, (penalty.rect.centerx - penalty_text.get_width()//2, penalty.rect.bottom + 10))
    
    def Draw_Play_screen(self, surface):
        """Design the play game screen"""
         # Apply screen effects for active powerups
        # Do this before applying screen shake
        
        # Then apply screen shake and draw all particle effects
        shake_offset = self.effects_manager.draw(surface)

        """if hasattr(self, 'effects_manager'):
            # Let the effects manager render particles and get the shake offset
            shake_offset = self.effects_manager.draw(surface)
        else:
            # Fallback to old system
            shake_offset = (0, 0)
            if self.screen_shake > 0:
                shake_offset = (
                    random.randint(-10, 10), 
                    random.randint(-10, 10)
                )"""
                
        # Draw stars
        for star in self.stars:
            pygame.draw.circle(
                surface, 
                (50, 50, 100), 
                (int(star['x'] + shake_offset[0]), int(star['y'] + shake_offset[1])), 
                int(star['size'])
            )
                
        # Draw particles
        for particle in self.particles:
            # Apply shake offset
            pygame.draw.circle(
                surface,
                particle.color,
                (int(particle.x + shake_offset[0]), int(particle.y + shake_offset[1])),
                int(particle.size)
            )
                
        # Draw balloons
        for balloon in self.balloons:
            # Apply shake offset
            original_pos = balloon.rect.topleft
            balloon.rect.x += shake_offset[0]
            balloon.rect.y += shake_offset[1]
                
            surface.blit(balloon.image, balloon.rect)
                
            # Restore original position
            balloon.rect.topleft = original_pos
                
        # Draw powerups
        for powerup in self.powerups:
            # Apply shake offset
            original_pos = powerup.rect.topleft
            powerup.rect.x += shake_offset[0]
            powerup.rect.y += shake_offset[1]
                
            surface.blit(powerup.image, powerup.rect)
                
            # Restore original position
            powerup.rect.topleft = original_pos
            
        # Draw pop animations
        for anim in self.pop_animations:
            # Apply shake offset
            original_pos = anim.rect.topleft
            anim.rect.x += shake_offset[0]
            anim.rect.y += shake_offset[1]
                
            surface.blit(anim.image, anim.rect)
                
            # Restore original position
            anim.rect.topleft = original_pos

        # Draw scores and time
        red_bg_rect = pygame.Rect(10, 10, 200, 80)
        green_bg_rect = pygame.Rect(WIDTH - 210, 10, 200, 80)
        time_bg_rect = pygame.Rect(WIDTH//2 - 100, 10, 200, 40)
            
        # Draw backgrounds with transparency
        s = pygame.Surface((200, 80), pygame.SRCALPHA)
        s.fill((255, 255, 255, 200))  # White with 80% opacity
        surface.blit(s, red_bg_rect)
        surface.blit(s, green_bg_rect)
            
        s = pygame.Surface((200, 40), pygame.SRCALPHA)
        s.fill((255, 255, 255, 200))  # White with 80% opacity
        surface.blit(s, time_bg_rect)
            
        # Draw score texts
        red_text = self.font.render(f"Red: {self.red_score}", True, RED)
        green_text = self.font.render(f"Green: {self.green_score}", True, GREEN)
        
        # Format time appropriately
        minutes = self.time_left // 60
        seconds = self.time_left % 60
        time_text = self.font.render(f"Time: {minutes}:{seconds:02d}", True, BLACK)
            
        surface.blit(red_text, (20, 20))
        surface.blit(green_text, (WIDTH - 200, 20))
        surface.blit(time_text, (WIDTH//2 - 70, 15))
        
        # For cooperative mode, show progress toward target
        if isinstance(self.game_mode, CooperativeMode):
            total_score = self.red_score + self.green_score
            target = self.game_mode.target_score
            progress = min(1.0, total_score / target)
            
            # Draw progress bar
            bar_width = 300
            bar_height = 20
            bar_x = WIDTH // 2 - bar_width // 2
            bar_y = 70
            
            # Background
            pygame.draw.rect(surface, (100, 100, 100), 
                            (bar_x, bar_y, bar_width, bar_height))
            
            # Fill based on progress
            fill_width = int(bar_width * progress)
            if fill_width > 0:
                pygame.draw.rect(surface, (100, 255, 100), 
                                (bar_x, bar_y, fill_width, bar_height))
                
            # Border
            pygame.draw.rect(surface, WHITE, 
                            (bar_x, bar_y, bar_width, bar_height), 2)
                
            # Text
            progress_text = self.small_font.render(
                f"Progress: {total_score}/{target}", True, WHITE)
            surface.blit(progress_text, 
                        (bar_x + bar_width // 2 - progress_text.get_width() // 2, 
                         bar_y + bar_height + 5))
        
        # For survival mode, show current level and quit button
        elif isinstance(self.game_mode, SurvivalMode):
            # Draw level text
            level_text = self.font.render(f"Level: {self.game_mode.level}", True, GOLD)
            level_rect = level_text.get_rect(center=(WIDTH//2, 70))
            surface.blit(level_text, level_rect)
            
            # Show time until next level
            next_level_seconds = self.game_mode.level_timer // FPS
            next_level_text = self.small_font.render(
                f"Next level in: {next_level_seconds}s", True, WHITE)
            next_level_rect = next_level_text.get_rect(center=(WIDTH//2, 100))
            surface.blit(next_level_text, next_level_rect)
            
        # Draw combo indicators
        if self.combo["red"] > 1:
            combo_text = self.small_font.render(f"Combo: {self.combo['red']}x", True, RED)
            surface.blit(combo_text, (20, 60))
                
        if self.combo["green"] > 1:  
            combo_text = self.small_font.render(f"Combo: {self.combo['green']}x", True, GREEN)
            surface.blit(combo_text, (WIDTH - 200, 60))
                
        # Draw active powerups
        if self.active_powerups:
            powerup_y = 80
            powerup_text = self.small_font.render("Active Powerups:", True, WHITE)
            surface.blit(powerup_text, (20, powerup_y))
            powerup_y += 30
                
            for powerup_type, time_left in self.active_powerups.items():
                color = PowerUp.TYPES[powerup_type]['color']
                name = PowerUp.TYPES[powerup_type]['effect']
                seconds = int(time_left / FPS)
                    
                text = self.small_font.render(f"{name}: {seconds}s", True, color)
                surface.blit(text, (30, powerup_y))
                powerup_y += 30
                    
        # Draw notifications
        for text, color, time_left, position in self.notifications:
            # Calculate transparency based on time left
            alpha = min(255, int(time_left * 3))
            color_with_alpha = (*color[:3], alpha)
                
            # Calculate size based on time (start bigger)
            size_factor = 1.0 + (60 - min(time_left, 20)) / 20 * 0.5
                
            # Render text
            duration_ratio = time_left / 60
            font_size = int(48 * (0.8 + duration_ratio * 0.4))
            font = pygame.font.Font(None, font_size)
            text_surf = font.render(text, True, color)
                
            # Apply scaling
            scaled_size = (
                int(text_surf.get_width() * size_factor),
                int(text_surf.get_height() * size_factor)
            )
            scaled_text = pygame.transform.scale(text_surf, scaled_size)
                
            # Set alpha
            scaled_text.set_alpha(alpha)
                
            # Calculate position (move upward as it fades)
            pos_x = position[0] - scaled_text.get_width() // 2
            pos_y = position[1] - scaled_text.get_height() // 2 - (60 - time_left) // 2
                
            # Apply shake to notifications too
            pos_x += shake_offset[0]
            pos_y += shake_offset[1]
                
            # Draw
            surface.blit(scaled_text, (pos_x, pos_y))

        self.apply_powerup_visual_effects(surface)

    def apply_powerup_visual_effects(self, surface):
        """Apply visual effects based on active powerups"""
        # Skip if no powerups active
        if not self.active_powerups:
            return
            
        # Slow-mo effect: Slight blue tint
        if 'slow' in self.active_powerups:
            tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            tint.fill((0, 0, 100, 30))  # Very light blue tint
            surface.blit(tint, (0, 0))
            
        # Double points effect: Gold borders
        if 'double' in self.active_powerups:
            # Create a pulsing gold border
            pulse = (math.sin(self.frame_count * 0.1) + 1) * 0.5  # 0 to 1
            border_width = int(10 * pulse) + 5
            pygame.draw.rect(surface, (255, 215, 0), (0, 0, WIDTH, HEIGHT), border_width)
            
        # Magnet effect: Show attraction lines in center
        if 'magnet' in self.active_powerups:
            center_x, center_y = WIDTH // 2, HEIGHT // 3
            # Draw a large pulsing magnet icon
            pulse = (math.sin(self.frame_count * 0.1) + 1) * 0.5  # 0 to 1
            size = int(80 + pulse * 40)  # Much larger
            
            # Draw central magnet
            pygame.draw.circle(surface, (255, 100, 100), (center_x, center_y), size, 5)
            pygame.draw.circle(surface, (255, 100, 100, 100), (center_x, center_y), size*2, 2)
            
            # Draw N/S text
            font = pygame.font.Font(None, 60)
            text = font.render("N", True, (255, 100, 100))
            surface.blit(text, (center_x - 15, center_y - 20))
            
            # Draw powerful attraction lines radiating from center
            segments = 16
            for i in range(segments):
                angle = i * 2 * math.pi / segments
                radius1 = size * 1.2
                radius2 = size * 2.5 + pulse * 100  # Long rays
                start_x = center_x + radius1 * math.cos(angle)
                start_y = center_y + radius1 * math.sin(angle)
                end_x = center_x + radius2 * math.cos(angle)
                end_y = center_y + radius2 * math.sin(angle)
                
                # Thicker, more visible lines with varying intensity
                line_width = int(3 + pulse * 3)
                alpha = int(200 - i * 10)
                pygame.draw.line(surface, (255, 100, 100, alpha), 
                                (start_x, start_y), (end_x, end_y), line_width)
        
        # Multi-ball effect: Show multiple ghost balls
        if 'multiball' in self.active_powerups:
            # Choose a new center position (for example, near the middle of the screen)
            center_x = WIDTH // 2
            center_y = HEIGHT // 2 + 100  # 100 pixels below the center
            for i in range(5):
                angle = self.frame_count * 0.1 + i * (2 * math.pi / 5)
                radius = 50
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                size = 15
                # Create a temporary surface with SRCALPHA
                temp_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(temp_surf, (255, 50, 255, 200), (size, size), size, 2)
                surface.blit(temp_surf, (int(x - size), int(y - size)))     

        # Giant ball effect: Show growing/shrinking circle
        if 'giant' in self.active_powerups:
            pulse = (math.sin(self.frame_count * 0.05) + 1) * 0.5
            size = int(30 + pulse * 20)
            # Create a temporary surface with per-pixel alpha
            temp_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(temp_surf, (200, 100, 50, 200), (size, size), size, 3)
            # Draw at a new, more visible position (for example, center-top)
            x = WIDTH // 2
            y = HEIGHT // 2 - 100  # 100 pixels above the center
            surface.blit(temp_surf, (x - size, y - size))

        # Freeze effect: Snow-like particles falling
        if 'freeze' in self.active_powerups:
            for i in range(20):
                x = (self.frame_count * 2 + i * 50) % WIDTH
                y = (self.frame_count * 3 + i * 70) % HEIGHT
                size = random.randint(2, 5)
                pygame.draw.circle(surface, (200, 200, 255), (int(x), int(y)), size)
        
        # Chain reaction effect: Connection lines between balloons
        if 'chain' in self.active_powerups:
            # Draw connecting lines between balloons if they're close enough
            for i, balloon1 in enumerate(self.balloons):
                for balloon2 in list(self.balloons)[i+1:]:
                    dx = balloon1.rect.centerx - balloon2.rect.centerx
                    dy = balloon1.rect.centery - balloon2.rect.centery
                    distance = math.sqrt(dx*dx + dy*dy)
                    if distance < BALLOON_SIZE * 2:
                        # Draw connection line
                        pygame.draw.line(
                            surface,
                            (100, 255, 100, 150),
                            (balloon1.rect.centerx, balloon1.rect.centery),
                            (balloon2.rect.centerx, balloon2.rect.centery),
                            2
                        )

    def Draw_Pause_Screen(self, surface):
         # Semi-transparent dark overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Slightly darker overlay
        surface.blit(overlay, (0, 0))
        
        # Title
        pause_title = pygame.font.Font(None, 100).render("GAME PAUSED", True, WHITE)
        title_rect = pause_title.get_rect(center=(WIDTH//2, HEIGHT//2 - 200))
        surface.blit(pause_title, title_rect)
        
        # Draw buttons with more space and different layout
        resume_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 - 50, 400, 80)
        quit_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 + 50, 400, 80)
        
        # Draw resume button
        pygame.draw.rect(surface, (0, 180, 0), resume_rect, border_radius=15)
        pygame.draw.rect(surface, WHITE, resume_rect, 3, border_radius=15)
        resume_text = self.font.render("Resume Game", True, WHITE)
        surface.blit(resume_text, resume_text.get_rect(center=resume_rect.center))
        
        # Draw quit button
        pygame.draw.rect(surface, (180, 0, 0), quit_rect, border_radius=15)
        pygame.draw.rect(surface, WHITE, quit_rect, 3, border_radius=15)
        quit_text = self.font.render("End Game", True, WHITE)
        surface.blit(quit_text, quit_text.get_rect(center=quit_rect.center))
        
        # Add a hint text
        hint_text = self.small_font.render("Press 'P' to resume", True, (200, 200, 200))
        hint_rect = hint_text.get_rect(center=(WIDTH//2, HEIGHT - 100))
        surface.blit(hint_text, hint_rect)
        
        
    def Draw_Game_Over_Screen(self, surface):
        """Design the Game_Over screen"""
        # Draw stars
        for star in self.stars:
            pygame.draw.circle(
                surface, 
                (100, 100, 150), 
                (int(star['x']), int(star['y'])), 
                int(star['size'])
            )
                
        # Determine winner based on game mode
        if isinstance(self.game_mode, CooperativeMode):
            total_score = self.red_score + self.green_score
            if total_score >= self.game_mode.target_score:
                winner_text = "Victory! Target Score Reached!"
                winner_color = GOLD
            else:
                winner_text = "Defeat! Time Ran Out"
                winner_color = (200, 0, 0)
        elif isinstance(self.game_mode, SurvivalMode):
            winner_text = f"Survived to Level {self.game_mode.level}!"
            winner_color = GOLD
        else:  # Standard or TimeAttack
            if self.green_score == self.red_score:
                winner_text = "It's a Tie!"
                winner_color = (200, 200, 200)
            elif self.green_score > self.red_score:
                winner_text = "Green Player Wins!"
                winner_color = GREEN
            else:
                winner_text = "Red Player Wins!"
                winner_color = RED
        
        # Draw semi-transparent background panel
        panel_rect = pygame.Rect(WIDTH//2 - 400, HEIGHT//2 - 250, 800, 500)
        s = pygame.Surface((800, 500), pygame.SRCALPHA)
        s.fill((0, 0, 40, 200))
        surface.blit(s, panel_rect)
        pygame.draw.rect(surface, (100, 100, 200), panel_rect, 3, border_radius=10)
        
        # Draw title
        title_font = pygame.font.Font(None, 80)
        end_text = title_font.render("Game Over!", True, WHITE)
        end_rect = end_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 200))
        surface.blit(end_text, end_rect)
        
        # Draw winner
        winner_font = pygame.font.Font(None, 70)
        winner_surface = winner_font.render(winner_text, True, winner_color)
        winner_rect = winner_surface.get_rect(center=(WIDTH//2, HEIGHT//2 - 120))
        surface.blit(winner_surface, winner_rect)
        
        # Draw final score
        if isinstance(self.game_mode, CooperativeMode):
            score_text = self.font.render(
                f"Final Score: {self.red_score + self.green_score}", 
                True, WHITE
            )
        else:
            score_text = self.font.render(
                f"Final Score - Red: {self.red_score}, Green: {self.green_score}", 
                True, WHITE
            )
        score_rect = score_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 50))
        surface.blit(score_text, score_rect)
        
        # Draw player statistics
        y_pos = HEIGHT//2
        
        # Red player stats
        red_stats = self.player_stats["red"]
        stats_text = [
            f"Hits: {red_stats['hits']}",
            f"Max Combo: {red_stats['max_combo']}x"
        ]
        
        # Draw red player header
        red_header = self.font.render("Red Player", True, RED)
        red_header_rect = red_header.get_rect(center=(WIDTH//2 - 150, y_pos))
        surface.blit(red_header, red_header_rect)
        
        # Draw red player stats
        for i, text in enumerate(stats_text):
            stat_text = self.small_font.render(text, True, WHITE)
            stat_rect = stat_text.get_rect(center=(WIDTH//2 - 150, y_pos + 40 + i * 30))
            surface.blit(stat_text, stat_rect)
                
        # Green player stats
        green_stats = self.player_stats["green"]  # Use "green" instead of "blue"
        stats_text = [
            f"Hits: {green_stats['hits']}",
            f"Max Combo: {green_stats['max_combo']}x"
        ]
        
        # Draw green player header
        green_header = self.font.render("Green Player", True, GREEN)
        green_header_rect = green_header.get_rect(center=(WIDTH//2 + 150, y_pos))
        surface.blit(green_header, green_header_rect)
        
        # Draw green player stats
        for i, text in enumerate(stats_text):
            stat_text = self.small_font.render(text, True, WHITE)
            stat_rect = stat_text.get_rect(center=(WIDTH//2 + 150, y_pos + 40 + i * 30))
            surface.blit(stat_text, stat_rect)
                
        # Draw restart button
        restart_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 150, 300, 60)
        pygame.draw.rect(surface, (0, 100, 200), restart_rect, border_radius=10)
        pygame.draw.rect(surface, WHITE, restart_rect, 2, border_radius=10)
        
        restart_text = self.font.render("Play Again", True, WHITE)
        restart_text_rect = restart_text.get_rect(center=restart_rect.center)
        surface.blit(restart_text, restart_text_rect)
        
        # Draw quit instruction
        quit_text = self.small_font.render("Press ESC to quit", True, (200, 200, 200))
        quit_rect = quit_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 230))
        surface.blit(quit_text, quit_rect)

    def draw(self, surface):
        """
        Draw the game in various game states
        """
        # Use white background for all screens
        surface.fill((255, 255, 255))  # White background can be changed to black
        
        # Call appropriate draw method based on game state
        if self.game_state == "mode_select":
            self.Draw_mode_select_screen(surface)
        elif self.game_state == "difficulty_select":
            self.Draw_difficulty_screen_select(surface)
        elif self.game_state == "start":
            self.Draw_start_screen(surface)
        elif self.game_state == "playing":
            self.Draw_Play_screen(surface)
        elif self.game_state == "paused":
            # Draw the playing screen first, then overlay the pause screen
            self.Draw_Play_screen(surface)
            self.Draw_Pause_Screen(surface)
        else:  # "end" state
            self.Draw_Game_Over_Screen(surface)

    def pop_balloon_at_point(self, event):
            """
            Expects event to be a tuple: (ball_color, x, y, detected_radius, frame_number, is_back)
            Checks if the detected ball's radius is within tolerance of the calibrated radius
            for the corresponding screen region before registering a balloon pop.
            """
            ball_color, x, y, detected_radius, frame_number, is_back = event
    
            # Determine the nearest calibration region
            min_dist = float('inf')
            nearest_region = None
            for region, pos in self.calibration_points.items():
                dist = ((x - pos[0])**2 + (y - pos[1])**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    nearest_region = region

            # Retrieve the expected calibrated radius for this region and color
            calibrated_radius = self.ball_calibration.get(ball_color, {}).get(nearest_region)
            if calibrated_radius is None:
                logger.warning(f"No calibration data for {ball_color} in region {nearest_region}")
                return
                
            # Convert to float values for comparison
            detected_radius = float(detected_radius.item() if isinstance(detected_radius, np.ndarray) else detected_radius)
            calibrated_radius = float(calibrated_radius.item() if isinstance(calibrated_radius, np.ndarray) else calibrated_radius)

                
            # Define a tolerance for the radius comparison (in pixels)
            RADIUS_TOLERANCE = 2.5

            # Check if the detected ball radius is expected and the ball is not returning from the wall
            if (abs(detected_radius - calibrated_radius) > RADIUS_TOLERANCE) or (is_back):
                logger.debug(f"Ball detection skipped: radius mismatch or ball returning from wall")
                return
            
            # First check for powerup collisions
            ball_rect = pygame.Rect(
                x - detected_radius,
                y - detected_radius,
                detected_radius * 2,
                detected_radius * 2
            )
            
            # Check for powerup collision
            for powerup in list(self.powerups):
                if powerup.rect.colliderect(ball_rect):
                    logger.info(f"Ball collision with {powerup.type} powerup detected")
                    self.collect_powerup(powerup)
                    return  # Don't also pop a balloon in the same hit
            
            # Apply multi-ball effect if active

            is_multiball = 'multiball' in self.active_powerups
            
            # Filter to balloons in vicinity for efficiency (spatial partitioning)
            potential_balloons = []
            for balloon in self.balloons:
                balloon_center = balloon.rect.center
                dx = balloon_center[0] - x
                dy = balloon_center[1] - y
                # Only check balloons within reasonable distance
                if is_multiball:
                    if abs(dx) < BALLOON_SIZE * 2 and abs(dy) < BALLOON_SIZE * 2:
                        potential_balloons.append(balloon)
                else:
                    if abs(dx) < BALLOON_SIZE * 1.5 and abs(dy) < BALLOON_SIZE * 1.5:
                        potential_balloons.append(balloon)
            
            popped_balloons = []
            # Check collision with filtered balloons
            for balloon in potential_balloons:
                balloon_center = balloon.rect.center
                base_radius = (balloon.rect.width + balloon.rect.height) / 4
                
                # Apply giant ball powerup effect
                scale = 1.5 if 'giant' in self.active_powerups else 1.0

                if 'multiball' in self.active_powerups:
                    tolerance = calibrated_radius * scale + 30  # increased extra tolerance
                else:
                    tolerance = calibrated_radius * scale + 15

                effective_radius = base_radius + tolerance
                dx = balloon_center[0] - x
                dy = balloon_center[1] - y
                distance = (dx*dx + dy*dy) ** 0.5

                if distance <= effective_radius:
                    # Check cooldown to prevent duplicate hits
                    if is_multiball:
                        hit_ok = True
                    else:
                        hit_ok = False
                        if balloon.color == RED and frame_number - self.REDLastEvent > self.COOLDOWN_FRAMES:
                            self.REDLastEvent = frame_number
                            hit_ok = True
                        elif balloon.color == GREEN and frame_number - self.GREENLastEvent > self.COOLDOWN_FRAMES:
                            self.GREENLastEvent = frame_number
                            hit_ok = True

                    if hit_ok:
                        popped_balloons.append(balloon)
                        if not is_multiball:
                            break # Only pop one balloon per hit
                            
            # Pop all the balloons that were hit
            for balloon in popped_balloons:
                self.pop_balloon(balloon, "camera")
                
                # Add trail particles
                if random.random() < 0.5:  # Only sometimes to avoid too many particles
                    for _ in range(5):
                        self.effects_manager.add_trail(
                        x + random.uniform(-10, 10),
                        y + random.uniform(-10, 10),
                        (255, 255, 200) if ball_color == "yellow" else (100, 100, 255),
                        count=1,
                        size=random.uniform(3, 5)
                    )


    def run(self):
        """Main game loop"""
        running = True
        try:
            while running:
                # Ensure display is initialized before each iteration
                if not pygame.display.get_init():
                    pygame.display.init()

                running = self.handle_events()
                self.update()
                
                # Create virtual surface at target resolution
                try:
                    virtual_surface = pygame.Surface((WIDTH, HEIGHT))
                except Exception as surface_e:
                    logger.critical(f"Failed to create surface: {surface_e}")
                    break
                self.draw(virtual_surface)
                
                # Scale virtual surface to actual display size
                try:
                    scaled_surface = pygame.transform.scale(virtual_surface, self.actual_surface.get_size())
                    self.actual_surface.blit(scaled_surface, (0, 0))
                    pygame.display.flip()
                except Exception as display_e:
                    logger.critical(f"Display update failed: {display_e}")
                    break
                
                clock.tick(FPS)
        except Exception as e:
            logger.critical(f"Game crashed: {e}", exc_info=True)
        finally:
            pygame.quit()
            logger.info("Game ended")
            sys.exit()

if __name__ == "__main__":
    game = Game()
    game.run()