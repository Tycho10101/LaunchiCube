import io
import json
import math
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
import shutil
import threading
import time

from PIL import Image, ImageTk

import utils

LOGO_SIZE = (150, 150)
MAX_TEXT_WIDTH = 140

class Gui:
    def __init__(self, root):
        self.root = root
        self.root.title("LaunchiCube")
        self.root.geometry("1200x750")
        self.root.configure(bg="#2C2F33")
        self.game_threads = {}
        self.game_processes = {}
        self.game_stop_flags = {}

        self.load_accounts()
        
        self.resize_after_id = None

        try:
            self.launcher_icon = ImageTk.PhotoImage(Image.open("logo.png").resize(LOGO_SIZE, Image.Resampling.LANCZOS))
            self.root.iconphoto(True, self.launcher_icon)
        # pylint: disable-next=bare-except
        except:
            print("logo.png not found!")
            self.launcher_icon = None

        self.top_frame = tk.Frame(root, bg="#3C3F41", height=50)
        self.top_frame.pack(fill="x")

        tk.Button(self.top_frame, text="Add Instance", command=self.open_add_instance,
                  bg="#7289DA", fg="white", font=("Arial", 12, "bold")).pack(pady=10, padx=10, side="left")
        tk.Button(self.top_frame, text="Update", command=self.update,
                  bg="#7289DA", fg="white", font=("Arial", 12, "bold")).pack(pady=10, padx=10, side="left")

        self.right_frame = tk.Frame(root, bg="#3C3F41", width=250)
        self.right_frame.pack_propagate(False)
        self.right_frame.pack(fill="y", side="right")                                    

        self.main_frame = tk.Frame(root, bg="#23272A")
        self.main_frame.pack(expand=True, fill="both")
        self.main_frame.bind("<Configure>", self.on_resize)

        self.selected_instance = None
        self.load_instances()

        self.acc_switch_button = tk.Button(
            self.top_frame, text="Select an Option", command=self.show_menu,
            bg="#7289DA", fg="white", font=("Arial", 12, "bold")
        )
        self.acc_switch_button.pack(pady=10, padx=10, side="right")
        
        self.dropdown_window = None
        
        accounts_json = json.loads(utils.load_file("accounts.json"))
        if not accounts_json["Selected Account"] is None:
            self.select_option(accounts_json["Selected Account"])

    def truncate_text(self, text, font, max_width):
        temp_text = text
        test_label = tk.Label(self.root, text=temp_text, font=font)
        test_label.update_idletasks()
        
        while test_label.winfo_reqwidth() > max_width and len(temp_text) > 1:
            temp_text = temp_text[:-1]
            test_label.config(text=temp_text + "...")
            test_label.update_idletasks()

        return temp_text + "..." if temp_text != text else text

    def on_resize(self, event=None): # pylint: disable=unused-argument
        last_instances_columns = 1
        instances_columns = math.floor(self.main_frame.winfo_width()/195)
        if not instances_columns == last_instances_columns:
            if self.resize_after_id is not None:
                self.root.after_cancel(self.resize_after_id)
            self.resize_after_id = self.root.after(10, self.load_instances)
        last_instances_columns = instances_columns
        
    def update(self):
        linkbase = "https://raw.githubusercontent.com/Tycho10101/LaunchiCube/refs/heads/main/"
        utils.save_link_as_file(f"{linkbase}misc/installer_backend.py", "installer_backend.py")
        installer_backend = __import__('installer_backend')
        installer_backend.install()
        os.remove("installer_backend.py")
        subprocess.Popen([sys.executable, "main.py"]) # pylint: disable=consider-using-with
        sys.exit()

    def start_game_thread(self, instance):
        instance_key = instance["dir"]
        self.game_stop_flags[instance_key] = threading.Event()
        thread = threading.Thread(target=self.start_game, args=(instance, self.game_stop_flags[instance_key]))
        self.game_threads[instance_key] = thread
        thread.start()
        
    def check_threads(self):
        ended_threads = []
        for name, thread in list(self.game_threads.items()):
            if not thread.is_alive():
                ended_threads.append(name)
        for name in ended_threads:
            if name in self.game_processes:
                del self.game_processes[name]
            if name in self.game_stop_flags:
                del self.game_stop_flags[name]
            del self.game_threads[name]
        
    def instance_running(self, instance):
        self.check_threads()
        return instance['dir'] in self.game_threads
        
    def kill_game(self, instance):
        instance_key = instance['dir']
        if instance_key in self.game_stop_flags:
            print(f"Signaling stop for {instance_key}")
            self.game_stop_flags[instance_key].set()
            self.root.after(100, lambda: self.update_right_bar(self.selected_instance))
        else:
            print(f"No stop flag found for {instance_key}, instance might not be running or already terminated.")
            self.update_right_bar(self.selected_instance)

    def start_game(self, instance, stop_flag):
        instance_key = instance['dir']
        self.update_right_bar(instance)
        print(f"Starting game for: {instance['name']}")
        accounts_json = json.loads(utils.load_file("accounts.json"))
        instancedir = instance['dir']

        if not accounts_json["Selected Account"] is None:
            selected_account_pass = None
            for acc in accounts_json["accounts"]:
                if acc["name"] == accounts_json["Selected Account"]:
                    selected_account_pass = acc["password"]

            utils.change_option(instancedir, "launcher-cc-username", accounts_json["Selected Account"])
            utils.change_option(instancedir, "launcher-dc-username", accounts_json["Selected Account"])
            utils.change_option(instancedir, "launcher-cc-password", selected_account_pass)

            opts = ['session', 'server', 'ip', 'port', 'mppass', 'dc-mppass', 'username']
            for o in opts:
                utils.delete_option(instancedir, f"launcher-{o}")

        ext = '.exe' if utils.PLAT_WIN else ''
        quote = "" if utils.PLAT_WIN else "'"
        pre = f'instances/{instancedir}/' if utils.PLAT_WIN else ''
        execute_dir = f"{instance['ver']}{ext}"
        target_path = f"instances/{instance['dir']}/ClassiCube{ext}"

        shutil.copy(f"clients/{execute_dir}", target_path)

        try:
            process = subprocess.Popen(
                [f"{quote}{pre}ClassiCube{quote}"],
                cwd=f'instances/{instancedir}/',
                shell=not utils.PLAT_WIN
            )
            self.game_processes[instance_key] = process
            
            while process.poll() is None:
                if stop_flag.is_set():
                    print(f"Stop flag set for {instance_key}. Terminating process...")
                    process.terminate()
                    process.wait(timeout=5)
                    if process.poll() is None:
                        print(f"Process for {instance_key} did not terminate gracefully, killing it.")
                        process.kill()
                    break
                    
                time.sleep(0.1)

            print(f"Game process for {instance_key} finished or was terminated.")

        except Exception as e:
            print(f"Error starting or running game for {instance_key}: {e}")
        finally:
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                    print(f"Removed temporary executable: {target_path}")
                except OSError as e:
                    print(f"Error removing temporary executable {target_path}: {e}")

            self.root.after(0, lambda: self.update_right_bar(self.selected_instance))
            if instance_key in self.game_processes:
                del self.game_processes[instance_key]
            if instance_key in self.game_stop_flags:
                self.game_stop_flags[instance_key].clear()

    def update_right_bar(self, instance):
        for widget in self.right_frame.winfo_children():
            widget.destroy()

        if not instance:
            return

        instance_dir = f"instances/{instance['dir']}"
        logo_path = f"{instance_dir}/logo.png"
        if os.path.exists(logo_path):
            instance_logo = ImageTk.PhotoImage(Image.open(logo_path).resize(LOGO_SIZE, Image.Resampling.LANCZOS))
        else:
            instance_logo = self.launcher_icon

        self.right_logo_label = tk.Label(self.right_frame, image=instance_logo, bg="#3C3F41")
        self.right_logo_label.image = instance_logo
        self.right_logo_label.pack(pady=20)

        self.right_name_label = tk.Label(self.right_frame, text=instance["name"], bg="#3C3F41",
                                         fg="white", font=("Arial", 14, "bold"))
        self.right_name_label.pack(pady=10)
        
        running = self.instance_running(instance)

        self.play_button = tk.Button(self.right_frame, text="Kill" if running else "Play",
                                     bg="#4CAF50", fg="white", font=("Arial", 12, "bold"),
                                     command=lambda: self.start_game_thread(instance) if not running else self.kill_game(instance))
        self.play_button.pack(pady=10)
        self.delete_button = tk.Button(self.right_frame, text="Delete", bg="#AF4C50", fg="white",
                                     font=("Arial", 12, "bold"), command=lambda: self.delete_instance(instance))
        self.delete_button.pack(pady=10)

    def load_instances(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        instances = json.loads(utils.load_file("instances/index.json"))

        num_columns = max(1, math.floor(self.main_frame.winfo_width() / 195))
        row, col = 0, 0
        
        def on_instance_click(inst):
            self.selected_instance = inst
            self.update_right_bar(inst)
        
        for instance in instances:
            instance_dir = f"instances/{instance['dir']}"
            logo_path = f"{instance_dir}/logo.png"

            if os.path.exists(logo_path):
                instance_icon = ImageTk.PhotoImage(Image.open(logo_path).resize(LOGO_SIZE, Image.Resampling.LANCZOS))
            else:
                instance_icon = self.launcher_icon

            frame = tk.Frame(self.main_frame, bg="#2C2F33", padx=5, pady=5, relief="flat")
            frame.grid(row=row, column=col, padx=10, pady=5, sticky="w")

            logo_label = tk.Label(frame, image=instance_icon, bg="#2C2F33")
            logo_label.image = instance_icon
            logo_label.pack(padx=5)

            truncated_text = self.truncate_text(instance["name"], ("Arial", 10), MAX_TEXT_WIDTH)
            name_label = tk.Label(frame, text=truncated_text, font=("Arial", 10), fg="white",
                                  bg="#2C2F33", anchor="w", wraplength=MAX_TEXT_WIDTH)
            name_label.pack(padx=5, fill="x", expand=True)

            frame.bind("<Button-1>", lambda e, i=instance: on_instance_click(i))
            logo_label.bind("<Button-1>", lambda e, i=instance: on_instance_click(i))
            name_label.bind("<Button-1>", lambda e, i=instance: on_instance_click(i))

            col += 1
            if col >= num_columns:
                col = 0
                row += 1
                
    def load_accounts(self):
        accounts_json = json.loads(utils.load_file("accounts.json"))
        
        self.options = []
        for acc in accounts_json["accounts"]:
            self.options.append(acc["name"])
        
        self.options.append("Manage Accounts")

        self.images = {}
        for opt in self.options:
            if opt != "Manage Accounts":
                r = utils.get(f"https://cdn.classicube.net/skin/{opt}.png")
                try:
                    img = Image.open(io.BytesIO(r.content))
                except IOError:
                    r = utils.get("https://Tycho10101.is-a.dev/Assets/char.png")
                    img = Image.open(io.BytesIO(r.content))
                width = img.size[0]
                mult = width/64
                img2 = img.crop((40*mult, 8*mult, 48*mult, 16*mult)).convert().convert('RGBA')
                img = img.crop((8*mult, 8*mult, 16*mult, 16*mult)).convert("RGB")
                img.paste(img2, (0,0), img2) 
                self.images[opt] = ImageTk.PhotoImage(img.resize((30, 30), Image.Resampling.NEAREST))
    
    def delete_instance(self, instance):
        if not self.instance_running(instance):
            instances = json.loads(utils.load_file("instances/index.json"))
            instances.remove(instance)
            utils.save_file("instances/index.json", json.dumps(instances))
            shutil.rmtree(f"instances/{instance['dir']}/")
            self.load_instances()
            self.update_right_bar(instances[0])

    def open_add_instance(self):
        add_window = tk.Toplevel(self.root)
        add_window.title("Add Instance")
        add_window.geometry("300x250")
        add_window.configure(bg="#2C2F33")

        tk.Label(add_window, text="Instance Name:", bg="#2C2F33", fg="white").pack(pady=5)
        name_entry = tk.Entry(add_window)
        name_entry.pack(pady=5)

        version_type = tk.StringVar(value="stable")
        versions_dropdown = ttk.Combobox(add_window, state="readonly")
        versions_dropdown["values"] = utils.get_versions("stable")
        versions_dropdown.current(0)

        def update_versions():
            versions_dropdown["values"] = utils.get_versions(version_type.get())
            versions_dropdown.current(0)

        stable_radio = tk.Radiobutton(add_window, text="Stable", variable=version_type, value="stable",
                                      command=update_versions, bg="#2C2F33", fg="white", selectcolor="#2C2F33")
        dev_radio = tk.Radiobutton(add_window, text="Dev", variable=version_type, value="dev",
                                   command=update_versions, bg="#2C2F33", fg="white", selectcolor="#2C2F33")

        stable_radio.pack()
        dev_radio.pack()
        versions_dropdown.pack(pady=5)

        def create_instance():
            name = name_entry.get().strip()
            version = versions_dropdown.get()
            if name and not utils.instance_name_exists(name):
                utils.make_instance(name, version)
                add_window.destroy()
                self.load_instances()

        tk.Button(add_window, text="Create", command=create_instance, bg="#7289DA", fg="white").pack(pady=10)

    def select_option(self, option):
        if not option == "Manage Accounts":
            if option in self.images:
                self.acc_switch_button.config(text=option, image=self.images[option], compound="left")
            else:
                self.acc_switch_button.config(text=option, image='', compound="left")
            accounts_json = json.loads(utils.load_file("accounts.json"))
            accounts_json["Selected Account"] = option
            utils.save_file("accounts.json", json.dumps(accounts_json))
        else:
            self.open_account_manager()
        self.close_menu()

    def show_menu(self):
        self.close_menu()

        self.dropdown_window = tk.Toplevel(self.root)
        self.dropdown_window.overrideredirect(True)
        self.update_menu_position()

        for option in self.options:
            frame = tk.Frame(self.dropdown_window)
            frame.pack(fill="x")

            if option in self.images:
                img_label = tk.Label(frame, image=self.images[option], width=30, height=30)
                img_label.pack(side="left")

            opt_button = tk.Button(frame, text=option, command=lambda opt=option: self.select_option(opt), anchor="w")
            opt_button.pack(fill="x", expand=True)

        self.root.bind("<Configure>", self.update_menu_position)

    def update_menu_position(self, event=None): # pylint: disable=unused-argument
        if self.dropdown_window:
            a = [
                str(35*len(self.options)),
                str(self.acc_switch_button.winfo_rootx()),
                str(self.acc_switch_button.winfo_rooty() + self.acc_switch_button.winfo_height())
            ]
            self.dropdown_window.geometry(f"150x{'+'.join(a)}")

    def close_menu(self):
        if self.dropdown_window:
            self.dropdown_window.destroy()
            self.dropdown_window = None
            self.root.unbind("<Configure>")
    
    def open_account_manager(self):
        add_window = tk.Toplevel(self.root)
        add_window.title("Account Manager")
        add_window.geometry("600x375")
        add_window.configure(bg="#2C2F33")
        left_frame = tk.Frame(add_window, bg="#3C3F41", width=150)
        left_frame.pack_propagate(False)
        left_frame.pack(fill="y", side="left")
        listbox = tk.Listbox(add_window, bg="#2C2F33", fg="#FFFFFF", bd=0, highlightthickness=0)
        listbox.pack(fill="both", expand=True, pady=5, padx=5)
        for i in range(0, len(self.options) - 1):
            listbox.insert(i + 1, self.options[i])
        
        def add_account():
            add_window.destroy()
            self.open_add_account()
            
        def del_account():
            selected_index = listbox.curselection()
            if selected_index:
                selected_value = listbox.get(selected_index[0])
                f = json.loads(utils.load_file("accounts.json"))
                
                acc = None
                for i in f["accounts"]:
                    if i["name"] == selected_value:
                        acc = i
                if acc is None:
                    raise RuntimeError("Could not find account to delete!")
                        
                f["accounts"].remove(acc)
                
                utils.save_file("accounts.json", json.dumps(f))
                self.load_accounts()
                self.select_option(f["accounts"][0]["name"])
                add_window.destroy()
        
        tk.Button(left_frame, text="Add Account", command=add_account, bg="#7289DA", fg="white")\
            .pack(pady=10, fill="x", padx=10)
        tk.Button(left_frame, text="Delete Account", command=del_account, bg="#7289DA", fg="white")\
            .pack(pady=10, fill="x", padx=10)
    
    def open_add_account(self):
        add_window = tk.Toplevel(self.root)
        add_window.title("Add Account")
        add_window.geometry("300x250")
        add_window.configure(bg="#2C2F33")

        tk.Label(add_window, text="Username:", bg="#2C2F33", fg="white").pack(pady=5)
        name_entry = tk.Entry(add_window)
        name_entry.pack(pady=5)
        
        tk.Label(add_window, text="Password:", bg="#2C2F33", fg="white").pack(pady=5)
        password_entry = tk.Entry(add_window, show="*")
        password_entry.pack(pady=5)
        
        status = tk.Label(add_window, text="", bg="#2C2F33", fg="red")
        status.pack(pady=5)

        def create_account():
            name = name_entry.get().strip()
            password = password_entry.get().strip()
            auth, username = utils.login_to_cc(name, password)
            if name and password and not utils.username_exists(username) and auth:
                utils.save_account(username, password)
                self.load_accounts()
                self.select_option(username)
                add_window.destroy()
            elif not name and not password:
                status.config(text = "No Username or Password")
            elif not name:
                status.config(text = "No Username")
            elif not password:
                status.config(text = "No Password")
            elif utils.username_exists(username):
                status.config(text = "Account already exists")
            else:
                status.config(text = "Failed to login")
                
        tk.Button(add_window, text="Login", command=create_account, bg="#7289DA", fg="white").pack(pady=10)