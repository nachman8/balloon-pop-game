# Balloon Pop Game

An interactive augmented reality game where players use physical balls to pop virtual balloons projected onto a surface. The game uses computer vision to track ball movements and detect collisions with virtual balloons.

## Overview

Balloon Pop Game combines a projector and camera setup to create an engaging physical gaming experience. Players throw or roll colored balls (blue and yellow) at a projection surface to pop virtual balloons (red and green). The game features multiple modes, difficulty levels, and power-ups to enhance gameplay.


![alt text](ball_game.webp)

## Features

- **Physical Interaction**: Use real balls to interact with virtual elements
- **Multiple Game Modes**: Standard, Time Attack, Survival, and Cooperative
- **Difficulty Levels**: Easy, Normal, and Hard settings
- **Power-ups**: Special abilities like slow motion, double points, and chain reactions
- **Combo System**: Chain hits together for bonus points
- **Visual Effects**: Explosions, trails, sparkles and other visual feedback
- **Analytics**: Track player statistics and achievements
- **Calibration Wizard**: Easy setup process for different environments

## Prerequisites

- Python 3.6+
- A projector
- A webcam/camera
- Blue and yellow physical balls

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/balloon-pop-game.git
   cd balloon-pop-game
   ```

2. Install required dependencies:
   ```
   pip install opencv-python numpy pygame pyyaml
   ```

3. Run the calibration wizard (recommended for first use):
   ```
   python CalibrationWizard.py
   ```

4. Start the game:
   ```
   python main.py
   ```

## System Requirements

- **Projector**: Any projector with sufficient brightness for your environment
- **Camera**: Any webcam capable of at least 30 FPS at 720p resolution
- **Computer**: 
  - 64-bit Windows, macOS, or Linux
  - 8GB RAM recommended
  - Intel Core i5 or equivalent processor
  - Dedicated GPU recommended but not required

## Calibration

Before playing, you'll need to calibrate the system using the Calibration Wizard, which guides you through:

1. **Camera Setup**: Configure the camera to see the projection area
2. **Projector Calibration**: Define the corners of the projection area
3. **Color Calibration**: Sample the colors of your physical balls
4. **Ball Size Calibration**: Measure ball sizes at different points in the projection

To run the calibration:
```
python CalibrationWizard.py
```

## Game Modes

### Standard
Competitive mode where red and green players compete for the highest score over a fixed time period.

### Time Attack
Pop as many balloons as possible before time runs out. The spawn rate increases as time decreases.

### Survival
Balloons get progressively faster and more numerous over time. How long can you last?

### Cooperative
Work together to reach a target score before time runs out.

## Power-ups

The game features several power-ups that appear during gameplay:

- **Slow Motion**: Slows down all balloons
- **Double Points**: Doubles the score for each popped balloon
- **Balloon Magnet**: Attracts balloons to the center of the screen
- **Multi-Ball**: Allows hitting multiple balloons with one throw
- **Giant Ball**: Increases the effective size of your ball
- **Freeze**: Temporarily freezes all balloons
- **Chain Reaction**: Creates a chain reaction of pops when a balloon is hit

## Controls

- Physical balls are the main control method
- **ESC**: Quit game
- **P**: Pause/unpause game
- Mouse can be used to navigate menus and manually pop balloons

## Project Structure

- `main.py` - Main entry point that initializes the camera and game
- `game.py` - Core game logic, rendering and game states
- `CalibrationWizard.py` - Calibration tool for camera and projector
- `Kalman_filter.py` - Ball trajectory prediction
- `enhanced_effects.py` - Visual effects system
- `game_analytics.py` - Player statistics and achievements
- `config-system.py` - Configuration management
- `menu_system.py` - UI menu system
- `video_recorder.py` - Utility for recording gameplay

## Configuration Files

The game uses YAML files for configuration:

- `calibration.yaml` - Color calibration for ball detection
- `ball_calibration.yaml` - Ball size calibration
- `projector_calibration.yaml` - Projector boundaries
- `game_config.yaml` - Game settings (optional)

## Troubleshooting

### Camera not detected
- Ensure your camera is properly connected
- Try a different USB port
- Run `python CalibrationWizard.py` to test the camera

### Poor ball detection
- Adjust lighting conditions
- Recalibrate the color detection system
- Use balls with more vibrant colors

### Performance issues
- Lower the camera resolution in `config-system.py`
- Enable frame skipping in settings
- Close other resource-intensive applications

## Development

To modify the game or contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenCV for computer vision capabilities
- PyGame for game rendering
- All contributors and testers
