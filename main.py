import time
import threading
import platform
import ctypes
import tkinter as tk
from pynput import mouse, keyboard
import queue

# --- Biến toàn cục ---
positions = {'Chanh City': None, 'Vào ngay!': None, 'ĐÓNG': None}
running = False
app_exit_event = threading.Event()
mouse_controller = mouse.Controller()
current_selection_key = None
selecting_position_active = False
temp_mouse_listener = None

message_queue = queue.Queue()
_tk_root_ref = None
SETUP_COMPLETE = False

# --- Cấu hình Tooltip ---
current_tooltip_instance = None # Chỉ một tooltip được hiển thị tại một thời điểm
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


# --- Hàm _configure_tk_root ---
def _configure_tk_root(root_window):
    global _tk_root_ref
    _tk_root_ref = root_window

# --- Hàm _show_all_queued_messages_now ---
def _show_all_queued_messages_now():
    global _tk_root_ref, current_tooltip_instance
    if not _tk_root_ref or not _tk_root_ref.winfo_exists() or not threading.current_thread() is threading.main_thread():
        return

    last_message_data = None
    processed_any_item_from_queue = False
    try:
        # Lấy thông báo mới nhất từ queue (nếu có nhiều)
        while not message_queue.empty():
            last_message_data = message_queue.get_nowait()
            processed_any_item_from_queue = True

        if last_message_data:
            title, msg_text, msg_type = last_message_data

            # Nếu có tooltip cũ đang hiển thị, hủy nó đi
            if current_tooltip_instance and current_tooltip_instance.winfo_exists():
                current_tooltip_instance.close_tooltip()
                current_tooltip_instance = None

            # Tạo và hiển thị tooltip mới
            full_message = f"{title.upper()}:\n{msg_text}" if title and title.lower() not in ["thông báo", "info", "message"] else msg_text
            if title and title.lower() in ["thông báo", "info", "message"] and not msg_text.startswith(title.upper()):
                full_message = msg_text
            
            # Tooltip mới luôn ở vị trí Y cố định trên cùng
            new_tooltip = CustomToolTip(_tk_root_ref, full_message,
                                        position_y=TOOLTIP_Y_OFFSET, msg_type=msg_type)
            current_tooltip_instance = new_tooltip
            # Không cần gọi _reposition_remaining_tooltips

    except queue.Empty: # Điều này không nên xảy ra nếu vòng lặp while ở trên chạy đúng
        pass
    except Exception as e_queue:
        print(f"Lỗi không mong muốn khi xử lý message queue cho tooltip: {e_queue}")

    if processed_any_item_from_queue and _tk_root_ref and _tk_root_ref.winfo_exists():
        try:
            _tk_root_ref.update_idletasks()
        except tk.TclError as e_update:
            print(f"Lỗi khi cập nhật Tkinter root: {e_update}")

# --- Hàm show_message ---
def show_message(message_text, title="Thông báo", type="info"):
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
        # selecting_position_active = False # Sẽ được set bởi get_single_position
        if temp_mouse_listener: # Dừng listener chuột hiện tại
            # temp_mouse_listener.stop() # Cách này có thể gây lỗi nếu listener đã tự dừng
            return False # Trả về False để dừng listener từ callback
    return True

