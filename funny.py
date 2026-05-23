import os
import sys
import time
import random
import ctypes
import winreg
import pygame
import pyautogui
try:
    import win32gui
    import win32process
    import win32con
    import commctrl
except ImportError:
    print("pywin32 module not found. Install it with: pip install pywin32")
import math

# Force true hardware resolution awareness immediately
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_desktop_listview_hwnd():
    """Finds the actual handle for the desktop list control window."""

    hwnd = win32gui.FindWindow("Progman", "Program Manager")
    shell_hwnd = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)

    if shell_hwnd:
        listview_hwnd = win32gui.FindWindowEx(
            shell_hwnd,
            0,
            "SysListView32",
            None
        )

        return listview_hwnd, shell_hwnd

    hwnds = []

    def callback(top_hwnd, extra):
        try:
            if win32gui.GetClassName(top_hwnd) == "WorkerW":

                shell_hwnd = win32gui.FindWindowEx(
                    top_hwnd,
                    0,
                    "SHELLDLL_DefView",
                    None
                )

                if shell_hwnd:

                    listview_hwnd = win32gui.FindWindowEx(
                        shell_hwnd,
                        0,
                        "SysListView32",
                        None
                    )

                    if listview_hwnd:
                        extra.append((listview_hwnd, shell_hwnd))

        except Exception:
            pass

        return True

    win32gui.EnumWindows(callback, hwnds)

    if hwnds:
        return hwnds[0]

    return None, None
    
def get_desktop_icon_positions():
    """Queries Windows API safely to get live icon locations."""
    hwnd, _ = get_desktop_listview_hwnd()
    if not hwnd:
        return []

    icon_count = win32gui.SendMessage(hwnd, commctrl.LVM_GETITEMCOUNT, 0, 0)
    if icon_count == 0:
        return []

    thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
    process_handle = ctypes.windll.kernel32.OpenProcess(0x38, False, pid)
    remote_point = ctypes.windll.kernel32.VirtualAllocEx(process_handle, None, ctypes.sizeof(POINT), 0x1000, 0x04)

    positions = []
    local_point = POINT()

    for i in range(icon_count):
        win32gui.SendMessage(hwnd, commctrl.LVM_GETITEMPOSITION, i, remote_point)
        ctypes.windll.kernel32.ReadProcessMemory(process_handle, remote_point, ctypes.byref(local_point), ctypes.sizeof(POINT), None)
        positions.append((local_point.x, local_point.y))

    ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_point, 0, 0x8000)
    ctypes.windll.kernel32.CloseHandle(process_handle)
    return positions

def toggle_desktop_icons():
    """Programmatically triggers the Windows Shell to toggle icons on/off instantly."""
    _, shell_hwnd = get_desktop_listview_hwnd()
    if shell_hwnd:
        win32gui.SendMessage(shell_hwnd, win32con.WM_COMMAND, 0x702D, 0)

