from math import floor
import keyboard, time
import template_finder
from config import Config
import numpy as np
from utils.misc import wait
from screen import convert_screen_to_monitor, grab
from logger import Logger
from utils.custom_mouse import mouse
from ui_manager import center_mouse, is_visible, select_screen_object_match, wait_until_visible, ScreenObjects
from inventory import personal, common, stash

gamble_count = 0
gamble_status = False

item_space = {
    "CIRCLET" : 4,
    "RING" : 1,
    "CORONET" : 4,
    "TALON" : 3,
    "AMULET" : 1
}

def get_gamble_count() -> int:
    global gamble_count
    return gamble_count

def set_gamble_count(count: int = 0):
    global gamble_count
    gamble_count = count

def get_gamble_status() -> bool:
    global gamble_status
    return gamble_status

def set_gamble_status(bool: bool):
    global gamble_status, gold_in_stash
    gamble_status = bool
    if gamble_status:
        set_gamble_count(0)
        Config().turn_off_goldpickup()
    else:
        Config().turn_on_goldpickup()

def repair() -> bool:
    """
    Repair and fills up TP buy selling tome and buying. Vendor inventory needs to be open!
    :return: Bool if success
    """
    if not (repair_btn := wait_until_visible(ScreenObjects.RepairBtn, timeout=4)).valid:
        return False
    select_screen_object_match(repair_btn)
    if wait_until_visible(ScreenObjects.NotEnoughGold, 1).valid:
        Logger.warning("Couldn't repair--out of gold. Continue.")
        keyboard.send("esc")
        return False
    return True

def gamble():
    if (refresh_btn := template_finder.search_and_wait("REFRESH", threshold=0.79, timeout=4)).valid:
        #Gambling window is open. Starting to spent some coins
        max_gamble_count = 30
        free_space = inventory_space = Config().char["num_loot_columns"] * 4
        items = None
        while get_gamble_status() and get_gamble_count() < max_gamble_count and free_space > 0:
            img=grab()
            for item in Config().char["gamble_items"]:
                # while desired gamble item is not on screen, refresh
                while not (desired_item := template_finder.search(item.upper(), img, roi=Config().ui_roi["left_inventory"])).valid:
                    mouse.move(*refresh_btn.center_monitor, randomize=12, delay_factor=[1.0, 1.5])
                    mouse.click(button="left")
                    wait(0.2, 0.25)
                    img=grab()
                # desired item found, purchase it
                mouse.move(*desired_item.center_monitor, randomize=12, delay_factor=[1.0, 1.5])
                prev_time = time.time()
                mouse.click(button="right")
                if desired_item.name in item_space:
                    free_space -= item_space[desired_item.name]
                else:
                    free_space -= 8
                if free_space < 8:
                    center_mouse()
                else:
                    x, y = desired_item.center
                    mouse.move(*convert_screen_to_monitor((420 if x > 220 else 25, y)), delay_factor=[1.4, 1.5])
                delta = time.time() - prev_time
                if delta < 1.0:
                    time.sleep(1.0 - delta)
                img=grab()
                # make sure the "not enough gold" message doesn't exist
                if is_visible(ScreenObjects.NotEnoughGold, img):
                    Logger.warning(f"Out of gold, stop gambling")
                    center_mouse()
                    mouse.click("left")
                    free_space = -1
                else:
                    new_count = get_gamble_count()+1
                    Logger.debug(f"Gamble purchase {new_count}/{max_gamble_count}")
                    set_gamble_count(new_count)
                    if free_space >= 8:
                        continue
                # inspect purchased item
                if personal.inventory_has_items(img):
                    items = personal.inspect_items(img, close_window=False)
                    if items:
                        # specifically in gambling scenario, all items returned from inspect_items, which sells/drops unwanted items, are to be kept
                        # if there is a desired item, end function and go to stash
                        Logger.debug("Found desired item, go to stash")
                        if new_count * 2 > max_gamble_count:
                            # if we gambled more than half of max_gamble_count, do not return to gamble after stashing
                            free_space = -1
                            break
                        common.close()
                        return items
                if new_count >= max_gamble_count or free_space < 0:
                    break
                free_space = inventory_space
        Logger.debug(f"Finish gambling")
        stash.set_curr_stash(gold = 0)
        personal.set_inventory_gold_full(False)
        if get_gamble_status():
            set_gamble_status(False)
        common.close()
        return items
    else:
        Logger.warning("gamble: gamble vendor window not detected")
        return False

def buy_item(template_name: str, quantity: int = 1, img: np.ndarray = None, shift_click: bool = False) -> bool:
    """
    Buy desired item from vendors. Vendor inventory needs to be open!
    :param template_name: Name of template for desired item to buy; e.g., SUPER_MANA_POTION
    :param quantity: How many of the item to buy
    :param img: Precaptured image of opened vendor inventory
    :param shift_click: whether to hold shift and right click to buy full stack
    returns bool for success/failure
    """
    if img is None:
        img = grab()
    if (desired_item := template_finder.search(template_name, inp_img=img, roi=Config().ui_roi["left_inventory"])).valid:
        mouse.move(*desired_item.center_monitor, randomize=8, delay_factor=[1.0, 1.5])
        if shift_click:
            keyboard.send('shift', do_release=False)
            wait(0.5, 0.8)
            mouse.click(button="right")
            wait(0.4, 0.6)
            if is_visible(ScreenObjects.NotEnoughGold):
                Logger.warning(f"Out of gold, could not purchase {template_name}")
                keyboard.send('shift', do_release=True)
                keyboard.send("esc")
                return False
            keyboard.send('shift', do_release=True)
            personal.set_inventory_gold_full(False)
            center_mouse()
            return True
        if quantity:
            for _ in range(quantity):
                mouse.click(button="right")
                wait(0.9, 1.1)
                if is_visible(ScreenObjects.NotEnoughGold):
                    Logger.warning(f"Out of gold, could not purchase {template_name}")
                    keyboard.send("esc")
                    return False
            personal.set_inventory_gold_full(False)
            center_mouse()
            return True
        else:
            Logger.error("buy_item: Quantity not specified")
            return False
    Logger.error(f"buy_item: Desired item {template_name} not found")
    return False
