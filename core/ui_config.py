# core/ui_config.py

UI_HIERARCHY = {
    "Torso & Head": {
        "icon": 'USER',
        "subsections": {
            "Spine": ["pelvis", "spine_01", "spine_02"],
            "Upper": ["neck", "head"]
        }
    },
    "Arms": {
        "icon": 'ARMATURE_DATA',
        "subsections": {
            "Left Arm": ["clavicle_L", "upperarm_L", "forearm_L", "hand_L"],
            "Right Arm": ["clavicle_R", "upperarm_R", "forearm_R", "hand_R"]
        }
    },
    "Legs": {
        "icon": 'MOD_DYNAMICPAINT',
        "subsections": {
            "Left Leg": ["thigh_L", "shin_L", "foot_L", "toe_L"],
            "Right Leg": ["thigh_R", "shin_R", "foot_R", "toe_R"]
        }
    },
    "Fingers (Left)": {
        "icon": 'HAND',
        "subsections": {
            "Thumb": ["thumb_01_L", "thumb_02_L", "thumb_03_L"],
            "Index": ["index_01_L", "index_02_L", "index_03_L"],
            "Middle": ["middle_01_L", "middle_02_L", "middle_03_L"],
            "Ring": ["ring_01_L", "ring_02_L", "ring_03_L"],
            "Pinky": ["pinky_01_L", "pinky_02_L", "pinky_03_L"],
        }
    },
    "Fingers (Right)": {
        "icon": 'HAND',
        "subsections": {
            "Thumb": ["thumb_01_R", "thumb_02_R", "thumb_03_R"],
            "Index": ["index_01_R", "index_02_R", "index_03_R"],
            "Middle": ["middle_01_R", "middle_02_R", "middle_03_R"],
            "Ring": ["ring_01_R", "ring_02_R", "ring_03_R"],
            "Pinky": ["pinky_01_R", "pinky_02_R", "pinky_03_R"],
        }
    }
}