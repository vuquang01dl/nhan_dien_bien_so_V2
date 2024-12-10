import cv2
import torch
import numpy as np
import serial
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime, timedelta
import os

class LicensePlateRecognizer:
    def __init__(self):
        # Load YOLOv5 models for license plate detection and text recognition
        self.model_plate = torch.hub.load(
            'ultralytics/yolov5', 'custom',
            path=r'D:\Cong_viec\nhan_dang_bien_so_v2\LP_detector_nano_61.pt',
            force_reload=True
        ).to('cpu')

        self.model_text = torch.hub.load(
            'ultralytics/yolov5', 'custom',
            path=r'D:\Cong_viec\nhan_dang_bien_so_v2\LP_ocr.pt',
            force_reload=True
        ).to('cpu')

        # Initialize serial communication with Arduino
        self.arduino_in = serial.Serial('COM8', 9600, timeout=1)
        self.arduino_out = serial.Serial('COM3', 9600, timeout=1)

        # Initialize cameras for entry and exit
        self.cap_in = cv2.VideoCapture(1)
        self.cap_out = cv2.VideoCapture(0)

        # Create folder for saving images if it doesn't exist
        self.save_folder = "Parking_Images"
        os.makedirs(self.save_folder, exist_ok=True)

        # Initialize parking status and read cooldowns
        self.max_parking_spots = 10
        self.current_parking_spots = self.max_parking_spots
        self.seen_plates = {}
        self.last_rfid_read_in = None
        self.last_rfid_read_out = None
        self.cooldown_period = timedelta(seconds=5)  # Set cooldown period

        # Initialize Tkinter interface
        self.root = tk.Tk()
        self.root.title("Smart Parking System")

        # Frame for cameras and buttons
        camera_frame = tk.Frame(self.root)
        camera_frame.pack()

        # Labels and button for exit gate
        exit_label = tk.Label(camera_frame, text="CỔNG RA", font=("Arial", 18))
        exit_label.grid(row=0, column=0, padx=5)
        self.button_send_b = tk.Button(camera_frame, text="Send 'B' (Exit)", command=self.send_command_b, font=("Arial", 14))
        self.button_send_b.grid(row=0, column=1, padx=10)
        
        self.label_out = tk.Label(camera_frame)
        self.label_out.grid(row=1, column=0, columnspan=2, padx=5)
        self.plate_out_label = tk.Label(camera_frame, text="", font=("Arial", 16))
        self.plate_out_label.grid(row=2, column=0, columnspan=2, padx=5)
        self.time_out_label = tk.Label(camera_frame, text="", font=("Arial", 12))
        self.time_out_label.grid(row=3, column=0, columnspan=2, padx=5)

        # Labels and button for entry gate
        entry_label = tk.Label(camera_frame, text="CỔNG VÀO", font=("Arial", 18))
        entry_label.grid(row=0, column=2, padx=5)
        self.button_send_a = tk.Button(camera_frame, text="Send 'A' (Entry)", command=self.send_command_a, font=("Arial", 14))
        self.button_send_a.grid(row=0, column=3, padx=10)
        
        self.label_in = tk.Label(camera_frame)
        self.label_in.grid(row=1, column=2, columnspan=2, padx=5)
        self.plate_in_label = tk.Label(camera_frame, text="", font=("Arial", 16))
        self.plate_in_label.grid(row=2, column=2, columnspan=2, padx=5)
        self.time_in_label = tk.Label(camera_frame, text="", font=("Arial", 12))
        self.time_in_label.grid(row=3, column=2, columnspan=2, padx=5)

        # Info label
        self.info_label = tk.Label(self.root, text="", font=("Arial", 16))
        self.info_label.pack(side=tk.BOTTOM)

        # Treeview for displaying plates and card IDs
        self.tree = ttk.Treeview(self.root, columns=("Card ID", "License Plate", "Entry Time", "Exit Time"), show='headings')
        self.tree.heading("Card ID", text="Card ID")
        self.tree.heading("License Plate", text="License Plate")
        self.tree.heading("Entry Time", text="Entry Time")
        self.tree.heading("Exit Time", text="Exit Time")
        self.tree.pack(pady=10)

        # Start recognition thread
        threading.Thread(target=self.start_recognition, daemon=True).start()

    def send_command_a(self):
        """Send command 'A' to the entry Arduino manually."""
        if self.arduino_in.is_open:
            self.arduino_in.write(b'A')
            print("Sent 'A' to entry gate")

    def send_command_b(self):
        """Send command 'B' to the exit Arduino manually."""
        if self.arduino_out.is_open:
            self.arduino_out.write(b'B')
            print("Sent 'B' to exit gate")

    def start_recognition(self):
        while True:
            # Entry camera frame processing
            ret_in, frame_in = self.cap_in.read()
            plate_text_in = ""
            if ret_in and frame_in is not None:
                results_in = self.model_plate(Image.fromarray(cv2.cvtColor(frame_in, cv2.COLOR_BGR2RGB)))
                plate_text_in = self.process_results(frame_in, results_in)

                card_id_in = self.read_rfid_from_arduino(self.arduino_in)

                # Process entry if there's a cooldown or if this is the first read
                if card_id_in and (self.last_rfid_read_in is None or datetime.now() - self.last_rfid_read_in > self.cooldown_period):
                    if card_id_in not in self.seen_plates.values():
                        self.seen_plates[plate_text_in] = card_id_in
                        self.current_parking_spots -= 1
                        self.arduino_in.write(b'A')
                        self.last_rfid_read_in = datetime.now()  # Update last read time

                        # Capture and save entry image
                        entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        filename_in = os.path.join(self.save_folder, f"{plate_text_in}_entry_{entry_time.replace(':', '-')}.jpg")
                        cv2.imwrite(filename_in, frame_in)

                        self.time_in_label.configure(text=f"Giờ vào: {entry_time}")
                        self.update_treeview(entry_time=entry_time, plate=plate_text_in)

            # Exit camera frame processing
            ret_out, frame_out = self.cap_out.read()
            plate_text_out = ""
            if ret_out and frame_out is not None:
                results_out = self.model_plate(Image.fromarray(cv2.cvtColor(frame_out, cv2.COLOR_BGR2RGB)))
                plate_text_out = self.process_results(frame_out, results_out)

                card_id_out = self.read_rfid_from_arduino(self.arduino_out)

                # Process exit if there's a cooldown or if this is the first read
                if card_id_out and (self.last_rfid_read_out is None or datetime.now() - self.last_rfid_read_out > self.cooldown_period):
                    if plate_text_out in self.seen_plates:
                        del self.seen_plates[plate_text_out]
                        self.current_parking_spots += 1
                        self.arduino_out.write(b'B')
                        self.last_rfid_read_out = datetime.now()  # Update last read time

                        # Capture and save exit image
                        exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        filename_out = os.path.join(self.save_folder, f"{plate_text_out}_exit_{exit_time.replace(':', '-')}.jpg")
                        cv2.imwrite(filename_out, frame_out)

                        self.time_out_label.configure(text=f"Giờ ra: {exit_time}")
                        self.update_treeview(exit_time=exit_time, plate=plate_text_out)

            # Update UI only if frames are valid
            if ret_in and ret_out:
                self.display_frame(frame_in, frame_out, plate_text_in, plate_text_out)

    def display_frame(self, frame_in, frame_out, plate_text_in, plate_text_out):
        if frame_in is not None:
            frame_in = cv2.cvtColor(frame_in, cv2.COLOR_BGR2RGB)
            img_in = Image.fromarray(frame_in)
            img_in_tk = ImageTk.PhotoImage(image=img_in)
            self.label_in.imgtk = img_in_tk
            self.label_in.configure(image=img_in_tk)

        if frame_out is not None:
            frame_out = cv2.cvtColor(frame_out, cv2.COLOR_BGR2RGB)
            img_out = Image.fromarray(frame_out)
            img_out_tk = ImageTk.PhotoImage(image=img_out)
            self.label_out.imgtk = img_out_tk
            self.label_out.configure(image=img_out_tk)

        self.info_label.configure(text=f"Số chỗ trống: {self.current_parking_spots}")
        self.plate_in_label.configure(text=f"Biển số vào: {plate_text_in if plate_text_in else 'Không tìm thấy'}")
        self.plate_out_label.configure(text=f"Biển số ra: {plate_text_out if plate_text_out else 'Không tìm thấy'}")

    def update_treeview(self, entry_time=None, exit_time=None, plate=None):
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        for plate, card_id in self.seen_plates.items():
            entry = entry_time if plate == plate else ""
            exit = exit_time if plate == plate else ""
            self.tree.insert("", "end", values=(card_id, plate, entry, exit))

    def process_results(self, frame, results):
        plate_text = ""
        for bbox in results.xyxy[0]:
            x1, y1, x2, y2 = map(int, bbox[:4])
            cropped_plate = frame[y1:y2, x1:x2]

            cropped_img_rgb = cv2.cvtColor(cropped_plate, cv2.COLOR_BGR2RGB)

            results_text = self.model_text(Image.fromarray(cropped_img_rgb))
            detected_chars = [
                (bbox[0], bbox[1], results_text.names[int(bbox[5].item())])
                for bbox in results_text.xyxy[0]
            ]
            detected_chars.sort(key=lambda char: (char[1], char[0]))
            plate_text = "".join([char[2] for char in detected_chars])

        return plate_text

    def read_rfid_from_arduino(self, arduino):
        if arduino.in_waiting > 0:
            return arduino.readline().decode('utf-8').strip()
        return None

    def on_close(self):
        self.cap_in.release()
        self.cap_out.release()
        self.root.destroy()
        if self.arduino_in.is_open:
            self.arduino_in.close()
        if self.arduino_out.is_open:
            self.arduino_out.close()

if __name__ == "__main__":
    app = LicensePlateRecognizer()
    app.root.mainloop()
