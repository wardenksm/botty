import cv2
import numpy as np
import time
import os
from dataclasses import dataclass
import math, re

from config import Config
from utils.misc import color_filter, cut_roi
from item import ItemCropper
from ocr import OcrResult, Ocr
from logger import Logger

@dataclass
class Template:
    data: np.ndarray = None
    hist = None
    blacklist: bool = False

@dataclass
class Item:
    center: tuple[float, float] = None # (x, y) in screen coordinates
    name: str = None
    score: float = -1.0
    dist: float = -1.0
    roi: list[int] = None
    color: str = None
    ocr_result: OcrResult = None
    def __getitem__(self, key):
        return super().__getattribute__(key)

class ItemFinder:
    def __init__(self):
        self._item_cropper = ItemCropper()

    def search(self, inp_img: np.ndarray) -> list[Item]:
        img = inp_img[:,:,:]
        start = time.time()
        item_text_clusters = self._item_cropper.crop(img, 7)
        item_list = []
        img1 = inp_img.copy()
        for cluster in item_text_clusters:
            x, y, w, h = cluster.roi
            # cv2.rectangle(inp_img, (x, y), (x+w, y+h), (0, 255, 0), 1)
            cropped_input = cluster.data
            best_score = None
            item = None
            if Config().advanced_options["ocr_during_pickit"]:
                item_text = cluster.ocr_result['text']
                if cluster.color in ["gray","white"] and item_text.startswith("SUPERIOR"):
                    item_text = item_text[len("SUPERIOR")+1:]
                elif re.match("[0-9]+ GOLD", item_text):
                    item_text = "GOLD"
                if item_text in Config().items_new[cluster.color] and Config().items_new[cluster.color][item_text].pickit_type:
                    item = Item(
                        center = [int(x + w * 0.5), int(y + h * 0.5)],
                        name   = item_text,
                        score  = 1,
                        roi    = cluster.roi,
                        color  = cluster.color,
                        ocr_result = cluster.ocr_result
                    )
                    item.center_abs = (item.center[0] - inp_img.shape[1] // 2, item.center[1] - inp_img.shape[0] // 2)
                    item.dist = math.dist(item.center_abs, (0, 0))
                    item_list.append(item)
                    t = "Pick"
                else:
                    t = "Discard"
                    if len(item_text.split()) > 4:
                        time_str = time.strftime('%Y%m%d_%H%M%S')
                        #cv2.imwrite(f"./loot_screenshots/failed_crop_{time_str}.png", cut_roi(inp_img, cluster.roi))
                        #cv2.imwrite(f"./loot_screenshots/failed_crop_full_{time_str}.png", inp_img)
                Logger.debug(f"OCR: [{cluster.color}]{cluster.ocr_result['text']}, Conf: {cluster.ocr_result['mean_confidence']} -> {t}")

        elapsed = time.time() - start
        # print(f"Item Search: {elapsed}")
        return item_list


# Testing: Throw some stuff on the ground see if it is found
if __name__ == "__main__":
    from screen import grab
    from config import Config

    item_finder = ItemFinder()
    while 1:
        # img = cv2.imread("")
        img = grab().copy()
        item_list = item_finder.search(img)
        for item in item_list:
            # print(item.name + " " + str(item.score))
            cv2.circle(img, item.center, 5, (255, 0, 255), thickness=3)
            cv2.rectangle(img, item.roi[:2], (item.roi[0] + item.roi[2], item.roi[1] + item.roi[3]), (0, 0, 255), 1)
            cv2.putText(img, item.ocr_result["text"], item.center, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        # img = cv2.resize(img, None, fx=0.5, fy=0.5)
        cv2.imshow('test', img)
        cv2.waitKey(1)