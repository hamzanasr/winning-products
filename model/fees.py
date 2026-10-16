# -*- coding: utf-8 -*-
"""Noon KSA fee model from the official FBN fee annex (effective 1 Sep 2025).
Source: supportagent.noon.partners/portal/en/kb/articles/fulfilled-by-noon-fbn-fees-in-ksa"""
import re

def _has(s, *words):
    return any(w in s for w in words)


def commission_rate(c, price):
    """Referral fee rate (fraction of selling price) from the official annex."""
    en = c["en"].lower(); cat = c["cat"]
    # --- Electronics / mobiles ---
    if _has(en, "earbuds", "earphones", "headphones", "headset", "headband", "bone conduction", "earplugs") and cat == "E":
        return 0.20
    if _has(en, "microphone"):
        return 0.15
    if _has(en, "smart watch", "smart band", "watch strap", "key finder", "tracker") and cat == "E":
        return 0.15
    if _has(en, "projector") and "screen" not in en:
        return 0.10
    if _has(en, "tv box", "streaming"):
        return 0.10
    if _has(en, "tv wall mount", "universal tv remote"):
        return 0.15
    if _has(en, "bluetooth speaker", "soundbar", "desktop speakers", "audio transmitter", "azan", "quran player"):
        return 0.10
    if _has(en, "action camera", "gimbal", "ring light", "led video light", "drone"):
        return 0.10 if price <= 250 else 0.08
    if _has(en, "tripod", "selfie stick", "webcam", "privacy screen", "dash cam") and cat in ("E", "C"):
        return 0.15 if price <= 250 else 0.08
    if _has(en, "microsd", "sd card"):
        return 0.07
    if _has(en, "flash drive"):
        return 0.15 if price <= 250 else 0.08
    if _has(en, "ssd", "enclosure"):
        return 0.06
    if _has(en, "wifi extender", "ethernet", "router"):
        return 0.06
    if _has(en, "laptop sleeve", "laptop backpack"):
        return 0.15
    if _has(en, "stylus"):
        return 0.10
    if _has(en, "label maker", "label printer", "barcode"):
        return 0.13
    if _has(en, "laptop", "keyboard", "mouse", "mousepad", "mouse pad", "usb hub", "hub 7", "usb 3.0 hub", "card reader", "cooling pad",
            "monitor", "hdmi", "usb-c to", "desk mat", "wrist rest", "gaming desk", "drawing tablet", "cable management", "webcam cover",
            "controller", "gamepad", "game controller", "finger sleeves", "phone cooler") and cat in ("E", "O"):
        return 0.13
    if cat == "E" and _has(en, "charger", "cable", "power bank", "charging", "phone", "tablet", "adapter", "magnetic", "wireless",
                          "case", "tempered", "lanyard", "ring holder", "usb c magnetic", "sleeve", "cleaner kit", "earbuds case"):
        return 0.20 if price <= 50 else 0.15
    if cat == "E" and _has(en, "vr headset"):
        return 0.12
    # --- appliances / home electronics ---
    if _has(en, "vacuum cleaner", "space heater", "mini fridge", "portable car fridge", "heater") and cat in ("H", "W", "C", "T"):
        return 0.10
    if _has(en, "air fryer", "kettle", "blender", "chopper", "espresso", "popcorn", "waffle", "toaster", "steamer", "steam iron", "mixer",
            "grill", "ice cream maker", "pressure cooker", "oven", "milk frother", "air purifier", "humidifier", "tower fan", "air cooler",
            "massager", "massage gun", "heated blanket", "heating pad", "can opener", "grinder electric", "water dispenser", "soap dispenser",
            "scale", "foot massager", "neck massager", "fan", "sewing machine", "dryer", "sanitizer"):
        return 0.15
    # --- by category ---
    if cat == "C":
        if _has(en, "child car seat", "booster"):
            return 0.15
        if _has(en, "jump starter", "tire inflator", "pressure washer", "jumper cables", "wrench", "tow rope", "warning triangle"):
            return 0.06
        return 0.10
    if cat == "B":
        return 0.20 if _has(en, "suitcase", "luggage", "shopping trolley") else 0.25
    if cat == "T":
        if _has(en, "suitcase", "duffel", "passport wallet", "packing cubes", "luggage", "tsa"):
            return 0.20 if _has(en, "suitcase", "luggage cover") else 0.25
        return 0.13 if price > 30 else 0.20
    if cat == "S":
        return 0.13 if price > 30 else 0.20
    if cat == "O":
        return 0.12
    if cat == "K":
        if _has(en, "stroller", "high chair", "travel cot", "diaper", "baby", "bath", "play mat", "monitor", "corner", "safety gate"):
            return 0.08 if price <= 50 else 0.15
        if _has(en, "lunch bag", "water bottle", "school"):
            return 0.14
        return 0.14
    if cat == "P":
        if _has(en, "toy", "toys", "laser", "chew"):
            return 0.14
        if _has(en, "bed"):
            return 0.08 if price <= 50 else 0.15
        return 0.15
    if cat == "W":
        return 0.09 if _has(en, "sponge", "gloves", "brush", "mop", "lint", "wash bags", "dryer balls", "squeegee", "scrub", "trap", "clothesline",
                              "drying rack", "trash") else 0.14
    if cat == "Z":
        return 0.14
    if cat == "R":
        return 0.14
    if cat in ("H", "L", "G", "D"):
        return 0.14
    return 0.14


def fbn_fee(c, price):
    """Outbound FBN fee per unit (SAR, excl VAT) from the official annex."""
    kg = c["kg"]; hi = price > 25
    if c["size"] == "L":
        base = [(1, 14), (2, 15), (3, 16), (4, 17), (5, 18)] if hi else [(1, 10), (2, 11), (3, 12), (4, 13), (5, 14)]
        for lim, fee in base:
            if kg <= lim:
                return fee
        return base[-1][1] + (int(kg) - 5)
    if c["size"] == "S" and kg <= 0.10:
        return 8.0 if hi else 6.0
    if kg <= 0.25:
        return 9.0 if hi else 7.0
    if kg <= 0.5:
        return 9.5 if hi else 7.5
    if kg <= 1.0:
        return 10.0 if hi else 8.0
    if kg <= 1.5:
        return 11.5 if hi else 8.5
    if kg <= 2.0:
        return 12.0 if hi else 9.0
    if kg <= 3.0:
        return 13.0 if hi else 10.0
    return (13.0 if hi else 10.0) + (int(kg) - 3)


A = dict(fx=3.75, agent=0.08, ship=8.0, customs=0.05, vat=0.15, ads=0.08, ret=0.03, target=0.30, ok=0.20)


def econ(c, price):
    landed = (c["usd"] * A["fx"] * (1 + A["agent"]) + c["kg"] * A["ship"]) * (1 + A["customs"])
    net = price / (1 + A["vat"])
    com = max(1.0, commission_rate(c, price) * price)
    fbn = fbn_fee(c, price)
    profit = net - landed - com - fbn - price * (A["ads"] + A["ret"])
    return dict(landed=landed, net=net, com=com, fbn=fbn, profit=profit, margin=profit / net)
