bl_info = {
    "name": "Import Image and Create Camera",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import > Image and Create Camera, View3D Sidebar > Image Camera",
    "description": "Import an image, create a camera, and configure it from the N panel",
    "category": "Import-Export",
}

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel


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


def _is_portrait(image: bpy.types.Image) -> bool:
    width, height = image.size
    return height > width


def _get_reference_camera(context):
    scene_camera = context.scene.camera
    if scene_camera and scene_camera.type == "CAMERA":
        return scene_camera

    active_object = context.view_layer.objects.active
    if active_object and active_object.type == "CAMERA":
        return active_object

    return None


def _sync_render_resolution_to_camera(context, camera_object):
    render = context.scene.render
    camera_data = camera_object.data

    sensor_width = camera_data.sensor_width
    sensor_height = camera_data.sensor_height
    if sensor_width <= 0 or sensor_height <= 0:
        return {"ERROR"}, "Camera sensor size is invalid"

    aspect = sensor_width / sensor_height
    base_width = max(1, int(render.resolution_x))
    base_height = max(1, int(render.resolution_y))

    if aspect >= 1.0:
        render.resolution_x = base_width
        render.resolution_y = max(1, round(base_width / aspect))
    else:
        render.resolution_y = base_height
        render.resolution_x = max(1, round(base_height * aspect))

    return {"INFO"}, (
        f"Synced render resolution to camera sensor ratio {sensor_width:.4g}:{sensor_height:.4g}"
    )


def _resolve_target_collection(context, collection):
    if collection is not None:
        return collection
    return context.collection


def _create_camera_from_image(
    context,
    filepath: str,
    target_collection,
    set_active_camera: bool,
    image_mode: str,
    frame_method: str,
    auto_orientation: bool,
    copy_position: bool,
    copy_focal_length: bool,
    copy_depth_of_field: bool,
):
    filepath = bpy.path.abspath(filepath)
    if not filepath:
        return {"ERROR"}, "No image file selected"

    if not os.path.exists(filepath):
        return {"ERROR"}, f"File not found: {filepath}"

    try:
        image = bpy.data.images.load(filepath, check_existing=True)
    except Exception as exc:
        return {"ERROR"}, f"Failed to load image: {exc}"

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
    _resolve_target_collection(context, target_collection).objects.link(camera_object)
    image.name = camera_name

    reference_camera = _get_reference_camera(context)
    if reference_camera:
        if copy_position:
            camera_object.matrix_world = reference_camera.matrix_world.copy()
        if copy_focal_length:
            camera_data.lens = reference_camera.data.lens
            camera_data.sensor_width = reference_camera.data.sensor_width
            camera_data.sensor_height = reference_camera.data.sensor_height
            camera_data.sensor_fit = reference_camera.data.sensor_fit
        if copy_depth_of_field:
            source_dof = reference_camera.data.dof
            target_dof = camera_data.dof
            target_dof.use_dof = source_dof.use_dof
            target_dof.focus_distance = source_dof.focus_distance
            target_dof.focus_object = source_dof.focus_object
            target_dof.focus_subtarget = source_dof.focus_subtarget
            target_dof.aperture_fstop = source_dof.aperture_fstop
            target_dof.aperture_blades = source_dof.aperture_blades
            target_dof.aperture_ratio = source_dof.aperture_ratio
            target_dof.aperture_rotation = source_dof.aperture_rotation
    else:
        if copy_position or copy_focal_length or copy_depth_of_field:
            print("Image Camera: no reference camera found; copy toggles were skipped.")

    bg = camera_data.background_images.new()
    bg.image = image
    bg.show_background_image = True
    bg.display_depth = "FRONT" if image_mode == "FOREGROUND" else "BACK"
    bg.show_on_foreground = image_mode == "FOREGROUND"
    bg.frame_method = frame_method
    camera_data.show_background_images = True

    if auto_orientation:
        camera_data.sensor_fit = "VERTICAL" if _is_portrait(image) else "HORIZONTAL"

    camera_object["source_image"] = image.name
    camera_object["source_image_filepath"] = bpy.path.relpath(filepath)

    if set_active_camera:
        context.view_layer.objects.active = camera_object
        context.scene.camera = camera_object

    return {"INFO"}, f"Created camera '{camera_name}' with {image_mode.lower()} image '{image.name}'"


