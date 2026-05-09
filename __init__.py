bl_info = {
    "name": "Import Image and Create Camera",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import > Image and Create Camera",
    "description": "Import an image and create a camera with the same name",
    "category": "Import-Export",
}

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator


def _unique_name(base_name: str, existing_names: set[str]) -> str:
    if base_name not in existing_names:
        return base_name

    index = 1
    while True:
        candidate = f"{base_name}.{index:03d}"
        if candidate not in existing_names:
            return candidate
        index += 1


def _strip_extension(filepath: str) -> str:
    stem = os.path.splitext(os.path.basename(filepath))[0]
    return stem or "Image"


class IMPORT_IMAGE_OT_create_camera(Operator):
    bl_idname = "import_image.create_camera"
    bl_label = "Image and Create Camera"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    set_active_camera: BoolProperty(
        name="Set Active Camera",
        description="Make the new camera the active scene camera",
        default=True,
    )

    image_mode: EnumProperty(
        name="Image Mode",
        description="Display the imported image in front of or behind objects in camera view",
        items=(
            ("BACKGROUND", "Background", "Show the image behind objects"),
            ("FOREGROUND", "Foreground", "Show the image in front of objects"),
        ),
        default="BACKGROUND",
    )

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.exr;*.webp",
        options={"HIDDEN"},
    )

    def execute(self, context):
        filepath = bpy.path.abspath(self.filepath)
        if not filepath:
            self.report({"ERROR"}, "No image file selected")
            return {"CANCELLED"}

        if not os.path.exists(filepath):
            self.report({"ERROR"}, f"File not found: {filepath}")
            return {"CANCELLED"}

        try:
            image = bpy.data.images.load(filepath, check_existing=True)
        except Exception as exc:
            self.report({"ERROR"}, f"Failed to load image: {exc}")
            return {"CANCELLED"}

        base_name = _strip_extension(filepath)
        existing_data_names = set(bpy.data.cameras.keys())
        existing_object_names = set(bpy.data.objects.keys())
        existing_image_names = set(bpy.data.images.keys())

        camera_name = _unique_name(
            base_name,
            existing_data_names | existing_object_names | existing_image_names,
        )

        camera_data = bpy.data.cameras.new(name=camera_name)
        camera_object = bpy.data.objects.new(name=camera_name, object_data=camera_data)
        context.collection.objects.link(camera_object)
        image.name = camera_name

        bg = camera_data.background_images.new()
        bg.image = image
        bg.show_background_image = True
        bg.display_depth = "FRONT" if self.image_mode == "FOREGROUND" else "BACK"
        bg.show_on_foreground = self.image_mode == "FOREGROUND"
        camera_data.show_background_images = True

        # Store the source image on the camera for later inspection or tooling.
        camera_object["source_image"] = image.name
        camera_object["source_image_filepath"] = bpy.path.relpath(filepath)

        if self.set_active_camera:
            context.view_layer.objects.active = camera_object
            context.scene.camera = camera_object

        self.report(
            {"INFO"},
            f"Created camera '{camera_name}' with {self.image_mode.lower()} image '{image.name}'",
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_IMAGE_OT_create_camera.bl_idname,
        text="Image and Create Camera",
    )


classes = (IMPORT_IMAGE_OT_create_camera,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