def get_single_position(key_name):
    global current_selection_key, selecting_position_active, temp_mouse_listener, app_exit_event
    current_selection_key = key_name
    selecting_position_active = True # Báo hiệu đang trong quá trình chọn vị trí

    show_message(f"CLICK CHUỘT TRÁI để chọn vị trí '{key_name}'.", title="Yêu Cầu Chọn Vị Trí", type="info")
    
    click_captured_event = threading.Event()

    # local_on_click phải được định nghĩa lại hoặc làm cho nó nhận biết được context hiện tại
    # để tránh xung đột nếu get_single_position được gọi nhiều lần.
    # Vì nó là nested function, nó sẽ tạo ra một closure mới mỗi lần get_single_position được gọi.

    def local_on_click(x,y,button,pressed):
        # Callback này sẽ chỉ hoạt động cho key_name hiện tại của get_single_position
        if selecting_position_active and current_selection_key == key_name and pressed and button == mouse.Button.left:
            positions[key_name] = (int(x), int(y)) # Ghi nhận vị trí cho key_name hiện tại
            print(f"INFO (local_on_click): Đã ghi nhớ vị trí '{key_name}': ({int(x)}, {int(y)})")
            click_captured_event.set()
            return False # Dừng listener này
        return True


    with mouse.Listener(on_click=local_on_click) as m_listener:
        temp_mouse_listener = m_listener
        print(f"INFO: Mouse listener cho '{key_name}' đã bắt đầu.")
        while not click_captured_event.is_set() and not app_exit_event.is_set():
            if _tk_root_ref and _tk_root_ref.winfo_exists():
                _tk_root_ref.update_idletasks()
                _tk_root_ref.update()
            
            # Kiểm tra xem listener có còn chạy không
            if not m_listener.is_alive() and not click_captured_event.is_set():
                print(f"CẢNH BÁO: Mouse listener cho '{key_name}' đã dừng ngoài ý muốn trước khi click được ghi nhận.")
                break # Thoát vòng lặp chờ nếu listener chết
            time.sleep(0.02) # sleep để giảm tải CPU và cho Tkinter xử lý

    print(f"INFO: Mouse listener cho '{key_name}' đã kết thúc. Click captured: {click_captured_event.is_set()}")
    selecting_position_active = False # Đặt lại trạng thái sau khi hoàn tất
    temp_mouse_listener = None # Xóa tham chiếu

    if not click_captured_event.is_set() and not app_exit_event.is_set():
        if positions[key_name] is None: # Nếu không có click và vị trí vẫn là None
            show_message(f"Chưa chọn vị trí cho '{key_name}'.", title="Cảnh Báo", type="warning")
            return False
    elif positions[key_name] is None and not app_exit_event.is_set(): # Nếu click_captured_event được set nhưng vị trí lại là None (hiếm)
        show_message(f"Lỗi không ghi được vị trí cho '{key_name}' dù đã click.", title="Lỗi", type="error")
        return False
        
    return positions[key_name] is not None or app_exit_event.is_set()


def select_all_positions():
    show_message("Xác định 3 vị trí: Chanh City, Vào ngay!, và ĐÓNG.", title="Hướng Dẫn Thiết Lập", type="info")

    if not get_single_position('Chanh City'): return False
    if app_exit_event.is_set(): return False
    if positions['Chanh City']: show_message(f"Đã chọn 'Chanh City': {positions['Chanh City']}", title="Thông Tin", type="success")

    if not get_single_position('Vào ngay!'): return False
    if app_exit_event.is_set(): return False
    if positions['Vào ngay!']: show_message(f"Đã chọn 'Vào ngay!': {positions['Vào ngay!']}", title="Thông Tin", type="success")

    if not get_single_position('ĐÓNG'): return False
    if app_exit_event.is_set(): return False
    if positions['ĐÓNG']: show_message(f"Đã chọn 'ĐÓNG': {positions['ĐÓNG']}", title="Thông Tin", type="success")
    
    show_message("Đã chọn đủ 3 vị trí. Sẵn sàng!", title="Hoàn Tất Cài Đặt", type="success")
    return True

