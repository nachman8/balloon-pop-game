# enhanced_effects.py - Add this file to your project

import pygame
import random
import math
import numpy as np
from typing import Tuple, List, Dict, Optional

class ParticleSystem:
    """Advanced particle system for visual effects"""
    
    def __init__(self, max_particles=1000):
        self.particles = []
        self.max_particles = max_particles
        
    def update(self):
        """Update all particles"""
        # Remove dead particles first
        self.particles = [p for p in self.particles if not p.dead]
        
        # Update remaining particles
        for particle in self.particles:
            particle.update()
            
    def draw(self, surface):
        """Draw all particles to the surface"""
        for particle in self.particles:
            particle.draw(surface)
            
    def create_explosion(self, x, y, color, count=20, size_range=(3, 8), 
                        speed_range=(2, 8), lifetime=30):
        """Create an explosion effect at the given position"""
        count = min(count, self.max_particles - len(self.particles))
        
        for _ in range(count):
            # Determine particle type based on randomness
            if random.random() < 0.2:  # 20% chance for special particles
                particle = StarParticle(
                    x, y, color, 
                    size=random.uniform(*size_range),
                    lifetime=int(random.uniform(lifetime * 0.5, lifetime * 1.5))
                )
            else:  # Regular particles
                particle = ExplosionParticle(
                    x, y, color, 
                    size=random.uniform(*size_range),
                    speed=random.uniform(*speed_range),
                    lifetime=int(random.uniform(lifetime * 0.7, lifetime * 1.3))
                )
            
            self.particles.append(particle)
            
    def create_trail(self, x, y, color, count=1, size=2, lifetime=10):
        """Create a trail effect behind moving objects"""
        count = min(count, self.max_particles - len(self.particles))
        
        for _ in range(count):
            offset_x = random.uniform(-2, 2)
            offset_y = random.uniform(-2, 2)
            
            particle = TrailParticle(
                x + offset_x, y + offset_y, color, 
                size=size * random.uniform(0.7, 1.3),
                lifetime=int(random.uniform(lifetime * 0.7, lifetime * 1.3))
            )
            
            self.particles.append(particle)
            
    def create_sparkle(self, x, y, color, count=3, size=3, duration=20):
        """Create a sparkle effect"""
        count = min(count, self.max_particles - len(self.particles))
        
        for _ in range(count):
            offset_x = random.uniform(-10, 10)
            offset_y = random.uniform(-10, 10)
            
            particle = SparkleParticle(
                x + offset_x, y + offset_y, color,
                size=size * random.uniform(0.8, 1.2),
                lifetime=int(random.uniform(duration * 0.8, duration * 1.2))
            )
            
            self.particles.append(particle)
            
    def create_text_popup(self, text, x, y, color, font_size=36, duration=60, 
                         rise=True, fade=True):
        """Create a floating text effect"""
        if len(self.particles) < self.max_particles:
            particle = TextParticle(
                text, x, y, color, font_size, duration, rise, fade
            )
            self.particles.append(particle)
            
    def clear(self):
        """Clear all particles"""
        self.particles.clear()


class BaseParticle:
    """Base class for all particles"""
    
    def __init__(self, x, y, color, lifetime=30):
        self.x = x
        self.y = y
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.dead = False
        
    def update(self):
        """Update particle state"""
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.dead = True
            
    def draw(self, surface):
        """Draw particle to the surface"""
        # Each subclass must implement this method
        pass


