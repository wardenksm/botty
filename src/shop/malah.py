import keyboard
import numpy as np
import cv2

from screen import grab
from config import Config
from logger import Logger
from npc_manager import Npc, open_npc_menu, press_npc_btn
import template_finder
from inventory import common
from shop.i_shopper import IShopper

class MalahShopper(IShopper):
    def __init__(self):
        super().__init__()
        self.weapon_list = []
        self.shop_scepters = Config().shop["shop_hammerdin_scepters"]
        if self.shop_scepters:
            self.weapon_list += ["SCEPTER4", "SCEPTER5"]
        self.shop_wands = Config().shop["shop_wands"]
        if self.shop_wands:
            self.weapon_list += ["WAND1", "WAND2"]
        self.shop_knives = Config().shop["shop_knives"]
        if self.shop_knives:
            self.weapon_list += ["KRIS"]

    def check_vendor_stash(self) -> int:
        items_bought = 0
        Logger().info("Check Malah stash")
        if self.use_edge:
            keyboard.send(Config().char["weapon_switch"])

        if self.shop_knives:
            common.select_tab(3)
            img = grab().copy()
            while (match := template_finder.search(["BALANCED_KNIFE"], img, 0.75, Config().ui_roi["left_inventory"])).valid:
                if self.check_vendor_item(match.center_monitor) > 0:
                    items_bought += 1
                img = cv2.rectangle(img, (match.region[0], match.region[1]),
                                    (match.region[0] + match.region[2], match.region[1] + match.region[3]),
                                    (255, 255, 255), -1)

        if len(self.weapon_list):
            common.select_tab(1)
            img = grab().copy()
            while (match := template_finder.search(self.weapon_list, img, 0.75, Config().ui_roi["left_inventory"])).valid:
                if self.check_vendor_item(match.center) > 0:
                    items_bought += 1
                img = cv2.rectangle(img, (match.region[0], match.region[1]),
                                    (match.region[0] + match.region[2], match.region[1] + match.region[3]),
                                    (255, 255, 255), -1)

        if self.use_edge:
            keyboard.send(Config().char["weapon_switch"])
        return items_bought