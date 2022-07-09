import keyboard
from typing import Callable
from utils.custom_mouse import mouse
from char import IChar
import template_finder
from pather import Pather
from screen import grab, convert_abs_to_monitor
from utils.misc import wait
import time, math, random
from pather import Pather
from config import Config
from ui_manager import ScreenObjects, is_visible

class Sorceress(IChar):
    def __init__(self, skill_hotkeys: dict, pather: Pather):
        super().__init__(skill_hotkeys)
        self._pather = pather

    def pick_up_item(self, pos: tuple[float, float], item_name: str = None, prev_cast_start: float = 0):
        if math.dist(pos, self._center_pos) > 150 and self._skill_hotkeys["telekinesis"] and\
        (item_name.endswith('POTION') or item_name.startswith('SCROLL OF') or item_name in ['POTION', 'GOLD']):
            keyboard.send(self._skill_hotkeys["telekinesis"])
            mouse.move(pos[0], pos[1])
            mouse.click(button="right")
            cast_start = time.time()
            # need about 0.4s delay before next capture for the item not to persist on screen
            interval = cast_start - prev_cast_start
            delay = max(0.35, self._cast_duration - interval)
            time.sleep(delay)
            return cast_start
        else:
            return super().pick_up_item(pos, item_name, prev_cast_start)

    def select_by_template(
        self,
        template_type:  str | list[str],
        success_func: Callable = None,
        timeout: float = 4,
        threshold: float = 0.68,
        telekinesis: bool = False,
        dynamic: bool = False
    ) -> bool:
        # In case telekinesis is False or hotkey is not set, just call the base implementation
        if not self._skill_hotkeys["telekinesis"] or not telekinesis:
            return super().select_by_template(template_type, success_func, timeout, threshold)
        if type(template_type) == list and "A5_STASH" in template_type:
            # sometimes waypoint is opened and stash not found because of that, check for that
            if is_visible(ScreenObjects.WaypointLabel):
                keyboard.send("esc")
        start = time.time()
        keyboard.send(self._skill_hotkeys["telekinesis"])
        prev_center = (0,0)
        while timeout is None or time.time() - start < timeout:
            template_match = template_finder.search(template_type, grab(), threshold=threshold)
            if template_match.valid:
                mouse.move(*template_match.center_monitor, is_async=True)
                if dynamic and math.dist(prev_center,template_match.center) > 3:
                    prev_center = template_match.center
                    time.sleep(0.1)
                    continue
                else:
                    mouse.sync()
                    mouse.click(button="right")
                # check the successfunction for 2 sec, if not found, try again
                check_success_start = time.time()
                while time.time() - check_success_start < 2:
                    if success_func is None or success_func():
                        return True
        # In case telekinesis fails, try again with the base implementation
        return super().select_by_template(template_type, success_func, timeout, threshold)

    def pre_buff(self):
        if Config().char["cta_available"]:
            self._pre_buff_cta()
        if self._skill_hotkeys["energy_shield"]:
            keyboard.send(self._skill_hotkeys["energy_shield"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        if self._skill_hotkeys["thunder_storm"]:
            keyboard.send(self._skill_hotkeys["thunder_storm"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        if self._skill_hotkeys["frozen_armor"]:
            keyboard.send(self._skill_hotkeys["frozen_armor"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)

    def _cast_static(self, duration: float = 1.4):
        if self._skill_hotkeys["static_field"]:
            keyboard.send(self._skill_hotkeys["static_field"])
            wait(0.1, 0.13)
            start = time.time()
            while time.time() - start < duration:
                mouse.click(button="right")
                wait(self._cast_duration)

    def _frozen_orb(self, cast_pos_abs: tuple[float, float], delay: tuple[float, float] = (0.2, 0.3), spray: float = 10):
        if self._skill_hotkeys["frozen_orb"]:
            keyboard.send(self._skill_hotkeys["frozen_orb"])
            for _ in range(1):
                x = cast_pos_abs[0] + (random.random() * 2 * spray - spray)
                y = cast_pos_abs[1] + (random.random() * 2 * spray - spray)
                cast_pos_monitor = convert_abs_to_monitor((x, y), avoid_hud=True)
                mouse.move(*cast_pos_monitor)
                mouse.press(button="right")
                wait(*delay)
                mouse.release(button="right")
