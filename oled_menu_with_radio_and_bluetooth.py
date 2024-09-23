import time
import psutil
from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont, Image, ImageDraw
import RPi.GPIO as GPIO
import os
import subprocess

# OLED display configuration
WIDTH = 128
HEIGHT = 64
INTERFACE = "SPI"  # Change this to "I2C" for I2C interface

if INTERFACE == "SPI":
    serial = spi(device=0, port=0)
    device = sh1106(serial, rotate=2, width=WIDTH, height=HEIGHT)
else:  # I2C
    serial = i2c(port=1, address=0x3C)
    device = sh1106(serial, rotate=2, width=WIDTH, height=HEIGHT)

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

# Menu options with icons
main_menu = [
    ("Network", "folder.bmp"),
    ("USB Tools", "usbfolder.bmp"),
    ("System", "wrench.bmp"),
    ("Monitoring", "graph.bmp"),
    ("Settings", "screwdriver.bmp"),
    ("Radio", "radio.bmp")
]

network_menu = [
    ("WiFi", "wifi.bmp"),
    ("Ethernet", "eth.bmp"),
    ("Router", "router.bmp"),
    ("Dual Band", "dualbandrouter.bmp"),
    ("Back", "back.bmp")
]

usb_menu = [
    ("USB Devices", "usb.bmp"),
    ("Bad USB", "badusb.bmp"),
    ("USB Exploit", "usbskull.bmp"),
    ("Back", "back.bmp")
]

system_menu = [
    ("Shell", "shell_laptop.bmp"),
    ("Tools", "tool.bmp"),
    ("Info", "magnifyer.bmp"),
    ("Shutdown", "back.bmp"),
    ("Restart", "back.bmp"),
    ("Back", "back.bmp")
]

monitoring_menu = [
    ("Network Traffic", "routeremit.bmp"),
    ("System Load", "graph.bmp"),
    ("Security Alerts", "skullemit.bmp"),
    ("Back", "back.bmp")
]

settings_menu = [
    ("Display", "tool.bmp"),
    ("Power", "tool.bmp"),
    ("Back", "back.bmp")
]

radio_menu = [
    ("FM Transmitter", "radio.bmp"),
    ("Bluetooth Spam", "bluetooth.bmp"),
    ("Back", "back.bmp")
]

current_menu = main_menu
menu_stack = []
selected_item = 0
scroll_position = 0
max_items = 4  # Maximum number of items to display at once

# Settings
brightness = 255
contrast = 255

# Debounce variables
last_button_press = 0
debounce_time = 0.2  # 200ms debounce

# Idle timer variables
idle_timeout = 30  # 30 seconds
last_activity_time = time.time()

# Idle animation settings
idle_animation_folder = "./idleAnimation"
idle_animation_delay = 0.01

# Boot and press button page BMP settings
boot_bmp = "boot_image.bmp"
press_button_bmp = "press_button.bmp"

# FM Transmitter settings
fm_process = None

def load_icon(icon_name):
    try:
        icon = Image.open(f"./icons/{icon_name}").convert("1")
        return icon.resize((12, 12))
    except:
        return Image.open("./icons/missing.bmp").convert("1").resize((12, 12))

def draw_menu(menu):
    global scroll_position
    with canvas(device) as draw:
        for i in range(max_items):
            index = scroll_position + i
            if index >= len(menu):
                break
            item, icon_name = menu[index]
            y = i * 16
            if index == selected_item:
                draw.rectangle((0, y, device.width, y + 16), outline="white", fill="white")
                draw.text((20, y + 2), item[:13], font=font, fill="black")
                icon = load_icon(icon_name)
                draw.bitmap((2, y + 2), icon, fill="black")
            else:
                draw.text((20, y + 2), item[:13], font=font, fill="white")
                icon = load_icon(icon_name)
                draw.bitmap((2, y + 2), icon, fill="white")
        
        # Draw scroll indicator
        if len(menu) > max_items:
            indicator_height = (max_items / len(menu)) * device.height
            indicator_pos = (scroll_position / len(menu)) * device.height
            draw.rectangle((device.width - 2, indicator_pos, device.width, indicator_pos + indicator_height), outline="white", fill="white")

