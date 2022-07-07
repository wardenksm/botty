from typing import Callable
from dataclasses import dataclass
import time, math, random
import cv2
from item import consumables
import health_manager
import keyboard
import numpy as np
from char.capabilities import CharacterCapabilities
from ui_manager import is_visible, wait_until_visible, detect_screen_object, ScreenObjects, get_closest_non_hud_pixel
from ui import skills
from utils.custom_mouse import mouse
from utils.misc import wait, cut_roi, is_in_roi, color_filter, arc_spread
from logger import Logger
from config import Config
from screen import grab, convert_monitor_to_screen, convert_screen_to_abs, convert_abs_to_monitor, convert_screen_to_monitor
import template_finder
from inventory import personal, common, belt

@dataclass
class MonsterInfo:
    range: np.ndarray
    roi: list[int]
    name_bar: list[str]
    hp_width: int
    color_check: Callable

monster_info = {
    "pindle": MonsterInfo(
        range = np.array([[86,34,32],[98,63,156]]),
        roi = Config().ui_roi["pindle_fight"],
        name_bar = ["PINDLE_BAR_1", "PINDLE_BAR_2"],
        hp_width = 62,
        color_check = lambda mean: mean[2] > mean[0] * 1.05
    ),
    "eldritch": MonsterInfo(
        range = np.array([[78,24,63],[93,59,199]]),
        roi = Config().ui_roi["eldritch"],
        name_bar = ["ELDRITCH_BAR_1", "ELDRITCH_BAR_2", "ELDRITCH_BAR_3"],
        hp_width = 120,
        color_check = None
    ),
    "nihlathak": MonsterInfo(
        range = None,
        roi = None,
        name_bar = ["NIHL_BAR_1"],
        hp_width = 0,
        color_check = None
    )
}

fe_range = np.array([[7,164,104],[15,202,129]])

