import time, random
import keyboard
import cv2
from operator import itemgetter
from ui_manager import ScreenObjects, is_visible
from utils.custom_mouse import mouse
from config import Config
from logger import Logger
from screen import grab, convert_abs_to_monitor, convert_screen_to_monitor
from item import ItemFinder, Item
from char import IChar
from inventory import consumables
import parse


class PickIt:
    def __init__(self, item_finder: ItemFinder):
        self._item_finder = item_finder
        self._last_closest_item: Item = None

    def pick_up_items(self, char: IChar, order = None) -> bool:
        """
        Pick up all items with specified char
        :param char: The character used to pick up the item
        :return: Bool if any items were picked up or not. (Does not account for picking up scrolls and pots)
        """
        found_nothing = 0
        found_items = False
        keyboard.send(Config().char["show_items"])
        time.sleep(1.0) # sleep needed here to give d2r time to display items on screen on keypress
        #Creating a screenshot of the current loot
        if Config().general["loot_screenshots"]:
            img = grab()
            cv2.imwrite("./loot_screenshots/info_debug_drop_" + time.strftime("%Y%m%d_%H%M%S") + ".png", img)
            Logger.debug("Took a screenshot of current loot")
        start = prev_cast_start = time.time()
        timeout = False
        picked_up_items = []
        skip_items = []
        curr_item_to_pick: Item = None
        same_item_timer = None
        did_force_move = False
        done_ocr=False

        while not timeout:
            if (time.time() - start) > 28:
                timeout = True
                Logger.warning("Got stuck during pickit, skipping it this time...")
                break
            img = grab()
            item_list = self._item_finder.search(img)

            if Config().advanced_options["ocr_during_pickit"] and not done_ocr:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                for cnt, item in enumerate(item_list):
                    for cnt2, x in enumerate(item.ocr_result['word_confidences']):
                        found_low_confidence = False
                        if x <= 88:
                            try:
                                Logger.debug(f"Low confidence word #{cnt2}: {item.ocr_result['original_text'].split()[cnt2]} -> {item.ocr_result['text'].split()[cnt2]}, Conf: {x}, save screenshot")
                                found_low_confidence = True
                            except: pass
                        if found_low_confidence and Config().general["loot_screenshots"]:
                            cv2.imwrite(f"./loot_screenshots/ocr_drop_{timestamp}_{cnt}_o.png", item.ocr_result['original_img'])
                            cv2.imwrite(f"./loot_screenshots/ocr_drop_{timestamp}_{cnt}_n.png", item.ocr_result['processed_img'])
                            with open(f"./loot_screenshots/ocr_drop_{timestamp}_{cnt}_o.gt.txt", 'w') as f:
                                f.write(item.ocr_result['text'])
                done_ocr = True

            # Check if we need to pick up any consumables
            needs = consumables.get_needs()
            if needs["mana"] <= 0:
                item_list = [x for x in item_list if "MANA POT" not in x.name]
            if needs["health"] <= 0:
                item_list = [x for x in item_list if "HEALING POT" not in x.name]
            if needs["rejuv"] <= 0:
                item_list = [x for x in item_list if "REJUVENATION POT" not in x.name]
            if needs["tp"] <= 0:
                item_list = [x for x in item_list if "TOWN PORTAL" not in x.name]
            if needs["id"] <= 0:
                item_list = [x for x in item_list if "IDENTIFY" not in x.name]
            if needs["key"] <= 0:
                item_list = [x for x in item_list if "KEY" != x.name]

            # filter out gold less than desired quantity
            if (min_gold := Config().char['min_gold_to_pick']):
                for item in item_list[:]:
                    if "GOLD" == item.name:
                        try:
                            ocr_gold = int(parse.search("{:d} GOLD", item.ocr_result.text).fixed[0])
                        except:
                            ocr_gold = 0
                        if ocr_gold < min_gold:
                            item_list.remove(item)

            all_item_skipped = False
            if len(item_list) == 0:
                # if twice no item was found, break
                found_nothing += 1
                if found_nothing > 1:
                    break
                else:
                    # Maybe we need to move cursor to another position to avoid highlighting items
                    pos_m = convert_abs_to_monitor((0, 0))
                    mouse.move(*pos_m, randomize=[90, 160])
                    time.sleep(0.2)
            else:
                found_nothing = 0
                if order == 'bottom-to-top':
                    item_list.sort(key=lambda x:x.center[0] - x.center[1] * 1.732)
                elif order == 'top-to-bottom':
                    item_list.sort(key=lambda x:x.center[1] * 1.732 - x.center[0])
                else: # nearest first
                    item_list.sort(key=itemgetter('dist'))
                if order is None:
                    closest_item = next((obj for obj in item_list if not any(map(obj["name"].__contains__, ["GOLD", "SCROLL", "KEY"])) and not obj.name in skip_items), None)
                else:
                    closest_item = next((obj for obj in item_list if not obj.name in skip_items), None)
                if not closest_item:
                    if len(skip_items) > 0:
                        Logger.warning(f"All items skipped. Randomly pick one")
                        all_item_skipped = True
                        closest_item = item_list[random.randrange(len(item_list))]
                        skip_items = []
                        curr_item_to_pick = None
                    else:
                        closest_item = item_list[0]

                # check if we trying to pickup the same item for a longer period of time
                force_move = False
                if curr_item_to_pick is not None:
                    is_same_item = (curr_item_to_pick.name == closest_item.name and \
                        abs(curr_item_to_pick.dist - closest_item.dist) < 20)
                    if same_item_timer is None or not is_same_item:
                        same_item_timer = time.time()
                        did_force_move = False
                    elif time.time() - same_item_timer > 1 and not did_force_move:
                        force_move = True
                        did_force_move = True
                    elif time.time() - same_item_timer > 3:
                        # backlist this item type for this pickit round
                        Logger.warning(f"Could not pick up: {closest_item.name}. Continue with other items")
                        skip_items.append(closest_item.name)
                curr_item_to_pick = closest_item

                # To avoid endless teleport or telekinesis loop
                force_pick_up = char.capabilities.can_teleport_natively and \
                                self._last_closest_item is not None and \
                                self._last_closest_item.name == closest_item.name and \
                                abs(self._last_closest_item.dist - closest_item.dist) < 20

                x_m, y_m = convert_screen_to_monitor(closest_item.center)
                if not force_move and (closest_item.dist < Config().ui_pos["item_dist"] or force_pick_up):
                    self._last_closest_item = None
                    # no need to stash potions, scrolls, gold, keys
                    if ("POTION" not in closest_item.name) and ("SCROLL OF" not in closest_item.name) and ("KEY" != closest_item.name):
                        if ("GOLD" != closest_item.name):
                            found_items = True
                    else:
                        # note: key pickup appears to be random between 1 and 5, but set here at minimum of 1 for now
                        consumables.increment_need(closest_item.name.lower(), -1)

                    prev_cast_start = char.pick_up_item((x_m, y_m), item_name=closest_item.name, prev_cast_start=prev_cast_start)
                    if not char.capabilities.can_teleport_natively:
                        time.sleep(0.2)

                    if is_visible(ScreenObjects.Overburdened):
                        found_items = True
                        Logger.warning("Inventory full, terminating pickit!")
                        # TODO: Could think about sth like: Go back to town, stash, come back picking up stuff
                        break
                    else:
                        # send log to discord
                        if found_items and closest_item.name not in picked_up_items:
                            Logger.info(f"Picking up: {closest_item.name} ({closest_item.score*100:.1f}% confidence)")
                        picked_up_items.append(closest_item.name)
                else:
                    if all_item_skipped and char.capabilities.can_teleport_with_charges:
                        char.select_tp()
                        Logger.info("Force teleport to item")
                    else:
                        char.pre_move()
                    char.move((x_m, y_m), force_move=True, force_tp=all_item_skipped)
                    if not char.capabilities.can_teleport_natively:
                        time.sleep(0.25)
                    time.sleep(0.1)
                    # save closeset item for next time to check potential endless loops of not reaching it or of telekinsis/teleport
                    self._last_closest_item = closest_item

        # Make sure not to highlight any items
        mouse.move(*convert_screen_to_monitor((640, 660)))
        keyboard.send(Config().char["show_items"])
        return found_items


if __name__ == "__main__":
    import os
    from config import Config
    from char.sorceress import LightSorc
    from char.paladin import Hammerdin
    from pather import Pather
    import keyboard

    keyboard.add_hotkey('f12', lambda: Logger.info('Force Exit (f12)') or os._exit(1))
    keyboard.wait("f11")
    pather = Pather()
    item_finder = ItemFinder()
    char = Hammerdin(Config().hammerdin, Config().char, pather)
    pickit = PickIt(item_finder)
    print(pickit.pick_up_items(char))
