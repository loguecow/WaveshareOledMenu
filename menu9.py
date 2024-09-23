import time
import psutil
from luma.core.interface.serial import i2c, spi
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont, Image, ImageDraw
import RPi.GPIO as GPIO
import os

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
    ("Settings", "screwdriver.bmp")
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

current_menu = main_menu
menu_stack = []
selected_item = 0
scroll_position = 0
max_items = 4  # Maximum number of items to display at once

# Settings
brightness = 255
inverted = False
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
    global brightness, inverted, contrast, last_activity_time
    display_menu = [
        ("Brightness", "tool.bmp"),
        ("Invert", "tool.bmp"),
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
            elif display_menu[display_selected][0] == "Invert":
                toggle_invert()
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

def toggle_invert():
    global inverted
    inverted = not inverted
    device.invert(inverted)
    show_setting("Invert", "On" if inverted else "Off")

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
    with canvas(device) as draw:
        draw.text((10, 10), "Welcome to", font=font, fill="white")
        draw.text((10, 25), "Raspberry Pi", font=font_bold, fill="white")
        draw.text((10, 40), "OLED Menu", font=font_bold, fill="white")
    time.sleep(3)  # Show the boot screen for 3 seconds

def show_start_page():
    global last_activity_time
    with canvas(device) as draw:
        draw.text((10, 10), "Press Key 1, 2, or 3", font=font_bold, fill="white")
        draw.text((10, 25), "to start", font=font_bold, fill="white")
    
    while True:
        if (GPIO.input(KEY1_PIN) == GPIO.LOW or
            GPIO.input(KEY2_PIN) == GPIO.LOW or
            GPIO.input(KEY3_PIN) == GPIO.LOW):
            last_activity_time = time.time()  # Reset idle timer
            time.sleep(debounce_time)  #
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
    GPIO.cleanup()
