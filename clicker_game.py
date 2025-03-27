import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QGridLayout,
                            QMessageBox, QTabWidget, QScrollArea, QStackedWidget,
                            QGraphicsOpacityEffect)
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
        self.achievement_description = f"Buy your first {name.lower()}"
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
            with open("clicker_save_game.json", "w") as f:
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
            with open("clicker_save_game.json", "r") as f:
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
        title = QLabel("Coin Clicker")
        title.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Spacing
        layout.addSpacing(50)
        
        # Buttons
        self.new_game_btn = QPushButton("Start New Game")
        self.new_game_btn.setFont(QFont("Arial", 16))
        self.new_game_btn.setMinimumSize(200, 50)
        layout.addWidget(self.new_game_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.load_game_btn = QPushButton("Load Saved Game")
        self.load_game_btn.setFont(QFont("Arial", 16))
        self.load_game_btn.setMinimumSize(200, 50)
        self.load_game_btn.setVisible(os.path.exists("clicker_save_game.json"))
        layout.addWidget(self.load_game_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFont(QFont("Arial", 16))
        self.settings_btn.setMinimumSize(200, 50)
        layout.addWidget(self.settings_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.exit_btn = QPushButton("Exit Game")
        self.exit_btn.setFont(QFont("Arial", 16))
        self.exit_btn.setMinimumSize(200, 50)
        layout.addWidget(self.exit_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add spacing between buttons
        layout.setSpacing(20)

class CoinButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(100, 100)  # Set fixed size to 200x200 pixels
        
        # Load sprite sheet
        self.spritesheet = QPixmap("images/coin_spritesheet.png")
        
        # Frame data - each frame is 22x22 pixels
        self.frame_width = 22
        self.frame_height = 22
        self.current_frame = 0
        self.total_frames = 4
        
        # Animation timer
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.next_frame)
        self.animation_timer.start(150)  # 150ms per frame = ~6.6 fps
        
        # Set flat style for button with no background
        self.setStyleSheet("QPushButton { background-color: transparent; border: none; }")
        
        # Click animation properties
        self.is_clicked = False
        self.click_scale = 0.9  # Scale down to 90% when clicked
        
    def next_frame(self):
        self.current_frame = (self.current_frame + 1) % self.total_frames
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Calculate source rect based on current frame
        x = self.current_frame * self.frame_width
        source_rect = QRect(x, 0, self.frame_width, self.frame_height)
        
        # Draw the current frame scaled to button size
        target_rect = QRect(0, 0, self.width(), self.height())
        
        # If clicked, scale down the drawing
        if self.is_clicked:
            # Calculate scaled rect
            scale_factor = self.click_scale
            width_diff = self.width() * (1 - scale_factor)
            height_diff = self.height() * (1 - scale_factor)
            scaled_rect = QRect(
                int(width_diff / 2),
                int(height_diff / 2),
                int(self.width() * scale_factor),
                int(self.height() * scale_factor)
            )
            painter.drawPixmap(scaled_rect, self.spritesheet, source_rect)
        else:
            painter.drawPixmap(target_rect, self.spritesheet, source_rect)
        
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

class CoinIconLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Set fixed size for the coin icon
        self.setFixedSize(24, 24)
        
        # Load sprite sheet
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
                background-color: rgba(0, 0, 0, 0.7);
                border-radius: 10px;
                border: 2px solid gold;
            }
            QPushButton#closeButton {
                background-color: rgba(255, 0, 0, 0.7);
                color: white;
                font-weight: bold;
                border-radius: 10px;
                border: 1px solid white;
                padding: 5px;
            }
            QPushButton#closeButton:hover {
                background-color: rgba(255, 0, 0, 0.9);
            }
            QPushButton#okButton {
                background-color: rgba(0, 128, 0, 0.7);
                color: white;
                font-weight: bold;
                border-radius: 10px;
                border: 1px solid white;
                padding: 5px;
                min-height: 30px;
                font-size: 14px;
            }
            QPushButton#okButton:hover {
                background-color: rgba(0, 128, 0, 0.9);
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
        self.title_label.setStyleSheet("color: gold;")
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

class ClickerGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coin Clicker")
        self.setFixedSize(800, 600)  # Set fixed size instead of minimum size
        
        # Create status bar
        self.statusBar().showMessage("Ready")
        
        # Set up audio players
        self.setup_audio()
        
        # Initialize game state
        self.coins = 0
        self.coins_per_click = 1
        self.total_coins = 0
        self.total_clicks = 0
        self.start_time = QDateTime.currentDateTime()
        self.last_save_time = self.start_time
        
        # Define upgrades with dependencies - now with 15 upgrades total
        self.upgrades = [
            Upgrade("Cursor", 10, 0.1, "🖱️", "Automatically clicks coins"),  # First upgrade, no dependency
            Upgrade("Grandma", 50, 0.5, "👵", "Collects coins with love", "Cursor"),  # Requires Cursor
            Upgrade("Farm", 200, 2.0, "🌾", "Grows coin plants", "Grandma"),  # Requires Grandma
            Upgrade("Factory", 1000, 10.0, "🏭", "Mass produces coins", "Farm"),  # Requires Farm
            Upgrade("Mine", 5000, 50.0, "⛏️", "Mines coin minerals", "Factory"),  # Requires Factory
            Upgrade("Bank", 10000, 200.0, "🏦", "Generates coins from interest", "Mine"),
            Upgrade("Temple", 50000, 500.0, "🏛️", "Prays for divine coin blessing", "Bank"),
            Upgrade("Wizard Tower", 100000, 1000.0, "🧙", "Summons coins with magic", "Temple"),
            Upgrade("Shipment", 500000, 5000.0, "🚀", "Imports coins from coin planet", "Wizard Tower"),
            Upgrade("Alchemy Lab", 1000000, 10000.0, "⚗️", "Turns gold into coins", "Shipment"),
            Upgrade("Portal", 5000000, 50000.0, "🌀", "Opens door to coin dimension", "Alchemy Lab"),
            Upgrade("Time Machine", 10000000, 100000.0, "⏰", "Brings coins from the past", "Portal"),
            Upgrade("Antimatter", 50000000, 500000.0, "⚛️", "Converts antimatter to coins", "Time Machine"),
            Upgrade("Prism", 100000000, 1000000.0, "🔮", "Converts light into coins", "Antimatter"),
            Upgrade("Fractal Engine", 500000000, 5000000.0, "🌈", "Generates coins through recursion", "Prism")
        ]
        
        # Achievements
        self.achievements = {
            "First Click": {"name": "First Click", "description": "Click the coin for the first time", "unlocked": False},
            "Coin Master": {"name": "Coin Master", "description": "Reach 100 coins", "unlocked": False},
            "Coin Empire": {"name": "Coin Empire", "description": "Reach 1000 coins", "unlocked": False}
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
        self.coins = 0
        self.coins_per_click = 1
        self.total_coins = 0
        self.total_clicks = 0
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
        
        # Switch to game view
        self.central_widget.setCurrentWidget(self.game_widget)
        
        # Update visible upgrades to reset the shop view
        self.update_visible_upgrades()
        
        self.update_display()
        self.update_stats()
        self.show_status_message("New game started")
        
    def show_settings(self):
        QMessageBox.information(self, "Settings", "Settings feature coming soon!")
        
    def setup_game_ui(self):
        # Create game layout
        game_layout = QVBoxLayout(self.game_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        game_layout.addWidget(self.tab_widget)
        
        # Create game tab
        game_tab = QWidget()
        game_tab_layout = QVBoxLayout(game_tab)
        
        # Create coin display
        self.coin_label = QLabel(f"Coins: {self.coins:.1f}")
        self.coin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.coin_label.setFont(QFont("Arial", 24))
        game_tab_layout.addWidget(self.coin_label)
        
        # Create generators discovered display
        self.generators_label = QLabel("1 of 15 generators discovered")
        self.generators_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.generators_label.setFont(QFont("Arial", 14))
        game_tab_layout.addWidget(self.generators_label)
        
        # Create animated coin button
        self.coin_button = CoinButton()
        self.coin_button.clicked.connect(self.click_coin)
        
        # Center the coin button
        coin_container = QWidget()
        coin_layout = QHBoxLayout(coin_container)
        coin_layout.addStretch()
        coin_layout.addWidget(self.coin_button)
        coin_layout.addStretch()
        
        game_tab_layout.addWidget(coin_container)
        
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
            
            cost_label = QLabel(f"Cost: {upgrade.cost}")
            cost_label.setFont(QFont("Arial", 16))
            
            buy_button = QPushButton(f"Buy {upgrade.name}")
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
        save_button = QPushButton("Save Game")
        save_button.setFont(QFont("Arial", 14))
        save_button.clicked.connect(lambda: self.save_game(silent=False))
        bottom_buttons_layout.addWidget(save_button)
        
        # Create return to menu button with new name
        menu_button = QPushButton("Return to Main Menu")
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
        
        # Total clicks
        clicks_widget = QWidget()
        clicks_layout = QHBoxLayout(clicks_widget)
        clicks_label = QLabel("👆 Total Clicks:")
        clicks_label.setFont(QFont("Arial", 16))
        self.stats_labels["clicks"] = QLabel("0")
        self.stats_labels["clicks"].setFont(QFont("Arial", 16))
        clicks_layout.addWidget(clicks_label)
        clicks_layout.addWidget(self.stats_labels["clicks"])
        stats_layout.addWidget(clicks_widget)
        
        # Total coins
        coins_widget = QWidget()
        coins_layout = QHBoxLayout(coins_widget)
        
        # Create custom coin icon instead of using emoji
        coin_icon = CoinIconLabel()
        coins_layout.addWidget(coin_icon)
        
        coins_label = QLabel("Total Coins:")
        coins_label.setFont(QFont("Arial", 16))
        self.stats_labels["total_coins"] = QLabel("0")
        self.stats_labels["total_coins"].setFont(QFont("Arial", 16))
        coins_layout.addWidget(coins_label)
        coins_layout.addWidget(self.stats_labels["total_coins"])
        stats_layout.addWidget(coins_widget)
        
        # Coins per second
        cps_widget = QWidget()
        cps_layout = QHBoxLayout(cps_widget)
        cps_label = QLabel("⚡ Coins per Second:")
        cps_label.setFont(QFont("Arial", 16))
        self.stats_labels["cps"] = QLabel("0")
        self.stats_labels["cps"].setFont(QFont("Arial", 16))
        cps_layout.addWidget(cps_label)
        cps_layout.addWidget(self.stats_labels["cps"])
        stats_layout.addWidget(cps_widget)
        
        # Add upgrade stats section
        upgrade_stats_label = QLabel("Upgrade Statistics")
        upgrade_stats_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        stats_layout.addWidget(upgrade_stats_label)
        
        # Create a scroll area for upgrade stats to ensure they're all visible
        upgrade_scroll = QScrollArea()
        upgrade_scroll.setWidgetResizable(True)
        upgrade_content = QWidget()
        upgrade_content_layout = QVBoxLayout(upgrade_content)
        upgrade_content_layout.setSpacing(10)  # Add spacing between upgrades
        
        # Create container widgets for upgrade stats but don't add them to layout yet
        self.upgrade_stat_widgets = {}
        for upgrade in self.upgrades:
            upgrade_widget = QWidget()
            upgrade_widget.setMinimumHeight(90)  # Set minimum height for each upgrade stat
            upgrade_layout = QVBoxLayout(upgrade_widget)  # Changed to QVBoxLayout for better text display
            upgrade_layout.setContentsMargins(5, 5, 5, 5)  # Add some padding
            
            # Create upgrade stats
            stats_text = f"{upgrade.icon} {upgrade.name}:"
            stats_text += f"\nTotal Bought: {upgrade.total_bought}"
            stats_text += f"\nTotal Spent: {upgrade.total_spent:,}"
            stats_text += f"\nCurrent Production: {upgrade.count * upgrade.production:.1f}/s"
            
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
                upgrade_content_layout.addWidget(upgrade_widget)
            
            # Store the upgrade label in stats_labels
            self.stats_labels[upgrade.name] = upgrade_label
        
        # Add stretch at the end to push content to the top
        upgrade_content_layout.addStretch(1)
        
        upgrade_scroll.setWidget(upgrade_content)
        stats_layout.addWidget(upgrade_scroll)
        
        # Add tabs to tab widget
        self.tab_widget.addTab(game_tab, "Game")
        self.tab_widget.addTab(achievements_tab, "Achievements")
        self.tab_widget.addTab(stats_tab, "Stats")
        
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
        self.coin_sound_paths = []
        for i in range(1, 6):  # coin1.wav to coin5.wav
            path = os.path.abspath(f"audio/coin{i}.wav")
            if os.path.exists(path):
                self.coin_sound_paths.append(path)
            else:
                print(f"Warning: Coin sound file not found at {path}")
        
        self.click_sound_path = os.path.abspath("audio/click.wav")
        self.achievement_sound_path = os.path.abspath("audio/achievement.wav")
        
        # Check if sound files exist
        self.has_coin_sounds = len(self.coin_sound_paths) > 0
        self.has_click_sound = os.path.exists(self.click_sound_path)
        self.has_achievement_sound = os.path.exists(self.achievement_sound_path)
        
        if not self.has_coin_sounds:
            print("Warning: No coin sound files found in audio folder")
        if not self.has_click_sound:
            print(f"Warning: Click sound file not found at {self.click_sound_path}")
        if not self.has_achievement_sound:
            print(f"Warning: Achievement sound file not found at {self.achievement_sound_path}")

    def click_coin(self):
        # Play a random coin sound
        if self.has_coin_sounds:
            random_coin_sound = random.choice(self.coin_sound_paths)
            play_sound(random_coin_sound)
        
        self.coins += self.coins_per_click
        self.total_coins += self.coins_per_click
        self.total_clicks += 1
        self.update_display()
        self.check_achievements()
        
        # Visual feedback
        self.coin_button.show_click_animation()
        
        # Check for first click achievement
        if not self.achievements["First Click"]["unlocked"]:
            self.unlock_achievement("First Click")
            
    def buy_upgrade(self, upgrade):
        if self.coins >= upgrade.cost:
            # Play click sound
            if self.has_click_sound:
                play_sound(self.click_sound_path)
            
            # Check if this is the first purchase of this upgrade
            first_purchase = upgrade.count == 0
            
            self.coins -= upgrade.cost
            upgrade.count += 1
            upgrade.total_bought += 1
            upgrade.total_spent += upgrade.cost
            upgrade.cost = int(upgrade.cost * 1.5)  # Increase cost by 50%
            upgrade.production += upgrade.base_production  # Increase production
            self.update_display()
            self.show_status_message(f"Bought {upgrade.name} for {upgrade.cost} coins")
            
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
            self.coins += total_production * (self.timer.interval() / 1000)
            self.total_coins += total_production * (self.timer.interval() / 1000)
            self.update_display()
            self.check_achievements()
            
    def update_display(self):
        self.coin_label.setText(f"Coins: {self.coins:.1f}")
        
        # Calculate number of discovered generators (showing in shop)
        discovered_count = 0
        for upgrade in self.upgrades:
            widget_data = self.upgrade_widgets[upgrade.name]
            if widget_data["visible"]:
                discovered_count += 1
        
        # Update generators discovered label
        self.generators_label.setText(f"{discovered_count} of {len(self.upgrades)} generators discovered")
        
        # Update all upgrade displays
        for upgrade in self.upgrades:
            widgets = self.upgrade_widgets[upgrade.name]
            widgets["count_label"].setText(f"{upgrade.icon} {upgrade.name}s: {upgrade.count}")
            widgets["cost_label"].setText(f"Cost: {upgrade.cost}")
            
            # Check if required upgrade is purchased
            can_buy = self.coins >= upgrade.cost
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
        
        # Update clicks
        self.stats_labels["clicks"].setText(f"{self.total_clicks:,}")
        
        # Update total coins
        self.stats_labels["total_coins"].setText(f"{self.total_coins:,.1f}")
        
        # Calculate and update coins per second
        total_cps = 0
        for upgrade in self.upgrades:
            if upgrade.count > 0:
                total_cps += upgrade.production * upgrade.count
        self.stats_labels["cps"].setText(f"{total_cps:.1f}")
        
        # Update upgrade stats with clear formatting
        for upgrade in self.upgrades:
            stats_text = f"{upgrade.icon} {upgrade.name}:"
            stats_text += f"\nTotal Bought: {upgrade.total_bought}"
            stats_text += f"\nTotal Spent: {upgrade.total_spent:,}"
            stats_text += f"\nCurrent Production: {upgrade.count * upgrade.production:.1f}/s"
            self.stats_labels[upgrade.name].setText(stats_text)
        
    def check_achievements(self):
        if self.coins >= 100 and not self.achievements["Coin Master"]["unlocked"]:
            self.unlock_achievement("Coin Master")
        if self.coins >= 1000 and not self.achievements["Coin Empire"]["unlocked"]:
            self.unlock_achievement("Coin Empire")
            
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
            "coins": self.coins,
            "coins_per_click": self.coins_per_click,
            "total_coins": self.total_coins,
            "total_clicks": self.total_clicks,
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
        self.save_worker.finished.connect(lambda: self.show_status_message("Game auto-saved"))
        self.save_worker.error.connect(lambda e: self.show_status_message(f"Failed to save game: {e}"))
        self.save_worker.start()

    def save_game(self, silent=False):
        save_data = {
            "coins": self.coins,
            "coins_per_click": self.coins_per_click,
            "total_coins": self.total_coins,
            "total_clicks": self.total_clicks,
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
            self.save_worker.finished.connect(lambda: self.show_status_message("Game saved successfully!"))
            self.save_worker.error.connect(lambda e: self.show_status_message(f"Failed to save game: {e}"))
        self.save_worker.start()
        self.last_save_time = QDateTime.currentDateTime()

    def return_to_menu(self):
        # Auto-save before returning to menu
        self.auto_save()
        # Switch to menu view
        self.central_widget.setCurrentWidget(self.main_menu)

    def load_game(self):
        if os.path.exists("clicker_save_game.json"):
            # Use proper Qt thread for loading
            self.load_worker = LoadWorker()
            self.load_worker.finished.connect(self.process_loaded_data)
            self.load_worker.error.connect(lambda e: self.show_status_message(f"Failed to load game: {e}"))
            self.load_worker.start()
        else:
            self.show_status_message("No save file found")

    def process_loaded_data(self, save_data):
        # Update game state on the main thread
        self.coins = save_data["coins"]
        self.coins_per_click = save_data["coins_per_click"]
        self.total_coins = save_data.get("total_coins", 0)
        self.total_clicks = save_data.get("total_clicks", 0)
        self.start_time = QDateTime.fromString(save_data.get("start_time", QDateTime.currentDateTime().toString()))
        self.achievements = save_data["achievements"]
        
        # Load upgrade data
        for upgrade in self.upgrades:
            if upgrade.name in save_data:
                upgrade_data = save_data[upgrade.name]
                upgrade.count = upgrade_data["count"]
                upgrade.cost = upgrade_data["cost"]
                upgrade.production = upgrade_data["production"]
                upgrade.total_bought = upgrade_data.get("total_bought", 0)
                upgrade.total_spent = upgrade_data.get("total_spent", 0)
        
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
        self.show_status_message("Game loaded successfully")

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    game = ClickerGame()
    game.show()
    sys.exit(app.exec()) 