import time
import threading
import platform
import ctypes
import tkinter as tk
from pynput import mouse, keyboard
import queue

# --- Biến toàn cục ---
# MODIFIED: positions are now hardcoded
positions = {
    'Chanh City': (150, 460),
    'Vào ngay!': (150, 550),
    'Đóng': (520, 800)
}
running = False
app_exit_event = threading.Event()
mouse_controller = mouse.Controller()
current_selection_key = None # Kept for potential future use with other dynamic selections
selecting_position_active = False # Kept for potential future use
temp_mouse_listener = None # Kept for potential future use

message_queue = queue.Queue()
_tk_root_ref = None
SETUP_COMPLETE = False

# --- Cấu hình Tooltip ---
current_tooltip_instance = None
TOOLTIP_DEFAULT_DURATION = 3500
TOOLTIP_ERROR_DURATION = 5000
TOOLTIP_Y_OFFSET = 20
TOOLTIP_X_OFFSET_FROM_RIGHT = 20

# --- Lớp Tooltip tùy chỉnh ---
class CustomToolTip(tk.Toplevel):
    def __init__(self, master, text, position_y, msg_type="info", **kwargs):
        super().__init__(master, **kwargs)
        self.overrideredirect(True)
        self.attributes("-alpha", 0.95)
        self.attributes("-topmost", True)

        bg_color = "#F0F0F0"; text_color = "#000000"; font_style = ("Arial", 9)
        if msg_type == "error":
            bg_color = "#FFDDDD"; text_color = "#8B0000"; font_style = ("Arial", 9, "bold")
        elif msg_type == "warning":
            bg_color = "#FFFACD"; text_color = "#5B5B00"
        elif msg_type == "info":
            bg_color = "#E0FFFF"; text_color = "#004D4D"
        elif msg_type == "success":
            bg_color = "#D4EDDA"; text_color = "#155724"

        lines = text.split('\n', 1)
        title_text = ""; message_content = text
        if len(lines) > 0:
            first_line_stripped = lines[0].strip()
            if first_line_stripped.endswith(':') and first_line_stripped[:-1].isupper() and len(first_line_stripped[:-1]) > 2 :
                title_text = first_line_stripped
                message_content = lines[1] if len(lines) > 1 else ""
            elif ":" in first_line_stripped and len(first_line_stripped) < 60:
                title_parts = first_line_stripped.split(':', 1)
                if len(title_parts) > 1 and title_parts[0].strip().isupper():
                    title_text = title_parts[0].strip() + ":"
                    message_content = title_parts[1].strip()
                    if len(lines) > 1: message_content += "\n" + "\n".join(lines[1:])
                else: message_content = text
            else: message_content = text

        container = tk.Frame(self, bg=bg_color, highlightbackground=text_color, highlightthickness=1)
        container.pack(fill=tk.BOTH, expand=True)

        if title_text:
            title_label = tk.Label(container, text=title_text, background=bg_color, fg=text_color,
                                   font=(font_style[0], font_style[1]+1, "bold"), justify=tk.LEFT, anchor="w")
            title_label.pack(padx=10, pady=(5, 0), fill=tk.X)
            separator = tk.Frame(container, height=1, bg=text_color, bd=0)
            separator.pack(fill=tk.X, padx=10, pady=(2,5))

        msg_label = tk.Label(container, text=message_content, background=bg_color, fg=text_color,
                             wraplength=350, justify=tk.LEFT, font=font_style, anchor="w")
        msg_label.pack(padx=10, pady=(0 if title_text else 5, 10), fill=tk.X)

        self.update_idletasks()
        width = self.winfo_width()
        screen_width = self.winfo_screenwidth()
        x_pos = screen_width - width - TOOLTIP_X_OFFSET_FROM_RIGHT
        self.geometry(f"+{int(x_pos)}+{int(position_y)}")

    def close_tooltip(self):
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

def _configure_tk_root(root_window):
    global _tk_root_ref
    _tk_root_ref = root_window

