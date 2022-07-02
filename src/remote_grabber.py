import threading, socket, json, ctypes
import numpy as np
from ctypes.wintypes import BOOL, DWORD, INT, LONG, UINT, WORD
from config import Config
from logger import Logger

class BITMAPINFOHEADER(ctypes.Structure):
    """ Information about the dimensions and color format of a DIB. """
    _fields_ = [
        ("biSize", DWORD),
        ("biWidth", LONG),
        ("biHeight", LONG),
        ("biPlanes", WORD),
        ("biBitCount", WORD),
        ("biCompression", DWORD),
        ("biSizeImage", DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]

class RemoteGrabber:
    def __init__(self, addr: str, port: int):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((addr, port))
        #Logger.info(f'Connected to frameserver {addr}:{port}')
        self.res = (0, 0)
        self.lock = threading.Lock()

    def get_client_offset(self):
        with self.lock:
            try:
                self.s.send('i'.encode(), 0)
                rb = self.s.recv(128)
            except:
                Logger.error("Failed to get client offset from server")
                return 0,0
        info = json.loads(rb.decode())
        self.res = (info['width'], info['height'])
        return info['x'], info['y']

    def grab(self, old_img: np.array):
        with self.lock:
            try:
                self.s.send('s'.encode(), 0)
                rb = self.s.recv(40)
            except:
                Logger.error("Failed to grab screen from server")
                return None
            dibHeader = BITMAPINFOHEADER.from_buffer_copy(rb)
            if len(rb) < dibHeader.biSize:
                Logger.info(f"Inavlid dibHeader! received {len(rb)} bytes < biSize({dibHeader.biSize})")
                return None
            if old_img is None or len(old_img.data) != dibHeader.biSizeImage:
                img_buf = ctypes.create_string_buffer(dibHeader.biSizeImage)
                channels = dibHeader.biBitCount >> 3
                stride = dibHeader.biSizeImage // -dibHeader.biHeight
                img = np.ndarray(shape=(-dibHeader.biHeight, dibHeader.biWidth, channels), buffer=img_buf, dtype=np.uint8, strides=(stride,channels,1))
            else:
                img_buf = old_img.data
                img = old_img
            view = memoryview(img_buf)
            total_bytes = self.s.recv_into(img_buf, dibHeader.biSizeImage)
            remaining = dibHeader.biSizeImage - total_bytes
            while remaining > 0:
                rbytes = self.s.recv_into(view[total_bytes:], remaining)
                total_bytes += rbytes
                remaining -= rbytes
        return img

    def close_window(self):
        with self.lock:
            self.s.send('c'.encode(), 0)
            self.s.close()

    def __del__(self):
        self.s.close()

remote_grabber = None
sandbox_ip = Config().general["sandbox_ip"]
frameserver_port = 51466 # CRC16/X-25 of "botty"

if sandbox_ip is not None and len(sandbox_ip) > 1:
    remote_grabber = RemoteGrabber(sandbox_ip, frameserver_port)
