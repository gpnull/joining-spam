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
    'Chanh City': (150, 550),
    'Vào ngay!': (150, 460),
    'Ok': (520, 690), # <<< BỔ SUNG VỊ TRÍ MỚI
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

def on_click_for_selection(x, y, button, pressed):
    global current_selection_key, selecting_position_active, temp_mouse_listener
    if selecting_position_active and pressed and button == mouse.Button.left:
        positions[current_selection_key] = (int(x), int(y))
        print(f"INFO: Đã ghi nhớ vị trí '{current_selection_key}': ({int(x)}, {int(y)}) (không hiển thị pop-up)")
        if temp_mouse_listener:
            return False
    return True

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

def select_all_positions():
    global positions

    if app_exit_event.is_set():
        return False

    initial_message = (
        "Các vị trí được thiết lập cố định như sau:\n"
        f"- Chanh City: {positions.get('Chanh City')}\n"
        f"- Vào ngay!: {positions.get('Vào ngay!')}\n"
        f"- Ok: {positions.get('Ok')}\n"
        f"- Đóng: {positions.get('Đóng')}"
    )
    show_message(initial_message, title="Thông Tin Thiết Lập", type="info")

    required_keys = ['Chanh City', 'Vào ngay!', 'Ok', 'Đóng']
    all_set_correctly = True
    for key in required_keys:
        if positions.get(key) is None:
            show_message(f"Lỗi: Vị trí cố định cho '{key}' không được tìm thấy trong cấu hình.",
                         title="Lỗi Cấu Hình", type="error")
            all_set_correctly = False
            break
        else:
            show_message(f"Đã xác nhận vị trí '{key}': {positions[key]}", title="Xác Nhận Vị Trí", type="success")

    if not all_set_correctly:
        show_message("Một hoặc nhiều vị trí cố định thiết yếu bị thiếu hoặc lỗi. Không thể tiếp tục.", title="Lỗi Cấu Hình Trọng Yếu", type="error")
        return False

    if app_exit_event.is_set():
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
            return False

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
            if not all(p is not None for p in positions.values()):
                show_message("Một hoặc nhiều vị trí chưa được thiết lập. Tự động tạm dừng.", title="Lỗi Vị Trí", type="warning")
                running = False
                time.sleep(0.02)
                continue

            # 1. Click chuột vào vị trí 'Chanh City'
            current_action_message = "thực hiện click 'Chanh City'"
            if not running or app_exit_event.is_set(): break

            point_key = 'Chanh City'
            if positions[point_key] is None:
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue

            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # -- Chờ 1 giây sau khi click 'Chanh City' --
            current_action_message = "chờ 1 giây sau khi click 'Chanh City'"
            if not running or app_exit_event.is_set(): break
            wait_msg_1 = f"Đang {current_action_message}..."
            print(f"INFO: {wait_msg_1}")
            show_message(wait_msg_1, title="Thông Tin Chu Trình", type="info") # Giữ lại thông báo này vì nó không phải là đếm ngược
            if not pausable_wait(1.0): break

            # 2. Click chuột vào vị trí 'Vào ngay!'
            current_action_message = "thực hiện click 'Vào ngay!'"
            if not running or app_exit_event.is_set(): break

            point_key = 'Vào ngay!'
            if positions[point_key] is None:
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue

            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # --- BỔ SUNG: Chờ 28 giây trước khi click 'Ok' ---
            current_action_message = "chờ 28 giây trước khi click 'Ok'"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...") # Giữ lại log console
            # Dòng show_message trước đó đã bị loại bỏ, pausable_wait sẽ hiển thị thông báo đếm ngược
            if not pausable_wait(28.0,
                                 countdown_prefix_message=f"Đang {current_action_message}",
                                 countdown_title="Đếm Ngược Chu Trình"): break
            # --- KẾT THÚC BỔ SUNG CHỜ ---

            # --- BỔ SUNG: Click chuột vào vị trí 'Ok' ---
            current_action_message = "thực hiện click 'Ok'"
            if not running or app_exit_event.is_set(): break

            point_key = 'Ok'
            if positions[point_key] is None: # Should not happen
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue

            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break # Short delay before click
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")
            # --- KẾT THÚC BỔ SUNG CLICK 'Ok' ---

            # 3. Chờ 1 giây (thời gian chờ này vẫn giữ nguyên sau click 'Ok')
            current_action_message = "chờ 1 giây trước khi click 'Đóng'"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...")
            if not pausable_wait(1.0,
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
        if key == keyboard.Key.page_up:
             show_message("Chương trình đang trong quá trình thiết lập ban đầu. Vui lòng đợi.", title="Thông Báo", type="info")
        return True

    if key == keyboard.Key.page_up:
        if not all(positions.get(k) is not None for k in ['Chanh City', 'Vào ngay!', 'Ok', 'Đóng']):
            show_message("Vui lòng đảm bảo các vị trí cố định đã được xác nhận (Chanh City, Vào ngay!, Ok, Đóng) trước khi bắt đầu!", title="Lỗi", type="warning")
            return True
        running = not running
        if running:
            show_message("BẮT ĐẦU chu trình click tự động.\nNhấn PAGE UP để TẠM DỪNG, PAGE DOWN để THOÁT.", title="Trạng Thái", type="success")
        else:
            show_message("TẠM DỪNG chu trình click tự động.\nNhấn PAGE UP để TIẾP TỤC, PAGE DOWN để THOÁT.", title="Trạng Thái", type="info")
    return True

def main():
    global SETUP_COMPLETE, _tk_root_ref, app_exit_event, positions, current_tooltip_instance

    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            print("INFO: Windows DPI Awareness set to Per Monitor Aware V2.")
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                print("INFO: Windows DPI Awareness set to Per Monitor Aware.")
            except (AttributeError, OSError):
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
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
        _configure_tk_root(temp_root_for_error)
        show_message(f"Lỗi listener bàn phím: {e_kl_start}. Chương trình sẽ thoát.", title="Lỗi Nghiêm Trọng", type="error")
        if _tk_root_ref:
            start_time = time.time()
            while time.time() - start_time < (TOOLTIP_ERROR_DURATION / 1000 + 0.2) and _tk_root_ref.winfo_exists():
                _tk_root_ref.update(); time.sleep(0.01)
            if _tk_root_ref and _tk_root_ref.winfo_exists(): _tk_root_ref.destroy()
        return

    root = tk.Tk()
    root.withdraw()
    _configure_tk_root(root)

    def periodic_queue_check():
        if not app_exit_event.is_set() and _tk_root_ref and _tk_root_ref.winfo_exists():
            _show_all_queued_messages_now()
            _tk_root_ref.after(200, periodic_queue_check)

    if _tk_root_ref: _tk_root_ref.after(100, periodic_queue_check)

    automation_thread = None
    try:
        print("-----------------------------------------------------------")
        current_os = platform.system()
        os_message = f"CHƯƠNG TRÌNH AUTO CLICKER (Hệ điều hành: {current_os})"
        if current_os == "Darwin":
            os_message = "AUTO CLICKER CHO MACOS\nLƯU Ý: Cần cấp quyền 'Input Monitoring' cho Terminal/App."
        elif current_os == "Windows":
            os_message = "CHƯƠNG TRÌNH AUTO CLICKER CHO WINDOWS"
        print(os_message.replace("\n", "\nINFO: "))
        show_message(os_message, title="Thông Tin Hệ Thống", type="info")
        print("-----------------------------------------------------------")

        if not select_all_positions():
            if not app_exit_event.is_set():
                show_message("Không thể xác nhận các vị trí cố định. Thoát.", title="Lỗi Khởi Tạo", type="error")
            if _tk_root_ref and _tk_root_ref.winfo_exists():
                start_time = time.time()
                while time.time() - start_time < (max(TOOLTIP_DEFAULT_DURATION, TOOLTIP_ERROR_DURATION) / 1000 + 0.2) and _tk_root_ref.winfo_exists():
                    _tk_root_ref.update(); time.sleep(0.01)
                if _tk_root_ref and _tk_root_ref.winfo_exists(): _tk_root_ref.destroy()
            return

        if app_exit_event.is_set():
            print("INFO: Thoát theo yêu cầu (PageDown) trong quá trình xác nhận vị trí.")
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
            else:
                if not app_exit_event.is_set():
                    print("WARN: Cửa sổ Tkinter root đã đóng bất ngờ. Thoát chương trình.")
                    app_exit_event.set()
                break
            time.sleep(0.02)

    finally:
        print("INFO: Chương trình đang trong quá trình thoát (finally block)...")
        if not app_exit_event.is_set(): app_exit_event.set()

        if keyboard_l and keyboard_l.is_alive():
            print("INFO: Đang dừng Listener bàn phím...")
            keyboard_l.stop()

        if automation_thread and automation_thread.is_alive():
            print("INFO: Đang đợi luồng tự động click kết thúc...")
            automation_thread.join(timeout=2.0)
            if automation_thread.is_alive(): print("CẢNH BÁO: Luồng tự động click không kết thúc kịp thời.")

        if current_tooltip_instance and current_tooltip_instance.winfo_exists() and \
           _tk_root_ref and _tk_root_ref.winfo_exists() and \
           threading.current_thread() is threading.main_thread():
            current_tooltip_instance.close_tooltip()
            current_tooltip_instance = None
            if _tk_root_ref.winfo_exists():
                _tk_root_ref.update()

        final_message_duration_ms = 1000

        if _tk_root_ref and _tk_root_ref.winfo_exists():
            def show_final_message_on_main_thread():
                show_message("Chương trình đang thoát. Tạm biệt!", title="Kết Thúc", type="info")

            if threading.current_thread() is not threading.main_thread():
                if _tk_root_ref.winfo_exists():
                    _tk_root_ref.after(0, show_final_message_on_main_thread)
            else:
                show_final_message_on_main_thread()

            start_time_final_msg = time.time()
            while time.time() - start_time_final_msg < (final_message_duration_ms / 1000.0):
                if _tk_root_ref and _tk_root_ref.winfo_exists():
                    if not message_queue.empty() and threading.current_thread() is threading.main_thread():
                         _tk_root_ref.after(0, _show_all_queued_messages_now)
                    _tk_root_ref.update_idletasks()
                    _tk_root_ref.update()
                else:
                    break
                time.sleep(0.01)
        else:
             print("INFO: [KẾT THÚC] (info) Chương trình đang thoát. Tạm biệt!")


        if _tk_root_ref and _tk_root_ref.winfo_exists():
            try:
                print("INFO: Đang hủy cửa sổ root Tkinter...")
                _tk_root_ref.destroy()
                print("INFO: Cửa sổ root Tkinter đã được hủy.")
            except tk.TclError as e_destroy:
                print(f"LỖI NHẸ: Lỗi khi hủy cửa sổ root Tkinter: {e_destroy}")
        _tk_root_ref = None
        print("INFO: Hoàn tất quá trình thoát chương trình (console).")

if __name__ == "__main__":
    try:
        _ = mouse.Controller()
        _ = keyboard.Key.page_up
    except NameError:
        print(f"LỖI CRITICAL: Pynput library không được tìm thấy hoặc không thể sử dụng.")
        input("Nhấn Enter để thoát.")
        exit(1)
    except Exception as e_pynput_init:
        print(f"LỖI CRITICAL khi khởi tạo pynput: {e_pynput_init}")
        print("Đảm bảo bạn có môi trường đồ họa phù hợp (ví dụ: X server trên Linux).")
        input("Nhấn Enter để thoát.")
        exit(1)
    main()