import keyboard
import time, math
import numpy as np
import cv2
from char.sorceress import Sorceress
import template_finder
from target_detect import get_visible_targets, FILTER_RANGES
from ui_manager import center_mouse
from utils.custom_mouse import mouse
from logger import Logger
from utils.misc import wait
from pather import Location
from screen import convert_abs_to_monitor, convert_screen_to_abs, grab
from config import Config


class NovaSorc(Sorceress):
    def __init__(self, *args, **kwargs):
        Logger.info("Setting up Nova Sorc")
        super().__init__(*args, **kwargs)
        # we want to change positions a bit of end points
        # shenk
        self._pather.offset_node(1148, (66, 32))
        # nihlathak
        self._pather.offset_node(1500, (-62, 22))
        self._pather.offset_node(1505, (60, 23))
        self._pather.offset_node(1510, (58, -28))
        self._pather.offset_node(1515, (-50, -34))
        # avoid nova being detected as mob
        FILTER_RANGES[1]["lh"] = 115

    def _nova(self, time_in_s: float):
        if not self._skill_hotkeys["nova"]:
            raise ValueError("You did not set nova hotkey!")
        keyboard.send(self._skill_hotkeys["nova"])
        time.sleep(0.04)
        start = time.time()
        while (time.time() - start) < time_in_s:
            wait(0.01, 0.02)
            mouse.press(button="right")
            wait(0.12, 0.2)
            mouse.release(button="right")

    def _move_and_attack(self, abs_move: tuple[int, int], atk_len: float):
        pos_m = convert_abs_to_monitor(abs_move)
        self.select_tp()
        self.move(pos_m, force_move=True)
        pos_m = convert_abs_to_monitor((abs_move[0]*0.25, abs_move[1]*0.25))
        mouse.move(*pos_m)
        self._nova(atk_len)

    def kill_pindle(self) -> bool:
        pindle_end = Config().path["pindle_end"][0]
        self._cast_static(0.6)
        self._frozen_orb(convert_screen_to_abs(pindle_end), spray=5)
        self._pather.traverse_nodes_fixed([(pindle_end[0]-180, pindle_end[1]+100)], self)
        self._nova(Config().char["atk_len_pindle"])
        return True

    def kill_eldritch(self) -> bool:
        self._pather.traverse_nodes_fixed([(675, 30)], self)
        self._cast_static(0.6)
        self._nova(Config().char["atk_len_eldritch"])
        self._frozen_orb((-300, -100), [0.1], 5)
        return True

    def kill_shenk(self) -> bool:
        center_mouse()
        self._cast_static(0.6)
        self._nova(Config().char["atk_len_shenk"])
        self._frozen_orb((-300, -140), [0.1], 5)
        return True

    def kill_council(self) -> bool:
        # Check out the node screenshot in assets/templates/trav/nodes to see where each node is at
        atk_len = Config().char["atk_len_trav"] * 0.21
        # change node to be further to the right
        offset_229 = np.array([200, 100])
        self._pather.offset_node(229, offset_229)
        center_mouse()
        self._cast_static(1.0)
        def clear_inside():
            self._frozen_orb((470,-240), [self._cast_duration-0.1], spray=1)
            self._pather.traverse_nodes_fixed([(1110, 120)], self)
            self._pather.traverse_nodes([229], self, timeout=0.8, force_tp=True)
            self._nova(atk_len)
            self._frozen_orb((-300,-150), [self._cast_duration-0.1], spray=5)
            self._move_and_attack((-40, -20), atk_len)
            self._frozen_orb((-300,-150), [self._cast_duration-0.1], spray=5)
            self._move_and_attack((80, 40), atk_len)
        def clear_outside():
            self._pather.traverse_nodes([226], self, timeout=0.8, force_tp=True)
            self._frozen_orb((-300,-150), [self._cast_duration-0.1], spray=5)
            self._nova(atk_len)
            self._frozen_orb((-300,-150), [self._cast_duration-0.1], spray=5)
            self._move_and_attack((45, -20), atk_len)
            self._frozen_orb((300,-160), [self._cast_duration-0.1], spray=5)
            self._move_and_attack((-45, 20), atk_len)
        clear_inside()
        clear_outside()
        clear_inside()
        clear_outside()
        # change back node as it is used in trav.py
        self._pather.offset_node(229, -offset_229)
        return True

    def kill_nihlathak(self, end_nodes: list[int]) -> bool:
        atk_len = Config().char["atk_len_nihlathak"] * 0.33
        # move mouse to center
        center_mouse()
        self._cast_static(0.6)
        self._nova(atk_len)
        self._frozen_orb((300, 250), [self._cast_duration-0.1], spray=5)
        self._move_and_attack((50, 25), atk_len)
        self._frozen_orb((300, -250), [self._cast_duration-0.1], spray=5)
        self._move_and_attack((-80, -40), atk_len)
        self._frozen_orb((-250, 0), spray=5)
        if self._mob_detect:
            delta_x = 0
            delta_y = 0
            for _ in range(4):
                time.sleep(0.5) # nova's blue rings conflict with mob detection
                img = grab(force_new=True).copy()
                if self._skill_hotkeys["oak_sage"]:
                    oak_sage = template_finder.search(["SPIRIT"], img, 0.80, self._summon_roi)
                    if oak_sage.valid:
                        x,y,w,h = tuple(oak_sage.region)
                        pt1 = (x-2, y-8) # include hp bar of summon
                        pt2 = (x+w+1, y+1)
                        img = cv2.rectangle(img, pt1, pt2, (0,0,0), -1)

                targets = get_visible_targets(img, radius_min = 200)
                if len(targets) < 1: break
                rec = []
                for t in targets:
                    rec.insert(0, list(t.roi))
                    rec.insert(0, list(t.roi))
                new_rec, weights = cv2.groupRectangles(rec, 1, 0.5)
                for t in new_rec:
                    cv2.rectangle(img, t[:2], (t[0]+t[2],t[1]+t[3]), (255,200,0), 1)
                for t in new_rec:
                    center = (t[0] + t[2]//2, t[1] + t[3]//2)
                    x, y = convert_screen_to_abs(center)
                    if math.dist((x,y), (delta_x,delta_y)) < 1400:
                        cv2.drawMarker(img, center, color=(255,0,255), markerType=cv2.MARKER_CROSS, thickness=2)
                        break
                else:
                    break

                Logger.info(f"Attacking mob at {x},{y}")
                self._frozen_orb((x, y), [self._cast_duration-0.1], spray=5)
                cv2.imwrite(f"./debug_screenshots/mob_detect_{time.strftime('%m%d_%H%M%S')}.png", img)
                self._move_and_attack((x*0.75, y*0.75), atk_len)
                self._frozen_orb((x*0.25, y*0.25), [self._cast_duration], spray=10)
                delta_x -= x
                delta_y -= y
            if abs(delta_x) > 480 or abs(delta_y) > 270:
                # HACK: convert to automap nodes
                am_node = end_nodes[0] + 999
                self._pather.traverse_nodes_automap([am_node], self, timeout = 3, force_move=True, threshold=0.98)
        return True

    def kill_summoner(self) -> bool:
        # move mouse to below altar
        pos_m = convert_abs_to_monitor((0, 20))
        mouse.move(*pos_m, randomize=80, delay_factor=[0.5, 0.7])
        # Attack
        self._nova(Config().char["atk_len_arc"])
        # Move a bit back and another round
        self._move_and_attack((0, 80), Config().char["atk_len_arc"] * 0.5)
        wait(0.1, 0.15)
        self._nova(Config().char["atk_len_arc"] * 0.5)
        return True


if __name__ == "__main__":
    import os
    import keyboard
    from pather import Pather
    keyboard.add_hotkey('f12', lambda: Logger.info('Force Exit (f12)') or os._exit(1))
    keyboard.wait("f11")
    from config import Config
    pather = Pather()
    char = NovaSorc(Config().nova_sorc, Config().char, pather)
