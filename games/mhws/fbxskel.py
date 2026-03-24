"""
fbxskel.7 parser, Blender loader, and binary writer for MHWs.
Adapted from Modder-Batch-Tool (wilds_suite).
"""

import bpy
import struct
import math
import os
from mathutils import Euler, Matrix, Vector, Quaternion


# ── Binary I/O ─────────────────────────────────────────────────────────────────

class _Reader:
    def __init__(self, data):
        self.offset = 0
        self.data = data

    def read(self, kind, size):
        result = struct.unpack(kind, self.data[self.offset:self.offset + size])[0]
        self.offset += size
        return result

    def seek(self, offset):
        self.offset = offset

    def readUInt(self):   return self.read("I", 4)
    def readUInt64(self): return self.read("Q", 8)
    def readShort(self):  return self.read("h", 2)
    def readUShort(self): return self.read("H", 2)
    def readFloat(self):  return self.read("f", 4)

    def readStringUTF(self):
        text = ""
        while True:
            char = self.read("H", 2)
            if char == 0:
                break
            text += chr(char)
        return text


class _Writer:
    def __init__(self):
        self.data = b""

    def tell(self):
        return len(self.data)

    def _pack(self, kind, value):
        self.data += struct.pack(kind, value)

    def writeAt(self, kind, offset, value):
        self.data = (self.data[:offset]
                     + struct.pack(kind, value)
                     + self.data[offset + struct.calcsize(kind):])

    def writeUInt64(self, v):        self._pack("Q", v)
    def writeUInt64At(self, o, v):   self.writeAt("Q", o, v)
    def writeUInt(self, v):          self._pack("I", v)
    def writeShort(self, v):         self._pack("h", v)
    def writeUShort(self, v):        self._pack("H", v)
    def writeFloat(self, v):         self._pack("f", v)

    def writeStringUTF(self, value):
        for char in value:
            self._pack("H", ord(char))
        self._pack("H", 0)


# ── MurmurHash3-32 ─────────────────────────────────────────────────────────────

