import numpy as np
import cv2
import time
from screen import grab, convert_screen_to_monitor
from config import Config
from logger import Logger
from utils.custom_mouse import mouse
from inventory import personal
from d2r_image import processing as d2r_image
from bnip.actions import should_keep

class IShopper:
    def __init__(self):
        self.roi_vendor = Config().ui_roi["left_inventory"]
        self.rx, self.ry, _, _ = self.roi_vendor
        self.sb_x, self.sb_y = convert_screen_to_monitor((180, 77))
        self.c_x, self.c_y = convert_screen_to_monitor((Config().ui_pos["center_x"], Config().ui_pos["center_y"]))
        self.use_edge = Config().char["edge_available"]
        self.slot_w = Config().ui_pos["slot_width"]
        self.slot_h = Config().ui_pos["slot_height"]
        self.left_inv_roi = Config().ui_roi["left_inventory"]

    def check_vendor_item(self, pos) -> int:
        mouse.move(*pos)
        time.sleep(0.25)
        for i in range(3):
            hovered_item = grab(True)
            # get the item description box
            item_properties, item_box = d2r_image.get_hovered_item(hovered_item, in_right_inv=False)
            if item_box is not None and item_box.ocr_result is not None:
                ocr_lines = item_box.ocr_result.text.splitlines()
                if len(ocr_lines[1]) > 1:
                    break
            mouse.move(*pos)
        else:
            Logger.warning(f"Failed to get item box at {pos}")
            return 0
        keep, expression = should_keep(item_properties.as_dict())
        Logger.debug(f"Checking {ocr_lines[1]}")
        if keep:
            mouse.click("right")
            Logger.info(f"Bought {ocr_lines[1]}. {ocr_lines[0]}")
            return 1
        return 0

    def inspect_slot(self, img, x, y):
        off_x = x * self.slot_w + self.left_inv_roi[0] + 2
        off_y = y * self.slot_h + self.left_inv_roi[1] + 2
        gray = cv2.cvtColor(img[off_y:off_y+self.slot_h-4, off_x:off_x+self.slot_w-4], cv2.COLOR_BGR2GRAY)
        if np.average(gray) > 32:
            return (off_x + self.slot_w // 2, off_y + self.slot_h // 2)
        return None