class ExplosionParticle(BaseParticle):
    """Particle for explosion effects"""
    
    def __init__(self, x, y, color, size=3, speed=5, lifetime=30):
        super().__init__(x, y, color, lifetime)
        
        # Randomize direction
        angle = random.uniform(0, math.pi * 2)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        
        # Physical properties
        self.size = size
        self.gravity = 0.1
        self.drag = 0.98
        
        # Visual properties
        r, g, b = color
        variation = 30
        self.color = (
            max(0, min(255, r + random.randint(-variation, variation))),
            max(0, min(255, g + random.randint(-variation, variation))),
            max(0, min(255, b + random.randint(-variation, variation)))
        )
        
    def update(self):
        """Update position and properties"""
        super().update()
        
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Apply physics
        self.vy += self.gravity
        self.vx *= self.drag
        self.vy *= self.drag
        
        # Shrink over time
        life_ratio = self.lifetime / self.max_lifetime
        self.current_size = self.size * life_ratio
        
    def draw(self, surface):
        """Draw the particle"""
        if self.dead:
            return
            
        # Calculate alpha based on remaining life
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        
        # Create a temporary surface with per-pixel alpha
        size = max(1, int(self.current_size * 2))
        temp = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Draw the particle with appropriate alpha
        pygame.draw.circle(
            temp, 
            (*self.color, alpha), 
            (size // 2, size // 2), 
            max(1, int(self.current_size))
        )
        
        # Blit to main surface
        surface.blit(temp, (int(self.x - self.current_size), int(self.y - self.current_size)))


class TrailParticle(BaseParticle):
    """Particle for motion trails"""
    
    def __init__(self, x, y, color, size=2, lifetime=10):
        super().__init__(x, y, color, lifetime)
        self.size = size
        
        # Add slight random movement
        self.vx = random.uniform(-0.3, 0.3) 
        self.vy = random.uniform(-0.3, 0.3)
        
    def update(self):
        """Update position and properties"""
        super().update()
        
        # Slight movement
        self.x += self.vx
        self.y += self.vy
        
        # Calculate current size based on lifetime
        life_ratio = self.lifetime / self.max_lifetime
        self.current_size = self.size * (life_ratio ** 1.5)
        
    def draw(self, surface):
        """Draw the particle"""
        if self.dead:
            return
            
        # Calculate alpha based on remaining life
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        
        # Create a temporary surface with per-pixel alpha
        size = max(1, int(self.current_size * 2))
        temp = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Draw the particle with appropriate alpha
        pygame.draw.circle(
            temp, 
            (*self.color, alpha), 
            (size // 2, size // 2), 
            max(1, int(self.current_size))
        )
        
        # Blit to main surface
        surface.blit(temp, (int(self.x - self.current_size), int(self.y - self.current_size)))


class StarParticle(BaseParticle):
    """Star-shaped particle for special effects"""
    
    def __init__(self, x, y, color, size=4, lifetime=20):
        super().__init__(x, y, color, lifetime)
        self.size = size
        self.rotation = random.uniform(0, math.pi * 2)
        self.rotation_speed = random.uniform(-0.2, 0.2)
        
        # Add slight movement
        self.vx = random.uniform(-1, 1)
        self.vy = random.uniform(-1, 1)
        
    def update(self):
        """Update position and properties"""
        super().update()
        
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Update rotation
        self.rotation += self.rotation_speed
        
        # Calculate current size based on lifetime
        life_ratio = self.lifetime / self.max_lifetime
        self.current_size = self.size * life_ratio
        
    def draw(self, surface):
        """Draw the star-shaped particle"""
        if self.dead:
            return
            
        # Calculate alpha based on remaining life
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        
        # Create a temporary surface with per-pixel alpha
        size = int(self.current_size * 4)
        temp = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Calculate star points
        points = []
        center = (size // 2, size // 2)
        outer_radius = self.current_size * 2
        inner_radius = self.current_size
        
        # Create a 5-pointed star
        for i in range(10):
            radius = outer_radius if i % 2 == 0 else inner_radius
            angle = self.rotation + (i * math.pi * 2 / 10)
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            points.append((x, y))
        
        # Draw the star with appropriate alpha
        if len(points) >= 3:
            pygame.draw.polygon(temp, (*self.color, alpha), points)
        
        # Blit to main surface
        surface.blit(temp, (int(self.x - size // 2), int(self.y - size // 2)))


class SparkleParticle(BaseParticle):
    """Sparkle effect for highlights and emphasis"""
    
    def __init__(self, x, y, color, size=3, lifetime=15):
        super().__init__(x, y, color, lifetime)
        self.size = size
        self.angle = random.uniform(0, math.pi * 2)
        self.rotation_speed = random.uniform(0.1, 0.3)
        self.pulse_rate = random.uniform(0.1, 0.2)
        
    def update(self):
        """Update properties"""
        super().update()
        
        # Update rotation
        self.angle += self.rotation_speed
        
        # Pulsing effect
        pulse = 0.7 + 0.3 * math.sin(self.lifetime * self.pulse_rate)
        self.current_size = self.size * pulse * (self.lifetime / self.max_lifetime)
        
    def draw(self, surface):
        """Draw a sparkle as crossing lines"""
        if self.dead:
            return
            
        # Calculate alpha based on remaining life
        alpha = int(255 * (self.lifetime / self.max_lifetime))
        
        # Create a temporary surface with per-pixel alpha
        size = int(self.current_size * 6)
        temp = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Draw crossed lines
        center = (size // 2, size // 2)
        length = self.current_size * 2
        
        for i in range(4):
            angle = self.angle + (i * math.pi / 4)
            start_x = center[0] + math.cos(angle) * length
            start_y = center[1] + math.sin(angle) * length
            end_x = center[0] - math.cos(angle) * length
            end_y = center[1] - math.sin(angle) * length
            
            pygame.draw.line(
                temp, 
                (*self.color, alpha), 
                (start_x, start_y), 
                (end_x, end_y), 
                max(1, int(self.current_size / 2))
            )
        
        # Blit to main surface
        surface.blit(temp, (int(self.x - size // 2), int(self.y - size // 2)))


class TextParticle(BaseParticle):
    """Floating text effect for score popups and notifications"""
    
    def __init__(self, text, x, y, color, font_size=36, lifetime=60, 
                rise=True, fade=True):
        super().__init__(x, y, color, lifetime)
        
        # Text properties
        self.text = text
        self.font_size = font_size
        self.font = pygame.font.Font(None, font_size)
        self.rise = rise
        self.fade = fade
        
        # Animation properties
        self.offset_y = 0
        self.scale = 1.2  # Start slightly larger
        
        # Pre-render text
        self.text_surface = self.font.render(text, True, color)
        self.width = self.text_surface.get_width()
        self.height = self.text_surface.get_height()
        
    def update(self):
        """Update position and properties"""
        super().update()
        
        # Rise effect
        if self.rise:
            self.offset_y -= max(0.5, 3.0 * (self.lifetime / self.max_lifetime))
        
        # Scale effect - shrink to normal size
        life_ratio = self.lifetime / self.max_lifetime
        if life_ratio > 0.7:  # First 30% of lifetime
            # Scale down from 1.2 to 1.0
            progress = (1.0 - (life_ratio - 0.7) / 0.3)  # 0 to 1
            self.scale = 1.0 + 0.2 * (1.0 - progress)
        else:
            self.scale = 1.0
        
    def draw(self, surface):
        """Draw the text effect"""
        if self.dead:
            return
            
        # Calculate alpha based on remaining life
        alpha = 255
        if self.fade:
            alpha = int(255 * (self.lifetime / self.max_lifetime))
        
        # Calculate scaled size
        scaled_width = int(self.width * self.scale)
        scaled_height = int(self.height * self.scale)
        
        # Scale text surface if needed
        if self.scale != 1.0:
            scaled_surface = pygame.transform.smoothscale(
                self.text_surface, (scaled_width, scaled_height))
        else:
            scaled_surface = self.text_surface
        
        # Apply alpha
        if alpha < 255:
            temp = pygame.Surface((scaled_width, scaled_height), pygame.SRCALPHA)
            temp.fill((0, 0, 0, 0))  # Transparent
            temp.blit(scaled_surface, (0, 0))
            temp.set_alpha(alpha)
            scaled_surface = temp
        
        # Calculate position
        pos_x = int(self.x - scaled_width / 2)
        pos_y = int(self.y - scaled_height / 2 + self.offset_y)
        
        # Draw to surface
        surface.blit(scaled_surface, (pos_x, pos_y))


class ScreenShake:
    """Screen shake effect for impacts and explosions"""
    
    def __init__(self):
        self.intensity = 0
        self.decay = 0.9  # How quickly the effect diminishes
        self.offset = (0, 0)
        
    def add_shake(self, amount):
        """Add shake intensity"""
        self.intensity = min(50, self.intensity + amount)
        
    def update(self):
        """Update the shake effect and return current offset"""
        if self.intensity > 0.5:
            # Calculate random shake offset based on intensity
            self.offset = (
                random.randint(-int(self.intensity), int(self.intensity)),
                random.randint(-int(self.intensity), int(self.intensity))
            )
            # Decay the shake effect
            self.intensity *= self.decay
        else:
            self.intensity = 0
            self.offset = (0, 0)
            
        return self.offset


class EffectsManager:
    """Manages all visual effects including particles, screen shake, and text"""
    
    def __init__(self):
        self.particle_system = ParticleSystem()
        self.screen_shake = ScreenShake()
        
    def update(self):
        """Update all effects"""
        self.particle_system.update()
        self.screen_shake.update()
        
    def draw(self, surface):
        """Draw all effects to the surface"""
        # Get current shake offset
        shake_offset = self.screen_shake.offset
        
        # Apply screen shake if any screen-space objects need it
        # Particles already handle their own drawing with positions
        
        # Draw all particles
        self.particle_system.draw(surface)
        
        return shake_offset
        
    def add_explosion(self, x, y, color, special=False, count=None):
        """Create an explosion effect"""
        # Determine particle count based on whether it's a special explosion
        if count is None:
            count = 30 if special else 20
            
        # Create particle explosion
        self.particle_system.create_explosion(
            x, y, color, count=count,
            size_range=(4, 12) if special else (3, 8),
            speed_range=(3, 10) if special else (2, 8),
            lifetime=40 if special else 30
        )
        
        # Add screen shake
        self.screen_shake.add_shake(10 if special else 5)
        
    def add_trail(self, x, y, color, count=1, size=2):
        """Create a trail behind moving objects"""
        self.particle_system.create_trail(x, y, color, count, size)
        
    def add_sparkle(self, x, y, color, count=3, size=3):
        """Create a sparkle effect for emphasis"""
        self.particle_system.create_sparkle(x, y, color, count, size)
        
    def add_text_popup(self, text, x, y, color, font_size=36, duration=60, rise=True):
        """Create a floating text popup"""
        self.particle_system.create_text_popup(text, x, y, color, font_size, duration, rise)
        
    def add_score_popup(self, score, x, y, color, combo=1):
        """Create a score popup with combo formatting"""
        prefix = f"{combo}x " if combo > 1 else ""
        sign = "+" if score >= 0 else ""
        text = f"{prefix}{sign}{score}"
        
        # Larger text for higher combos
        font_size = 36 + min(60, combo * 4)
        
        self.particle_system.create_text_popup(text, x, y, color, font_size)
        
        # Add sparkles for higher combos
        if combo >= 3:
            sparkle_count = min(20, combo * 2)
            self.particle_system.create_sparkle(
                x, y, color, count=sparkle_count, size=combo * 0.5)
        
    def clear(self):
        """Clear all effects"""
        self.particle_system.clear()