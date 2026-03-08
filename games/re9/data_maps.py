# RE9 FakeBone data maps
# Same structure as RE4 but with RE9 bone naming convention

FAKEBONE_BODY_BONES = [
    "Spine_0", "Spine_1", "Spine_2", "L_Arm_Clavicle", "R_Arm_Clavicle",
    "Neck_0", "Neck_1", "Head_0", "R_Leg_Upper", "L_Leg_Upper", "L_Arm_Upper", "R_Arm_Upper"
]

FAKEBONE_BODY_FAKES = [
    "Hip", "Spine_0", "Spine_1", "Spine_2", "L_Arm_Clavicle", "R_Arm_Clavicle", "Neck_0", "Neck_1"
]

FAKEBONE_BODY_PARENTS = {
    "Hip": ["Spine_0", "R_Leg_Upper", "L_Leg_Upper"],
    "Spine_0": ["Spine_1"],
    "Spine_1": ["Spine_2"],
    "Spine_2": ["L_Arm_Clavicle", "R_Arm_Clavicle", "Neck_0"],
    "L_Arm_Clavicle": ["L_Arm_Upper"],
    "R_Arm_Clavicle": ["R_Arm_Upper"],
    "Neck_0": ["Neck_1"],
    "Neck_1": ["Head_0"],
}

FAKEBONE_FINGER_BONES = [
    "R_Arm_Hand", "R_Hand_ThumbF_1", "R_Hand_ThumbF_2", "R_Hand_ThumbF_3",
    "R_Hand_IndexF_1", "R_Hand_IndexF_2", "R_Hand_IndexF_3",
    "R_Hand_MiddleF_1", "R_Hand_MiddleF_2", "R_Hand_MiddleF_3",
    "R_Hand_Palm", "R_Hand_RingF_1", "R_Hand_RingF_2", "R_Hand_RingF_3",
    "R_Hand_PinkyF_1", "R_Hand_PinkyF_2", "R_Hand_PinkyF_3",
    "L_Arm_Hand", "L_Hand_ThumbF_1", "L_Hand_ThumbF_2", "L_Hand_ThumbF_3",
    "L_Hand_IndexF_1", "L_Hand_IndexF_2", "L_Hand_IndexF_3",
    "L_Hand_MiddleF_1", "L_Hand_MiddleF_2", "L_Hand_MiddleF_3",
    "L_Hand_Palm", "L_Hand_RingF_1", "L_Hand_RingF_2", "L_Hand_RingF_3",
    "L_Hand_PinkyF_1", "L_Hand_PinkyF_2", "L_Hand_PinkyF_3",
]

FAKEBONE_FINGER_MERGE_MAP = {
    "L_Wep": "L_Arm_Hand_end",
    "L_Hand_IndexF_1": "L_Arm_Hand_endI",
    "L_Hand_MiddleF_1": "L_Arm_Hand_endM",
    "L_Hand_Palm": "L_Arm_Hand_endP",
    "L_Hand_ThumbF_1": "L_Arm_Hand_endT",
    "L_Hand_PinkyF_1": "L_Hand_Palm_endP",
    "L_Hand_RingF_1": "L_Hand_Palm_endR",
    "R_Wep": "R_Arm_Hand_end",
    "R_Hand_IndexF_1": "R_Arm_Hand_endI",
    "R_Hand_MiddleF_1": "R_Arm_Hand_endM",
    "R_Hand_Palm": "R_Arm_Hand_endP",
    "R_Hand_ThumbF_1": "R_Arm_Hand_endT",
    "R_Hand_PinkyF_1": "R_Hand_Palm_endP",
    "R_Hand_RingF_1": "R_Hand_Palm_endR",
}

FAKEBONE_FINGER_PATTERNS = [
    ("L_Hand_IndexF_", 3), ("L_Hand_MiddleF_", 3), ("L_Hand_RingF_", 3),
    ("L_Hand_PinkyF_", 3), ("L_Hand_ThumbF_", 3),
    ("R_Hand_IndexF_", 3), ("R_Hand_MiddleF_", 3), ("R_Hand_RingF_", 3),
    ("R_Hand_PinkyF_", 3), ("R_Hand_ThumbF_", 3),
]
