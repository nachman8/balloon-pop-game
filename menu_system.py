# menu_system.py - Add this file to your project

import pygame
import math
import time
import random
from typing import Dict, List, Tuple, Callable, Optional, Any

class MenuItem:
    """Represents a selectable item in a menu"""
    
    def __init__(self, text, action=None, value=None):
        self.text = text
        self.action = action  # Function to call when selected
        self.value = value    # Value to pass to action
        self.rect = None      # Will be set when drawn
        self.hover = False
        self.enabled = True
        self.selected = False
        
    def is_clicked(self, pos):
        """Check if this item is clicked at the given position"""
        return self.rect is not None and self.rect.collidepoint(pos) and self.enabled

class MenuScreen:
    """Base class for menu screens"""
    
    def __init__(self, title, parent=None):
        self.title = title
        self.parent = parent
        self.items = []
        self.background = None
        self.font_large = pygame.font.Font(None, 64)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 36)
        
    def add_item(self, text, action=None, value=None):
        """Add a menu item"""
        self.items.append(MenuItem(text, action, value))
        return self
        
    def add_back_button(self, text="Back"):
        """Add a back button that returns to the parent menu"""
        def go_back(menu_system):
            if self.parent:
                menu_system.set_active_screen(self.parent)
        self.add_item(text, go_back)
        return self
        
    def update(self, dt):
        """Update menu state"""
        # Update animations, etc.
        pass
        
    def handle_event(self, event, menu_system):
        """Handle input events"""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Left mouse button
            pos = pygame.mouse.get_pos()
            for item in self.items:
                if item.is_clicked(pos) and item.enabled:
                    if item.action:
                        if item.value is not None:
                            item.action(menu_system, item.value)
                        else:
                            item.action(menu_system)
                    return True
                    
        return False
        
    def draw(self, surface, time_passed=0):
        """Draw the menu screen"""
        # Set background
        if self.background:
            surface.blit(self.background, (0, 0))
        else:
            surface.fill((0, 0, 40))  # Dark blue background
            
            # Draw animated stars in the background
            for i in range(50):
                x = (math.sin(time_passed * 0.1 + i * 0.3) * 0.5 + 0.5) * surface.get_width()
                y = (math.cos(time_passed * 0.15 + i * 0.7) * 0.5 + 0.5) * surface.get_height()
                size = (math.sin(time_passed * 0.05 + i) * 0.5 + 0.5) * 3 + 1
                color = (180, 180, 255)
                pygame.draw.circle(surface, color, (int(x), int(y)), int(size))
            
        # Draw title
        title_surf = self.font_large.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(centerx=surface.get_width()//2, y=50)
        surface.blit(title_surf, title_rect)
        
        # Draw menu items
        item_y = 200
        for item in self.items:
            # Choose appropriate color
            if not item.enabled:
                color = (150, 150, 150)  # Gray
            elif item.selected:
                color = (255, 255, 0)    # Yellow
            elif item.hover:
                color = (100, 255, 100)  # Light green
            else:
                color = (255, 255, 255)  # White
                
            # Render text
            text_surf = self.font_medium.render(item.text, True, color)
            text_rect = text_surf.get_rect(centerx=surface.get_width()//2, y=item_y)
            surface.blit(text_surf, text_rect)
            
            # Store rectangle for click detection
            item.rect = text_rect
            
            # Move down for next item
            item_y += 60
            
    def check_hover(self, mouse_pos):
        """Update hover state for menu items"""
        for item in self.items:
            item.hover = item.rect is not None and item.rect.collidepoint(mouse_pos) and item.enabled


class MainMenu(MenuScreen):
    """Main menu screen with animated elements"""
    
    def __init__(self):
        super().__init__("Balloon Pop Challenge")
        
        # Animation properties
        self.balloon_positions = []
        for _ in range(10):
            self.balloon_positions.append({
                'x': pygame.display.get_surface().get_width() * 0.1 + pygame.display.get_surface().get_width() * 0.8 * math.random(),
                'y': pygame.display.get_surface().get_height() + 100,
                'speed': 1 + 2 * math.random(),
                'size': 50 + 100 * math.random(),
                'color': random.choice([(255, 0, 0), (0, 255, 0)]),
                'wobble': 40 * math.random(),
                'wobble_speed': 0.01 + 0.05 * math.random(),
                'time': 6.28 * math.random()
            })
            
    def update(self, dt):
        """Update menu animations"""
        # Update floating balloons
        for balloon in self.balloon_positions:
            balloon['y'] -= balloon['speed'] * dt
            balloon['time'] += balloon['wobble_speed'] * dt
            
            # Reset balloons that go off screen
            if balloon['y'] < -balloon['size']:
                balloon['y'] = pygame.display.get_surface().get_height() + 100
                balloon['x'] = pygame.display.get_surface().get_width() * 0.1 + pygame.display.get_surface().get_width() * 0.8 * math.random()
                
    def draw(self, surface, time_passed):
        """Draw the main menu with animations"""
        # First call the parent draw method for background
        super().draw(surface, time_passed)
        
        # Draw animated balloons
        for balloon in self.balloon_positions:
            x = balloon['x'] + math.sin(balloon['time']) * balloon['wobble']
            pygame.draw.circle(
                surface, 
                balloon['color'], 
                (int(x), int(balloon['y'])),
                int(balloon['size'] / 2)
            )


class DifficultyMenu(MenuScreen):
    """Menu for selecting game difficulty"""
    
    def __init__(self, game_mode, parent=None):
        super().__init__(f"{game_mode.name} Mode", parent)
        self.game_mode = game_mode
        
    def draw(self, surface, time_passed):
        """Draw the difficulty menu with game mode description"""
        super().draw(surface, time_passed)
        
        # Draw game mode description
        desc_text = self.font_small.render(self.game_mode.description, True, (200, 200, 255))
        desc_rect = desc_text.get_rect(centerx=surface.get_width()//2, y=120)
        surface.blit(desc_text, desc_rect)


class OptionsMenu(MenuScreen):
    """Menu for game options like sound, display, etc."""
    
    def __init__(self, parent=None):
        super().__init__("Options", parent)
        
        # Slider elements
        self.sliders = []
        
    def add_slider(self, text, value, min_val, max_val, action=None):
        """Add a slider control"""
        self.sliders.append({
            'text': text,
            'value': value,
            'min': min_val,
            'max': max_val,
            'action': action,
            'rect': None,
            'dragging': False
        })
        return self
        
    def handle_event(self, event, menu_system):
        """Handle input events for menu items and sliders"""
        # First check regular menu items
        if super().handle_event(event, menu_system):
            return True
            
        # Handle slider events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = pygame.mouse.get_pos()
            for slider in self.sliders:
                if slider['rect'] and slider['rect'].collidepoint(pos):
                    slider['dragging'] = True
                    # Update slider value based on click position
                    self._update_slider_value(slider, pos[0])
                    return True
                    
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for slider in self.sliders:
                if slider['dragging']:
                    slider['dragging'] = False
                    return True
                    
        elif event.type == pygame.MOUSEMOTION:
            pos = pygame.mouse.get_pos()
            for slider in self.sliders:
                if slider['dragging']:
                    # Update slider value based on drag position
                    self._update_slider_value(slider, pos[0])
                    return True
                    
        return False
        
    def _update_slider_value(self, slider, x_pos):
        """Update slider value based on x position and call action"""
        if not slider['rect']:
            return
            
        # Calculate slider width
        slider_width = 200
        slider_left = slider['rect'].centerx - slider_width // 2
        
        # Calculate new value based on position
        rel_x = max(0, min(slider_width, x_pos - slider_left))
        value_range = slider['max'] - slider['min']
        new_value = slider['min'] + (rel_x / slider_width) * value_range
        
        # Update value and call action if provided
        slider['value'] = new_value
        if slider['action']:
            slider['action'](new_value)
        
    def draw(self, surface, time_passed):
        """Draw the options menu with sliders"""
        super().draw(surface, time_passed)
        
        # Draw sliders
        slider_y = 200 + len(self.items) * 60
        for slider in self.sliders:
            # Draw label
            text_surf = self.font_small.render(slider['text'], True, (255, 255, 255))
            text_rect = text_surf.get_rect(centerx=surface.get_width()//2, y=slider_y)
            surface.blit(text_surf, text_rect)
            
            # Draw slider track
            slider_width = 200
            slider_height = 8
            slider_left = surface.get_width()//2 - slider_width // 2
            slider_top = slider_y + 30
            track_rect = pygame.Rect(slider_left, slider_top, slider_width, slider_height)
            pygame.draw.rect(surface, (100, 100, 100), track_rect, border_radius=4)
            
            # Draw slider handle
            handle_radius = 12
            value_range = slider['max'] - slider['min']
            rel_pos = (slider['value'] - slider['min']) / value_range
            handle_x = slider_left + int(rel_pos * slider_width)
            handle_y = slider_top + slider_height // 2
            pygame.draw.circle(surface, (200, 200, 255), (handle_x, handle_y), handle_radius)
            
            # Store slider rect for interaction
            slider['rect'] = pygame.Rect(slider_left - handle_radius, 
                                         slider_top - handle_radius,
                                         slider_width + handle_radius * 2, 
                                         slider_height + handle_radius * 2)
            
            # Draw value
            value_text = self.font_small.render(f"{slider['value']:.2f}", True, (200, 200, 255))
            value_rect = value_text.get_rect(centerx=surface.get_width()//2, y=slider_y + 60)
            surface.blit(value_text, value_rect)
            
            # Move down for next slider
            slider_y += 100


class StatsScreen(MenuScreen):
    """Screen for displaying player statistics and achievements"""
    
    def __init__(self, analytics, parent=None):
        super().__init__("Player Statistics", parent)
        self.analytics = analytics
        
    def draw(self, surface, time_passed):
        """Draw player statistics"""
        super().draw(surface, time_passed)
        
        # Get latest stats
        high_scores = self.analytics.get_high_scores()
        player_stats = self.analytics.get_player_stats()
        achievements = self.analytics.get_achievement_progress()
        
        # Draw stats sections
        self._draw_high_scores(surface, high_scores, 150)
        self._draw_player_stats(surface, player_stats, 350)
        self._draw_achievements(surface, achievements, 550)
        
    def _draw_high_scores(self, surface, high_scores, y_start):
        """Draw high scores section"""
        # Section title
        section_title = self.font_medium.render("High Scores", True, (255, 255, 100))
        title_rect = section_title.get_rect(centerx=surface.get_width()//2, y=y_start)
        surface.blit(section_title, title_rect)
        
        # Draw high scores for each mode
        y = y_start + 50
        x_center = surface.get_width() // 2
        
        # Standard mode
        mode_text = self.font_small.render("Standard Mode:", True, (200, 200, 255))
        surface.blit(mode_text, (x_center - 250, y))
        
        red_score = self.font_small.render(f"Red: {high_scores['standard']['red']}", True, (255, 100, 100))
        surface.blit(red_score, (x_center + 50, y))
        
        green_score = self.font_small.render(f"Green: {high_scores['standard']['green']}", True, (100, 255, 100))
        surface.blit(green_score, (x_center + 150, y))
        
        # Time Attack mode
        y += 30
        mode_text = self.font_small.render("Time Attack:", True, (200, 200, 255))
        surface.blit(mode_text, (x_center - 250, y))
        
        red_score = self.font_small.render(f"Red: {high_scores['time_attack']['red']}", True, (255, 100, 100))
        surface.blit(red_score, (x_center + 50, y))
        
        green_score = self.font_small.render(f"Green: {high_scores['time_attack']['green']}", True, (100, 255, 100))
        surface.blit(green_score, (x_center + 150, y))
        
        # Survival mode
        y += 30
        mode_text = self.font_small.render("Survival:", True, (200, 200, 255))
        surface.blit(mode_text, (x_center - 250, y))
        
        level_score = self.font_small.render(f"Level: {high_scores['survival']['level']} Score: {high_scores['survival']['score']}", True, (255, 255, 255))
        surface.blit(level_score, (x_center + 50, y))
        
        # Cooperative mode
        y += 30
        mode_text = self.font_small.render("Cooperative:", True, (200, 200, 255))
        surface.blit(mode_text, (x_center - 250, y))
        
        score = self.font_small.render(f"Score: {high_scores['cooperative']['score']}", True, (255, 255, 255))
        surface.blit(score, (x_center + 50, y))
        
    def _draw_player_stats(self, surface, player_stats, y_start):
        """Draw player stats section"""
        # Section title
        section_title = self.font_medium.render("Player Statistics", True, (255, 255, 100))
        title_rect = section_title.get_rect(centerx=surface.get_width()//2, y=y_start)
        surface.blit(section_title, title_rect)
        
        # Draw stats for each player
        y = y_start + 50
        x_center = surface.get_width() // 2
        
        # Red player title
        red_title = self.font_small.render("Red Player", True, (255, 100, 100))
        red_title_rect = red_title.get_rect(centerx=x_center - 150, y=y)
        surface.blit(red_title, red_title_rect)
        
        # Green player title
        green_title = self.font_small.render("Green Player", True, (100, 255, 100))
        green_title_rect = green_title.get_rect(centerx=x_center + 150, y=y)
        surface.blit(green_title, green_title_rect)
        
        # Stats rows
        y += 40
        
        # Total score
        red_score = self.font_small.render(f"Total Score: {player_stats['red']['total_score']}", True, (255, 255, 255))
        surface.blit(red_score, (x_center - 250, y))
        
        green_score = self.font_small.render(f"Total Score: {player_stats['green']['total_score']}", True, (255, 255, 255))
        surface.blit(green_score, (x_center + 50, y))
        
        # Balloons popped
        y += 30
        red_popped = self.font_small.render(f"Balloons: {player_stats['red']['balloons_popped']}", True, (255, 255, 255))
        surface.blit(red_popped, (x_center - 250, y))
        
        green_popped = self.font_small.render(f"Balloons: {player_stats['green']['balloons_popped']}", True, (255, 255, 255))
        surface.blit(green_popped, (x_center + 50, y))
        
        # Highest combo
        y += 30
        red_combo = self.font_small.render(f"Best Combo: {player_stats['red']['highest_combo']}x", True, (255, 255, 255))
        surface.blit(red_combo, (x_center - 250, y))
        
        green_combo = self.font_small.render(f"Best Combo: {player_stats['green']['highest_combo']}x", True, (255, 255, 255))
        surface.blit(green_combo, (x_center + 50, y))
        
    def _draw_achievements(self, surface, achievements, y_start):
        """Draw achievements section"""
        # Section title
        section_title = self.font_medium.render("Achievements", True, (255, 255, 100))
        title_rect = section_title.get_rect(centerx=surface.get_width()//2, y=y_start)
        surface.blit(section_title, title_rect)
        
        # Draw achievements
        y = y_start + 50
        x_left = surface.get_width() // 2 - 250
        
        # First Game
        achieved = "✓" if achievements["games_played"]["first_game"] else "✗"
        text = self.font_small.render(f"{achieved} First Game Completed", True, 
                                     (100, 255, 100) if achievements["games_played"]["first_game"] else (200, 200, 200))
        surface.blit(text, (x_left, y))
        
        # Ten Games
        y += 30
        achieved = "✓" if achievements["games_played"]["ten_games"] else "✗"
        text = self.font_small.render(f"{achieved} Play 10 Games ({min(achievements['games_played']['current'], 10)}/10)", True, 
                                     (100, 255, 100) if achievements["games_played"]["ten_games"] else (200, 200, 200))
        surface.blit(text, (x_left, y))
        
        # Draw progress bar
        progress_width = 200
        progress_height = 10
        progress_x = x_left + 400
        progress_y = y + 10
        
        # Background bar
        pygame.draw.rect(surface, (100, 100, 100), 
                        (progress_x, progress_y, progress_width, progress_height), 
                        border_radius=5)
        
        # Fill bar
        fill_width = int(progress_width * achievements["games_played"]["ten_games_progress"])
        if fill_width > 0:
            pygame.draw.rect(surface, (100, 255, 100), 
                            (progress_x, progress_y, fill_width, progress_height), 
                            border_radius=5)
        
        # Hundred Games
        y += 30
        achieved = "✓" if achievements["games_played"]["hundred_games"] else "✗"
        text = self.font_small.render(f"{achieved} Play 100 Games ({min(achievements['games_played']['current'], 100)}/100)", True, 
                                     (100, 255, 100) if achievements["games_played"]["hundred_games"] else (200, 200, 200))
        surface.blit(text, (x_left, y))
        
        # Progress bar
        progress_y = y + 10
        
        # Background bar
        pygame.draw.rect(surface, (100, 100, 100), 
                        (progress_x, progress_y, progress_width, progress_height), 
                        border_radius=5)
        
        # Fill bar
        fill_width = int(progress_width * achievements["games_played"]["hundred_games_progress"])
        if fill_width > 0:
            pygame.draw.rect(surface, (100, 255, 100), 
                            (progress_x, progress_y, fill_width, progress_height), 
                            border_radius=5)
        
        # Combo Master
        y += 30
        achieved = "✓" if achievements["combo_master"]["achieved"] else "✗"
        text = self.font_small.render(f"{achieved} Combo Master: Get a 10x combo ({achievements['combo_master']['current']}/10)", True, 
                                     (100, 255, 100) if achievements["combo_master"]["achieved"] else (200, 200, 200))
        surface.blit(text, (x_left, y))
        
        # Progress bar
        progress_y = y + 10
        
        # Background bar
        pygame.draw.rect(surface, (100, 100, 100), 
                        (progress_x, progress_y, progress_width, progress_height), 
                        border_radius=5)
        
        # Fill bar
        fill_width = int(progress_width * achievements["combo_master"]["progress"])
        if fill_width > 0:
            pygame.draw.rect(surface, (100, 255, 100), 
                            (progress_x, progress_y, fill_width, progress_height), 
                            border_radius=5)


class MenuSystem:
    """Manages all menu screens and transitions"""
    
    def __init__(self, game):
        self.game = game
        self.screens = {}
        self.active_screen = None
        self.transition = None
        self.start_time = time.time()
        
        # Transition properties
        self.transition_duration = 0.5
        self.transition_progress = 0
        self.transition_from = None
        self.transition_to = None
        
    def add_screen(self, name, screen):
        """Add a screen to the menu system"""
        self.screens[name] = screen
        return self
        
    def set_active_screen(self, name):
        """Set the active screen with transition"""
        if name in self.screens:
            # Start transition
            self.transition_from = self.active_screen
            self.transition_to = name
            self.transition_progress = 0
            
    def update(self, dt):
        """Update menu state and transitions"""
        # Update transition if active
        if self.transition_from is not None and self.transition_to is not None:
            self.transition_progress += dt / self.transition_duration
            
            if self.transition_progress >= 1.0:
                # Transition complete
                self.active_screen = self.transition_to
                self.transition_from = None
                self.transition_to = None
                self.transition_progress = 0
        
        # Update the active screen
        if self.active_screen:
            self.screens[self.active_screen].update(dt)
            
        # Update hover state
        if self.active_screen:
            mouse_pos = pygame.mouse.get_pos()
            self.screens[self.active_screen].check_hover(mouse_pos)
            
    def handle_event(self, event):
        """Handle input events"""
        if self.active_screen:
            return self.screens[self.active_screen].handle_event(event, self)
        return False
        
    def draw(self, surface):
        """Draw the current menu screen with transitions"""
        # Calculate time for animations
        time_passed = time.time() - self.start_time
        
        if self.transition_from is None and self.transition_to is None:
            # No transition, just draw the active screen
            if self.active_screen:
                self.screens[self.active_screen].draw(surface, time_passed)
        else:
            # Draw transition
            if self.transition_from:
                # Create a surface for the from screen
                from_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                self.screens[self.transition_from].draw(from_surface, time_passed)
                
                # Apply fade out
                alpha = int(255 * (1.0 - self.transition_progress))
                from_surface.set_alpha(alpha)
                
                # Draw to main surface
                surface.fill((0, 0, 0))
                surface.blit(from_surface, (0, 0))
            
            if self.transition_to:
                # Create a surface for the to screen
                to_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                self.screens[self.transition_to].draw(to_surface, time_passed)
                
                # Apply fade in
                alpha = int(255 * self.transition_progress)
                to_surface.set_alpha(alpha)
                
                # Draw to main surface
                surface.blit(to_surface, (0, 0))