def click_automation_loop():
    global running, app_exit_event, positions

    # Hàm tiện ích để chờ có thể tạm dừng hoặc thoát
    def pausable_wait(duration_seconds):
        # 'running' và 'app_exit_event' được truy cập từ scope của click_automation_loop (global)
        end_time = time.time() + duration_seconds
        while time.time() < end_time:
            if app_exit_event.is_set():  # Kiểm tra sự kiện thoát chương trình
                return False  # Bị ngắt bởi sự kiện thoát
            if not running:  # Kiểm tra trạng thái chạy/tạm dừng
                return False  # Bị ngắt bởi lệnh tạm dừng (Page Up)
            time.sleep(0.02)  # Kiểm tra định kỳ (ví dụ: 50 lần/giây)
        
        # Kiểm tra lần cuối sau khi hết thời gian, phòng trường hợp sự kiện xảy ra đúng lúc kết thúc
        if app_exit_event.is_set() or not running:
            return False
        return True  # Hoàn thành thời gian chờ bình thường

    current_action_message = "" # Dùng để ghi log nếu vòng lặp bị ngắt

    while not app_exit_event.is_set():
        if running:
            # Kiểm tra lại tất cả các vị trí trước mỗi chu trình
            if not all(p is not None for p in positions.values()):
                show_message("Một hoặc nhiều vị trí chưa được thiết lập. Tự động tạm dừng.", title="Lỗi Vị Trí", type="warning")
                running = False
                time.sleep(0.02) # Cho phép xử lý ngắn cho các thread/event khác
                continue # Quay lại đầu vòng lặp while, sẽ vào nhánh 'else' do running = False

            # 1. Click chuột vào vị trí 'Chanh City'
            current_action_message = "thực hiện click 'Chanh City'"
            if not running or app_exit_event.is_set(): break # Thoát nếu đang không chạy hoặc có lệnh thoát
            
            point_key = 'Chanh City'
            if positions[point_key] is None:
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue # Tạm dừng và kiểm tra lại ở vòng lặp tiếp theo
            
            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break # Chờ rất ngắn/kiểm tra thoát/tạm dừng trước khi click
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # -- Chờ 1 giây sau khi click 'Chanh City' --
            current_action_message = "chờ 1 giây sau khi click 'Chanh City'"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...")
            if not pausable_wait(1.0): break # Nếu pausable_wait trả về False (bị ngắt), thoát vòng lặp

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

            # 3. Chờ 10 giây
            current_action_message = "chờ 10 giây trước khi click 'ĐÓNG'"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...")
            if not pausable_wait(10.0): break 

            # 4. Click chuột vào vị trí 'ĐÓNG'
            current_action_message = "thực hiện click 'ĐÓNG'"
            if not running or app_exit_event.is_set(): break

            point_key = 'ĐÓNG'
            if positions[point_key] is None:
                show_message(f"Lỗi: Vị trí '{point_key}' không hợp lệ. Tạm dừng.", title="Lỗi Vị Trí", type="error")
                running = False; continue
            
            x, y = positions[point_key]
            mouse_controller.position = (x, y)
            if not pausable_wait(0.05): break
            mouse_controller.click(mouse.Button.left, 1)
            print(f"ACTION: Đã click '{point_key}' tại ({x}, {y})")

            # 5. Chờ 20 giây trước khi quay trở lại thực hiện bước tiếp theo (lặp lại chu trình)
            current_action_message = "chờ 20 giây trước khi bắt đầu lại chu trình"
            if not running or app_exit_event.is_set(): break
            print(f"INFO: Đang {current_action_message}...")
            if not pausable_wait(20.0): break
            
            print("INFO: Hoàn tất một chu trình, chuẩn bị lặp lại.")

        else: # Nếu running là False (đang tạm dừng)
            # Trong khi tạm dừng, vẫn kiểm tra thường xuyên sự kiện thoát chương trình
            if app_exit_event.wait(timeout=0.1): # Chờ với timeout ngắn
                break # Thoát vòng lặp chính nếu có sự kiện thoát
    
    # Các dòng print này sẽ được thực thi khi vòng lặp `while not app_exit_event.is_set():` kết thúc
    if app_exit_event.is_set():
        print(f"INFO: Luồng click đã nhận tín hiệu thoát (có thể trong khi {current_action_message}).")
    elif not running: # Nếu vòng lặp dừng do 'running' thành False (tạm dừng và sau đó thoát)
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
        return True

    if key == keyboard.Key.page_up:
        if not all(p is not None for p in positions.values()):
            show_message("Vui lòng hoàn tất việc chọn vị trí (Chanh City, Vào ngay!, ĐÓNG) trước khi bắt đầu!", title="Lỗi", type="warning")
            return True
        running = not running
        if running:
            show_message("BẮT ĐẦU chu trình click tự động.\nNhấn PAGE UP để TẠM DỪNG, PAGE DOWN để THOÁT.", title="Trạng Thái", type="success")
        else:
            show_message("TẠM DỪNG chu trình click tự động.\nNhấn PAGE UP để TẠM DỪNG, PAGE DOWN để THOÁT.", title="Trạng Thái", type="info")
    return True