def button_callback(channel):
    global selected_item, current_menu, scroll_position, last_button_press, last_activity_time, menu_stack
    current_time = time.time()
    
    if current_time - last_button_press < debounce_time:
        return
    
    last_button_press = current_time
    last_activity_time = current_time  # Reset idle timer on button press

    if channel == KEY_UP_PIN:
        selected_item = (selected_item - 1) % len(current_menu)
    elif channel == KEY_DOWN_PIN:
        selected_item = (selected_item + 1) % len(current_menu)
    elif channel == KEY_PRESS_PIN or channel == KEY_RIGHT_PIN:
        handle_selection()
    elif channel == KEY_LEFT_PIN:
        if menu_stack:
            current_menu = menu_stack.pop()
            selected_item = 0
            scroll_position = 0
    
    # Adjust scroll position
    if selected_item < scroll_position:
        scroll_position = selected_item
    elif selected_item >= scroll_position + max_items:
        scroll_position = selected_item - max_items + 1
    
    draw_menu(current_menu)

def handle_selection():
    global current_menu, selected_item, menu_stack
    item = current_menu[selected_item][0]
    
    if item == "Back":
        if menu_stack:
            current_menu = menu_stack.pop()
            selected_item = 0
            scroll_position = 0
    elif item == "Network":
        menu_stack.append(current_menu)
        current_menu = network_menu
        selected_item = 0
    elif item == "USB Tools":
        menu_stack.append(current_menu)
        current_menu = usb_menu
        selected_item = 0
    elif item == "System":
        menu_stack.append(current_menu)
        current_menu = system_menu
        selected_item = 0
    elif item == "Monitoring":
        menu_stack.append(current_menu)
        current_menu = monitoring_menu
        selected_item = 0
    elif item == "Settings":
        menu_stack.append(current_menu)
        current_menu = settings_menu
        selected_item = 0
    elif item == "Radio":
        menu_stack.append(current_menu)
        current_menu = radio_menu
        selected_item = 0
    elif item == "FM Transmitter":
        start_fm_transmitter()
    elif item == "Bluetooth Spam":
        start_bluetooth_spam()
    elif item == "Info":
        show_system_info()
    elif item == "Shutdown":
        shutdown()
    elif item == "Restart":
        restart()
    elif item == "Display":
        adjust_display_settings()
    else:
        print(f"Selected: {item}")
    
    draw_menu(current_menu)

def show_system_info():
    global last_activity_time
    last_update = time.time()
    update_interval = 1  # Update every 1 second
    exit_flag = False

    while not exit_flag:
        current_time = time.time()
        if current_time - last_update >= update_interval:
            with canvas(device) as draw:
                draw.text((0, 0), "System Info", font=font_bold, fill="white")
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                draw.text((0, 15), f"CPU: {cpu:.1f}%", font=font, fill="white")
                draw.text((0, 25), f"RAM: {ram:.1f}%", font=font, fill="white")
                draw.text((0, 35), f"Disk: {disk:.1f}%", font=font, fill="white")
                draw.text((0, 55), "Press any key to exit", font=font, fill="white")
            last_update = current_time

        if (GPIO.input(KEY_UP_PIN) == GPIO.LOW or
            GPIO.input(KEY_DOWN_PIN) == GPIO.LOW or
            GPIO.input(KEY_PRESS_PIN) == GPIO.LOW or
            GPIO.input(KEY1_PIN) == GPIO.LOW or
            GPIO.input(KEY2_PIN) == GPIO.LOW or
            GPIO.input(KEY3_PIN) == GPIO.LOW):
            exit_flag = True
            last_activity_time = time.time()  # Reset idle timer
            time.sleep(debounce_time)  # Debounce

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

def adjust_display_settings():
    global brightness, contrast, last_activity_time
    display_menu = [
        ("Brightness", "tool.bmp"),
        ("Contrast", "tool.bmp"),
        ("Back", "back.bmp")
    ]
    display_selected = 0

    while True:
        with canvas(device) as draw:
            for i, (item, icon) in enumerate(display_menu):
                y = i * 16
                if i == display_selected:
                    draw.rectangle((0, y, device.width, y + 16), outline="white", fill="white")
                    draw.text((20, y + 2), item, font=font, fill="black")
                    icon = load_icon(icon)
                    draw.bitmap((2, y + 2), icon, fill="black")
                else:
                    draw.text((20, y + 2), item, font=font, fill="white")
                    icon = load_icon(icon)
                    draw.bitmap((2, y + 2), icon, fill="white")

        time.sleep(0.1)
        
        if GPIO.input(KEY_UP_PIN) == GPIO.LOW:
            display_selected = (display_selected - 1) % len(display_menu)
            last_activity_time = time.time()
            time.sleep(debounce_time)
        elif GPIO.input(KEY_DOWN_PIN) == GPIO.LOW:
            display_selected = (display_selected + 1) % len(display_menu)
            last_activity_time = time.time()
            time.sleep(debounce_time)
        elif GPIO.input(KEY_PRESS_PIN) == GPIO.LOW or GPIO.input(KEY_RIGHT_PIN) == GPIO.LOW:
            if display_menu[display_selected][0] == "Brightness":
                adjust_brightness()
            elif display_menu[display_selected][0] == "Contrast":
                adjust_contrast()
            elif display_menu[display_selected][0] == "Back":
                break
            last_activity_time = time.time()
            time.sleep(debounce_time)
        elif GPIO.input(KEY_LEFT_PIN) == GPIO.LOW:
            break

