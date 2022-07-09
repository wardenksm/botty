import keyboard
from ui_manager import center_mouse
from utils.custom_mouse import mouse
from char import IChar
from logger import Logger
from screen import convert_abs_to_monitor, convert_screen_to_abs, grab
from config import Config
from utils.misc import wait, rotate_vec, unit_vector
import random
from pather import Location, Pather
import template_finder
import numpy as np
import cv2, time, math

class Trapsin(IChar):
    def __init__(self, skill_hotkeys: dict, pather: Pather):
        Logger.info("Setting up Trapsin")
        super().__init__(skill_hotkeys)
        self._pather = pather
        self._pather.offset_node(103, [120, -20])
        self._pather.offset_node(104, [-120, 20])

    def town_buff(self):
        if self._skill_hotkeys["burst_of_speed"]:
            keyboard.send(self._skill_hotkeys["burst_of_speed"])
            wait(0.05, 0.1)
            mouse.click(button="right")

    def pre_buff(self):
        if Config().char["cta_available"]:
            self._pre_buff_cta()
        if self._skill_hotkeys["fade"]:
            keyboard.send(self._skill_hotkeys["fade"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        if self._skill_hotkeys["blade_shield"]:
            keyboard.send(self._skill_hotkeys["blade_shield"])
            wait(0.05, 0.1)
            mouse.click(button="right")
            wait(self._cast_duration)

    def _fire_blast(self, cast_pos_abs: tuple[float, float], spray: int, monster = None):
        keyboard.send(Config().char["stand_still"], do_release=False)
        if self._skill_hotkeys["skill_left"]:
            keyboard.send(self._skill_hotkeys["skill_left"])
        cast_pos_monitor = convert_abs_to_monitor(cast_pos_abs)
        mouse.move(*cast_pos_monitor)
        mouse.press(button="left")
        prev_time = start_time = time.perf_counter()
        while True:
            if monster is not None:
                img = grab()
                found_name_bar = self.find_name_bar(img, monster)
                new_monster_pos = self.find_monster_pos(img, monster)
                if new_monster_pos is not None:
                    # left attack needs to follow the target
                    #Logger.debug(f"Found monster at {new_monster_pos}")
                    cast_pos_abs = convert_screen_to_abs(new_monster_pos)
                elif not found_name_bar:
                    if self._name_bar_gone_cnt >= 0:
                        self._name_bar_gone_cnt += 1
                    #Logger.debug("Could not find monster")
                    # assuming monster is moving towards you
                    pass #cast_pos_abs = (cast_pos_abs[0] * 0.95, cast_pos_abs[1] * 0.95)

            name_lock = monster is None or found_name_bar
            x = cast_pos_abs[0] + (random.random() - 0.75)*spray
            y = cast_pos_abs[1] + (random.random() - 0.25)*spray
            cast_pos_monitor = convert_abs_to_monitor((x, y))
            if name_lock:
                mouse.move(*cast_pos_monitor)
                curr_time = time.perf_counter()
                delta = 0.04 - curr_time + prev_time
                if delta > 0:
                    time.sleep(delta)
                    prev_time = time.perf_counter()
                else:
                    prev_time = curr_time
            if not name_lock:
                mouse.move(*cast_pos_monitor)
                mouse.release(button="left")
                time.sleep(0.04)
                mouse.press(button="left")
                prev_time = time.perf_counter()

            if prev_time - start_time > 1.5:
                break
        time.sleep(0.04)
        mouse.release(button="left")
        keyboard.send(Config().char["stand_still"], do_press=False)
        return cast_pos_abs

    def _lay_lightning_sentry(self, cast_pos_abs: tuple[float, float], spray: float, num_traps = 4, monster = None):
        keyboard.send(self._skill_hotkeys["lightning_sentry"])
        x = cast_pos_abs[0] * 0.5
        y = cast_pos_abs[1] * 0.5
        cast_pos_monitor = convert_abs_to_monitor((x, y))
        mouse.move(*cast_pos_monitor)
        mouse.press(button="right")
        prev_time = start_time = time.perf_counter()
        while True:
            if monster is not None:
                img = grab()
                self.find_name_bar(img, monster)
                new_monster_pos = self.find_monster_pos(img, monster)

            x = cast_pos_abs[0] + (random.random() - 0.5)*spray
            y = cast_pos_abs[1] + (random.random() - 0.5)*spray
            cast_pos_monitor = convert_abs_to_monitor((x, y))
            mouse.move(*cast_pos_monitor)
            curr_time = time.perf_counter()
            delta = 0.04 - curr_time + prev_time
            if delta > 0:
                time.sleep(delta)
                prev_time = time.perf_counter()
            else:
                prev_time = curr_time
            if prev_time - start_time > num_traps * self._attack_duration:
                break
        mouse.release(button="right")
        if monster is not None and new_monster_pos is not None:
            return convert_screen_to_abs(new_monster_pos)
        else:
            return cast_pos_abs

    def _lay_death_sentry(self, cast_pos_abs: tuple[float, float]):
        keyboard.send(self._skill_hotkeys["death_sentry"])
        cast_pos_monitor = convert_abs_to_monitor(cast_pos_abs)
        mouse.move(*cast_pos_monitor)
        mouse.press(button="right")
        time.sleep(0.1)
        mouse.release(button="right")

    def _shock_web(self, cast_pos_abs: tuple[float, float], spray: int, atk_len = 3, monster = None):
        keyboard.send(self._skill_hotkeys["shock_web"])
        x = cast_pos_abs[0] * 0.5
        y = cast_pos_abs[1] * 0.5
        cast_pos_monitor = convert_abs_to_monitor((x, y))
        mouse.move(*cast_pos_monitor)
        mouse.click(button="right")
        for _ in range(atk_len - 1):
            cast_time = time.perf_counter()
            if monster is not None:
                img = grab()
                found_name_bar = self.find_name_bar(img, monster)
                new_monster_pos = self.find_monster_pos(img, monster)
                if new_monster_pos is not None:
                    cast_pos_abs = convert_screen_to_abs(new_monster_pos)
                elif not found_name_bar:
                    if self._name_bar_gone_cnt >= 0:
                        self._name_bar_gone_cnt += 2

            x = cast_pos_abs[0] + (random.random() - 0.5)*spray
            y = cast_pos_abs[1] + (random.random() - 0.5)*spray
            cast_pos_monitor = convert_abs_to_monitor((x, y))
            mouse.move(*cast_pos_monitor)
            curr_time = time.perf_counter()
            delta = 0.6 + self._attack_duration - curr_time + cast_time
            if delta > 0:
                time.sleep(delta)
            mouse.click(button="right")
        return cast_pos_abs

    def kill_pindle(self) -> bool:
        atk_len = max(1, int(Config().char["atk_len_pindle"]))
        self._found_monster_bar = False
        self._immunities = ''
        self._name_bar_gone_cnt = -1
        self._monster_gone_cnt = 0
        self._monster_hp = 1.0
        if self._skill_hotkeys["cloak_of_shadows"]:
            keyboard.send(self._skill_hotkeys["cloak_of_shadows"])
            wait(0.05, 0.1)
            mouse.click(button="right")
        pindle_img = grab()
        pindle_pos = self.find_monster_pos(pindle_img, "pindle")
        if pindle_pos is None:
            pindle_pos_abs = self._pather.find_abs_node_pos(104, pindle_img, threshold=0.75)
            if pindle_pos_abs is None or not (0 > math.atan2(pindle_pos_abs[1], pindle_pos_abs[0]) > -math.pi*0.5):
                Logger.warning(f"Invalid pindle_pos_abs at {pindle_pos_abs}")
                pindle_pos = Config().path["pindle_end"][0]
                cv2.imwrite(f"./info_screenshots/invalid_pindle_pos_{time.strftime('%H%M%S')}.png", pindle_img)
            found_pindle = False
        else:
            found_pindle = True
        if pindle_pos is not None:
            pindle_pos_abs = convert_screen_to_abs(pindle_pos)
        cast_pos_monitor = convert_abs_to_monitor((pindle_pos_abs[0]+50, pindle_pos_abs[1]+10))
        mouse.move(*cast_pos_monitor)
        #pindle_img = grab()
        if self._skill_hotkeys["shadow_warrior"]:
            keyboard.send(self._skill_hotkeys["shadow_warrior"])
            wait(self._cast_duration, self._cast_duration + 0.04)
            mouse.click(button="right")
        #if not self.find_name_bar(pindle_img, "pindle") and found_pindle:
            #cv2.imwrite(f"./info_screenshots/no_pindle_bar_{time.strftime('%H%M%S')}.png",
                        #cv2.circle(np.array(pindle_img), pindle_pos, radius=4, color=(0,0,255), thickness=1))
        cast_pos_abs = [pindle_pos_abs[0] * 0.8, pindle_pos_abs[1] * 0.8]

        cast_pos_abs = self._lay_lightning_sentry(cast_pos_abs, 30, 4, "pindle")
        cast_pos_abs = self._fire_blast(cast_pos_abs, 10, "pindle")
        self._lay_death_sentry(cast_pos_abs)
        cast_pos_abs = self._fire_blast(cast_pos_abs, 10, "pindle")

        #keep attacking until pindle is dead
        self._fe_explosin_cnt = 0
        for _ in range(atk_len):
            if self._skill_hotkeys["shadow_warrior"] and not template_finder.search(["SHADOW"], grab(), 0.80, self._summon_roi).valid:
                keyboard.send(self._skill_hotkeys["shadow_warrior"])
                wait(self._cast_duration+0.1, self._cast_duration + 0.15)
                mouse.click(button="right")
            else:
                wait(0.5, 0.6)
            if self._monster_hp < 0.75:
                Logger.info(f"Pindle hp = {round(self._monster_hp * 100)}%")
            if 'f' in self._immunities:
                cast_pos_abs = self._shock_web(cast_pos_abs, 20, 3, "pindle")
            else:
                cast_pos_abs = self._fire_blast(cast_pos_abs, 5, "pindle")
            if self._monster_gone_cnt + self._name_bar_gone_cnt + self._fe_explosin_cnt > self._monster_hp * 9:
                Logger.debug(f"Pindle dead")
                break
        #time.sleep(0.1)
        self._lay_death_sentry(cast_pos_abs)
        if self._skill_hotkeys["dragon_flight"]:
            keyboard.send(self._skill_hotkeys["dragon_flight"])
            wait(self._cast_duration+0.08, self._cast_duration + 0.12)
            mouse.click(button="right")

        # Move to items
        if self.capabilities.can_teleport_natively:
            self._pather.traverse_nodes_fixed("pindle_end", self)
        else:
            self._pather.traverse_nodes((Location.A5_PINDLE_SAFE_DIST, Location.A5_PINDLE_END), self, force_tp=True)
        return True

    def kill_eldritch(self) -> bool:
        atk_len = max(1, int(Config().char["atk_len_eldritch"] / 2))
        self._found_monster_bar = False
        self._immunities = ''
        self._name_bar_gone_cnt = -1
        self._monster_gone_cnt = 0
        self._monster_hp = 1.0
        eld_pos_abs = convert_screen_to_abs(Config().path["eldritch_end"][0])
        cast_pos_abs = [eld_pos_abs[0] * 0.9, eld_pos_abs[1] * 0.9]
        if self._skill_hotkeys["shadow_warrior"]:
            keyboard.send(self._skill_hotkeys["shadow_warrior"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        if self._skill_hotkeys["cloak_of_shadows"]:
            keyboard.send(self._skill_hotkeys["cloak_of_shadows"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        self._lay_lightning_sentry(cast_pos_abs, 90)
        self._fire_blast(cast_pos_abs, 50)
        self.find_name_bar(grab(), "eldritch")
        self._lay_death_sentry(cast_pos_abs)
        
        cast_pos_abs = [eld_pos_abs[0] * 0.75, eld_pos_abs[1] * 0.75]
        for _ in range(atk_len):
            if self._skill_hotkeys["shadow_warrior"] and not template_finder.search(["SHADOW"], grab(), 0.80, self._summon_roi).valid:
                keyboard.send(self._skill_hotkeys["shadow_warrior"])
                wait(self._cast_duration+0.1, self._cast_duration + 0.15)
                mouse.click(button="right")
            if self._monster_hp < 0.75:
                Logger.info(f"Eldritch hp = {round(self._monster_hp * 100)}%")
            if self._found_monster_bar and 'f' in self._immunities:
                cast_pos_abs = self._shock_web(cast_pos_abs, 20, 3, "eldritch")
                time.sleep(0.6)
            else:
                cast_pos_abs = self._fire_blast(cast_pos_abs, 5, "eldritch")
            if self._name_bar_gone_cnt > self._monster_hp * 4:
                Logger.debug("Eldritch dead")
                break

        if self._skill_hotkeys["dragon_flight"]:
            keyboard.send(self._skill_hotkeys["dragon_flight"])
            wait(self._cast_duration+0.08, self._cast_duration + 0.12)
            mouse.click(button="right")

        # Move to items
        if self.capabilities.can_teleport_natively:
            self._pather.traverse_nodes_fixed("eldritch_end", self)
        else:
            self._pather.traverse_nodes((Location.A5_ELDRITCH_SAFE_DIST, Location.A5_ELDRITCH_END), self, timeout=0.6, force_tp=True)
        return True

    def kill_shenk(self) -> bool:
        atk_len = max(1, int(Config().char["atk_len_shenk"] / 2))
        shenk_pos_abs = self._pather.find_abs_node_pos(149, grab())
        if shenk_pos_abs is None:
            shenk_pos_abs = convert_screen_to_abs(Config().path["shenk_end"][0])
        cast_pos_abs = [shenk_pos_abs[0] * 0.9, shenk_pos_abs[1] * 0.9]
        if self._skill_hotkeys["shadow_warrior"]:
            keyboard.send(self._skill_hotkeys["shadow_warrior"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        if self._skill_hotkeys["cloak_of_shadows"]:
            keyboard.send(self._skill_hotkeys["cloak_of_shadows"])
            wait(0.1, 0.13)
            mouse.click(button="right")
            wait(self._cast_duration)
        self._lay_lightning_sentry(cast_pos_abs, 90)
        self._fire_blast(cast_pos_abs, 90)
        self._lay_death_sentry(cast_pos_abs)
        roi = Config().ui_roi["cut_skill_bar"]
        for _ in range(atk_len):
            self._fire_blast(shenk_pos_abs, 90)
            if template_finder.search(["SHENK_DEATH_0", "SHENK_DEATH_1", "SHENK_DEATH_2", "SHENK_DEATH_3", "SHENK_DEATH_4"],
                                      grab(), roi=roi).valid:
                break
        # Move to items
        #wait(self._cast_duration, self._cast_duration + 0.2)
        self._pather.traverse_nodes((Location.A5_SHENK_SAFE_DIST, Location.A5_SHENK_END), self, timeout=1.4, force_tp=True)
        return True

    def kill_nihlathak(self, end_nodes: list[int]) -> bool:
        # Find nilhlatak position
        atk_len = max(1, int(Config().char["atk_len_nihlathak"] / 2))
        for i in range(atk_len):
            nihlathak_pos_abs = self._pather.find_abs_node_pos(end_nodes[-1], grab())
            if nihlathak_pos_abs is None:
                return False
            cast_pos_abs = np.array([nihlathak_pos_abs[0] * 0.9, nihlathak_pos_abs[1] * 0.9])
            if self._skill_hotkeys["shadow_warrior"]:
                keyboard.send(self._skill_hotkeys["shadow_warrior"])
                wait(0.1, 0.13)
                mouse.click(button="right")
                wait(self._cast_duration)
            if self._skill_hotkeys["cloak_of_shadows"]:
                keyboard.send(self._skill_hotkeys["cloak_of_shadows"])
                wait(0.1, 0.13)
                mouse.click(button="right")
                wait(self._cast_duration)
            self._fire_blast(cast_pos_abs, 90)
            self._lay_lightning_sentry(cast_pos_abs, 90)
            self._lay_death_sentry(cast_pos_abs)
            self._fire_blast(cast_pos_abs, 90)
            # Do some tele "dancing" after each sequence
            if i < atk_len - 1:
                rot_deg = random.randint(-10, 10) if i % 2 == 0 else random.randint(170, 190)
                tele_pos_abs = unit_vector(rotate_vec(cast_pos_abs, rot_deg)) * 100
                pos_m = convert_abs_to_monitor(tele_pos_abs)
                self.pre_move()
                self.move(pos_m)
        # Move to items
        wait(self._cast_duration, self._cast_duration + 0.2)
        self._pather.traverse_nodes(end_nodes, self, timeout=0.8)
        return True


if __name__ == "__main__":
    import os
    import keyboard
    keyboard.add_hotkey('f12', lambda: Logger.info('Force Exit (f12)') or os._exit(1))
    keyboard.wait("f11")
    from config import Config
    from char import Trapsin
    pather = Pather()
    char = Trapsin(Config().trapsin, Config().char, pather)