def get_windows_wallpaper_path():
    """Reads the active wallpaper path straight out of the Windows Registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        wallpaper_path, _ = winreg.QueryValueEx(key, "Wallpaper")
        winreg.CloseKey(key)
        if os.path.exists(wallpaper_path) and wallpaper_path.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
            return wallpaper_path
    except Exception:
        pass
    return os.path.join(os.environ['WINDIR'], 'Web', 'Wallpaper', 'Windows', 'img0.jpg')

def minimize_all_windows():
    """Minimizes foreground applications to reveal the desktop."""
    ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
    time.sleep(0.6)

def remove_background_pixels(icon_surf, bg_surf, tolerance=35):
    """Isolates the icon artwork and text into an alpha transparent layer."""
    transparent_surf = pygame.Surface(icon_surf.get_size(), pygame.SRCALPHA).convert_alpha()
    
    for x in range(icon_surf.get_width()):
        for y in range(icon_surf.get_height()):
            icon_pixel = icon_surf.get_at((x, y))
            bg_pixel = bg_surf.get_at((x, y))
            
            diff_r = abs(icon_pixel.r - bg_pixel.r)
            diff_g = abs(icon_pixel.g - bg_pixel.g)
            diff_b = abs(icon_pixel.b - bg_pixel.b)
            
            if diff_r < tolerance and diff_g < tolerance and diff_b < tolerance:
                transparent_surf.set_at((x, y), (0, 0, 0, 0))
            else:
                transparent_surf.set_at((x, y), icon_pixel)
                
    return transparent_surf

def main():
    icon_coords = get_desktop_icon_positions()
    if not icon_coords:
        print("Error: Could not retrieve system icon positions. Ensure 'Auto arrange icons' is disabled.")
        return

    wallpaper_file = get_windows_wallpaper_path()
    minimize_all_windows()

    # Force Pygame to window coordinate 0,0 (absolute top-left corner)
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"

    pygame.init()
    info = pygame.display.Info()
    screen_width, full_screen_height = info.current_w, info.current_h
    
    # Precise taskbar cushion setup
    taskbar_height = 40 
    usable_height = full_screen_height - taskbar_height

    # FIXED: Build the window to the exact full width/height immediately instead of maximizing later
    pygame.display.set_caption("Desktop Physics Window")
    screen = pygame.display.set_mode((screen_width, usable_height), pygame.NOFRAME)
    clock = pygame.time.Clock()

    # Hide the window briefly for a clean snapshot
    pygame_hwnd = pygame.display.get_wm_info()['window']
    win32gui.ShowWindow(pygame_hwnd, win32con.SW_HIDE)
    time.sleep(0.1)

    # Capture the desktop
    screenshot = pyautogui.screenshot(region=(0, 0, screen_width, full_screen_height))
    screenshot_bytes = screenshot.tobytes()
    raw_desktop = pygame.image.fromstring(screenshot_bytes, screenshot.size, screenshot.mode).convert()

    # Automatically hide your real static desktop icons
    toggle_desktop_icons()
    time.sleep(0.1)

    # FIXED: Re-show window and pin it directly to (0,0) without triggering buggy Windows maximize code
    win32gui.ShowWindow(pygame_hwnd, win32con.SW_SHOW)
    ctypes.windll.user32.SetWindowPos(
        pygame_hwnd,
        1,  # HWND_BOTTOM
        0,
        0,
        screen_width,
        usable_height,
        0x0040
    )
    ctypes.windll.user32.SetForegroundWindow(pygame_hwnd)
    win32gui.SetParent(pygame_hwnd, win32gui.FindWindow("Progman", "Program Manager"))
    time.sleep(0.1)

    try:
        loaded_bg = pygame.image.load(wallpaper_file).convert()
        background_img = pygame.transform.scale(loaded_bg, (screen_width, full_screen_height))
        background_img = background_img.subsurface(pygame.Rect(0, 0, screen_width, usable_height))
    except Exception:
        background_img = pygame.Surface((screen_width, usable_height))
        background_img.fill((0, 120, 215))

    blocks = []
    icon_w, icon_h = 75, 76

    for x_pos, y_pos in icon_coords:
        if y_pos >= usable_height - icon_h or x_pos >= screen_width - icon_w:
            continue

        rect = pygame.Rect(x_pos, y_pos, icon_w, icon_h)
        icon_raw_surface = raw_desktop.subsurface(rect).copy()
        bg_slice_surface = background_img.subsurface(rect).copy()

        transparent_icon = remove_background_pixels(icon_raw_surface, bg_slice_surface)
        mask = pygame.mask.from_surface(transparent_icon)
        
        if mask.count() < 50:
            continue

        blocks.append({
            "surf": transparent_icon,
            "mask": mask,
            "x": float(rect.x),
            "y": float(rect.y),
            "vx": random.uniform(-0.5, 0.5),
            "vy": random.uniform(-1.0, 0.0),
            "width": icon_w,
            "height": icon_h,
            "floor": usable_height - icon_h - random.randint(4, 12)
        })

    gravity = 0.35
    bounce_loss = 0.3
    friction = 0.95

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        # Physics Calculations Core Loops
        for i, b in enumerate(blocks):
            b["vy"] += gravity
            b["x"] += b["vx"]
            b["y"] += b["vy"]

            if b["y"] >= b["floor"]:
                b["y"] = b["floor"]
                b["vy"] = -b["vy"] * bounce_loss
                b["vx"] *= friction
                if abs(b["vy"]) < 0.5: b["vy"] = 0

            if b["x"] <= 0:
                b["x"] = 0
                b["vx"] = -b["vx"] * bounce_loss
            elif b["x"] >= screen_width - b["width"]:
                b["x"] = screen_width - b["width"]
                b["vx"] = -b["vx"] * bounce_loss

            # Mask boundary intersections
                        # REAL collision physics
            for j in range(i + 1, len(blocks)):
                other = blocks[j]

                offset_x = int(other["x"] - b["x"])
                offset_y = int(other["y"] - b["y"])

                if b["mask"].overlap(other["mask"], (offset_x, offset_y)):

                    center_b_x = b["x"] + b["width"] / 2
                    center_b_y = b["y"] + b["height"] / 2

                    center_o_x = other["x"] + other["width"] / 2
                    center_o_y = other["y"] + other["height"] / 2

                    dx = center_o_x - center_b_x
                    dy = center_o_y - center_b_y

                    distance = math.hypot(dx, dy)

                    if distance == 0:
                        distance = 0.1

                    nx = dx / distance
                    ny = dy / distance

                    # Push apart
                    overlap = 4

                    b["x"] -= nx * overlap / 2
                    b["y"] -= ny * overlap / 2

                    other["x"] += nx * overlap / 2
                    other["y"] += ny * overlap / 2

                    # Relative velocity
                    rvx = other["vx"] - b["vx"]
                    rvy = other["vy"] - b["vy"]

                    velocity_along_normal = rvx * nx + rvy * ny

                    if velocity_along_normal > 0:
                        continue

                    restitution = 0.45

                    impulse = -(1 + restitution) * velocity_along_normal
                    impulse /= 2

                    impulse_x = impulse * nx
                    impulse_y = impulse * ny

                    b["vx"] -= impulse_x
                    b["vy"] -= impulse_y

                    other["vx"] += impulse_x
                    other["vy"] += impulse_y
        # Render Loop scene matrix compilation
        screen.blit(background_img, (0, 0)) 

        for b in blocks:
            screen.blit(b["surf"], (int(b["x"]), int(b["y"])))

        pygame.display.flip()
        clock.tick(60)

    # Restore desktop icons automatically on clean exit
    toggle_desktop_icons()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
