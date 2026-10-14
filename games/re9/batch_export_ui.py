"""RE9's batch export dialog and its helper operators, built from the shared
classes in core/scheme_batch_export.py."""

import bpy

from ...core.scheme_batch_export import build_classes
from .batch_export import EXPORTER

classes = build_classes(EXPORTER)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