def adjust_brightness():
    global brightness, last_activity_time
    exit_flag = False
    while not exit_flag:
        with canvas(device) as draw:
            draw.text((0, 0), "Adjust Brightness", font=font_bold, fill="white")
            draw.text((0, 20), f"Current: {brightness}", font=font, fill="white")
            draw.text((0, 40), "Up/Down to adjust", font=font, fill="white")
            draw.text((0, 50), "Press to confirm", font=font, fill="white")
        
        time.sleep(0.1)
        
        if GPIO.input(KEY_UP_PIN) == GPIO.LOW:
            brightness = min(255, brightness + 5)
            device.contrast(brightness)
            last_activity_time = time.time()  # Reset idle timer
            time.sleep(debounce_time)
        elif GPIO.input(KEY_DOWN_PIN) == GPIO.LOW:
            brightness = max(0, brightness - 5)
            device.contrast(brightness)
            last_activity_time = time.time()  # Reset idle timer
            time.sleep(debounce_time)
        elif GPIO.input(KEY_PRESS_PIN) == GPIO.LOW:
            exit_flag = True
            last_activity_time = time.time()  # Reset idle timer
            time.sleep(debounce_time)

def adjust_contrast():
    global contrast
    contrast = (contrast + 50) % 256
    device.contrast(contrast)
    show_setting("Contrast", contrast)

def show_setting(setting, value):
    with canvas(device) as draw:
        draw.text((0, 20), f"{setting}: {value}", font=font, fill="white")
    time.sleep(1)

def show_boot_screen():
    try:
        boot_image = Image.open(boot_bmp).convert("1")
        boot_image = boot_image.resize((device.width, device.height))
        device.display(boot_image)
    except FileNotFoundError:
        with canvas(device) as draw:
            draw.text((10, 10), "Welcome to", font=font, fill="white")
            draw.text((10, 25), "Raspberry Pi", font=font_bold, fill="white")
            draw.text((10, 40), "OLED Menu", font=font_bold, fill="white")
    time.sleep(3)  # Show the boot screen for 3 seconds

def show_start_page():
    global last_activity_time
    try:
        press_button_image = Image.open(press_button_bmp).convert("1")
        press_button_image = press_button_image.resize((device.width, device.height))
        device.display(press_button_image)
    except FileNotFoundError:
        with canvas(device) as draw:
            draw.text((10, 10), "Press Key 1, 2, or 3", font=font_bold, fill="white")
            draw.text((10, 25), "to start", font=font_bold, fill="white")
    
    while True:
        if (GPIO.input(KEY1_PIN) == GPIO.LOW or
            GPIO.input(KEY2_PIN) == GPIO.LOW or
            GPIO.input(KEY3_PIN) == GPIO.LOW):
            last_activity_time = time.time()  # Reset idle timer
            time.sleep(debounce_time)  # Debounce
            break
        time.sleep(0.1)

def show_idle_animation():
    frames = {}
    frame_files = sorted([f for f in os.listdir(idle_animation_folder) if f.startswith("frame") and f.endswith(".bmp")])
    frame_count = len(frame_files)

    for i, file in enumerate(frame_files, 1):
        bmp = Image.open(os.path.join(idle_animation_folder, file))
        frames[i] = bmp.resize((device.width, device.height))

    current_frame = 1
    while True:
        if (GPIO.input(KEY_UP_PIN) == GPIO.LOW or
            GPIO.input(KEY_DOWN_PIN) == GPIO.LOW or
            GPIO.input(KEY_PRESS_PIN) == GPIO.LOW or
            GPIO.input(KEY1_PIN) == GPIO.LOW or
            GPIO.input(KEY2_PIN) == GPIO.LOW or
            GPIO.input(KEY3_PIN) == GPIO.LOW):
            break

        image = Image.new('1', (device.width, device.height), 255)  # 255: clear the frame
        image.paste(frames[current_frame])
        device.display(image)

        current_frame = (current_frame % frame_count) + 1
        time.sleep(idle_animation_delay)