def _show_all_queued_messages_now():
    global _tk_root_ref, current_tooltip_instance
    if not _tk_root_ref or not _tk_root_ref.winfo_exists() or not threading.current_thread() is threading.main_thread():
        return

    last_message_data = None
    processed_any_item_from_queue = False
    try:
        while not message_queue.empty():
            last_message_data = message_queue.get_nowait()
            processed_any_item_from_queue = True

        if last_message_data:
            title, msg_text, msg_type = last_message_data
            if current_tooltip_instance and current_tooltip_instance.winfo_exists():
                current_tooltip_instance.close_tooltip()
                current_tooltip_instance = None

            full_message = f"{title.upper()}:\n{msg_text}" if title and title.lower() not in ["thông báo", "info", "message"] else msg_text
            if title and title.lower() in ["thông báo", "info", "message"] and not msg_text.startswith(title.upper()):
                full_message = msg_text

            new_tooltip = CustomToolTip(_tk_root_ref, full_message,
                                        position_y=TOOLTIP_Y_OFFSET, msg_type=msg_type)
            current_tooltip_instance = new_tooltip
    except queue.Empty:
        pass
    except Exception as e_queue:
        print(f"Lỗi không mong muốn khi xử lý message queue cho tooltip: {e_queue}")

    if processed_any_item_from_queue and _tk_root_ref and _tk_root_ref.winfo_exists():
        try:
            _tk_root_ref.update_idletasks()
        except tk.TclError as e_update:
            print(f"Lỗi khi cập nhật Tkinter root: {e_update}")

def show_message(message_text, title="Thông báo", type="info", log_to_console=True):
    if log_to_console:
        print(f"[{title.upper() if title else 'MESSAGE'}] ({type}) {message_text}")

    message_queue.put((title, message_text, type))
    if _tk_root_ref and threading.current_thread() is threading.main_thread():
        if _tk_root_ref.winfo_exists():
            _tk_root_ref.after(0, _show_all_queued_messages_now)

# This function is kept for potential future use with other dynamically selected positions.
# It is NOT used for 'Chanh City', 'Vào ngay!', 'Đóng' in the current setup.
def on_click_for_selection(x, y, button, pressed):
    global current_selection_key, selecting_position_active, temp_mouse_listener
    if selecting_position_active and pressed and button == mouse.Button.left:
        positions[current_selection_key] = (int(x), int(y))
        print(f"INFO: Đã ghi nhớ vị trí '{current_selection_key}': ({int(x)}, {int(y)}) (không hiển thị pop-up)")
        if temp_mouse_listener:
            return False
    return True

# This function is kept for potential future use with other dynamically selected positions.
# It is NOT called by select_all_positions for the hardcoded items.
def get_single_position(key_name):
    global current_selection_key, selecting_position_active, temp_mouse_listener, app_exit_event
    current_selection_key = key_name
    selecting_position_active = True

    show_message(f"CLICK CHUỘT TRÁI để chọn vị trí '{key_name}'.", title="Yêu Cầu Chọn Vị Trí", type="info")

    click_captured_event = threading.Event()

    def local_on_click(x,y,button,pressed):
        if selecting_position_active and current_selection_key == key_name and pressed and button == mouse.Button.left:
            positions[key_name] = (int(x), int(y))
            print(f"INFO (local_on_click): Đã ghi nhớ vị trí '{key_name}': ({int(x)}, {int(y)})")
            click_captured_event.set()
            return False
        return True

    with mouse.Listener(on_click=local_on_click) as m_listener:
        temp_mouse_listener = m_listener
        print(f"INFO: Mouse listener cho '{key_name}' đã bắt đầu.")
        while not click_captured_event.is_set() and not app_exit_event.is_set():
            if _tk_root_ref and _tk_root_ref.winfo_exists():
                _tk_root_ref.update_idletasks()
                _tk_root_ref.update()

            if not m_listener.is_alive() and not click_captured_event.is_set():
                print(f"CẢNH BÁO: Mouse listener cho '{key_name}' đã dừng ngoài ý muốn trước khi click được ghi nhận.")
                break
            time.sleep(0.02)

    print(f"INFO: Mouse listener cho '{key_name}' đã kết thúc. Click captured: {click_captured_event.is_set()}")
    selecting_position_active = False
    temp_mouse_listener = None

    if not click_captured_event.is_set() and not app_exit_event.is_set():
        if positions[key_name] is None:
            show_message(f"Chưa chọn vị trí cho '{key_name}'.", title="Cảnh Báo", type="warning")
            return False
    elif positions[key_name] is None and not app_exit_event.is_set():
        show_message(f"Lỗi không ghi được vị trí cho '{key_name}' dù đã click.", title="Lỗi", type="error")
        return False

    return positions[key_name] is not None or app_exit_event.is_set()

