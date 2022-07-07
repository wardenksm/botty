import keyboard
import numpy as np
import cv2, re
from screen import grab, convert_screen_to_monitor
from config import Config
from logger import Logger
from utils.custom_mouse import mouse
from inventory import personal
from item import ItemCropper
import property_parser

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

    @staticmethod
    def parse_item(ocr_lines: list[str], color) -> int:
        item_name = personal.get_item_name_from_ocr_result(ocr_lines, color)
        Logger.debug(f"OCR DESCRIPTION for {item_name}:")
        item_prop = property_parser.parse_lines(ocr_lines[1:], True)
        if 'PLATE' in item_name and item_prop["life"] < 20 and item_prop["fhr"] < 10:
            return -1
        if 'GAUNTLETS' in item_name and item_prop["ias"] < 20:
            return -1
        
        if item_name in Config().items_new[color]:
            pickit_desc = Config().items_new[color][item_name]
            if pickit_desc.expression is None:
                return 0
            # assign variables with values
            for var, expr in Config().variables_new:
                try:
                    item_prop[var] = eval(expr, item_prop)
                except:
                    Logger.error(f"Error assigning variable: {var} = {expr}")
            # evaluate expression
            try:
                if eval(pickit_desc.expression, item_prop):
                    return 1
            except:
                Logger.error(f"Error evaluating expr for ({item_name}): {pickit_desc.expression}")
                return 1
        return 0

    def check_vendor_item(self, pos) -> int:
        mouse.move(*pos)
        hovered_item = grab()
        # get the item description box
        item_box = ItemCropper().crop_item_descr(hovered_item, inventory_side="left")
        if item_box.valid:
            ocr_lines = list(filter(None, re.split(' *[,\n] *', item_box.ocr_result.text)))
            r = self.parse_item(ocr_lines[1:], item_box.color)
            if r > 0:
                mouse.click("right")
                Logger.info(f"Bought {ocr_lines[1]}. {ocr_lines[0]}")
                return 1
            return r
        return 0

    def inspect_slot(self, img, x, y):
        off_x = x * self.slot_w + self.left_inv_roi[0] + 2
        off_y = y * self.slot_h + self.left_inv_roi[1] + 2
        gray = cv2.cvtColor(img[off_y:off_y+self.slot_h-4, off_x:off_x+self.slot_w-4], cv2.COLOR_BGR2GRAY)
        if np.average(gray) > 32:
            return (off_x + self.slot_w // 2, off_y + self.slot_h // 2)
        return None