class IMPORT_IMAGE_OT_create_camera(Operator):
    bl_idname = "import_image.create_camera"
    bl_label = "Image and Create Camera"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    target_collection: PointerProperty(type=bpy.types.Collection)
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

    frame_method: EnumProperty(
        name="Frame Method",
        description="How the image fits in the camera frame",
        items=(
            ("STRETCH", "Stretch", "Scale the image to fill the frame"),
            ("FIT", "Fit", "Fit the image inside the frame"),
            ("CROP", "Crop", "Fill the frame and crop overflow"),
        ),
        default="FIT",
    )

    auto_orientation: BoolProperty(
        name="Auto Orientation",
        description="Match the camera fit to the image aspect ratio",
        default=True,
    )

    copy_position: BoolProperty(
        name="Copy Position",
        description="Copy the current camera transform to the new camera",
        default=False,
    )

    copy_focal_length: BoolProperty(
        name="Copy Focal Length",
        description="Copy the current camera lens and sensor settings",
        default=False,
    )

    copy_depth_of_field: BoolProperty(
        name="Copy Depth of Field",
        description="Copy the current camera depth of field settings",
        default=False,
    )

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.exr;*.webp",
        options={"HIDDEN"},
    )

    def execute(self, context):
        status, message = _create_camera_from_image(
            context,
            self.filepath,
            self.target_collection,
            self.set_active_camera,
            self.image_mode,
            self.frame_method,
            self.auto_orientation,
            self.copy_position,
            self.copy_focal_length,
            self.copy_depth_of_field,
        )
        if status == {"ERROR"}:
            self.report(status, message)
            return {"CANCELLED"}
        self.report(status, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        scene_collection = getattr(context.scene, "image_camera_target_collection", None)
        self.target_collection = scene_collection
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class IMAGECAMERA_OT_create_from_panel(Operator):
    bl_idname = "image_camera.create_from_panel"
    bl_label = "Create Camera"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        status, message = _create_camera_from_image(
            context,
            scene.image_camera_filepath,
            scene.image_camera_target_collection,
            scene.image_camera_set_active_camera,
            scene.image_camera_mode,
            scene.image_camera_frame_method,
            scene.image_camera_auto_orientation,
            scene.image_camera_copy_position,
            scene.image_camera_copy_focal_length,
            scene.image_camera_copy_depth_of_field,
        )
        if status == {"ERROR"}:
            self.report(status, message)
            return {"CANCELLED"}
        self.report(status, message)
        return {"FINISHED"}


class IMAGECAMERA_OT_sync_render_resolution(Operator):
    bl_idname = "image_camera.sync_render_resolution"
    bl_label = "Sync Render Resolution"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        camera_object = _get_reference_camera(context)
        if not camera_object:
            self.report({"ERROR"}, "No camera found to sync from")
            return {"CANCELLED"}

        status, message = _sync_render_resolution_to_camera(context, camera_object)
        if status == {"ERROR"}:
            self.report(status, message)
            return {"CANCELLED"}

        self.report(status, message)
        return {"FINISHED"}


class VIEW3D_PT_image_camera(Panel):
    bl_label = "Image Camera"
    bl_idname = "VIEW3D_PT_image_camera"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Image Camera"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "image_camera_filepath", text="Image")
        layout.prop(scene, "image_camera_target_collection", text="Collection")
        layout.prop(scene, "image_camera_mode")
        layout.prop(scene, "image_camera_frame_method")
        layout.prop(scene, "image_camera_auto_orientation")
        layout.prop(scene, "image_camera_copy_position")
        layout.prop(scene, "image_camera_copy_focal_length")
        layout.prop(scene, "image_camera_copy_depth_of_field")
        layout.prop(scene, "image_camera_set_active_camera")

        layout.operator(
            IMAGECAMERA_OT_create_from_panel.bl_idname,
            text="Create Camera",
            icon="CAMERA_DATA",
        )

        layout.operator(
            IMAGECAMERA_OT_sync_render_resolution.bl_idname,
            text="Sync Render Resolution",
            icon="OUTPUT",
        )


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_IMAGE_OT_create_camera.bl_idname,
        text="Image and Create Camera",
    )


classes = (
    IMPORT_IMAGE_OT_create_camera,
    IMAGECAMERA_OT_create_from_panel,
    IMAGECAMERA_OT_sync_render_resolution,
    VIEW3D_PT_image_camera,
)


def _register_properties():
    bpy.types.Scene.image_camera_filepath = StringProperty(
        name="Image File",
        subtype="FILE_PATH",
        description="Image file used to create the camera",
        default="",
    )
    bpy.types.Scene.image_camera_target_collection = PointerProperty(
        name="Collection",
        description="Collection where the new camera will be linked",
        type=bpy.types.Collection,
    )
    bpy.types.Scene.image_camera_set_active_camera = BoolProperty(
        name="Set Active Camera",
        description="Make the new camera the active scene camera",
        default=True,
    )
    bpy.types.Scene.image_camera_mode = EnumProperty(
        name="Image Mode",
        description="Display the imported image in front of or behind objects in camera view",
        items=(
            ("BACKGROUND", "Background", "Show the image behind objects"),
            ("FOREGROUND", "Foreground", "Show the image in front of objects"),
        ),
        default="BACKGROUND",
    )
    bpy.types.Scene.image_camera_frame_method = EnumProperty(
        name="Frame Method",
        description="How the image fits in the camera frame",
        items=(
            ("STRETCH", "Stretch", "Scale the image to fill the frame"),
            ("FIT", "Fit", "Fit the image inside the frame"),
            ("CROP", "Crop", "Fill the frame and crop overflow"),
        ),
        default="FIT",
    )
    bpy.types.Scene.image_camera_auto_orientation = BoolProperty(
        name="Auto Orientation",
        description="Match the camera fit to the image aspect ratio",
        default=True,
    )
    bpy.types.Scene.image_camera_copy_position = BoolProperty(
        name="Copy Position",
        description="Copy the current camera transform to the new camera",
        default=False,
    )
    bpy.types.Scene.image_camera_copy_focal_length = BoolProperty(
        name="Copy Focal Length",
        description="Copy the current camera lens and sensor settings",
        default=False,
    )
    bpy.types.Scene.image_camera_copy_depth_of_field = BoolProperty(
        name="Copy Depth of Field",
        description="Copy the current camera depth of field settings",
        default=False,
    )


def _unregister_properties():
    del bpy.types.Scene.image_camera_filepath
    del bpy.types.Scene.image_camera_target_collection
    del bpy.types.Scene.image_camera_set_active_camera
    del bpy.types.Scene.image_camera_mode
    del bpy.types.Scene.image_camera_frame_method
    del bpy.types.Scene.image_camera_auto_orientation
    del bpy.types.Scene.image_camera_copy_position
    del bpy.types.Scene.image_camera_copy_focal_length
    del bpy.types.Scene.image_camera_copy_depth_of_field


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _register_properties()
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    _unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