def _murmurhash32(key, seed=0x0):
    def fmix(h):
        h ^= h >> 16
        h  = (h * 0x85ebca6b) & 0xFFFFFFFF
        h ^= h >> 13
        h  = (h * 0xc2b2ae35) & 0xFFFFFFFF
        h ^= h >> 16
        return h

    length   = len(key)
    nblocks  = length // 4
    h1, c1, c2 = seed, 0xcc9e2d51, 0x1b873593

    for bs in range(0, nblocks * 4, 4):
        k1 = (key[bs+3] << 24 | key[bs+2] << 16 | key[bs+1] << 8 | key[bs])
        k1 = (c1 * k1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF
        k1 = (c2 * k1) & 0xFFFFFFFF
        h1 ^= k1
        h1  = (h1 << 13 | h1 >> 19) & 0xFFFFFFFF
        h1  = (h1 * 5 + 0xe6546b64) & 0xFFFFFFFF

    ti, k1, ts = nblocks * 4, 0, length & 3
    if ts >= 3: k1 ^= key[ti + 2] << 16
    if ts >= 2: k1 ^= key[ti + 1] << 8
    if ts >= 1: k1 ^= key[ti]
    if ts > 0:
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    return fmix(h1 ^ length)


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_fbxskel(data):
    """Parse binary fbxskel.7 bytes → list of bone_info dicts."""
    bs = _Reader(data)
    version = bs.readUInt()
    magic   = bs.readUInt()
    if magic != 1852599155 or version != 7:
        raise RuntimeError(
            f"Not a valid fbxskel.7 (magic={magic}, version={version})")

    bs.readUInt64()               # reserved
    bone_offset = bs.readUInt64()
    bs.readUInt64()               # hash_offset (unused during load)
    bone_count  = bs.readUShort()

    bs.seek(bone_offset)
    bone_infos = []
    for _ in range(bone_count):
        bi = {}
        bi["name_offset"] = bs.readUInt64()
        bi["name_hash"]   = bs.readUInt()
        bi["parent"]      = bs.readShort()   # -1 = root
        bi["id"]          = bs.readUShort()
        bi["rot_quat"]    = [bs.readFloat() for _ in range(4)]
        bi["loc"]         = [bs.readFloat() for _ in range(3)]
        bi["scl"]         = [bs.readFloat() for _ in range(3)]
        bs.readUInt64()   # padding
        bone_infos.append(bi)

    for bi in bone_infos:
        bs.seek(bi["name_offset"])
        bi["name"] = bs.readStringUTF()

    return bone_infos


# ── Loader ─────────────────────────────────────────────────────────────────────

def load_reference_skeleton(filepath):
    """
    Load the reference fbxskel.7 into the scene as a Blender armature.
    Applies 90° X rotation and transform_apply immediately.
    Sets mhws_skel_id custom property on each bone.
    Returns the armature Object.
    """
    with open(filepath, "rb") as f:
        data = f.read()
    bone_infos = _parse_fbxskel(data)

    arm_name = "ch03_000_9000.fbxskel"
    # Remove stale objects/armatures from previous runs
    for ob in list(bpy.data.objects):
        if ob.name.startswith(arm_name):
            bpy.data.objects.remove(ob, do_unlink=True)
    for arm in list(bpy.data.armatures):
        if arm.name.startswith(arm_name):
            bpy.data.armatures.remove(arm)

    arm_data = bpy.data.armatures.new(arm_name)
    arm_obj  = bpy.data.objects.new(arm_name, arm_data)
    arm_obj.rotation_mode = "XYZ"
    arm_obj.rotation_euler.rotate(Euler([math.radians(90), 0, 0]))
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj

    bpy.ops.object.mode_set(mode='EDIT')
    for bi in bone_infos:
        bone = arm_data.edit_bones.new(bi["name"])
        bone.head = (0.0, 0.0, 0.0)
        bone.tail = (0.0, 0.1, 0.0)
        loc = Vector(bi["loc"])
        rot = Quaternion([bi["rot_quat"][3], bi["rot_quat"][0],
                          bi["rot_quat"][1], bi["rot_quat"][2]])
        scl = Vector(bi["scl"])
        mat = Matrix.LocRotScale(loc, rot, scl)
        new_tfr = bone.matrix @ mat
        if bi["parent"] != -1:
            bone.parent = arm_data.edit_bones[bi["parent"]]
            bone.matrix = bone.parent.matrix @ new_tfr
        else:
            bone.matrix = new_tfr
        bone.length = 0.1
        bone["mhws_skel_id"] = bi["id"]
    bpy.ops.object.mode_set(mode='OBJECT')

    # Deselect everything, select only the new armature, apply transforms
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    arm_obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    arm_obj.select_set(False)

    return arm_obj


# ── Writer ─────────────────────────────────────────────────────────────────────

def export_fbxskel(armature_obj):
    """
    Extract bone rest-pose data from armature_obj.
    Returns list of bone_info dicts (after applying coordinate transform).
    Requires mhws_skel_id custom property on each edit bone.
    """
    arm_data   = armature_obj.data
    arm_matrix = armature_obj.matrix_world
    bone_dict  = {b.name: i for i, b in enumerate(arm_data.bones)}
    rot4       = Matrix.Rotation(math.radians(-90.0), 4, 'X')
    scale_mat  = Matrix.LocRotScale(None, None, arm_matrix.to_scale())

    bone_infos = []
    for i, bone in enumerate(arm_data.bones):
        if bone.parent is None:
            local_mat = rot4 @ (arm_matrix @ bone.matrix_local)
        else:
            local_mat = (scale_mat
                         @ bone.parent.matrix_local.inverted()
                         @ bone.matrix_local)
        loc, rot, scl = local_mat.decompose()
        bone_infos.append({
            "name":      bone.name,
            "index":     i,
            "id":        bone["mhws_skel_id"],
            "parent_id": -1 if bone.parent is None else bone_dict[bone.parent.name],
            "loc":       list(loc),
            "rot":       [rot[1], rot[2], rot[3], rot[0]],  # x,y,z,w
            "scl":       list(scl),
        })
    return bone_infos


def write_fbxskel(bone_infos):
    """Serialize bone_infos to binary fbxskel.7 bytes."""
    w = _Writer()
    w.writeUInt(7)
    w.writeUInt(1852599155)
    w.writeUInt64(0)  # reserved

    bone_off_pos = w.tell(); w.writeUInt64(0)
    hash_off_pos = w.tell(); w.writeUInt64(0)
    w.writeUInt64(len(bone_infos))
    w.writeUInt64(0)

    w.writeUInt64At(bone_off_pos, w.tell())
    for bi in bone_infos:
        bi["_name_off"] = w.tell()
        w.writeUInt64(0)  # name_offset placeholder
        w.writeUInt(_murmurhash32(bi["name"].encode("utf-16LE"), 0xFFFFFFFF))
        w.writeShort(bi["parent_id"])
        w.writeUShort(bi["id"])
        for x in bi["rot"]: w.writeFloat(x)
        for x in bi["loc"]: w.writeFloat(x)
        for x in bi["scl"]: w.writeFloat(x)
        w.writeUInt64(0)  # padding

    w.writeUInt64At(hash_off_pos, w.tell())
    hashes = sorted(
        [(_murmurhash32(bi["name"].encode("utf-16LE"), 0xFFFFFFFF), bi["index"])
         for bi in bone_infos],
        key=lambda x: x[0],
    )
    for h, idx in hashes:
        w.writeUInt(h)
        w.writeUInt(idx)

    for bi in bone_infos:
        w.writeUInt64At(bi["_name_off"], w.tell())
        w.writeStringUTF(bi["name"])

    return w.data
