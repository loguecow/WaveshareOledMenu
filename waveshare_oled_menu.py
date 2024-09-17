import time
import psutil
from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont, Image, ImageDraw
import RPi.GPIO as GPIO
import os

# OLED display configuration for Waveshare 1.3inch OLED HAT
serial = spi(device=0, port=0)
device = sh1106(serial, rotate=2, width=128, height=64)

# Button GPIO pins for Waveshare 1.3inch OLED HAT
KEY_UP_PIN     = 6 
KEY_DOWN_PIN   = 19
KEY_LEFT_PIN   = 5
KEY_RIGHT_PIN  = 26
KEY_PRESS_PIN  = 13
KEY1_PIN       = 21
KEY2_PIN       = 20
KEY3_PIN       = 16

# Load fonts
font = ImageFont.load_default()
font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)

# Menu options
main_menu = [
    "Connect WiFi",
    "Bluetooth On/Off",
    "GPIO Control",
    "Run Script 1",
    "Run Script 2",
    "System"
]

system_menu = [
    "System Info",
    "Shutdown",
    "Restart",
    "Back to Main Menu"
]

current_menu = main_menu
selected_item = 0

def draw_menu(menu):
    with canvas(device) as draw:
        for i, item in enumerate(menu):
            if i == selected_item:
                draw.rectangle((0, i*10, device.width, (i+1)*10), outline="white", fill="white")
                draw.text((5, i*10), item, font=font, fill="black")
            else:
                draw.text((5, i*10), item, font=font, fill="white")

def button_callback(channel):
    global selected_item, current_menu
    if channel == KEY_UP_PIN:
        selected_item = (selected_item - 1) % len(current_menu)
    elif channel == KEY_DOWN_PIN:
        selected_item = (selected_item + 1) % len(current_menu)
    elif channel == KEY_PRESS_PIN:
        if current_menu == main_menu:
            if current_menu[selected_item] == "System":
                current_menu = system_menu
                selected_item = 0
            else:
                print(f"Selected: {current_menu[selected_item]}")
                # Add logic for other main menu items here
        elif current_menu == system_menu:
            if system_menu[selected_item] == "System Info":
                show_system_info()
            elif system_menu[selected_item] == "Shutdown":
                shutdown()
            elif system_menu[selected_item] == "Restart":
                restart()
            elif system_menu[selected_item] == "Back to Main Menu":
                current_menu = main_menu
                selected_item = 0
    draw_menu(current_menu)

def show_system_info():
    last_update = time.time()
    update_interval = 1  # Update every 1 second
    exit_delay = 0.5  # Delay before allowing exit

    while True:
        current_time = time.time()
        if current_time - last_update >= update_interval:
            with canvas(device) as draw:
                draw.text((0, 0), "System Info", font=font_bold, fill="white")
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                draw.text((0, 15), f"CPU: {cpu}%", font=font, fill="white")
                draw.text((0, 25), f"RAM: {ram}%", font=font, fill="white")
                draw.text((0, 35), f"Disk: {disk}%", font=font, fill="white")
                draw.text((0, 55), "Press any key to exit", font=font, fill="white")
            last_update = current_time

        if current_time - last_update >= exit_delay:
            if (GPIO.input(KEY_UP_PIN) == GPIO.LOW or
                GPIO.input(KEY_DOWN_PIN) == GPIO.LOW or
                GPIO.input(KEY_PRESS_PIN) == GPIO.LOW):
                time.sleep(0.2)  # Debounce
                break

        time.sleep(0.1)  # Small delay to prevent busy waiting

def shutdown():
    with canvas(device) as draw:
        draw.text((5, 20), "Shutting down...", font=font, fill="white")
    time.sleep(2)
    os.system("sudo shutdown -h now")

def restart():
    with canvas(device) as draw:
        draw.text((5, 20), "Restarting...", font=font, fill="white")
    time.sleep(2)
    os.system("sudo reboot")

def show_boot_screen():
    # Create a new image with a black background
    image = Image.new('1', (device.width, device.height))
    draw = ImageDraw.Draw(image)

    # Draw your boot screen
    draw.text((10, 10), "Welcome to", font=font, fill="white")
    draw.text((10, 25), "Raspberry Pi", font=font_bold, fill="white")
    draw.text((10, 40), "OLED Menu", font=font_bold, fill="white")

    # Display the boot screen
    device.display(image)
    time.sleep(3)  # Show the boot screen for 3 seconds

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(KEY_UP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_DOWN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_LEFT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_RIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY_PRESS_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(KEY3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.add_event_detect(KEY_UP_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(KEY_DOWN_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(KEY_PRESS_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

try:
    print("Initializing menu...")
    show_boot_screen()
    draw_menu(current_menu)
    print("Menu initialized. Use the UP and DOWN buttons to navigate, and PRESS to select.")
    while True:
        time.sleep(0.1)
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    GPIO.cleanup()