# --- Hàm chính của chương trình ---
def main():
    global SETUP_COMPLETE, _tk_root_ref, app_exit_event, positions, current_tooltip_instance # Thêm current_tooltip_instance

    # <<< XỬ LÝ DPI SCALING TRÊN WINDOWS >>>
    if platform.system() == "Windows":
        try:
            # Cố gắng đặt DPI Awareness cho mỗi Monitor V2 (Windows 10 1703+)
            # Giá trị -4 tương ứng với DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            ctypes.windll.shcore.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            print("INFO: Windows DPI Awareness set to Per Monitor Aware V2.")
        except (AttributeError, OSError): # AttributeError nếu shcore hoặc hàm không tồn tại, OSError nếu có lỗi gọi
            try:
                # Cố gắng đặt DPI Awareness cho mỗi Monitor (Windows 8.1+)
                # Giá trị 2 tương ứng với PROCESS_PER_MONITOR_DPI_AWARE
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                print("INFO: Windows DPI Awareness set to Per Monitor Aware.")
            except (AttributeError, OSError):
                try:
                    # Cố gắng đặt DPI Awareness cho toàn hệ thống (Windows Vista+)
                    ctypes.windll.user32.SetProcessDPIAware()
                    print("INFO: Windows DPI Awareness set to System Aware.")
                except (AttributeError, OSError):
                    print("WARNING: Could not set DPI awareness. Mouse positions might be incorrect on scaled displays.")
    # <<< KẾT THÚC XỬ LÝ DPI SCALING TRÊN WINDOWS >>>
    
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
            _tk_root_ref.destroy()
        return

    root = tk.Tk()
    root.withdraw()
    _configure_tk_root(root)

    def periodic_queue_check():
        if not app_exit_event.is_set() and _tk_root_ref and _tk_root_ref.winfo_exists():
            _show_all_queued_messages_now()
            _tk_root_ref.after(200, periodic_queue_check) # Tần suất kiểm tra queue

    if _tk_root_ref: _tk_root_ref.after(100, periodic_queue_check)

    automation_thread = None
    try:
        print("-----------------------------------------------------------")
        current_os = platform.system()
        os_message = f"CHƯƠNG TRÌNH AUTO CLICKER (Hệ điều hành: {current_os})"
        if current_os == "Darwin":
            os_message = "AUTO CLICKER CHO MACOS\nLƯU Ý: Cần cấp quyền 'Input Monitoring' cho Terminal/App." # Ngắn gọn hơn
        elif current_os == "Windows":
            os_message = "CHƯƠNG TRÌNH AUTO CLICKER CHO WINDOWS"
        print(os_message.replace("\n", "\nINFO: "))
        show_message(os_message, title="Thông Tin Hệ Thống", type="info")
        print("-----------------------------------------------------------")

        if not select_all_positions():
            if not app_exit_event.is_set():
                show_message("Không thể thiết lập vị trí. Thoát.", title="Lỗi Khởi Tạo", type="error") # Ngắn gọn hơn
            if _tk_root_ref and _tk_root_ref.winfo_exists():
                 start_time = time.time()
                 while time.time() - start_time < (max(TOOLTIP_DEFAULT_DURATION, TOOLTIP_ERROR_DURATION) / 1000 + 0.2) and _tk_root_ref.winfo_exists():
                    _tk_root_ref.update(); time.sleep(0.01)
            return

        if app_exit_event.is_set():
            print("INFO: Thoát theo yêu cầu (PageDown) khi chọn vị trí.")
            return

        SETUP_COMPLETE = True
        print("INFO: Cài đặt hoàn tất! Listener bàn phím giờ sẽ xử lý các lệnh chính.")
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

        # Hủy tooltip hiện tại (nếu có) trước khi hiển thị thông báo cuối cùng
        if current_tooltip_instance and current_tooltip_instance.winfo_exists() and \
           _tk_root_ref and _tk_root_ref.winfo_exists() and \
           threading.current_thread() is threading.main_thread():
            current_tooltip_instance.close_tooltip()
            current_tooltip_instance = None
            if _tk_root_ref.winfo_exists(): # Kiểm tra lại trước khi update
                _tk_root_ref.update() # Xử lý việc hủy tooltip
        
        # Hiển thị thông báo cuối cùng. Nó sẽ là tooltip duy nhất.
        final_message_duration = 1000 
        if _tk_root_ref and _tk_root_ref.winfo_exists():
            # Đảm bảo show_message và xử lý queue chạy trên luồng chính
            def show_final_message_on_main_thread():
                show_message("Chương trình đang thoát. Tạm biệt!", title="Kết Thúc", type="info")

            if threading.current_thread() is not threading.main_thread():
                _tk_root_ref.after(0, show_final_message_on_main_thread)
            else:
                show_final_message_on_main_thread()
            
            # Chờ cho message cuối cùng được xử lý và hiển thị
            start_time = time.time()
            processed_final_message = False
            
            # Đảm bảo message cuối được xử lý (nếu chưa)
            # Cần gọi _show_all_queued_messages_now sau khi show_message được gọi
            # và trước vòng lặp chờ.
            if threading.current_thread() is threading.main_thread() and _tk_root_ref.winfo_exists():
                if not message_queue.empty(): # Chỉ gọi nếu có message
                    _tk_root_ref.after(0, _show_all_queued_messages_now) # Lên lịch xử lý sớm
                _tk_root_ref.update() # Cho cơ hội xử lý ngay

            # THAY ĐỔI: Vòng lặp chờ đúng final_message_duration (tính bằng giây)
            while time.time() - start_time < (final_message_duration / 1000.0): 
                if _tk_root_ref and _tk_root_ref.winfo_exists():
                    _tk_root_ref.update_idletasks()
                    _tk_root_ref.update()
                    # Xử lý message cuối nếu nó chưa được xử lý trong lần update() ngay trên
                    if not message_queue.empty() and not processed_final_message: 
                        _show_all_queued_messages_now()
                        processed_final_message = True
                else: break # Thoát nếu root không còn tồn tại
                time.sleep(0.01) # sleep để giảm tải CPU
        else:
             print("INFO: [KẾT THÚC] (info) Chương trình đang thoát. Tạm biệt!")

        if _tk_root_ref and _tk_root_ref.winfo_exists():
            try:
                print("INFO: Đang hủy cửa sổ root Tkinter...")
                _tk_root_ref.destroy()
                print("INFO: Cửa sổ root Tkinter đã được hủy.")
            except tk.TclError as e_destroy: print(f"LỖI NHẸ: Lỗi khi hủy cửa sổ root Tkinter: {e_destroy}")
        _tk_root_ref = None
        print("INFO: Hoàn tất quá trình thoát chương trình (console).")

if __name__ == "__main__":
    try: _ = mouse.Controller(); _ = keyboard.Key.page_up 
    except NameError: 
        print(f"LỖI CRITICAL: Không thể sử dụng pynput."); input("Nhấn Enter để thoát."); exit(1)
    except Exception as e_pynput_init:
        print(f"LỖI CRITICAL khi khởi tạo pynput: {e_pynput_init}"); input("Nhấn Enter để thoát."); exit(1)
    main()