# MODIFIED: This function now confirms hardcoded positions
def select_all_positions():
    global positions # Ensure using the global dictionary with hardcoded values

    if app_exit_event.is_set(): # Check for early exit request
        return False

    # Announce the use of hardcoded positions
    initial_message = (
        "Các vị trí được thiết lập cố định như sau:\n"
        f"- Chanh City: {positions.get('Chanh City')}\n"
        f"- Vào ngay!: {positions.get('Vào ngay!')}\n"
        f"- Đóng: {positions.get('Đóng')}"
    )
    show_message(initial_message, title="Thông Tin Thiết Lập", type="info")

    # Verify that all required positions are indeed set (they should be due to hardcoding)
    required_keys = ['Chanh City', 'Vào ngay!', 'Đóng']
    all_set_correctly = True
    for key in required_keys:
        if positions.get(key) is None:
            show_message(f"Lỗi: Vị trí cố định cho '{key}' không được tìm thấy trong cấu hình.",
                         title="Lỗi Cấu Hình", type="error")
            all_set_correctly = False
            break # Exit loop if a key is missing
        else:
            # Show success message for each hardcoded position
            show_message(f"Đã xác nhận vị trí '{key}': {positions[key]}", title="Xác Nhận Vị Trí", type="success")

    if not all_set_correctly:
        show_message("Một hoặc nhiều vị trí cố định thiết yếu bị thiếu hoặc lỗi. Không thể tiếp tục.", title="Lỗi Cấu Hình Trọng Yếu", type="error")
        return False

    if app_exit_event.is_set(): # Re-check for exit request during message displays
        return False

    show_message("Các vị trí cố định đã được xác nhận. Sẵn sàng!", title="Hoàn Tất Cài Đặt", type="success")
    return True


def pausable_wait(duration_seconds, countdown_prefix_message=None, countdown_title="Đếm Ngược"):
    end_time = time.time() + duration_seconds
    last_displayed_remaining_seconds = -1

    if countdown_prefix_message:
        initial_remaining = int(round(duration_seconds))
        if initial_remaining < 0: initial_remaining = 0
        show_message(f"{countdown_prefix_message}... còn {initial_remaining} giây",
                       title=countdown_title,
                       type="info",
                       log_to_console=False) # Countdown messages are tooltip-only
        last_displayed_remaining_seconds = initial_remaining

    while time.time() < end_time:
        if app_exit_event.is_set():
            return False
        if not running: # Allows pausing during the wait
            # If paused, we effectively stop the countdown and return False,
            # indicating the wait was not completed as 'running'.
            # The calling function should handle this state.
            # For a true pausable wait that resumes, more complex state management is needed.
            # This implementation prioritizes aborting the wait if not 'running'.
            return False # Or, if you want it to just freeze here, you'd loop on 'running' state.

        current_time = time.time()
        if countdown_prefix_message:
            remaining_seconds = int(round(end_time - current_time))
            if remaining_seconds < 0:
                remaining_seconds = 0

            if remaining_seconds != last_displayed_remaining_seconds:
                full_countdown_msg = f"{countdown_prefix_message}... còn {remaining_seconds} giây"
                show_message(full_countdown_msg,
                             title=countdown_title,
                             type="info",
                             log_to_console=False) # Countdown messages are tooltip-only
                last_displayed_remaining_seconds = remaining_seconds

        time.sleep(0.02)

    if app_exit_event.is_set() or not running: # Check again after loop
        return False

    if countdown_prefix_message and last_displayed_remaining_seconds != 0:
       show_message(f"{countdown_prefix_message}... còn 0 giây",
                    title=countdown_title,
                    type="info",
                    log_to_console=False) # Countdown messages are tooltip-only

    return True