def start_fm_transmitter():
    global fm_process, last_activity_time
    frequency = 100.6
    
    # Get list of .wav files
    wav_files = [f for f in os.listdir("./fm_transmitter") if f.endswith(".wav")]
    if not wav_files:
        with canvas(device) as draw:
            draw.text((0, 20), "No .wav files found", font=font, fill="white")
        time.sleep(2)
        return
    
    selected_file = 0
    
    while True:
        with canvas(device) as draw:
            draw.text((0, 0), "FM Transmitter", font=font_bold, fill="white")
            draw.text((0, 15), f"Freq: {frequency:.1f} MHz", font=font, fill="white")
            draw.text((0, 25), f"File: {wav_files[selected_file][:13]}", font=font, fill="white")
            status = "Transmitting" if fm_process else "Stopped"
            draw.text((0, 35), f"Status: {status}", font=font, fill="white")
            draw.text((0, 45), "Key1/2: Change File", font=font, fill="white")
            draw.text((0, 55), "Key3: Start/Stop", font=font, fill="white")
        
        time.sleep(0.1)
        
        if GPIO.input(KEY1_PIN) == GPIO.LOW:
            selected_file = (selected_file - 1) % len(wav_files)
            last_activity_time = time.time()
            time.sleep(debounce_time)
        elif GPIO.input(KEY2_PIN) == GPIO.LOW:
            selected_file = (selected_file + 1) % len(wav_files)
            last_activity_time = time.time()
            time.sleep(debounce_time)
        elif GPIO.input(KEY3_PIN) == GPIO.LOW:
            if fm_process is None:
                # Start FM transmission
                sound_file = os.path.join("./fm_transmitter", wav_files[selected_file])
                fm_process = subprocess.Popen(["sudo", "./fm_transmitter/fm_transmitter", "-f", f"{frequency:.1f}", sound_file])
            else:
                # Stop FM transmission
                fm_process.terminate()
                fm_process = None
            last_activity_time = time.time()
            time.sleep(debounce_time)
        elif GPIO.input(KEY_LEFT_PIN) == GPIO.LOW:
            if fm_process:
                fm_process.terminate()
                fm_process = None
            break

def start_bluetooth_spam():
    global last_activity_time
    spam_process = None
    
    while True:
        with canvas(device) as draw:
            draw.text((0, 0), "Bluetooth Spam", font=font_bold, fill="white")
            status = "Running" if spam_process else "Stopped"
            draw.text((0, 20), f"Status: {status}", font=font, fill="white")
            draw.text((0, 40), "Key3 to Start/Stop", font=font, fill="white")
            draw.text((0, 50), "Left to exit", font=font, fill="white")
        
        time.sleep(0.1)
        
        if GPIO.input(KEY3_PIN) == GPIO.LOW:
            if spam_process is None:
                # Start Bluetooth Spam
                spam_process = subprocess.Popen(["python3", "./AppleJuice/app.py", "-r", "-i", "20"])
                last_activity_time = time.time()
            else:
                # Stop Bluetooth Spam
                spam_process.terminate()
                spam_process = None
            time.sleep(debounce_time)
        elif GPIO.input(KEY_LEFT_PIN) == GPIO.LOW:
            if spam_process:
                spam_process.terminate()
            break
        
        last_activity_time = time.time()

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
GPIO.add_event_detect(KEY_LEFT_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(KEY_RIGHT_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)
GPIO.add_event_detect(KEY_PRESS_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

try:
    print("Initializing menu...")
    show_boot_screen()
    show_start_page()
    draw_menu(current_menu)
    print("Menu initialized. Use the UP and DOWN buttons to navigate, and PRESS or RIGHT to select.")
    while True:
        current_time = time.time()
        if current_time - last_activity_time > idle_timeout:
            show_idle_animation()
            last_activity_time = time.time()  # Reset idle timer after showing animation
        time.sleep(0.1)
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if fm_process:
        fm_process.terminate()
    GPIO.cleanup()