class IChar:
    _CrossGameCapabilities: None | CharacterCapabilities = None

    def __init__(self, skill_hotkeys: dict):
        self._skill_hotkeys = skill_hotkeys
        self._last_tp = time.time()
        # Add a bit to be on the save side
        self._cast_duration = Config().char["casting_frames"] * 0.04 + 0.01
        self.damage_scaling = float(Config().char.get("damage_scaling", 1.0))
        if Config().char["attack_frames"]:
            self._attack_duration = Config().char["attack_frames"] * 0.04 + 0.01
        else:
            self._attack_duration = self._cast_duration

        self._fe_explosin_cnt = 0
        self._found_monster_bar = False
        self._monster_gone_cnt = 0
        self._name_bar_gone_cnt = 0
        self._immunities = None
        self._immunity_dict = dict({
            "l": Config().colors["yellow"],
            "f": Config().colors["red"],
            "c": Config().colors["blue"],
            "p": Config().colors["green"]
        })
        self._monster_hp = 1.0
        self._summon_roi = [14,20,116,40]
        self._enemy_info_roi = Config().ui_roi["enemy_info"]
    
        self.capabilities = None
        self._active_skill = {
            "left": "",
            "right": ""
        }
        self._use_safer_routines = Config().char["safer_routines"]

    def _set_active_skill(self, mouse_click_type: str = "left", skill: str =""):
        self._active_skill[mouse_click_type] = skill

    def _select_skill(self, skill: str, mouse_click_type: str = "left", delay: float | list | tuple = None):
        if not (
            skill in self._skill_hotkeys and (hotkey := self._skill_hotkeys[skill])
            or (skill in Config().char and (hotkey := Config().char[skill]))
        ):
            Logger.warning(f"No hotkey for skill: {skill}")
            self._set_active_skill(mouse_click_type, "")
            return False

        if self._active_skill[mouse_click_type] != skill:
            keyboard.send(hotkey)
        self._set_active_skill(mouse_click_type, skill)
        if delay:
            try:
                wait(*delay)
            except:
                try:
                    wait(delay)
                except Exception as e:
                    Logger.warning(f"_select_skill: Failed to delay with delay: {delay}. Exception: {e}")
        return True

    def _discover_capabilities(self) -> CharacterCapabilities:
        override = Config().advanced_options["override_capabilities"]
        if override is None:
            if Config().char["teleport"]:
                if self.select_tp():
                    if self.skill_is_charged():
                        return CharacterCapabilities(can_teleport_natively=False, can_teleport_with_charges=True)
                    else:
                        return CharacterCapabilities(can_teleport_natively=True, can_teleport_with_charges=False)
                return CharacterCapabilities(can_teleport_natively=False, can_teleport_with_charges=True)
            else:
                return CharacterCapabilities(can_teleport_natively=False, can_teleport_with_charges=False)
        else:
            Logger.debug(f"override_capabilities is set to {override}")
            return CharacterCapabilities(
                can_teleport_natively="can_teleport_natively" in override,
                can_teleport_with_charges="can_teleport_with_charges" in override
            )

    def find_immune(self, img) -> str:
        immunity = ''
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        for i in self._immunity_dict:
            lower = self._immunity_dict[i][0]
            higher = self._immunity_dict[i][1]
            mask = cv2.inRange(hsv, lower, higher)
            if cv2.countNonZero(mask) > 160:
                immunity += i
        return immunity

    def check_monster_hp(self, img) -> float:
        red_blue = np.int16(img[:,:,2]) - np.int16(img[:,:,0])
        _, mask = cv2.threshold(red_blue, 50, 255, cv2.THRESH_BINARY)
        return cv2.countNonZero(mask) / mask.size

    def find_monster_pos(self, img, name:str):
        monster = monster_info[name]
        bgr = cut_roi(img, monster.roi)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        #check FE explosion of pindleskin death
        mask = cv2.inRange(hsv, fe_range[0], fe_range[1])
        kernel = np.ones((2, 2), 'uint8')
        mask = cv2.erode(mask, kernel, None, iterations=1)
        cnt = cv2.countNonZero(mask)
        if cnt > 300:
            #Logger.info(f"Found FE explosion! {cnt}")
            self._fe_explosin_cnt += 1

        #check monster
        mask = cv2.inRange(hsv, monster.range[0], monster.range[1])
        kernel = np.ones((2, 1), 'uint8')
        mask = cv2.erode(mask, kernel, None, iterations=1)
        if cv2.countNonZero(mask) < 4:
            self._monster_gone_cnt += 1
            return None
        dist = cv2.distanceTransform(~mask, cv2.DIST_L1, cv2.DIST_MASK_3)
        k = 30
        bw = np.uint8(dist < k)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        bw2 = cv2.morphologyEx(bw, cv2.MORPH_ERODE, kernel)
        contours, _ = cv2.findContours(bw2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_area = 10
        largest_contour = -1
        for i,c in enumerate(contours):
            area = cv2.contourArea(c)
            if area > max_area:
                if monster.color_check is not None:
                    contour_mask = np.zeros(bgr.shape, np.uint8)
                    cv2.drawContours(contour_mask, contours, i, (255,255,255), -1)
                    mean = cv2.mean(bgr, contour_mask[:,:,0])
                    if not monster.color_check(mean):
                        continue
                max_area = area
                largest_contour = i
        if largest_contour < 0:
            return None
        m = cv2.moments(contours[largest_contour])
        x = round(m['m10']/m['m00']) + monster.roi[0]
        y = round(m['m01']/m['m00']) + monster.roi[1] - 5
        self._monster_gone_cnt = 0
        return x, 0 if y < 0 else y

    def find_name_bar(self, img, name:str) -> bool:
        monster = monster_info[name]
        x,y,w,h = self._enemy_info_roi
        name_img = img[y:y+h,x:x+w]
        if template_finder.search(monster.name_bar, name_img, threshold=0.75).valid:
            if monster.hp_width:
                hp_img = cv2.addWeighted(img[20:23, 640-monster.hp_width:640+monster.hp_width], 0.5,
                                         img[23:26, 640-monster.hp_width:640+monster.hp_width], 0.5, 0)
                self._monster_hp = self.check_monster_hp(hp_img)
                percent = round(self._monster_hp*100)
            self._immunities = self.find_immune(name_img[50:350,50:])
            self._found_monster_bar = True
            #Logger.info(f"Found name bar! Immunity: {self._immunities}")
            self._monster_gone_cnt = 0
            self._name_bar_gone_cnt = 0
            self._fe_explosin_cnt = 0
            return True
        return False

    def discover_capabilities(self, force = False):
        if IChar._CrossGameCapabilities is None or force:
            capabilities = self._discover_capabilities()
            self.capabilities = capabilities
        Logger.info(f"Capabilities: {self.capabilities}")
        self.on_capabilities_discovered(self.capabilities)

    def on_capabilities_discovered(self, capabilities: CharacterCapabilities):
        pass

    def pick_up_item(self, pos: tuple[float, float], item_name: str = None, prev_cast_start: float = 0):
        mouse.move(pos[0], pos[1])
        time.sleep(0.1)
        mouse.click(button="left")
        wait(0.25, 0.3)
        return prev_cast_start

    def select_by_template(
        self,
        template_type:  str | list[str],
        success_func: Callable = None,
        timeout: float = 8,
        threshold: float = 0.68,
        telekinesis: bool = False
    ) -> bool:
        """
        Finds any template from the template finder and interacts with it
        :param template_type: Strings or list of strings of the templates that should be searched for
        :param success_func: Function that will return True if the interaction is successful e.g. return True when loading screen is reached, defaults to None
        :param timeout: Timeout for the whole template selection, defaults to None
        :param threshold: Threshold which determines if a template is found or not. None will use default form .ini files
        :return: True if success. False otherwise
        """
        if type(template_type) == list and "A5_STASH" in template_type:
            # sometimes waypoint is opened and stash not found because of that, check for that
            if is_visible(ScreenObjects.WaypointLabel):
                keyboard.send("esc")
        start = time.time()
        while timeout is None or (time.time() - start) < timeout:
            template_match = template_finder.search(template_type, grab(), threshold=threshold)
            if template_match.valid:
                Logger.debug(f"Select {template_match.name} ({template_match.score*100:.1f}% confidence)")
                mouse.move(*template_match.center_monitor)
                wait(0.2, 0.3)
                mouse.click(button="left")
                # check the successfunction for 2 sec, if not found, try again
                check_success_start = time.time()
                while time.time() - check_success_start < 2:
                    if success_func is None or success_func():
                        return True
        Logger.error(f"Wanted to select {template_type}, but could not find it")
        return False

    def skill_is_charged(self, img: np.ndarray = None) -> bool:
        if img is None:
            img = grab()
        skill_img = cut_roi(img, Config().ui_roi["skill_right"])
        charge_mask, _ = color_filter(skill_img, Config().colors["blue"])
        if np.sum(charge_mask) > 0:
            return True
        return False

    def is_low_on_teleport_charges(self):
        img = grab()
        charges_remaining = skills.get_skill_charges(img)
        if charges_remaining:
            Logger.debug(f"{charges_remaining} teleport charges remain")
            return charges_remaining <= 3
        else:
            charges_present = self.skill_is_charged(img)
            if charges_present:
                Logger.error("is_low_on_teleport_charges: unable to determine skill charges, assume zero")
            return True

    def _remap_skill_hotkey(self, skill_asset, hotkey, skill_roi, expanded_skill_roi):
        x, y, w, h = skill_roi
        x, y = convert_screen_to_monitor((x, y))
        mouse.move(x + w/2, y + h / 2)
        mouse.click("left")
        wait(0.3)
        match = template_finder.search(skill_asset, grab(), threshold=0.84, roi=expanded_skill_roi)
        if match.valid:
            mouse.move(*match.center_monitor)
            wait(0.3)
            keyboard.send(hotkey)
            wait(0.3)
            mouse.click("left")
            wait(0.3)

    def remap_right_skill_hotkey(self, skill_asset, hotkey):
        return self._remap_skill_hotkey(skill_asset, hotkey, Config().ui_roi["skill_right"], Config().ui_roi["skill_right_expanded"])

    def select_tp(self):
        return skills.select_tp(Config().char["teleport"])

    def pre_move(self):
        # if teleport hotkey is set and if teleport is not already selected
        if self.capabilities.can_teleport_natively:
            self.select_tp()
            self._set_active_skill("right", "teleport")

    def move(self, pos_monitor: tuple[float, float], force_tp: bool = False, force_move: bool = False):
        factor = Config().advanced_options["pathing_delay_factor"]
        if "teleport" in Config().char and Config().char["teleport"] and (
            force_tp
            or (
                skills.is_right_skill_selected(["TELE_ACTIVE"])
                and skills.is_right_skill_active()
            )
        ):
            self._set_active_skill("right", "teleport")
            mouse.move(pos_monitor[0], pos_monitor[1], randomize=3, delay_factor=[factor*0.1, factor*0.14])
            mouse.click(button="right")
            time.sleep(self._cast_duration+0.01)
        else:
            # in case we want to walk we actually want to move a bit before the point cause d2r will always "overwalk"
            pos_screen = convert_monitor_to_screen(pos_monitor)
            pos_abs = convert_screen_to_abs(pos_screen)
            dist = math.dist(pos_abs, (0, 0))
            min_wd = max(10, Config().ui_pos["min_walk_dist"])
            max_wd = random.randint(int(Config().ui_pos["max_walk_dist"] * 0.65), Config().ui_pos["max_walk_dist"])
            adjust_factor = max(max_wd, min(min_wd, dist - 50)) / max(min_wd, dist)
            pos_abs = [int(pos_abs[0] * adjust_factor), int(pos_abs[1] * adjust_factor)]
            x, y = convert_abs_to_monitor(pos_abs)
            mouse.move(x, y, randomize=5, delay_factor=[factor*0.1, factor*0.14])
            if force_move:
                keyboard.send(Config().char["force_move"])
            else:
                mouse.click(button="left")

    def walk(self, pos_abs: tuple[float, float], force_move: bool = False):
        factor = Config().advanced_options["pathing_delay_factor"]
        # in case we want to walk we actually want to move a bit before the point cause d2r will always "overwalk"
        dist = math.dist(pos_abs, (0, 0))
        min_wd = max(10, Config().ui_pos["min_walk_dist"])
        max_wd = random.randint(int(Config().ui_pos["max_walk_dist"] * 0.65), Config().ui_pos["max_walk_dist"])
        adjust_factor = max(max_wd, min(min_wd, dist - 50)) / max(min_wd, dist)
        pos_abs = [int(pos_abs[0] * adjust_factor), int(pos_abs[1] * adjust_factor)]
        x, y = convert_abs_to_monitor(pos_abs)
        mouse.move(x, y, randomize=5, delay_factor=[factor*0.1, factor*0.14])
        wait(0.012, 0.02)
        if force_move:
            keyboard.send(Config().char["force_move"])
        else:
            mouse.click(button="left")

    def cast_tp(self):
        # cast from belt
        if belt.tp_column >= 0:
            if consumables.get_needs("tp") > 10:
                # Do not use up all tp scrolls in belt
                return False
            key = f"potion{belt.tp_column+1}"
            keyboard.send(Config().char[key])
            consumables.increment_need("tp", 5)
            return True
        # cast from skill hotkey
        if skills.has_tps():
            mouse.click(button="right")
            consumables.increment_need("tp", 1)
            time.sleep(self._cast_duration)
            return True
        # cast from inventory
        health_manager.set_pause_state(True)
        img = personal.open()
        match = template_finder.search(
            ["INV_SCROLL_TP", "TP_TOME"], img,
            roi = Config().ui_roi["right_inventory"],
            best_match = True
        )
        success = False
        if match.valid:
            mouse.move(*match.center_monitor)
            mouse.click("right")
            consumables.increment_need("tp", 1)
            success = True
        common.close()
        health_manager.set_pause_state(False)
        return success

    def tp_town(self):
        # will check if tp is available and select the skill
        if not self.cast_tp():
            return False
        roi_mouse_move = [
            int(Config().ui_pos["screen_width"] * 0.3),
            0,
            int(Config().ui_pos["screen_width"] * 0.4),
            int(Config().ui_pos["screen_height"] * 0.7)
        ]
        pos_away = convert_abs_to_monitor((-167, -30))
        wait(0.56, 0.6) # takes quite a while for tp to be visible
        start = time.time()
        retry_count = 0
        while (time.time() - start) < 8:
            if time.time() - start > 3.7 and retry_count == 0:
                retry_count += 1
                Logger.debug("Move to another position and try to open tp again")
                pos_m = convert_abs_to_monitor((random.randint(-70, 70), random.randint(-70, 70)))
                self.pre_move()
                self.move(pos_m)
                if self.cast_tp():
                    wait(0.56, 0.6) # takes quite a while for tp to be visible
            pos = None
            img = grab()
            if (template_match := detect_screen_object(ScreenObjects.TownPortal, img)).valid:
                pos = template_match.center_monitor
                # Note: Template is top of portal, thus move the y-position a bit to the bottom
                pos = (pos[0], pos[1] + 30)
            else:
                # Look for the blue circle
                tp_img = cut_roi(img, Config().ui_roi["tp_search"])
                hsv = cv2.cvtColor(tp_img, cv2.COLOR_BGR2HSV)
                color_range = Config().colors["blue_portal"]
                mask = cv2.inRange(hsv, color_range[0], color_range[1])
                kernel = np.ones((2, 2), 'uint8')
                mask = cv2.erode(mask, kernel, None, iterations=1)
                if cv2.countNonZero(mask) > 100:
                    m = cv2.moments(mask)
                    x = round(m['m10']/m['m00']) + Config().ui_roi["tp_search"][0]
                    y = round(m['m01']/m['m00']) + Config().ui_roi["tp_search"][1]
                    pos = convert_screen_to_monitor((x, y))
            if pos is not None:
                mouse.move(*pos, randomize=6, delay_factor=[0.9, 1.1])
                mouse.click(button="left")
                if wait_until_visible(ScreenObjects.Loading, 2).valid:
                    return True
            # move mouse away to not overlay with the town portal if mouse is in center
            pos_screen = convert_monitor_to_screen(mouse.get_position())
            if is_in_roi(roi_mouse_move, pos_screen):
                mouse.move(*pos_away, randomize=40, delay_factor=[0.8, 1.4])
        return False

    def _pre_buff_cta(self):
        # Save current skill img
        skill_before = cut_roi(grab(), Config().ui_roi["skill_right"])
        # Try to switch weapons and select bo until we find the skill on the right skill slot
        start = time.time()
        switch_sucess = False
        while time.time() - start < 4:
            keyboard.send(Config().char["weapon_switch"])
            wait(0.3, 0.35)
            self._select_skill(skill = "battle_command", mouse_click_type="right", delay=(0.1, 0.2))
            if skills.is_right_skill_selected(["BC", "BO"]):
                switch_sucess = True
                break

        if not switch_sucess:
            Logger.warning("You dont have Battle Command bound, or you do not have CTA. ending CTA buff")
            Config().char["cta_available"] = 0
        else:
            # We switched succesfully, let's pre buff
            mouse.click(button="right")
            wait(self._cast_duration + 0.16, self._cast_duration + 0.18)
            self._select_skill(skill = "battle_orders", mouse_click_type="right", delay=(0.1, 0.2))
            mouse.click(button="right")
            wait(self._cast_duration + 0.16, self._cast_duration + 0.18)

        # Make sure the switch back to the original weapon is good
        start = time.time()
        while time.time() - start < 4:
            keyboard.send(Config().char["weapon_switch"])
            wait(0.3, 0.35)
            skill_after = cut_roi(grab(), Config().ui_roi["skill_right"])
            _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(skill_after, skill_before, cv2.TM_CCOEFF_NORMED))
            if max_val > 0.9:
                break
            else:
                Logger.warning("Failed to switch weapon, try again")
                wait(0.5)


    def vec_to_monitor(self, target):
        circle_pos_abs = get_closest_non_hud_pixel(pos = target, pos_type="abs")
        return convert_abs_to_monitor(circle_pos_abs)

    @staticmethod
    def _lerp(a: float, b: float, f:float):
        return a + f * (b - a)

    def cast_in_arc(self, ability: str, cast_pos_abs: tuple[float, float] = [0,-100], time_in_s: float = 3, spread_deg: float = 10, hold=True, btn="right"):
        #scale cast time by damage_scaling
        time_in_s *= self.damage_scaling
        Logger.debug(f'Casting {ability} for {time_in_s:.02f}s at {cast_pos_abs} with {spread_deg}°')
        if self._skill_hotkeys[ability]:
            self._select_skill(skill = ability, mouse_click_type=btn, delay=0.02)
        elif btn == "right":
            raise ValueError(f"You did not set {ability} hotkey!")
        keyboard.send(Config().char["stand_still"], do_release=False)

        target = self.vec_to_monitor(arc_spread(cast_pos_abs, spread_deg=spread_deg))
        mouse.move(*target,delay_factor=[0.95, 1.05])
        if hold:
            mouse.press(button=btn)
        start = time.time()
        while (time.time() - start) < time_in_s:
            target = self.vec_to_monitor(arc_spread(cast_pos_abs, spread_deg=spread_deg))
            if hold:
                mouse.move(*target,delay_factor=[3, 8])
            else:
                mouse.move(*target,delay_factor=[.2, .4])
                #wait(0.02, 0.04)
                mouse.press(button=btn)
                #wait(0.02, 0.06)
                wait(self._cast_duration, self._cast_duration)
                mouse.release(button=btn)
        if hold:
            mouse.release(button=btn)
        keyboard.send(Config().char["stand_still"], do_press=False)


    def pre_buff(self):
        pass

    def kill_pindle(self) -> bool:
        raise ValueError("Pindle is not implemented!")

    def kill_shenk(self) -> bool:
        raise ValueError("Shenk is not implemented!")

    def kill_eldritch(self) -> bool:
        raise ValueError("Eldritch is not implemented!")

    def kill_council(self) -> bool:
        raise ValueError("Council is not implemented!")

    def kill_nihlathak(self, end_nodes: list[int]) -> bool:
        raise ValueError("Nihlathak is not implemented!")

    def kill_summoner(self) -> bool:
        raise ValueError("Arcane is not implemented!")

    def run_to_cs(self) -> bool:
        return False

    def kill_diablo(self) -> bool:
        raise ValueError("Diablo is not implemented!")

    def kill_deseis(self, seal_layout:str) -> bool:
        raise ValueError("Diablo De Seis is not implemented!")

    def kill_infector(self, seal_layout:str) -> bool:
        raise ValueError("Diablo Infector is not implemented!")

    def kill_vizier(self, seal_layout:str) -> bool:
        raise ValueError("Diablo Vizier is not implemented!")

    def kill_cs_trash(self, location:str) -> bool:
        raise ValueError("Diablo CS Trash is not implemented!")

if __name__ == "__main__":
    import os
    import keyboard
    keyboard.add_hotkey('f12', lambda: os._exit(1))
    print(f"Get on D2R screen and press F11 when ready")
    keyboard.wait("f11")
    from utils.misc import cut_roi
    from config import Config
    from ui import skills

    skill_hotkeys = {}

    i_char = IChar({})

    while True:
        print(skills.get_skill_charges(grab()))
        wait(1)
