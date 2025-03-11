# game_analytics.py - Add this file to your project

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class GameAnalytics:
    """Tracks and manages player statistics and game history"""
    
    def __init__(self, save_file="game_stats.json"):
        self.save_file = save_file
        self.current_session = {
            "start_time": time.time(),
            "games_played": 0,
            "total_time": 0,
            "game_history": []
        }
        self.stats = self._load_stats()
        
    def _load_stats(self) -> Dict[str, Any]:
        """Load statistics from file if available"""
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading game statistics: {e}")
        
        # Default stats if file doesn't exist or is invalid
        return {
            "total_games": 0,
            "total_playtime": 0,
            "high_scores": {
                "standard": {"red": 0, "green": 0},
                "time_attack": {"red": 0, "green": 0},
                "survival": {"level": 0, "score": 0},
                "cooperative": {"score": 0}
            },
            "achievements": {
                "first_game": False,
                "ten_games": False,
                "hundred_games": False,
                "combo_master": False,  # Get a 10x combo
                "perfect_game": False   # Win with no misses
            },
            "player_stats": {
                "red": {
                    "total_score": 0,
                    "balloons_popped": 0,
                    "highest_combo": 0
                },
                "green": {
                    "total_score": 0,
                    "balloons_popped": 0,
                    "highest_combo": 0
                }
            },
            "game_history": []  # Last 50 games
        }
        
    def save_stats(self) -> None:
        """Save current statistics to file"""
        try:
            with open(self.save_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except IOError as e:
            print(f"Error saving game statistics: {e}")
    
    def start_game(self, game_mode: str, difficulty: str) -> None:
        """Record the start of a new game"""
        self.current_game = {
            "mode": game_mode,
            "difficulty": difficulty,
            "start_time": time.time(),
            "duration": 0,
            "red_score": 0,
            "green_score": 0,
            "red_hits": 0,
            "green_hits": 0,
            "red_max_combo": 0,
            "green_max_combo": 0,
            "powerups_collected": 0,
            "survival_level": 1
        }
        
    def update_game(self, **kwargs) -> None:
        """Update current game statistics with new values"""
        if hasattr(self, 'current_game'):
            self.current_game.update(kwargs)
            
    def end_game(self) -> None:
        """Record the end of the current game"""
        if not hasattr(self, 'current_game'):
            return
            
        # Calculate duration
        self.current_game["duration"] = time.time() - self.current_game["start_time"]
        
        # Update session stats
        self.current_session["games_played"] += 1
        self.current_session["total_time"] += self.current_game["duration"]
        self.current_session["game_history"].append(self.current_game.copy())
        
        # Update global stats
        self.stats["total_games"] += 1
        self.stats["total_playtime"] += self.current_game["duration"]
        
        # Update player stats
        for color in ["red", "green"]:
            self.stats["player_stats"][color]["total_score"] += self.current_game[f"{color}_score"]
            self.stats["player_stats"][color]["balloons_popped"] += self.current_game[f"{color}_hits"]
            
            if self.current_game[f"{color}_max_combo"] > self.stats["player_stats"][color]["highest_combo"]:
                self.stats["player_stats"][color]["highest_combo"] = self.current_game[f"{color}_max_combo"]
        
        # Check for high scores
        mode = self.current_game["mode"]
        if mode == "standard":
            for color in ["red", "green"]:
                if self.current_game[f"{color}_score"] > self.stats["high_scores"]["standard"][color]:
                    self.stats["high_scores"]["standard"][color] = self.current_game[f"{color}_score"]
        elif mode == "time_attack":
            for color in ["red", "green"]:
                if self.current_game[f"{color}_score"] > self.stats["high_scores"]["time_attack"][color]:
                    self.stats["high_scores"]["time_attack"][color] = self.current_game[f"{color}_score"]
        elif mode == "survival":
            total_score = self.current_game["red_score"] + self.current_game["green_score"]
            if self.current_game["survival_level"] > self.stats["high_scores"]["survival"]["level"] or \
               (self.current_game["survival_level"] == self.stats["high_scores"]["survival"]["level"] and \
                total_score > self.stats["high_scores"]["survival"]["score"]):
                self.stats["high_scores"]["survival"]["level"] = self.current_game["survival_level"]
                self.stats["high_scores"]["survival"]["score"] = total_score
        elif mode == "cooperative":
            total_score = self.current_game["red_score"] + self.current_game["green_score"]
            if total_score > self.stats["high_scores"]["cooperative"]["score"]:
                self.stats["high_scores"]["cooperative"]["score"] = total_score
        
        # Check for achievements
        if not self.stats["achievements"]["first_game"]:
            self.stats["achievements"]["first_game"] = True
            
        if self.stats["total_games"] >= 10 and not self.stats["achievements"]["ten_games"]:
            self.stats["achievements"]["ten_games"] = True
            
        if self.stats["total_games"] >= 100 and not self.stats["achievements"]["hundred_games"]:
            self.stats["achievements"]["hundred_games"] = True
            
        max_combo = max(self.current_game["red_max_combo"], self.current_game["green_max_combo"])
        if max_combo >= 10 and not self.stats["achievements"]["combo_master"]:
            self.stats["achievements"]["combo_master"] = True
            
        # Add to game history (keep last 50)
        game_record = self.current_game.copy()
        game_record["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stats["game_history"].append(game_record)
        self.stats["game_history"] = self.stats["game_history"][-50:]
        
        # Save stats to file
        self.save_stats()
        
    def get_achievement_progress(self) -> Dict[str, Any]:
        """Get progress toward achievements"""
        progress = {}
        
        # Games played progress
        total_games = self.stats["total_games"]
        progress["games_played"] = {
            "current": total_games,
            "first_game": self.stats["achievements"]["first_game"],
            "ten_games": self.stats["achievements"]["ten_games"],
            "ten_games_progress": min(10, total_games) / 10,
            "hundred_games": self.stats["achievements"]["hundred_games"],
            "hundred_games_progress": min(100, total_games) / 100
        }
        
        # Combo achievement
        max_combo = max(self.stats["player_stats"]["red"]["highest_combo"],
                        self.stats["player_stats"]["green"]["highest_combo"])
        progress["combo_master"] = {
            "achieved": self.stats["achievements"]["combo_master"],
            "current": max_combo,
            "target": 10,
            "progress": min(10, max_combo) / 10
        }
        
        # Add other achievements...
        
        return progress
        
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current play session"""
        return {
            "duration": time.time() - self.current_session["start_time"],
            "games_played": self.current_session["games_played"],
            "average_game_time": (self.current_session["total_time"] / max(1, self.current_session["games_played"]))
        }
        
    def get_player_stats(self) -> Dict[str, Any]:
        """Get player statistics"""
        return self.stats["player_stats"]
        
    def get_high_scores(self) -> Dict[str, Any]:
        """Get high scores for all game modes"""
        return self.stats["high_scores"]