def click_automation_loop():
    global running, app_exit_event, positions
    current_action_message = ""

    while not app_exit_event.is_set():
        if running:
            if not all(p is not None for p in positions.values()): # Should be true with hardcoded values
                show_message("Một hoặc nhiều vị trí chưa được thiết lập. Tự động tạm dừng.", title="Lỗi Vị Trí", type="warning")
                running = False
                time.sleep(0.02)
                continue

            # 1. Click chuột vào vị trí 'Chanh City'
            current_action_message = "thực hiện click 'Chanh City'"
            if not running or app_exit_event.is_set(): break

            point_key = 'Chanh City'
            if positions[point_key] is None: # Should not happen with hardcoding
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue

            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break # Short delay before click
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # -- Chờ 1 giây sau khi click 'Chanh City' --
            current_action_message = "chờ 1 giây sau khi click 'Chanh City'"
            if not running or app_exit_event.is_set(): break
            wait_msg_1 = f"Đang {current_action_message}..."
            print(f"INFO: {wait_msg_1}")
            show_message(wait_msg_1, title="Thông Tin Chu Trình", type="info")
            if not pausable_wait(1.0): break

            # 2. Click chuột vào vị trí 'Vào ngay!'
            current_action_message = "thực hiện click 'Vào ngay!'"
            if not running or app_exit_event.is_set(): break

            point_key = 'Vào ngay!'
            if positions[point_key] is None: # Should not happen
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue

            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # 3. Chờ 10 giây
            current_action_message = "chờ 10 giây trước khi click 'Đóng'"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...")
            if not pausable_wait(10.0,
                                 countdown_prefix_message=f"Đang {current_action_message}",
                                 countdown_title="Đếm Ngược Chu Trình"): break

            # 4. Click chuột vào vị trí 'Đóng'
            current_action_message = "thực hiện click 'Đóng'"
            if not running or app_exit_event.is_set(): break

            point_key = 'Đóng'
            if positions[point_key] is None: # Should not happen
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue

            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # 5. Chờ 40 giây
            current_action_message = "chờ 40 giây trước khi bắt đầu lại chu trình"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...")
            if not pausable_wait(40.0,
                                 countdown_prefix_message=f"Đang {current_action_message}",
                                 countdown_title="Đếm Ngược Chu Trình"): break

            print("INFO: Hoàn tất một chu trình, chuẩn bị lặp lại.")

        else:
            if app_exit_event.wait(timeout=0.1):
                break

    if app_exit_event.is_set():
        print(f"INFO: Luồng click đã nhận tín hiệu thoát (có thể trong khi {current_action_message}).")
    elif not running:
        print(f"INFO: Luồng click đã được tạm dừng (có thể trong khi {current_action_message}) và sau đó kết thúc.")

    print("INFO: Luồng tự động click đã kết thúc (đã thoát khỏi vòng lặp chính).")


def on_key_press(key):
    global running, SETUP_COMPLETE, app_exit_event

    if key == keyboard.Key.page_down:
        print("INFO: Nhấn Page Down, chuẩn bị thoát.")
        show_message("Đang thoát chương trình...", title="Thông Báo Thoát", type="info")
        app_exit_event.set()
        running = False
        return False

    if not SETUP_COMPLETE:
        # Prevent starting if setup (even if just confirmation of hardcoded values) is not done
        if key == keyboard.Key.page_up:
             show_message("Chương trình đang trong quá trình thiết lập ban đầu. Vui lòng đợi.", title="Thông Báo", type="info")
        return True

    if key == keyboard.Key.page_up:
        # This check is technically redundant if select_all_positions ensures all are set
        # and SETUP_COMPLETE is only true after that. But as a safeguard:
        if not all(positions.get(k) is not None for k in ['Chanh City', 'Vào ngay!', 'Đóng']):
            show_message("Vui lòng đảm bảo các vị trí cố định đã được xác nhận (Chanh City, Vào ngay!, Đóng) trước khi bắt đầu!", title="Lỗi", type="warning")
            return True
        running = not running
        if running:
            show_message("BẮT ĐẦU chu trình click tự động.\nNhấn PAGE UP để TẠM DỪNG, PAGE DOWN để THOÁT.", title="Trạng Thái", type="success")
        else:
            show_message("TẠM DỪNG chu trình click tự động.\nNhấn PAGE UP để TIẾP TỤC, PAGE DOWN để THOÁT.", title="Trạng Thái", type="info") # Changed TẠM DỪNG to TIẾP TỤC for clarity
    return True

