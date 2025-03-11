import yaml
import os
import logging
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='config.log'
)
logger = logging.getLogger('GameConfig')

# Default configuration values
DEFAULT_CONFIG = {
    # Game settings
    "game": {
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "fullscreen": True,
        "game_duration": 120,  # seconds
        "balloon_size": 200,
        "difficulty_settings": {
            "easy": {
                "spawn_rate": 210,
                "speed_range": [1, 2],
                "max_balloons": 4,
                "special_chance": 0.1
            },
            "normal": {
                "spawn_rate": 180, 
                "speed_range": [2, 3], 
                "max_balloons": 6,
                "special_chance": 0.15
            },
            "hard": {
                "spawn_rate": 150, 
                "speed_range": [2, 4], 
                "max_balloons": 8,
                "special_chance": 0.2
            }
        },
        "sound": {
            "enabled": True,
            "volume": 0.7
        },
        "powerups": {
            "enabled": True,
            "spawn_chance": 0.01,
            "types": ["slow", "double", "magnet"]
        }
    },
    
    # Camera settings
    "camera": {
        "index": 0,
        "max_index": 5,
        "display_width": 1280,
        "display_height": 720,
        "show_debug_info": True,
        "area_threshold": 200,
        "min_ball_size": 5,
        "max_ball_size": 50,
        "frame_skip": {
            "enabled": False,
            "count": 1
        },
        "tracking": {
            "use_ball_tracker": True,
            "trajectory_history": 20,
            "cooldown_frames": 12
        },
        "recording": {
            "clean_video_filename": "clean_video.avi",
            "contour_video_filename": "contour_video.avi"
        }
    },
    
    # Kalman filter settings
    "kalman": {
        "sample_rate": 30,
        "process_noise": {
            "position": 1e-1,
            "velocity": 5e-1,
            "acceleration": 1.0,
            "radius": 2e-2
        },
        "measurement_noise": {
            "position": 1e-2,
            "radius": 1e-3
        },
        "direction_change_threshold": {
            "x": 1.0,
            "y": 1.0
        },
        "min_bounce_velocity": 3.0
    },
    
    # File paths
    "paths": {
        "calibration": {
            "projector": "projector_calibration.yaml",
            "color": "calibration.yaml",
            "ball": "ball_calibration.yaml"
        },
        "sounds": {
            "pop_green": "pop_balloon.wav",
            "pop_red": "pop_red_ballon.wav",
            "powerup": "pop_balloon.wav",  # Reused for now
            "bonus": "pop_balloon.wav",    # Reused for now
            "combo": "pop_red_ballon.wav"  # Reused for now
        },
        "images": {
            "red_balloon": "red_balloon.png",
            "green_balloon": "green_balloon.png"
        },
        "logs": {
            "game": "game.log",
            "camera": "camera.log",
            "kalman": "kalman.log",
            "config": "config.log"
        }
    }
}

class ConfigManager:
    """Manages loading and saving configuration settings"""
    
    def __init__(self, config_file="game_config.yaml"):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
                
                # Merge with defaults to ensure all keys exist
                return self._merge_configs(DEFAULT_CONFIG, config)
            except Exception as e:
                logger.error(f"Error loading configuration: {e}")
                return DEFAULT_CONFIG.copy()
        else:
            logger.info(f"Configuration file {self.config_file} not found, using defaults")
            return DEFAULT_CONFIG.copy()
    
    def _merge_configs(self, default: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge custom config with defaults"""
        result = default.copy()
        
        for key, value in custom.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            with open(self.config_file, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a configuration value by path of keys"""
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, value: Any, *keys: str) -> bool:
        """Set a configuration value by path of keys"""
        if not keys:
            return False
            
        config = self.config
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
            
        config[keys[-1]] = value
        return True
    
    def create_default_config(self) -> bool:
        """Create a default configuration file if it doesn't exist"""
        if not os.path.exists(self.config_file):
            try:
                with open(self.config_file, "w") as f:
                    yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
                logger.info(f"Created default configuration file {self.config_file}")
                return True
            except Exception as e:
                logger.error(f"Error creating default configuration: {e}")
                return False
        return False


# Global config instance
config = ConfigManager()

# Create default config file if it doesn't exist
config.create_default_config()

if __name__ == "__main__":
    # If run directly, print the current configuration
    import json
    print(json.dumps(config.config, indent=2))
    
    # Ask if user wants to reset to defaults
    if input("Reset to default configuration? (y/n): ").lower() == 'y':
        config.config = DEFAULT_CONFIG.copy()
        config.save_config()
        print("Configuration reset to defaults.")
