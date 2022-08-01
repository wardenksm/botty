import datetime
import os
import time

import keyboard
import numpy as np
import cv2

from screen import grab, convert_screen_to_monitor
from config import Config
from logger import Logger
from npc_manager import Npc, open_npc_menu, press_npc_btn
import template_finder
from ui_manager import is_visible, ScreenObjects
from utils.custom_mouse import mouse
from utils.misc import wait, load_template
from inventory import common

from messages import Messenger
from shop.i_shopper import IShopper

def exit(run_obj):
    run_time = str(datetime.timedelta(seconds=round(time.time() - run_obj.start_time)))
    Logger.info("Exiting shopping mall...")
    print(
        "STATS \truns \t\ttime \t\tias_gloves_seen \tgloves_bought \tclaws_evaluated \tclaws_bought\n"
        f"\t{run_obj.run_count} \t\t{run_time}"
        f"\t\t{run_obj.ias_gloves_seen} \t\t\t{run_obj.gloves_bought} \t\t{run_obj.claws_evaluated} \t\t\t{run_obj.claws_bought}"
    )
    os._exit(0)


def wait_for_loading_screen(timeout):
    start = time.time()
    while time.time() - start < timeout:
        img = grab()
        is_loading_black_roi = np.average(img[:700, 0:250]) < 4.0
        if is_loading_black_roi:
            return True
    return False


class AnyaShopper(IShopper):
    """
    Shop at Anya for 20 ias, +3 java skill gloves and more...

    In order to start the shopping bot:
    1.) Run this this file in Python.
    2.) Be ingame in Harrogath (act 5 town).
    3.) Stand close to Anya and the red portal.
    4.) While being ingame, press resume_key (default F11) to start the shopping, and exit_key (default F12) to stop it.
    """

    def __init__(self):
        # Set look_for variables to False if you dont like your personal shopper to look for these
        # Obviously something need to be set to True, or your shopper will be very confused
        # For the trap claw scores use:
        # 7 if you are happy with any + to traps or +2 assassin
        # 9 if you want at least +2 assassin or two useful trap stats
        # 11 if you want at least +3 traps or +2 and a sentry bonus
        # Similar for melee claws but not really worth keeping any less that 11 here since you really want both +2 assassin and a useful other stat, feedback needed
        super().__init__()
        self.look_for_gloves = Config().shop["shop_skills_ias_gloves"]
        self.look_for_claws = Config().shop["shop_claws"]
        self.look_for_archon_plates = Config().shop["shop_jewelers_archon_plate"]
        self._messenger = Messenger()
        self.run_count = 0
        self.start_time = time.time()
        self.ias_gloves_seen = 0
        self.armor_list = ["IAS_GLOVES"] if self.look_for_gloves else []
        if self.look_for_archon_plates:
            self.armor_list += ["ARCHON_PLATE_OF_THE_WHALE", "ARCHON_PLATE_OF_STABILITY"]

    def check_vendor(self) -> int:
        if not open_npc_menu(Npc.ANYA, 3):
            return 0
        low_quantity = is_visible(ScreenObjects.LowQuantity)

        press_npc_btn(Npc.ANYA, "trade")
        time.sleep(0.1)
        if not common.wait_for_left_inventory():
            return 0

        if self.use_edge and not low_quantity:
            keyboard.send(Config().char["weapon_switch"])
        items_bought = 0
        if len(self.armor_list):
            common.select_tab(0)
            img = grab(force_new=True).copy()
            for match in template_finder.search_all(self.armor_list, img, 0.994, Config().ui_roi["left_inventory"], use_grayscale=False):
                #x,y,w,h = match.region
                r = self.check_vendor_item(match.center_monitor)
                if r > 0:
                    items_bought += 1
                #elif r < 0:
                    #cv2.imwrite(f"./debug_screenshots/fp_{time.strftime('%Y%m%d_%H%M%S')}_{int(match.score*1000)}.png", img[y:y+h,x:x+w])
                #else:
                    #cv2.imwrite(f"./debug_screenshots/tp_{time.strftime('%Y%m%d_%H%M%S')}_{int(match.score*1000)}.png", img[y:y+h,x:x+w])

        if self.look_for_claws:
            common.select_tab(1, True)
            img = grab(force_new=True).copy()
            # Anya sells claws only. Just check whether the slot is empy.
            for x in [2,1,0]:
                for y in range(3):
                    center = self.inspect_slot(img, x, y * 3 + 1)
                    if center is None:
                        break
                    if self.check_vendor_item(convert_screen_to_monitor(center)) > 0:
                        items_bought += 1

        if self.use_edge:
            keyboard.send(Config().char["weapon_switch"])
        common.close()
        return items_bought

    def run(self):
        Logger.info("Personal Anya Shopper at your service! Hang on, running some errands...")
        # Shop loop
        items_bought = 0
        while True:
            items_bought += self.check_vendor()
            # Done with this shopping round
            self.reset_shop()
            self.run_count += 1

    def reset_shop(self):
        while 1:
            success = self.select_by_template("A5_RED_PORTAL")
            success &= wait_for_loading_screen(2)
            if success:
                break
            else:
                mouse.move(800, 450, randomize=50, delay_factor=[0.7, 0.7])
        time.sleep(2.5)
        while 1:
            success = self.select_by_template("A5_RED_PORTAL")
            success &= wait_for_loading_screen(2)
            if success:
                break
            else:
                mouse.move(800, 450, randomize=50, delay_factor=[0.7, 0.7])

    def select_by_template(self, template_type: str) -> bool:
        Logger.debug(f"Select {template_type}")
        template_match = template_finder.search_and_wait(template_type, timeout=10)
        if template_match.valid:
            mouse.move(*template_match.center_monitor)
            wait(0.1, 0.2)
            mouse.click(button="left")
            return True
        return False