def main():
    global SETUP_COMPLETE, _tk_root_ref, app_exit_event, positions, current_tooltip_instance

    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)) # Per Monitor Aware V2
            print("INFO: Windows DPI Awareness set to Per Monitor Aware V2.")
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per Monitor Aware
                print("INFO: Windows DPI Awareness set to Per Monitor Aware.")
            except (AttributeError, OSError):
                try:
                    ctypes.windll.user32.SetProcessDPIAware() # System Aware
                    print("INFO: Windows DPI Awareness set to System Aware.")
                except (AttributeError, OSError):
                    print("WARNING: Could not set DPI awareness. Mouse positions might be incorrect on scaled displays.")

    keyboard_l = None
    try:
        keyboard_l = keyboard.Listener(on_press=on_key_press, daemon=True)
        print("INFO: Khởi tạo Listener bàn phím...")
        keyboard_l.start()
        print("INFO: Listener bàn phím đã được start().")
    except Exception as e_kl_start:
        print(f"LỖI NGHIÊM TRỌNG: Không thể khởi tạo listener bàn phím: {e_kl_start}")
        temp_root_for_error = tk.Tk()
        temp_root_for_error.withdraw()
        _configure_tk_root(temp_root_for_error) # Configure root for show_message
        show_message(f"Lỗi listener bàn phím: {e_kl_start}. Chương trình sẽ thoát.", title="Lỗi Nghiêm Trọng", type="error")
        if _tk_root_ref:
            start_time = time.time()
            while time.time() - start_time < (TOOLTIP_ERROR_DURATION / 1000 + 0.2) and _tk_root_ref.winfo_exists():
                _tk_root_ref.update(); time.sleep(0.01)
            if _tk_root_ref and _tk_root_ref.winfo_exists(): _tk_root_ref.destroy()
        return

    root = tk.Tk()
    root.withdraw()
    _configure_tk_root(root) # Main Tk root for tooltips

    def periodic_queue_check():
        if not app_exit_event.is_set() and _tk_root_ref and _tk_root_ref.winfo_exists():
            _show_all_queued_messages_now()
            _tk_root_ref.after(200, periodic_queue_check) # Check queue every 200ms

    if _tk_root_ref: _tk_root_ref.after(100, periodic_queue_check) # Start periodic check

    automation_thread = None
    try:
        print("-----------------------------------------------------------")
        current_os = platform.system()
        os_message = f"CHƯƠNG TRÌNH AUTO CLICKER (Hệ điều hành: {current_os})"
        if current_os == "Darwin": # macOS
            os_message = "AUTO CLICKER CHO MACOS\nLƯU Ý: Cần cấp quyền 'Input Monitoring' cho Terminal/App."
        elif current_os == "Windows":
            os_message = "CHƯƠNG TRÌNH AUTO CLICKER CHO WINDOWS"
        print(os_message.replace("\n", "\nINFO: "))
        show_message(os_message, title="Thông Tin Hệ Thống", type="info")
        print("-----------------------------------------------------------")

        if not select_all_positions(): # This will now confirm hardcoded positions
            if not app_exit_event.is_set(): # If not already exiting due to PageDown during setup
                show_message("Không thể xác nhận các vị trí cố định. Thoát.", title="Lỗi Khởi Tạo", type="error")
            # Ensure error tooltip is visible
            if _tk_root_ref and _tk_root_ref.winfo_exists():
                start_time = time.time()
                # Wait for the longest possible tooltip duration + a bit
                while time.time() - start_time < (max(TOOLTIP_DEFAULT_DURATION, TOOLTIP_ERROR_DURATION) / 1000 + 0.2) and _tk_root_ref.winfo_exists():
                    _tk_root_ref.update(); time.sleep(0.01)
                if _tk_root_ref and _tk_root_ref.winfo_exists(): _tk_root_ref.destroy()
            return

        if app_exit_event.is_set(): # User might press PageDown during select_all_positions' messages
            print("INFO: Thoát theo yêu cầu (PageDown) trong quá trình xác nhận vị trí.")
            # Message already shown by on_key_press for PageDown.
            # Allow finally block to clean up.
            return

        SETUP_COMPLETE = True
        print("INFO: Cài đặt (xác nhận vị trí cố định) hoàn tất! Listener bàn phím giờ sẽ xử lý các lệnh chính.")
        show_message("Nhấn PAGE UP để BẮT ĐẦU/TẠM DỪNG.\nNhấn PAGE DOWN để THOÁT.", title="Điều Khiển", type="info")

        automation_thread = threading.Thread(target=click_automation_loop, daemon=True)
        automation_thread.start()

        print("INFO: Luồng chính đang chạy vòng lặp Tkinter và chờ sự kiện thoát...")
        while not app_exit_event.is_set():
            if _tk_root_ref and _tk_root_ref.winfo_exists():
                _tk_root_ref.update_idletasks()
                _tk_root_ref.update()
            else: # Tk root window closed unexpectedly
                if not app_exit_event.is_set(): # If not already exiting
                    print("WARN: Cửa sổ Tkinter root đã đóng bất ngờ. Thoát chương trình.")
                    app_exit_event.set() # Trigger exit for other threads
                break
            time.sleep(0.02) # Reduce CPU usage

    finally:
        print("INFO: Chương trình đang trong quá trình thoát (finally block)...")
        if not app_exit_event.is_set(): app_exit_event.set() # Ensure exit event is set

        if keyboard_l and keyboard_l.is_alive():
            print("INFO: Đang dừng Listener bàn phím...")
            keyboard_l.stop()
            # keyboard_l.join() # Consider joining if it's not a daemon or if issues occur

        if automation_thread and automation_thread.is_alive():
            print("INFO: Đang đợi luồng tự động click kết thúc...")
            automation_thread.join(timeout=2.0) # Wait for 2 seconds
            if automation_thread.is_alive(): print("CẢNH BÁO: Luồng tự động click không kết thúc kịp thời.")

        # Close any existing tooltip from the main thread
        if current_tooltip_instance and current_tooltip_instance.winfo_exists() and \
           _tk_root_ref and _tk_root_ref.winfo_exists() and \
           threading.current_thread() is threading.main_thread():
            current_tooltip_instance.close_tooltip()
            current_tooltip_instance = None
            if _tk_root_ref.winfo_exists(): # Update to reflect tooltip closure
                _tk_root_ref.update()

        final_message_duration_ms = 1000 # Show final message for 1 second

        if _tk_root_ref and _tk_root_ref.winfo_exists():
            def show_final_message_on_main_thread():
                # This final message will log to console by default
                show_message("Chương trình đang thoát. Tạm biệt!", title="Kết Thúc", type="info")

            if threading.current_thread() is not threading.main_thread():
                if _tk_root_ref.winfo_exists():
                    _tk_root_ref.after(0, show_final_message_on_main_thread)
            else: # Already on main thread
                show_final_message_on_main_thread()

            start_time_final_msg = time.time()
            # Process remaining messages and keep UI responsive for a short while
            while time.time() - start_time_final_msg < (final_message_duration_ms / 1000.0):
                if _tk_root_ref and _tk_root_ref.winfo_exists():
                    # Ensure all queued messages are processed by the main thread
                    if not message_queue.empty() and threading.current_thread() is threading.main_thread():
                         _tk_root_ref.after(0, _show_all_queued_messages_now) # Schedule if on main thread

                    _tk_root_ref.update_idletasks()
                    _tk_root_ref.update()
                else: # Root window gone
                    break
                time.sleep(0.01)
        else: # Fallback if Tk root is already gone
             print("INFO: [KẾT THÚC] (info) Chương trình đang thoát. Tạm biệt!")


        if _tk_root_ref and _tk_root_ref.winfo_exists():
            try:
                print("INFO: Đang hủy cửa sổ root Tkinter...")
                _tk_root_ref.destroy()
                print("INFO: Cửa sổ root Tkinter đã được hủy.")
            except tk.TclError as e_destroy:
                print(f"LỖI NHẸ: Lỗi khi hủy cửa sổ root Tkinter: {e_destroy}")
        _tk_root_ref = None # Clear reference
        print("INFO: Hoàn tất quá trình thoát chương trình (console).")

if __name__ == "__main__":
    try:
        _ = mouse.Controller() # Check if pynput.mouse can be initialized
        _ = keyboard.Key.page_up # Check if pynput.keyboard can be accessed
    except NameError: # pynput might not be imported correctly if this happens earlier
        print(f"LỖI CRITICAL: Pynput library không được tìm thấy hoặc không thể sử dụng.")
        input("Nhấn Enter để thoát.")
        exit(1)
    except Exception as e_pynput_init: # Catch other pynput init errors (e.g., display server issues on Linux)
        print(f"LỖI CRITICAL khi khởi tạo pynput: {e_pynput_init}")
        print("Đảm bảo bạn có môi trường đồ họa phù hợp (ví dụ: X server trên Linux).")
        input("Nhấn Enter để thoát.")
        exit(1)
    main()