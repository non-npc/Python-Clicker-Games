import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QGridLayout,
                            QMessageBox, QTabWidget, QScrollArea, QStackedWidget,
                            QGraphicsOpacityEffect, QStackedLayout)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QDateTime, QThread, pyqtSignal, QObject, QUrl, QRect
from PyQt6.QtGui import QFont, QColor, QPainter, QPixmap
import threading
import queue
import winsound  # Windows-only sound module
import random

# Use a flag to prevent too many sounds playing at once
MAX_CONCURRENT_SOUNDS = 4
active_sounds = 0

def play_sound_thread(sound_file):
    """Play sound in a separate thread to allow multiple sounds"""
    global active_sounds
    active_sounds += 1
    if active_sounds <= MAX_CONCURRENT_SOUNDS:
        try:
            # Use SND_ASYNC flag to allow sound to play in background
            # Don't use SND_NOSTOP flag to allow multiple instances
            winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            print(f"Error playing sound: {e}")
    active_sounds -= 1

def play_sound(sound_file):
    """Windows sound playing function that doesn't cut off previous sounds"""
    # Start a new thread for each sound to allow overlapping
    sound_thread = threading.Thread(target=play_sound_thread, args=(sound_file,))
    sound_thread.daemon = True  # Make thread terminate when main program exits
    sound_thread.start()

class Upgrade:
    def __init__(self, name, base_cost, base_production, icon, description, required_upgrade=None):
        self.name = name
        self.count = 0
        self.base_cost = base_cost
        self.cost = base_cost
        self.base_production = base_production
        self.production = base_production
        self.icon = icon
        self.description = description
        self.achievement_name = f"First {name}"
        self.achievement_description = f"Recruit your first {name.lower()}"
        self.required_upgrade = required_upgrade  # Name of the required upgrade
        # Add stats tracking
        self.total_bought = 0
        self.total_spent = 0

class SaveWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, save_data):
        super().__init__()
        self.save_data = save_data
        
    def run(self):
        try:
            with open("space_save_game.json", "w") as f:
                json.dump(self.save_data, f)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class LoadWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def run(self):
        try:
            with open("space_save_game.json", "r") as f:
                save_data = json.load(f)
            self.finished.emit(save_data)
        except Exception as e:
            error_msg = str(e)
            print(f"Failed to load game: {error_msg}")
            self.error.emit(error_msg)

class RotationHelper(QObject):
    rotationChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 0
    
    def getRotation(self):
        return self._rotation
        
    def setRotation(self, value):
        if self._rotation != value:
            self._rotation = value
            self.rotationChanged.emit(value)
    
    rotation = property(getRotation, setRotation)

class MainMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title = QLabel("Galactic Defender")
        title.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Spacing
        layout.addSpacing(50)
        
        # Buttons
        self.new_game_btn = QPushButton("Start New Mission")
        self.new_game_btn.setFont(QFont("Arial", 16))
        self.new_game_btn.setMinimumSize(200, 50)
        layout.addWidget(self.new_game_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.load_game_btn = QPushButton("Continue Mission")
        self.load_game_btn.setFont(QFont("Arial", 16))
        self.load_game_btn.setMinimumSize(200, 50)
        self.load_game_btn.setVisible(os.path.exists("space_save_game.json"))
        layout.addWidget(self.load_game_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.settings_btn = QPushButton("Ship Settings")
        self.settings_btn.setFont(QFont("Arial", 16))
        self.settings_btn.setMinimumSize(200, 50)
        layout.addWidget(self.settings_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.exit_btn = QPushButton("Return to Earth")
        self.exit_btn.setFont(QFont("Arial", 16))
        self.exit_btn.setMinimumSize(200, 50)
        layout.addWidget(self.exit_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add spacing between buttons
        layout.setSpacing(20)

class EnemyButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(130, 150)  # Increased height for HP bar
        
        # Find all enemy images
        self.enemy_images = {}
        self.enemy_directory = "images/enemies"
        self.load_enemy_images()
        
        # Enemy state
        self.current_enemy = None
        self.enemy_name = ""
        self.enemy_hp = 100
        self.max_hp = 100
        self.is_new_enemy = True  # Flag to track if enemy is new and not yet defeated
        
        # Select initial enemy
        self.select_random_enemy()
        
        # Click animation properties
        self.is_clicked = False
        self.click_scale = 0.9  # Scale down to 90% when clicked
        
    def load_enemy_images(self):
        """Load all enemy images from the enemies directory"""
        import glob
        import os
        
        # Use forward slashes for consistency
        path_pattern = self.enemy_directory.replace("\\", "/") + "/*.png"
        image_files = glob.glob(path_pattern)
        
        for image_file in image_files:
            name = os.path.basename(image_file).split(".")[0]  # Get filename without extension
            self.enemy_images[name] = QPixmap(image_file)
            
        if not self.enemy_images:
            print(f"Warning: No enemy images found in {self.enemy_directory}")
            # Create a fallback red square as a placeholder
            placeholder = QPixmap(512, 512)
            placeholder.fill(QColor(255, 0, 0))
            self.enemy_images["placeholder"] = placeholder
    
    def select_random_enemy(self):
        """Select a random enemy from the available images"""
        if not self.enemy_images:
            return
            
        import random
        self.enemy_name = random.choice(list(self.enemy_images.keys()))
        self.current_enemy = self.enemy_images[self.enemy_name]
        self.enemy_hp = self.max_hp
        self.is_new_enemy = True  # Mark this as a new enemy that hasn't been defeated
        self.update()
        
    def damage_enemy(self, damage):
        """Apply damage to the current enemy"""
        self.enemy_hp -= damage
        if self.enemy_hp <= 0:
            # Get the defeated enemy's name and ID before selecting a new one
            defeated_enemy_name = self.enemy_name
            defeated_enemy_id = self.enemy_name
            defeated_enemy_formatted_name = self.get_enemy_name()
            
            # Enemy defeated, select a new one
            self.select_random_enemy()
            
            # Return both the defeated status and the defeated enemy info
            return True, defeated_enemy_id, defeated_enemy_formatted_name
        
        self.update()
        # Return False for not defeated and None for enemy info
        return False, None, None
    
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Draw enemy image
        if self.current_enemy:
            # Calculate target rect for the image (120x120 at the top)
            target_rect = QRect(5, 5, 100, 100)
            
            # If clicked, scale down the drawing
            if self.is_clicked:
                # Calculate scaled rect
                scale_factor = self.click_scale
                width_diff = target_rect.width() * (1 - scale_factor)
                height_diff = target_rect.height() * (1 - scale_factor)
                scaled_rect = QRect(
                    int(target_rect.x() + width_diff / 2),
                    int(target_rect.y() + height_diff / 2),
                    int(target_rect.width() * scale_factor),
                    int(target_rect.height() * scale_factor)
                )
                painter.drawPixmap(scaled_rect, self.current_enemy)
            else:
                painter.drawPixmap(target_rect, self.current_enemy)
        
        # Draw HP bar background
        bar_rect = QRect(5, 130, 120, 15)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(60, 60, 60))
        painter.drawRect(bar_rect)
        
        # Draw HP bar fill based on current HP
        if self.max_hp > 0:
            hp_width = int((self.enemy_hp / self.max_hp) * bar_rect.width())
            hp_rect = QRect(bar_rect.x(), bar_rect.y(), hp_width, bar_rect.height())
            
            # Color changes based on HP percentage
            hp_percent = self.enemy_hp / self.max_hp
            if hp_percent > 0.6:
                # Green for high health
                hp_color = QColor(0, 200, 0)
            elif hp_percent > 0.3:
                # Yellow for medium health
                hp_color = QColor(200, 200, 0)
            else:
                # Red for low health
                hp_color = QColor(200, 0, 0)
                
            painter.setBrush(hp_color)
            painter.drawRect(hp_rect)
        
        # Draw border around HP bar
        painter.setPen(QColor(200, 200, 200))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bar_rect)
        
        painter.end()
    
    def show_click_animation(self):
        # Set clicked state
        self.is_clicked = True
        self.update()
        
        # Reset after short delay
        QTimer.singleShot(100, self.reset_click_animation)
    
    def reset_click_animation(self):
        self.is_clicked = False
        self.update()
        
    def get_enemy_name(self):
        """Return formatted enemy name for display"""
        # Convert string like "some-enemy-name" to "Some Enemy Name"
        if not self.enemy_name:
            return "Unknown Enemy"
        return " ".join(word.capitalize() for word in self.enemy_name.split("-"))

class XPIconLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Set fixed size for the XP icon
        self.setFixedSize(24, 24)
        
        # Load sprite sheet - use the coin spritesheet for now
        # In a real game, you'd replace this with an XP icon
        self.spritesheet = QPixmap("images/coin_spritesheet.png")
        
        # Frame data - each frame is 22x22 pixels
        self.frame_width = 22
        self.frame_height = 22
        
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Calculate source rect based on first frame only
        source_rect = QRect(0, 0, self.frame_width, self.frame_height)
        
        # Draw the first frame scaled to label size
        target_rect = QRect(0, 0, self.width(), self.height())
        painter.drawPixmap(target_rect, self.spritesheet, source_rect)
        
        painter.end()

class NotificationOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up overlay properties
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create container for notification with semi-transparent background
        self.notification_container = QWidget()
        self.notification_container.setObjectName("notificationContainer")
        self.notification_container.setStyleSheet("""
            #notificationContainer {
                background-color: rgba(20, 20, 40, 0.9);
                border-radius: 10px;
                border: 2px solid purple;
            }
            QPushButton#closeButton {
                background-color: rgba(120, 0, 120, 0.7);
                color: white;
                font-weight: bold;
                border-radius: 10px;
                border: 1px solid white;
                padding: 5px;
            }
            QPushButton#closeButton:hover {
                background-color: rgba(170, 0, 170, 0.9);
            }
            QPushButton#okButton {
                background-color: rgba(60, 0, 120, 0.7);
                color: white;
                font-weight: bold;
                border-radius: 10px;
                border: 1px solid white;
                padding: 5px;
                min-height: 30px;
                font-size: 14px;
            }
            QPushButton#okButton:hover {
                background-color: rgba(90, 0, 180, 0.9);
            }
        """)
        
        self.notification_layout = QVBoxLayout(self.notification_container)
        self.notification_layout.setContentsMargins(20, 20, 20, 20)
        
        # Add close button to top-right corner
        close_button_container = QWidget()
        close_layout = QHBoxLayout(close_button_container)
        close_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title in a container with close button
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title label
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: white;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(self.title_label)
        
        # Close button
        self.close_button = QPushButton("X")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.close_notification)
        title_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Add the title container to the main layout
        self.notification_layout.addWidget(title_container)
        
        # Icon label
        self.icon_label = QLabel()
        self.icon_label.setFont(QFont("Arial", 48))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_layout.addWidget(self.icon_label)
        
        # Message label
        self.message_label = QLabel()
        self.message_label.setFont(QFont("Arial", 14))
        self.message_label.setStyleSheet("color: white;")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_layout.addWidget(self.message_label)
        
        # Add OK button at the bottom
        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("okButton")
        self.ok_button.setFixedWidth(100)
        self.ok_button.clicked.connect(self.close_notification)
        ok_button_container = QWidget()
        ok_button_layout = QHBoxLayout(ok_button_container)
        ok_button_layout.addWidget(self.ok_button, alignment=Qt.AlignmentFlag.AlignCenter)
        ok_button_layout.setContentsMargins(0, 10, 0, 0)  # Add some top margin
        self.notification_layout.addWidget(ok_button_container)
        
        # Add the container to the main layout
        self.layout.addWidget(self.notification_container)
        
        # Set fixed size for notification
        self.notification_container.setFixedSize(400, 300)  # Increased height to accommodate OK button
        
        # Initially hide the overlay
        self.hide()
        
        # Auto-hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.hide_animation)
        
        # Animation for fading in/out
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.notification_container.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(500)  # 500ms for fade
        self.fade_animation.finished.connect(self.on_animation_finished)
    
    def show_notification(self, title, icon, message, duration=3000):
        """Show a notification with title, icon, and message for the specified duration"""
        self.title_label.setText(title)
        self.icon_label.setText(icon)
        self.message_label.setText(message)
        
        # Position overlay centered in parent
        if self.parent():
            parent_rect = self.parent().rect()
            self.setGeometry(parent_rect)
        
        # Show overlay
        self.show()
        
        # Start fade-in animation
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        
        # Set auto-hide timer
        self.hide_timer.start(duration)
    
    def close_notification(self):
        """Immediately close the notification when the close button is clicked"""
        self.hide_timer.stop()
        self.hide_animation()
    
    def hide_animation(self):
        """Start fade-out animation"""
        self.hide_timer.stop()
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()
    
    def on_animation_finished(self):
        """Handle animation completion"""
        if self.opacity_effect.opacity() == 0:
            self.hide()

class RPGGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Galactic Defender")
        self.setFixedSize(800, 700)  # Set fixed size to 800x700
        
        # Create status bar
        self.statusBar().showMessage("Ready")
        
        # Set up audio players
        self.setup_audio()
        
        # Initialize game state
        self.xp = 0
        self.xp_per_click = 1
        self.total_xp = 0
        self.total_clicks = 0
        self.player_level = 1
        self.xp_to_next_level = 100  # Base XP needed for level 2
        self.enemies_defeated = 0
        self.enemy_stats = {}  # Dictionary to track statistics for each unique enemy
        self.start_time = QDateTime.currentDateTime()
        self.last_save_time = self.start_time
        
        # Define upgrades with dependencies - space themed
        self.upgrades = [
            Upgrade("Drone", 10, 0.1, "🛸", "A basic drone that attacks alien ships"),  # First upgrade, no dependency
            Upgrade("Fighter", 50, 0.5, "🚀", "A small fighter ship with laser weapons", "Drone"),  # Requires Drone
            Upgrade("Bomber", 200, 2.0, "💣", "Attacks alien fleets with explosive payloads", "Fighter"),  # Requires Fighter
            Upgrade("Cruiser", 1000, 10.0, "🛰️", "Medium-sized ship with advanced weapons systems", "Bomber"),  # Requires Bomber
            Upgrade("Repair Ship", 5000, 50.0, "🔧", "Keeps your fleet operational during battle", "Cruiser"),  # Requires Cruiser
            Upgrade("Destroyer", 10000, 200.0, "⚡", "Heavy warship with devastating firepower", "Repair Ship"),
            Upgrade("Stealth Ship", 50000, 500.0, "🔍", "Invisible to alien sensors for surprise attacks", "Destroyer"),
            Upgrade("Battleship", 100000, 1000.0, "🔥", "Massive warship with planet-destroying weapons", "Stealth Ship"),
            Upgrade("Carrier", 500000, 5000.0, "🛩️", "Launches squadrons of fighter drones", "Battleship"),
            Upgrade("Dreadnought", 1000000, 10000.0, "⚓", "Flagship vessel with unmatched firepower", "Carrier"),
            Upgrade("Star Destroyer", 5000000, 50000.0, "💫", "Obliterates entire alien fleets with ease", "Dreadnought"),
            Upgrade("Time Ship", 10000000, 100000.0, "⏳", "Uses temporal weapons to attack across time", "Star Destroyer"),
            Upgrade("Nova Cannon", 50000000, 500000.0, "☀️", "Harnesses the power of a dying star", "Time Ship"),
            Upgrade("Galaxy Defender", 100000000, 1000000.0, "🌌", "Protects entire star systems from invasion", "Nova Cannon"),
            Upgrade("Universe Guardian", 500000000, 5000000.0, "🌠", "The ultimate defense against cosmic threats", "Galaxy Defender")
        ]
        
        # Achievements
        self.achievements = {
            "First Kill": {"name": "First Kill", "description": "Defeat your first alien ship", "unlocked": False},
            "Monster Hunter": {"name": "Alien Hunter", "description": "Reach Level 5", "unlocked": False},
            "Legendary Slayer": {"name": "Galactic Defender", "description": "Reach Level 20", "unlocked": False}
        }
        
        # Add achievements for each upgrade
        for upgrade in self.upgrades:
            self.achievements[upgrade.achievement_name] = {
                "name": upgrade.achievement_name,
                "description": upgrade.achievement_description,
                "unlocked": False
            }
        
        # Create central widget with stacked layout
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create and add main menu
        self.main_menu = MainMenu()
        self.central_widget.addWidget(self.main_menu)
        
        # Create and add game widget
        self.game_widget = QWidget()
        self.setup_game_ui()
        self.central_widget.addWidget(self.game_widget)
        
        # Create notification overlay
        self.notification_overlay = NotificationOverlay(self)
        
        # Connect menu buttons
        self.main_menu.new_game_btn.clicked.connect(self.start_new_game)
        self.main_menu.load_game_btn.clicked.connect(self.load_game)
        self.main_menu.settings_btn.clicked.connect(self.show_settings)
        self.main_menu.exit_btn.clicked.connect(self.close)
        
        # Center the window
        self.center_window()
        
    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)
        
    def start_new_game(self):
        # Reset game state
        self.xp = 0
        self.xp_per_click = 1
        self.total_xp = 0
        self.total_clicks = 0
        self.player_level = 1
        self.xp_to_next_level = 100  # Base XP needed for level 2
        self.enemies_defeated = 0
        self.enemy_stats = {}  # Clear enemy statistics
        self.start_time = QDateTime.currentDateTime()
        self.last_save_time = self.start_time
        
        # Reset upgrades
        for upgrade in self.upgrades:
            upgrade.count = 0
            upgrade.cost = upgrade.base_cost
            upgrade.production = upgrade.base_production
            upgrade.total_bought = 0
            upgrade.total_spent = 0
        
        # Reset achievements
        for achievement in self.achievements.values():
            achievement["unlocked"] = False
        
        # Reset enemy
        self.enemy_button.select_random_enemy()
        self.enemy_name_label.setText(f"Alien: {self.enemy_button.get_enemy_name()}")
        self.enemies_defeated_label.setText(f"Aliens Defeated: {self.enemies_defeated}")
        
        # Clear enemy statistics display
        self.clear_enemy_stats_display()
        
        # Switch to game view
        self.central_widget.setCurrentWidget(self.game_widget)
        
        # Update visible upgrades to reset the shop view
        self.update_visible_upgrades()
        
        self.update_display()
        self.update_stats()
        self.show_status_message("New mission started")
        
    def show_settings(self):
        QMessageBox.information(self, "Ship Settings", "Settings feature coming soon!")
        
    def setup_game_ui(self):
        # Create game layout
        game_layout = QVBoxLayout(self.game_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        game_layout.addWidget(self.tab_widget)
        
        # Create game tab
        game_tab = QWidget()
        game_tab_layout = QVBoxLayout(game_tab)
        
        # Create XP and level display
        self.level_label = QLabel(f"Level: {self.player_level}")
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.level_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        game_tab_layout.addWidget(self.level_label)
        
        self.xp_label = QLabel(f"XP: {self.xp}/{self.xp_to_next_level}")
        self.xp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.xp_label.setFont(QFont("Arial", 18))
        game_tab_layout.addWidget(self.xp_label)
        
        # Create party members discovered display
        self.party_label = QLabel("1 of 15 fleet ships deployed")
        self.party_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.party_label.setFont(QFont("Arial", 14))
        game_tab_layout.addWidget(self.party_label)
        
        # Create enemy name label
        self.enemy_name_label = QLabel("Alien: Unknown")
        self.enemy_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enemy_name_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        game_tab_layout.addWidget(self.enemy_name_label)
        
        # Create animated enemy button (replacing monster button)
        self.enemy_button = EnemyButton()
        
        # Create click area for the enemy (using transparent button overlay)
        self.enemy_container = QWidget()
        self.enemy_container.setFixedSize(130, 150)
        enemy_container_layout = QVBoxLayout(self.enemy_container)
        enemy_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add the enemy button to the container
        self.enemy_button.setParent(self.enemy_container)
        
        # Create a clickable overlay
        self.enemy_click_area = QPushButton(self.enemy_container)
        self.enemy_click_area.setFixedSize(130, 150)
        self.enemy_click_area.setStyleSheet("background-color: transparent; border: none;")
        self.enemy_click_area.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enemy_click_area.clicked.connect(self.click_enemy)
        
        # Make sure the overlay is on top
        self.enemy_click_area.raise_()
        
        # Center the enemy container
        enemy_layout = QHBoxLayout()
        enemy_layout.addStretch()
        enemy_layout.addWidget(self.enemy_container)
        enemy_layout.addStretch()
        
        game_tab_layout.addLayout(enemy_layout)
        
        # Add enemy defeated counter
        self.enemies_defeated_label = QLabel("Aliens Defeated: 0")
        self.enemies_defeated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enemies_defeated_label.setFont(QFont("Arial", 14))
        game_tab_layout.addWidget(self.enemies_defeated_label)
        
        # Create shop section with scrollable area
        shop_scroll = QScrollArea()
        shop_scroll.setWidgetResizable(True)
        shop_content = QWidget()
        shop_layout = QGridLayout(shop_content)
        shop_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create shop items for each upgrade, but add them to layout later dynamically
        self.upgrade_widgets = {}
        for i, upgrade in enumerate(self.upgrades):
            # Create labels and button for each upgrade
            count_label = QLabel(f"{upgrade.icon} {upgrade.name}s: {upgrade.count}")
            count_label.setFont(QFont("Arial", 16))
            
            cost_label = QLabel(f"Cost: {upgrade.cost} XP")
            cost_label.setFont(QFont("Arial", 16))
            
            buy_button = QPushButton(f"Deploy {upgrade.name}")
            buy_button.clicked.connect(lambda checked, u=upgrade: self.buy_upgrade(u))
            
            # Store widgets for updating
            self.upgrade_widgets[upgrade.name] = {
                "count_label": count_label,
                "cost_label": cost_label,
                "buy_button": buy_button,
                "row": i,  # Store row index for later placement
                "visible": False  # Track if currently visible in shop
            }
        
        # Add the shop content to the scroll area
        shop_scroll.setWidget(shop_content)
        shop_scroll.setMinimumHeight(250)  # Set a reasonable height for the shop
        game_tab_layout.addWidget(shop_scroll)
        
        # Store references for later use
        self.shop_layout = shop_layout
        self.shop_content = shop_content
        
        # Initialize visible upgrades
        self.update_visible_upgrades()
        
        # Create bottom button layout
        bottom_buttons_layout = QHBoxLayout()
        
        # Create save game button
        save_button = QPushButton("Save Mission")
        save_button.setFont(QFont("Arial", 14))
        save_button.clicked.connect(lambda: self.save_game(silent=False))
        bottom_buttons_layout.addWidget(save_button)
        
        # Create return to menu button with new name
        menu_button = QPushButton("Return to Command Center")
        menu_button.setFont(QFont("Arial", 14))
        menu_button.clicked.connect(self.return_to_menu)
        bottom_buttons_layout.addWidget(menu_button)
        
        game_tab_layout.addLayout(bottom_buttons_layout)
        
        # Create achievements tab
        achievements_tab = QWidget()
        achievements_layout = QVBoxLayout(achievements_tab)
        
        # Create scroll area for achievements
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(5)  # Reduce spacing between achievements
        scroll_layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        
        # Create achievement labels
        self.achievement_labels = {}
        for achievement_name, achievement in self.achievements.items():
            achievement_widget = QWidget()
            achievement_widget.setMaximumHeight(100)  # Set maximum height
            achievement_layout = QHBoxLayout(achievement_widget)
            achievement_layout.setContentsMargins(5, 5, 5, 5)  # Reduce internal margins
            achievement_layout.setSpacing(10)  # Set spacing between icon and text
            
            # Create status icon
            status_label = QLabel("🏆")
            status_label.setFont(QFont("Arial", 16))
            status_label.setFixedWidth(30)  # Fixed width for icon
            achievement_layout.addWidget(status_label)
            
            # Create achievement info
            info_widget = QWidget()
            info_layout = QVBoxLayout(info_widget)
            info_layout.setContentsMargins(0, 0, 0, 0)  # Remove internal margins
            info_layout.setSpacing(2)  # Minimal spacing between name and description
            
            name_label = QLabel(achievement["name"])
            name_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            info_layout.addWidget(name_label)
            
            desc_label = QLabel(achievement["description"])
            desc_label.setFont(QFont("Arial", 12))
            info_layout.addWidget(desc_label)
            
            achievement_layout.addWidget(info_widget)
            
            # Only add to layout if unlocked
            if achievement["unlocked"]:
                scroll_layout.addWidget(achievement_widget)
            
            # Store label for updating
            self.achievement_labels[achievement_name] = {
                "widget": achievement_widget,
                "status_label": status_label
            }
        
        # Add spacer at the end to push content up
        scroll_layout.addStretch(1)
        
        scroll.setWidget(scroll_content)
        achievements_layout.addWidget(scroll)
        
        # Create stats tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        
        # Create stats display
        self.stats_labels = {}
        
        # Time played
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_label = QLabel("⏱️ Time Played:")
        time_label.setFont(QFont("Arial", 16))
        self.stats_labels["time"] = QLabel("0:00:00")
        self.stats_labels["time"].setFont(QFont("Arial", 16))
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.stats_labels["time"])
        stats_layout.addWidget(time_widget)
        
        # Player level
        level_widget = QWidget()
        level_layout = QHBoxLayout(level_widget)
        level_label = QLabel("👑 Player Level:")
        level_label.setFont(QFont("Arial", 16))
        self.stats_labels["level"] = QLabel(f"{self.player_level}")
        self.stats_labels["level"].setFont(QFont("Arial", 16))
        level_layout.addWidget(level_label)
        level_layout.addWidget(self.stats_labels["level"])
        stats_layout.addWidget(level_widget)
        
        # Total clicks (monster kills)
        clicks_widget = QWidget()
        clicks_layout = QHBoxLayout(clicks_widget)
        clicks_label = QLabel("⚔️ Aliens Destroyed:")
        clicks_label.setFont(QFont("Arial", 16))
        self.stats_labels["clicks"] = QLabel("0")
        self.stats_labels["clicks"].setFont(QFont("Arial", 16))
        clicks_layout.addWidget(clicks_label)
        clicks_layout.addWidget(self.stats_labels["clicks"])
        stats_layout.addWidget(clicks_widget)
        
        # Enemies defeated counter
        enemies_defeated_widget = QWidget()
        enemies_defeated_layout = QHBoxLayout(enemies_defeated_widget)
        enemies_defeated_label = QLabel("🏆 Aliens Defeated:")
        enemies_defeated_label.setFont(QFont("Arial", 16))
        self.stats_labels["enemies_defeated"] = QLabel("0")
        self.stats_labels["enemies_defeated"].setFont(QFont("Arial", 16))
        enemies_defeated_layout.addWidget(enemies_defeated_label)
        enemies_defeated_layout.addWidget(self.stats_labels["enemies_defeated"])
        stats_layout.addWidget(enemies_defeated_widget)
        
        # Total XP
        xp_widget = QWidget()
        xp_layout = QHBoxLayout(xp_widget)
        
        # Create custom XP icon
        xp_icon = XPIconLabel()
        xp_layout.addWidget(xp_icon)
        
        xp_label = QLabel("Total XP Earned:")
        xp_label.setFont(QFont("Arial", 16))
        self.stats_labels["total_xp"] = QLabel("0")
        self.stats_labels["total_xp"].setFont(QFont("Arial", 16))
        xp_layout.addWidget(xp_label)
        xp_layout.addWidget(self.stats_labels["total_xp"])
        stats_layout.addWidget(xp_widget)
        
        # XP per second
        xps_widget = QWidget()
        xps_layout = QHBoxLayout(xps_widget)
        xps_label = QLabel("⚡ XP per Second:")
        xps_label.setFont(QFont("Arial", 16))
        self.stats_labels["xps"] = QLabel("0")
        self.stats_labels["xps"].setFont(QFont("Arial", 16))
        xps_layout.addWidget(xps_label)
        xps_layout.addWidget(self.stats_labels["xps"])
        stats_layout.addWidget(xps_widget)
        
        # Add party member stats section
        party_stats_label = QLabel("Fleet Statistics")
        party_stats_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        stats_layout.addWidget(party_stats_label)
        
        # Create a scroll area for party stats to ensure they're all visible
        party_scroll = QScrollArea()
        party_scroll.setWidgetResizable(True)
        party_content = QWidget()
        party_content_layout = QVBoxLayout(party_content)
        party_content_layout.setSpacing(10)  # Add spacing between party members
        
        # Create container widgets for party stats but don't add them to layout yet
        self.upgrade_stat_widgets = {}
        for upgrade in self.upgrades:
            upgrade_widget = QWidget()
            upgrade_widget.setMinimumHeight(90)  # Set minimum height for each party stat
            upgrade_layout = QVBoxLayout(upgrade_widget)  # Changed to QVBoxLayout for better text display
            upgrade_layout.setContentsMargins(5, 5, 5, 5)  # Add some padding
            
            # Create party stats
            stats_text = f"{upgrade.icon} {upgrade.name}:"
            stats_text += f"\nTotal Recruited: {upgrade.total_bought}"
            stats_text += f"\nTotal XP Spent: {upgrade.total_spent:,}"
            stats_text += f"\nCurrent XP/s: {upgrade.count * upgrade.production:.1f}/s"
            
            upgrade_label = QLabel(stats_text)
            upgrade_label.setFont(QFont("Arial", 11))
            upgrade_label.setWordWrap(True)  # Enable word wrap
            upgrade_layout.addWidget(upgrade_label)
            
            # Store the widget and label for later use
            self.upgrade_stat_widgets[upgrade.name] = {
                "widget": upgrade_widget,
                "label": upgrade_label
            }
            
            # Only add to layout if already unlocked (for loading saved games)
            if upgrade.count > 0:
                party_content_layout.addWidget(upgrade_widget)
            
            # Store the upgrade label in stats_labels
            self.stats_labels[upgrade.name] = upgrade_label
        
        # Add stretch at the end to push content to the top
        party_content_layout.addStretch(1)
        
        party_scroll.setWidget(party_content)
        stats_layout.addWidget(party_scroll)
        
        # Create enemies tab for tracking enemy statistics
        enemies_tab = QWidget()
        enemies_layout = QVBoxLayout(enemies_tab)
        
        # Add header label
        enemies_header_label = QLabel("Alien Records")
        enemies_header_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        enemies_header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        enemies_layout.addWidget(enemies_header_label)
        
        # Create a scrollable area for enemy statistics
        enemies_scroll = QScrollArea()
        enemies_scroll.setWidgetResizable(True)
        enemies_content = QWidget()
        self.enemies_content_layout = QVBoxLayout(enemies_content)
        self.enemies_content_layout.setSpacing(5)
        self.enemies_content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create a message for when no enemies have been defeated
        self.no_enemies_label = QLabel("No aliens defeated yet. Defend your galaxy!")
        self.no_enemies_label.setFont(QFont("Arial", 14))
        self.no_enemies_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enemies_content_layout.addWidget(self.no_enemies_label)
        
        # Dictionary to store enemy statistic widgets
        self.enemy_stat_widgets = {}
        
        # Add stretch to push content to the top
        self.enemies_content_layout.addStretch(1)
        
        enemies_scroll.setWidget(enemies_content)
        enemies_layout.addWidget(enemies_scroll)
        
        # Add tabs to tab widget
        self.tab_widget.addTab(game_tab, "Mission")
        self.tab_widget.addTab(achievements_tab, "Achievements")
        self.tab_widget.addTab(stats_tab, "Stats")
        self.tab_widget.addTab(enemies_tab, "Alien Database")
        
        # Setup auto-clicker timer with longer interval
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_click)
        self.timer.start(250)  # Update every 250ms instead of 100ms
        
        # Setup stats update timer with longer interval
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(2000)  # Update every 2 seconds instead of 1 second
        
        # Setup auto-save timer with longer interval
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(60000)  # Auto-save every 60 seconds instead of 30 seconds
        
    def setup_audio(self):
        # Define sound file paths
        self.monster_sound_paths = []
        for i in range(1, 6):  # coin1.wav to coin5.wav - reuse coin sounds for now
            path = os.path.abspath(f"audio/coin{i}.wav")
            if os.path.exists(path):
                self.monster_sound_paths.append(path)
            else:
                print(f"Warning: Monster sound file not found at {path}")
        
        self.click_sound_path = os.path.abspath("audio/click.wav")
        self.achievement_sound_path = os.path.abspath("audio/achievement.wav")
        self.level_up_sound_path = os.path.abspath("audio/achievement.wav")  # Reuse achievement sound for level up
        
        # Check if sound files exist
        self.has_monster_sounds = len(self.monster_sound_paths) > 0
        self.has_click_sound = os.path.exists(self.click_sound_path)
        self.has_achievement_sound = os.path.exists(self.achievement_sound_path)
        self.has_level_up_sound = os.path.exists(self.level_up_sound_path)
        
        if not self.has_monster_sounds:
            print("Warning: No monster sound files found in audio folder")
        if not self.has_click_sound:
            print(f"Warning: Click sound file not found at {self.click_sound_path}")
        if not self.has_achievement_sound:
            print(f"Warning: Achievement sound file not found at {self.achievement_sound_path}")
        if not self.has_level_up_sound:
            print(f"Warning: Level up sound file not found at {self.level_up_sound_path}")

    def click_enemy(self):
        # Play a random monster sound
        if self.has_monster_sounds:
            random_monster_sound = random.choice(self.monster_sound_paths)
            play_sound(random_monster_sound)
        
        # Get the current enemy's name for the label
        current_enemy_name = self.enemy_button.get_enemy_name()
        self.enemy_name_label.setText(f"Alien: {current_enemy_name}")
        
        # Apply damage to the enemy (basic damage = xp_per_click)
        enemy_defeated, defeated_enemy_id, defeated_enemy_name = self.enemy_button.damage_enemy(self.xp_per_click)
        
        # Award XP and update counters
        self.xp += self.xp_per_click
        self.total_xp += self.xp_per_click
        self.total_clicks += 1
        
        # If enemy was defeated, update the counter and show notification
        if enemy_defeated:
            self.enemies_defeated += 1
            self.enemies_defeated_label.setText(f"Aliens Defeated: {self.enemies_defeated}")
            
            # Track statistics for the defeated enemy
            if defeated_enemy_id not in self.enemy_stats:
                self.enemy_stats[defeated_enemy_id] = {
                    "name": defeated_enemy_name,
                    "defeats": 1,
                    "last_defeated": QDateTime.currentDateTime().toString()
                }
            else:
                self.enemy_stats[defeated_enemy_id]["defeats"] += 1
                self.enemy_stats[defeated_enemy_id]["last_defeated"] = QDateTime.currentDateTime().toString()
            
            # Update the enemy statistics display
            self.update_enemy_stats_display()
            
            # Get the new enemy's name after defeat
            new_enemy_name = self.enemy_button.get_enemy_name()
            self.enemy_name_label.setText(f"Alien: {new_enemy_name}")
            
            # Show enemy defeated notification
            self.notification_overlay.show_notification(
                "Alien Defeated!",
                "🛸",
                f"You defeated {defeated_enemy_name}!\nA {new_enemy_name} approaches!",
                2000  # Show for 2 seconds
            )
            
            # Check for first kill achievement - only when actually defeating an enemy
            if not self.achievements["First Kill"]["unlocked"] and self.enemies_defeated > 0:
                self.unlock_achievement("First Kill")
        
        # Check for level up
        self.check_level_up()
        
        # Update display and check achievements
        self.update_display()
        self.check_achievements()
        
        # Visual feedback
        self.enemy_button.show_click_animation()
        
    def check_level_up(self):
        if self.xp >= self.xp_to_next_level:
            # Level up
            self.xp -= self.xp_to_next_level
            self.player_level += 1
            
            # Calculate new XP needed for next level (increasing by 50% each level)
            self.xp_to_next_level = int(self.xp_to_next_level * 1.5)
            
            # Play level up sound
            if self.has_level_up_sound:
                play_sound(self.level_up_sound_path)
            
            # Show level up notification
            self.notification_overlay.show_notification(
                "Level Up!",
                "⬆️",
                f"You've reached level {self.player_level}!\nYou now need {self.xp_to_next_level} XP for next level.",
                4000  # Show for 4 seconds
            )
            
            # Play achievement sound for level up notification
            if self.has_achievement_sound:
                play_sound(self.achievement_sound_path)
            
            # Check for level-based achievements
            if self.player_level >= 5 and not self.achievements["Monster Hunter"]["unlocked"]:
                self.unlock_achievement("Monster Hunter")
            if self.player_level >= 20 and not self.achievements["Legendary Slayer"]["unlocked"]:
                self.unlock_achievement("Legendary Slayer")
        
    def buy_upgrade(self, upgrade):
        if self.xp >= upgrade.cost:
            # Play click sound
            if self.has_click_sound:
                play_sound(self.click_sound_path)
            
            # Check if this is the first purchase of this upgrade
            first_purchase = upgrade.count == 0
            
            self.xp -= upgrade.cost
            upgrade.count += 1
            upgrade.total_bought += 1
            upgrade.total_spent += upgrade.cost
            upgrade.cost = int(upgrade.cost * 1.5)  # Increase cost by 50%
            upgrade.production += upgrade.base_production  # Increase production
            self.update_display()
            self.show_status_message(f"Deployed {upgrade.name} for {upgrade.cost} XP")
            
            # Update visible upgrades after purchase to potentially reveal new ones
            self.update_visible_upgrades()
            
            # If first purchase, add the upgrade to the stats tab
            if first_purchase:
                # Find the upgrade stats scroll area content
                stats_tab = self.tab_widget.widget(2)  # Stats is the third tab (index 2)
                upgrade_scroll = stats_tab.findChild(QScrollArea)
                upgrade_content = upgrade_scroll.widget()
                upgrade_layout = upgrade_content.layout()
                
                # Find the stretch item at the end (if exists)
                if upgrade_layout.count() > 0 and upgrade_layout.itemAt(upgrade_layout.count() - 1).spacerItem():
                    # Remove the stretch
                    upgrade_layout.removeItem(upgrade_layout.itemAt(upgrade_layout.count() - 1))
                
                # Add the upgrade widget to the layout
                upgrade_layout.addWidget(self.upgrade_stat_widgets[upgrade.name]["widget"])
                
                # Add the stretch back
                upgrade_layout.addStretch(1)
            
            # Check for upgrade achievement
            if not self.achievements[upgrade.achievement_name]["unlocked"]:
                self.unlock_achievement(upgrade.achievement_name)
            
    def auto_click(self):
        total_production = 0
        for upgrade in self.upgrades:
            if upgrade.count > 0:
                total_production += upgrade.production * upgrade.count
        
        if total_production > 0:
            # Calculate XP earned this tick
            xp_earned = total_production * (self.timer.interval() / 1000)
            self.xp += xp_earned
            self.total_xp += xp_earned
            
            # Auto-damage enemy based on party members' contribution
            if self.enemy_button:
                # Apply auto-damage from party members
                damage_per_second = total_production
                damage_this_tick = damage_per_second * (self.timer.interval() / 1000)
                enemy_defeated, defeated_enemy_id, defeated_enemy_name = self.enemy_button.damage_enemy(damage_this_tick)
                
                # If enemy was defeated by auto-damage
                if enemy_defeated:
                    self.enemies_defeated += 1
                    self.enemies_defeated_label.setText(f"Aliens Defeated: {self.enemies_defeated}")
                    
                    # Track statistics for the defeated enemy
                    if defeated_enemy_id not in self.enemy_stats:
                        self.enemy_stats[defeated_enemy_id] = {
                            "name": defeated_enemy_name,
                            "defeats": 1,
                            "last_defeated": QDateTime.currentDateTime().toString()
                        }
                    else:
                        self.enemy_stats[defeated_enemy_id]["defeats"] += 1
                        self.enemy_stats[defeated_enemy_id]["last_defeated"] = QDateTime.currentDateTime().toString()
                    
                    # Update the enemy statistics display
                    self.update_enemy_stats_display()
                    
                    # Get new enemy name for notification
                    new_enemy_name = self.enemy_button.get_enemy_name()
                    
                    # Update the enemy name display
                    self.enemy_name_label.setText(f"Alien: {new_enemy_name}")
                    
                    # Check for first kill achievement when defeating an enemy through auto-damage
                    if not self.achievements["First Kill"]["unlocked"] and self.enemies_defeated > 0:
                        self.unlock_achievement("First Kill")
            
            # Check for level up
            self.check_level_up()
            
            self.update_display()
            self.check_achievements()
        
    def update_display(self):
        # Update level and XP displays
        self.level_label.setText(f"Level: {self.player_level}")
        self.xp_label.setText(f"XP: {self.xp:.1f}/{self.xp_to_next_level}")
        
        # Calculate number of discovered party members (showing in shop)
        discovered_count = 0
        for upgrade in self.upgrades:
            widget_data = self.upgrade_widgets[upgrade.name]
            if widget_data["visible"]:
                discovered_count += 1
        
        # Update party members discovered label
        self.party_label.setText(f"{discovered_count} of {len(self.upgrades)} fleet ships deployed")
        
        # Update all upgrade displays
        for upgrade in self.upgrades:
            widgets = self.upgrade_widgets[upgrade.name]
            widgets["count_label"].setText(f"{upgrade.icon} {upgrade.name}s: {upgrade.count}")
            widgets["cost_label"].setText(f"Cost: {upgrade.cost} XP")
            
            # Check if required upgrade is purchased
            can_buy = self.xp >= upgrade.cost
            if upgrade.required_upgrade:
                # Find the required upgrade object
                for req_upgrade in self.upgrades:
                    if req_upgrade.name == upgrade.required_upgrade:
                        # Only enable if required upgrade has been bought
                        if req_upgrade.count == 0:
                            can_buy = False
                            # Update cost label to show requirement
                            widgets["cost_label"].setText(f"Requires {upgrade.required_upgrade}")
                        break
            
            widgets["buy_button"].setEnabled(can_buy)
        
        # Update achievement displays
        for achievement_name, achievement in self.achievements.items():
            self.achievement_labels[achievement_name]["status_label"].setText("🏆" if achievement["unlocked"] else "🔒")
            
    def update_stats(self):
        # Update time played
        current_time = QDateTime.currentDateTime()
        time_diff = self.start_time.secsTo(current_time)
        hours = time_diff // 3600
        minutes = (time_diff % 3600) // 60
        seconds = time_diff % 60
        self.stats_labels["time"].setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Update level
        self.stats_labels["level"].setText(f"{self.player_level}")
        
        # Update monster kills (clicks)
        self.stats_labels["clicks"].setText(f"{self.total_clicks:,}")
        
        # Update enemies defeated
        if "enemies_defeated" in self.stats_labels:
            self.stats_labels["enemies_defeated"].setText(f"{self.enemies_defeated:,}")
        
        # Update total XP
        self.stats_labels["total_xp"].setText(f"{self.total_xp:,.1f}")
        
        # Calculate and update XP per second
        total_xps = 0
        for upgrade in self.upgrades:
            if upgrade.count > 0:
                total_xps += upgrade.production * upgrade.count
        self.stats_labels["xps"].setText(f"{total_xps:.1f}")
        
        # Update upgrade stats with clear formatting
        for upgrade in self.upgrades:
            stats_text = f"{upgrade.icon} {upgrade.name}:"
            stats_text += f"\nTotal Recruited: {upgrade.total_bought}"
            stats_text += f"\nTotal XP Spent: {upgrade.total_spent:,}"
            stats_text += f"\nCurrent XP/s: {upgrade.count * upgrade.production:.1f}/s"
            self.stats_labels[upgrade.name].setText(stats_text)
        
    def check_achievements(self):
        # Level-based achievements are now checked in check_level_up method
        pass
            
    def unlock_achievement(self, achievement_name):
        self.achievements[achievement_name]["unlocked"] = True
        achievement_data = self.achievement_labels[achievement_name]
        achievement_data["status_label"].setText("🏆")
        
        # Add the achievement widget to the scroll layout
        scroll_content = self.tab_widget.widget(1).findChild(QScrollArea).widget()
        scroll_layout = scroll_content.layout()
        
        # Remove stretch if it exists
        if scroll_layout.count() > 0 and scroll_layout.itemAt(scroll_layout.count() - 1).spacerItem():
            scroll_layout.removeItem(scroll_layout.itemAt(scroll_layout.count() - 1))
        
        # Add the achievement widget
        scroll_layout.addWidget(achievement_data["widget"])
        
        # Add stretch back to push content up
        scroll_layout.addStretch(1)
        
        # Show status message
        self.show_status_message(f"Achievement unlocked: {self.achievements[achievement_name]['name']}")
        
        # Show achievement notification using overlay instead of dialog
        self.notification_overlay.show_notification(
            "Achievement Unlocked!",
            "🏆",
            f"{self.achievements[achievement_name]['name']}\n{self.achievements[achievement_name]['description']}",
            4000  # Show for 4 seconds
        )
        
        # Play achievement sound if available
        if self.has_achievement_sound:
            play_sound(self.achievement_sound_path)

    def show_status_message(self, message, timeout=3000):
        self.statusBar().showMessage(message, timeout)

    def auto_save(self):
        save_data = {
            "xp": self.xp,
            "xp_per_click": self.xp_per_click,
            "total_xp": self.total_xp,
            "total_clicks": self.total_clicks,
            "player_level": self.player_level,
            "xp_to_next_level": self.xp_to_next_level,
            "enemies_defeated": self.enemies_defeated,
            "enemy_stats": self.enemy_stats,  # Save enemy statistics
            "start_time": self.start_time.toString(),
            "achievements": self.achievements
        }
        
        # Save upgrade data
        for upgrade in self.upgrades:
            save_data[upgrade.name] = {
                "count": upgrade.count,
                "cost": upgrade.cost,
                "production": upgrade.production,
                "total_bought": upgrade.total_bought,
                "total_spent": upgrade.total_spent
            }
        
        # Create and start save worker thread
        self.save_worker = SaveWorker(save_data)
        self.save_worker.finished.connect(lambda: self.show_status_message("Mission auto-saved"))
        self.save_worker.error.connect(lambda e: self.show_status_message(f"Failed to save mission: {e}"))
        self.save_worker.start()

    def save_game(self, silent=False):
        save_data = {
            "xp": self.xp,
            "xp_per_click": self.xp_per_click,
            "total_xp": self.total_xp,
            "total_clicks": self.total_clicks,
            "player_level": self.player_level,
            "xp_to_next_level": self.xp_to_next_level,
            "enemies_defeated": self.enemies_defeated,
            "enemy_stats": self.enemy_stats,  # Save enemy statistics
            "start_time": self.start_time.toString(),
            "achievements": self.achievements
        }
        
        # Save upgrade data
        for upgrade in self.upgrades:
            save_data[upgrade.name] = {
                "count": upgrade.count,
                "cost": upgrade.cost,
                "production": upgrade.production,
                "total_bought": upgrade.total_bought,
                "total_spent": upgrade.total_spent
            }
        
        # Create and start save worker thread
        self.save_worker = SaveWorker(save_data)
        if not silent:
            self.save_worker.finished.connect(lambda: self.show_status_message("Mission saved successfully!"))
            self.save_worker.error.connect(lambda e: self.show_status_message(f"Failed to save mission: {e}"))
        self.save_worker.start()
        self.last_save_time = QDateTime.currentDateTime()

    def return_to_menu(self):
        # Auto-save before returning to menu
        self.auto_save()
        # Switch to menu view
        self.central_widget.setCurrentWidget(self.main_menu)

    def load_game(self):
        if os.path.exists("space_save_game.json"):
            # Use proper Qt thread for loading
            self.load_worker = LoadWorker()
            self.load_worker.finished.connect(self.process_loaded_data)
            self.load_worker.error.connect(lambda e: self.show_status_message(f"Failed to load mission: {e}"))
            self.load_worker.start()
        else:
            self.show_status_message("No save file found")

    def process_loaded_data(self, save_data):
        # Update game state on the main thread
        self.xp = save_data.get("xp", 0)
        self.xp_per_click = save_data.get("xp_per_click", 1)
        self.total_xp = save_data.get("total_xp", 0)
        self.total_clicks = save_data.get("total_clicks", 0)
        self.player_level = save_data.get("player_level", 1)
        self.xp_to_next_level = save_data.get("xp_to_next_level", 100)
        self.enemies_defeated = save_data.get("enemies_defeated", 0)
        
        # Load enemy statistics if available
        self.enemy_stats = save_data.get("enemy_stats", {})
        
        self.start_time = QDateTime.fromString(save_data.get("start_time", QDateTime.currentDateTime().toString()))
        self.achievements = save_data["achievements"]
        
        # Update enemy counter display
        self.enemies_defeated_label.setText(f"Aliens Defeated: {self.enemies_defeated}")
        
        # Update enemy name
        enemy_name = self.enemy_button.get_enemy_name()
        self.enemy_name_label.setText(f"Alien: {enemy_name}")
        
        # Load upgrade data
        for upgrade in self.upgrades:
            if upgrade.name in save_data:
                upgrade_data = save_data[upgrade.name]
                upgrade.count = upgrade_data["count"]
                upgrade.cost = upgrade_data["cost"]
                upgrade.production = upgrade_data["production"]
                upgrade.total_bought = upgrade_data.get("total_bought", 0)
                upgrade.total_spent = upgrade_data.get("total_spent", 0)
        
        # Update enemy statistics display
        self.update_enemy_stats_display()
        
        # Update visible upgrades in the shop based on loaded data
        self.update_visible_upgrades()
        
        # Restore achievement widgets
        scroll_content = self.tab_widget.widget(1).findChild(QScrollArea).widget()
        scroll_layout = scroll_content.layout()
        
        # Clear existing widgets
        while scroll_layout.count():
            item = scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add unlocked achievements to the scroll layout
        for achievement_name, achievement in self.achievements.items():
            if achievement["unlocked"]:
                achievement_data = self.achievement_labels[achievement_name]
                achievement_data["status_label"].setText("🏆")
                scroll_layout.addWidget(achievement_data["widget"])
        
        # Add spacer to push content up
        scroll_layout.addStretch(1)
        
        # Restore upgrade stat widgets
        stats_tab = self.tab_widget.widget(2)  # Stats is the third tab (index 2)
        upgrade_scroll = stats_tab.findChild(QScrollArea)
        upgrade_content = upgrade_scroll.widget()
        upgrade_layout = upgrade_content.layout()
        
        # Clear existing widgets
        while upgrade_layout.count():
            item = upgrade_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                upgrade_layout.removeItem(item)
        
        # Add only unlocked upgrades to the stats tab
        for upgrade in self.upgrades:
            if upgrade.count > 0:
                upgrade_layout.addWidget(self.upgrade_stat_widgets[upgrade.name]["widget"])
        
        # Add spacer to push content to the top
        upgrade_layout.addStretch(1)
        
        # Update UI on the main thread
        self.update_display()
        self.update_stats()
        self.central_widget.setCurrentWidget(self.game_widget)
        self.show_status_message("Mission loaded successfully")

    def update_visible_upgrades(self):
        """Update which upgrades should be visible in the shop based on prerequisites"""
        # First, determine which upgrades should be visible
        visible_upgrades = []
        unlocked_names = set()
        next_upgrades = set()
        
        # Collect names of all unlocked upgrades (count > 0)
        for upgrade in self.upgrades:
            if upgrade.count > 0:
                unlocked_names.add(upgrade.name)
                
        # Always show first upgrade
        visible_upgrades.append(self.upgrades[0])
        
        # Determine which upgrades should be visible now
        for upgrade in self.upgrades:
            if upgrade.count > 0:
                # Always show unlocked upgrades
                if upgrade not in visible_upgrades:
                    visible_upgrades.append(upgrade)
            elif not upgrade.required_upgrade or upgrade.required_upgrade in unlocked_names:
                # Show unlockable upgrades (those whose prerequisite is met)
                if upgrade not in visible_upgrades:
                    visible_upgrades.append(upgrade)
                    next_upgrades.add(upgrade.name)
        
        # Update shop layout
        for upgrade in self.upgrades:
            widget_data = self.upgrade_widgets[upgrade.name]
            
            # Check if widget should be visible
            should_be_visible = upgrade in visible_upgrades
            
            # Only update if visibility changed
            if should_be_visible != widget_data["visible"]:
                if should_be_visible:
                    # Add widget to layout
                    row = widget_data["row"]
                    self.shop_layout.addWidget(widget_data["count_label"], row, 0)
                    self.shop_layout.addWidget(widget_data["cost_label"], row, 1)
                    self.shop_layout.addWidget(widget_data["buy_button"], row, 2)
                else:
                    # Remove widget from layout
                    self.shop_layout.removeWidget(widget_data["count_label"])
                    self.shop_layout.removeWidget(widget_data["cost_label"])
                    self.shop_layout.removeWidget(widget_data["buy_button"])
                    widget_data["count_label"].hide()
                    widget_data["cost_label"].hide()
                    widget_data["buy_button"].hide()
                
                # Update visibility state
                widget_data["visible"] = should_be_visible
                
                # If now visible, show the widgets
                if should_be_visible:
                    widget_data["count_label"].show()
                    widget_data["cost_label"].show()
                    widget_data["buy_button"].show()
        
        # Refresh the shop content
        self.shop_content.adjustSize()

    def update_enemy_stats_display(self):
        """Update the enemy statistics tab with current enemy defeat data"""
        # If there are no defeated enemies yet, show the no enemies message
        if not self.enemy_stats:
            self.no_enemies_label.setVisible(True)
            return
            
        # Hide the no enemies message if we have defeated enemies
        self.no_enemies_label.setVisible(False)
        
        # For each enemy in the stats dictionary, create or update its display widget
        for enemy_id, stats in self.enemy_stats.items():
            # Check if we already have a widget for this enemy
            if enemy_id in self.enemy_stat_widgets:
                # Update existing widget
                enemy_widget = self.enemy_stat_widgets[enemy_id]["widget"]
                stats_label = self.enemy_stat_widgets[enemy_id]["label"]
                
                # Update the stats text
                stats_text = f"<b>{stats['name']}</b><br>"
                stats_text += f"Defeated: {stats['defeats']} times<br>"
                stats_text += f"Last defeated: {stats['last_defeated']}"
                stats_label.setText(stats_text)
            else:
                # Create a new widget for this enemy
                enemy_widget = QWidget()
                enemy_layout = QHBoxLayout(enemy_widget)
                enemy_layout.setContentsMargins(5, 5, 5, 5)
                
                # Create image thumbnail (gray placeholder for now)
                image_label = QLabel()
                image_label.setFixedSize(80, 80)
                # Try to get the enemy image
                try:
                    # Load a thumbnail of the enemy
                    enemy_image = QPixmap(f"images/enemies/{enemy_id}.png")
                    if not enemy_image.isNull():
                        enemy_image = enemy_image.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
                        image_label.setPixmap(enemy_image)
                    else:
                        # Create a gray placeholder
                        placeholder = QPixmap(80, 80)
                        placeholder.fill(QColor(200, 200, 200))
                        image_label.setPixmap(placeholder)
                except Exception:
                    # Create a gray placeholder
                    placeholder = QPixmap(80, 80)
                    placeholder.fill(QColor(200, 200, 200))
                    image_label.setPixmap(placeholder)
                
                enemy_layout.addWidget(image_label)
                
                # Create stats info
                stats_label = QLabel()
                stats_label.setFont(QFont("Arial", 12))
                stats_label.setWordWrap(True)
                
                # Format the stats text
                stats_text = f"<b>{stats['name']}</b><br>"
                stats_text += f"Defeated: {stats['defeats']} times<br>"
                stats_text += f"Last defeated: {stats['last_defeated']}"
                stats_label.setText(stats_text)
                
                enemy_layout.addWidget(stats_label, 1)  # Give the stats label stretch factor
                
                # Store the widget and label for future updates
                self.enemy_stat_widgets[enemy_id] = {
                    "widget": enemy_widget,
                    "label": stats_label,
                    "image": image_label
                }
                
                # Add the widget to the layout - remove stretch first if it exists
                if self.enemies_content_layout.count() > 0 and self.enemies_content_layout.itemAt(self.enemies_content_layout.count() - 1).spacerItem():
                    self.enemies_content_layout.removeItem(self.enemies_content_layout.itemAt(self.enemies_content_layout.count() - 1))
                
                self.enemies_content_layout.addWidget(enemy_widget)
                
                # Add stretch back to push content to the top
                self.enemies_content_layout.addStretch(1)

    def clear_enemy_stats_display(self):
        """Clear the enemy statistics display"""
        # Clear all enemy stat widgets
        for enemy_id, widget_data in self.enemy_stat_widgets.items():
            widget = widget_data["widget"]
            if widget.parentWidget():
                self.enemies_content_layout.removeWidget(widget)
                widget.setParent(None)
        
        # Reset the enemy stat widgets dictionary
        self.enemy_stat_widgets = {}
        
        # Show the no enemies message
        self.no_enemies_label.setVisible(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = RPGGame()
    game.show()
    sys.exit(app.exec()) 