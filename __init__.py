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
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
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


def _get_active_camera(context):
    camera_object = _get_reference_camera(context)
    if camera_object and camera_object.type == "CAMERA":
        return camera_object
    return None


def _apply_camera_to_view(context, enabled: bool):
    window_manager = context.window_manager
    for window in window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.lock_camera = enabled
                if enabled and space.region_3d:
                    space.region_3d.view_perspective = "CAMERA"


def _update_camera_to_view(self, context):
    if context is None:
        return
    _apply_camera_to_view(context, bool(self.image_camera_camera_to_view))


def _get_camera_background_image(camera_object):
    for bg in camera_object.data.background_images:
        if bg.image:
            return bg.image
    return None


def _get_active_camera_background_slot(camera_object):
    background_images = camera_object.data.background_images
    if len(background_images) == 0:
        return None

    for bg in background_images:
        if bg.image and bg.show_background_image:
            return bg

    for bg in background_images:
        if bg.image:
            return bg

    return background_images[0]


def _get_scene_active_camera_background_slot(scene):
    if scene is None:
        return None

    camera_object = _get_active_camera(bpy.context)
    if not camera_object:
        return None

    return _get_active_camera_background_slot(camera_object)


def _get_scene_active_camera_bg_opacity(self):
    bg_slot = _get_scene_active_camera_background_slot(self)
    if not bg_slot:
        return 0.0
    return float(bg_slot.alpha)


def _set_scene_active_camera_bg_opacity(self, value):
    bg_slot = _get_scene_active_camera_background_slot(self)
    if not bg_slot:
        return
    bg_slot.alpha = value


def _get_scene_active_camera_passepartout(self):
    camera_object = _get_active_camera(bpy.context)
    if not camera_object:
        return False
    return bool(camera_object.data.show_passepartout)


def _set_scene_active_camera_passepartout(self, value):
    camera_object = _get_active_camera(bpy.context)
    if not camera_object:
        return
    camera_object.data.show_passepartout = bool(value)


def _get_scene_active_camera_passepartout_alpha(self):
    camera_object = _get_active_camera(bpy.context)
    if not camera_object:
        return 0.0
    return float(camera_object.data.passepartout_alpha)


def _set_scene_active_camera_passepartout_alpha(self, value):
    camera_object = _get_active_camera(bpy.context)
    if not camera_object:
        return
    camera_object.data.passepartout_alpha = value


def _get_image_aspect_ratio(image):
    width, height = image.size
    if width <= 0 or height <= 0:
        return None
    return width / height


def _is_background_portrait(camera_object):
    bg_image = _get_camera_background_image(camera_object)
    if not bg_image:
        return None
    aspect = _get_image_aspect_ratio(bg_image)
    if aspect is None:
        return None
    return aspect < 1.0


def _sync_render_resolution_to_camera(context, camera_object):
    render = context.scene.render
    bg_image = _get_camera_background_image(camera_object)
    if bg_image:
        aspect = _get_image_aspect_ratio(bg_image)
        aspect_label = f"background image '{bg_image.name}'"
    else:
        camera_data = camera_object.data
        sensor_width = camera_data.sensor_width
        sensor_height = camera_data.sensor_height
        if sensor_width <= 0 or sensor_height <= 0:
            return {"ERROR"}, "No background image found and camera sensor size is invalid"
        aspect = sensor_width / sensor_height
        aspect_label = "camera sensor"

    if not aspect:
        return {"ERROR"}, "Reference image aspect ratio is invalid"

    base_width = max(1, int(render.resolution_x))
    base_height = max(1, int(render.resolution_y))

    if aspect >= 1.0:
        render.resolution_x = base_width
        render.resolution_y = max(1, round(base_width / aspect))
    else:
        render.resolution_y = base_height
        render.resolution_x = max(1, round(base_height * aspect))

    return {"INFO"}, f"Synced render resolution to {aspect_label} ratio"


def _sync_render_resolution_to_camera_with_long_edge(context, camera_object, long_edge: int):
    render = context.scene.render
    camera_data = camera_object.data
    sensor_width = camera_data.sensor_width
    sensor_height = camera_data.sensor_height
    if sensor_width <= 0 or sensor_height <= 0:
        return {"ERROR"}, "Camera sensor size is invalid"

    sensor_ratio = sensor_width / sensor_height
    if sensor_ratio <= 0:
        return {"ERROR"}, "Camera sensor ratio is invalid"

    is_portrait = _is_background_portrait(camera_object)
    if is_portrait is None:
        is_portrait = sensor_width < sensor_height

    long_edge = max(1, int(long_edge))

    if is_portrait:
        render.resolution_y = long_edge
        render.resolution_x = max(1, round(long_edge / sensor_ratio))
    else:
        render.resolution_x = long_edge
        render.resolution_y = max(1, round(long_edge / sensor_ratio))

    orientation_label = "portrait" if is_portrait else "landscape"
    return {"INFO"}, f"Synced render resolution to {orientation_label} using long edge {long_edge}"


def _resolve_target_collection(context, collection):
    if collection is not None:
        return collection
    return context.collection


def _iter_cameras_in_collection(collection):
    for obj in sorted(collection.objects, key=lambda item: item.name.lower()):
        if obj.type == "CAMERA":
            yield obj


def _camera_output_stem(camera_object):
    stem = bpy.path.clean_name(camera_object.name)
    return stem or "Camera"


def _output_png_path(output_dir, camera_object):
    return os.path.join(output_dir, _camera_output_stem(camera_object) + ".png")


def _find_output_conflicts(output_dir, cameras):
    conflicts = []
    for camera_object in cameras:
        output_path = _output_png_path(output_dir, camera_object)
        if os.path.exists(output_path):
            conflicts.append((camera_object, output_path))
    return conflicts


def _list_unused_cameras_and_images():
    cameras = [camera for camera in bpy.data.cameras if camera.users == 0 and camera.library is None]
    images = [image for image in bpy.data.images if image.users == 0 and image.library is None]
    cameras.sort(key=lambda item: item.name.lower())
    images.sort(key=lambda item: item.name.lower())
    return cameras, images


def _purge_unused_cameras_and_images():
    removed_camera_names = []
    removed_image_names = []

    while True:
        cameras, images = _list_unused_cameras_and_images()
        if not cameras and not images:
            break

        for camera_data in cameras:
            removed_camera_names.append(camera_data.name)
            bpy.data.cameras.remove(camera_data)

        for image in images:
            removed_image_names.append(image.name)
            bpy.data.images.remove(image)

    return removed_camera_names, removed_image_names


def _next_available_output_path(output_dir, stem):
    index = 1
    while True:
        candidate = os.path.join(output_dir, f"{stem}_{index:03d}.png")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _draw_collapsible_header(layout, scene, prop_name, label):
    row = layout.row(align=True)
    expanded = bool(getattr(scene, prop_name))
    icon = "TRIA_DOWN" if expanded else "TRIA_RIGHT"
    row.prop(scene, prop_name, text="", emboss=False, icon=icon)
    row.label(text=label)
    return expanded


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
        scene = context.scene
        if hasattr(scene, "image_camera_camera_to_view"):
            scene.image_camera_camera_to_view = True
        else:
            _apply_camera_to_view(context, True)

    return {"INFO"}, f"Created camera '{camera_name}' with {image_mode.lower()} image '{image.name}'"


def _render_camera_collection_to_png(context, collection, output_dir, sync_mode, long_edge, conflict_mode):
    if collection is None:
        return {"ERROR"}, "No collection selected"

    output_dir = bpy.path.abspath(output_dir)
    if not output_dir:
        return {"ERROR"}, "No output directory selected"

    os.makedirs(output_dir, exist_ok=True)

    scene = context.scene
    render = scene.render
    original_camera = scene.camera
    original_filepath = render.filepath
    original_format = render.image_settings.file_format
    original_color_mode = render.image_settings.color_mode
    original_resolution_x = render.resolution_x
    original_resolution_y = render.resolution_y

    cameras = list(_iter_cameras_in_collection(collection))
    if not cameras:
        return {"ERROR"}, f"No cameras found in collection '{collection.name}'"

    rendered = 0
    failures = []

    try:
        render.image_settings.file_format = "PNG"
        render.image_settings.color_mode = "RGBA"

        for camera_object in cameras:
            scene.camera = camera_object

            if sync_mode == "LONG_EDGE":
                status, message = _sync_render_resolution_to_camera_with_long_edge(
                    context,
                    camera_object,
                    long_edge,
                )
            else:
                status, message = _sync_render_resolution_to_camera(context, camera_object)

            if status == {"ERROR"}:
                failures.append(f"{camera_object.name}: {message}")
                continue

            output_path = _output_png_path(output_dir, camera_object)
            if os.path.exists(output_path):
                if conflict_mode == "SKIP":
                    continue
                if conflict_mode == "EXTRA_NAME":
                    output_path = _next_available_output_path(output_dir, _camera_output_stem(camera_object))

            render.filepath = os.path.splitext(output_path)[0]

            try:
                bpy.ops.render.render(write_still=True)
            except Exception as exc:
                failures.append(f"{camera_object.name}: {exc}")
                continue

            rendered += 1

    finally:
        scene.camera = original_camera
        render.filepath = original_filepath
        render.image_settings.file_format = original_format
        render.image_settings.color_mode = original_color_mode
        render.resolution_x = original_resolution_x
        render.resolution_y = original_resolution_y

    message = f"Rendered {rendered} camera(s) from collection '{collection.name}'"
    if failures:
        message += f"; {len(failures)} failed"
    return {"INFO" if not failures else "WARNING"}, message


def _render_single_camera(context, camera_object, output_dir, sync_mode, long_edge, conflict_mode):
    scene = context.scene
    output_dir = bpy.path.abspath(output_dir)
    if not output_dir:
        return {"ERROR"}, "No output directory selected"

    os.makedirs(output_dir, exist_ok=True)
    original_camera = scene.camera
    original_filepath = scene.render.filepath
    original_camera_to_view = bool(getattr(scene, "image_camera_camera_to_view", False))

    try:
        scene.camera = camera_object
        if original_camera_to_view:
            _apply_camera_to_view(context, True)
        if sync_mode == "LONG_EDGE":
            status, message = _sync_render_resolution_to_camera_with_long_edge(
                context,
                camera_object,
                long_edge,
            )
        else:
            status, message = _sync_render_resolution_to_camera(context, camera_object)
        if status == {"ERROR"}:
            return status, message

        output_path = _output_png_path(output_dir, camera_object)
        if os.path.exists(output_path):
            if conflict_mode == "SKIP":
                return {"INFO"}, f"Skipped active camera '{camera_object.name}' because output already exists"
            if conflict_mode == "EXTRA_NAME":
                output_path = _next_available_output_path(output_dir, _camera_output_stem(camera_object))

        scene.render.filepath = os.path.splitext(output_path)[0]
        bpy.ops.render.render(write_still=True)
    finally:
        scene.camera = original_camera
        scene.render.filepath = original_filepath
        if original_camera_to_view:
            scene.image_camera_camera_to_view = False

    return {"INFO"}, f"Rendered active camera '{camera_object.name}'"


class IMPORT_IMAGE_OT_create_camera(Operator):
    bl_idname = "import_image.create_camera"
    bl_label = "Accept and Create"
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

        scene = context.scene
        sync_mode = getattr(scene, "image_camera_sync_mode", "BACKGROUND_RATIO")
        if sync_mode == "LONG_EDGE":
            status, message = _sync_render_resolution_to_camera_with_long_edge(
                context,
                camera_object,
                scene.image_camera_sync_long_edge,
            )
        else:
            status, message = _sync_render_resolution_to_camera(context, camera_object)
        if status == {"ERROR"}:
            self.report(status, message)
            return {"CANCELLED"}

        self.report(status, message)
        return {"FINISHED"}


class IMAGECAMERA_OT_batch_render_cameras(Operator):
    bl_idname = "image_camera.batch_render_cameras"
    bl_label = "Batch Render Cameras"
    bl_options = {"REGISTER", "UNDO"}

    conflict_mode: EnumProperty(
        name="Conflict Action",
        description="How to handle output files that already exist",
        items=(
            ("SKIP", "Skip", "Skip cameras whose output file already exists"),
            ("OVERWRITE", "Overwrite", "Overwrite existing output files"),
            ("EXTRA_NAME", "Extra Naming", "Save as _001, _002, etc"),
        ),
        default="EXTRA_NAME",
    )

    _conflict_count: IntProperty(options={"HIDDEN"}, default=0)

    def draw(self, context):
        layout = self.layout
        if self._conflict_count:
            layout.label(text=f"{self._conflict_count} output file(s) already exist.")
        layout.prop(self, "conflict_mode")

    def invoke(self, context, event):
        scene = context.scene
        collection = scene.image_camera_batch_collection or scene.image_camera_target_collection
        cameras = list(_iter_cameras_in_collection(collection)) if collection else []
        output_dir = bpy.path.abspath(scene.image_camera_batch_output_dir)
        conflicts = _find_output_conflicts(output_dir, cameras) if output_dir else []
        self._conflict_count = len(conflicts)
        self.conflict_mode = scene.image_camera_batch_conflict_mode
        if self._conflict_count:
            return context.window_manager.invoke_props_dialog(self, width=420)
        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        if hasattr(self, "conflict_mode"):
            scene.image_camera_batch_conflict_mode = self.conflict_mode
        collection = scene.image_camera_batch_collection or scene.image_camera_target_collection
        status, message = _render_camera_collection_to_png(
            context,
            collection,
            scene.image_camera_batch_output_dir,
            scene.image_camera_sync_mode,
            scene.image_camera_sync_long_edge,
            self.conflict_mode,
        )
        if status == {"ERROR"}:
            self.report(status, message)
            return {"CANCELLED"}
        self.report(status, message)
        return {"FINISHED"}


class IMAGECAMERA_OT_render_active_camera(Operator):
    bl_idname = "image_camera.render_active_camera"
    bl_label = "Render Active Camera"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        camera_object = _get_active_camera(context)
        if not camera_object:
            self.report({"ERROR"}, "No active camera found")
            return {"CANCELLED"}

        scene = context.scene
        status, message = _render_single_camera(
            context,
            camera_object,
            scene.image_camera_batch_output_dir,
            scene.image_camera_sync_mode,
            scene.image_camera_sync_long_edge,
            scene.image_camera_batch_conflict_mode,
        )
        if status == {"ERROR"}:
            self.report(status, message)
            return {"CANCELLED"}

        self.report(status, message)
        return {"FINISHED"}


class IMAGECAMERA_OT_purge_unused_datablocks(Operator):
    bl_idname = "image_camera.purge_unused_datablocks"
    bl_label = "Purge Unused Data"
    bl_options = {"REGISTER", "UNDO"}

    camera_names: StringProperty(options={"HIDDEN"}, default="")
    image_names: StringProperty(options={"HIDDEN"}, default="")
    camera_count: IntProperty(options={"HIDDEN"}, default=0)
    image_count: IntProperty(options={"HIDDEN"}, default=0)

    def draw(self, context):
        layout = self.layout

        layout.label(text=f"Unused Cameras: {self.camera_count}")
        if self.camera_names:
            box = layout.box()
            for name in self.camera_names.split("\n"):
                if name:
                    box.label(text=name)
        else:
            layout.label(text="No unused cameras found")

        layout.separator()

        layout.label(text=f"Unused Images: {self.image_count}")
        if self.image_names:
            box = layout.box()
            for name in self.image_names.split("\n"):
                if name:
                    box.label(text=name)
        else:
            layout.label(text="No unused images found")

    def invoke(self, context, event):
        cameras, images = _list_unused_cameras_and_images()
        self.camera_count = len(cameras)
        self.image_count = len(images)
        self.camera_names = "\n".join(camera.name for camera in cameras)
        self.image_names = "\n".join(image.name for image in images)

        if self.camera_count == 0 and self.image_count == 0:
            self.report({"INFO"}, "No unused camera or image datablocks found")
            return {"CANCELLED"}

        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        removed_cameras, removed_images = _purge_unused_cameras_and_images()
        self.report(
            {"INFO"},
            f"Removed {len(removed_cameras)} camera(s) and {len(removed_images)} image(s)",
        )
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

        if _draw_collapsible_header(layout, scene, "image_camera_show_create", "Create Camera"):
            create_box = layout.box()
            create_box.prop(scene, "image_camera_filepath", text="Image")
            if _draw_collapsible_header(create_box, scene, "image_camera_show_create_settings", "Settings"):
                settings_box = create_box.box()
                settings_box.prop(scene, "image_camera_target_collection", text="Collection")
                settings_box.prop(scene, "image_camera_mode")
                settings_box.prop(scene, "image_camera_frame_method")
                settings_box.prop(scene, "image_camera_auto_orientation")
                settings_box.prop(scene, "image_camera_copy_position")
                settings_box.prop(scene, "image_camera_copy_focal_length")
                settings_box.prop(scene, "image_camera_copy_depth_of_field")
                settings_box.prop(scene, "image_camera_set_active_camera")
            create_box.operator(
                IMAGECAMERA_OT_create_from_panel.bl_idname,
                text="Create Camera",
                icon="CAMERA_DATA",
            )

        layout.separator()

        if _draw_collapsible_header(layout, scene, "image_camera_show_active", "Active Camera"):
            active_box = layout.box()
            camera_object = _get_active_camera(context)
            if camera_object:
                active_box.prop(camera_object.data, "lens", text="Focal Length")
                active_box.prop(scene, "image_camera_camera_to_view")
                bg_row = active_box.row()
                bg_row.enabled = _get_active_camera_background_slot(camera_object) is not None
                bg_row.prop(scene, "image_camera_bg_opacity", text="BG Opacity")
                pass_row = active_box.row(align=True)
                pass_row.enabled = True
                pass_row.prop(scene, "image_camera_passepartout", text="Passepartout")
                alpha_row = active_box.row()
                alpha_row.enabled = bool(scene.image_camera_passepartout)
                alpha_row.prop(scene, "image_camera_passepartout_alpha", text="Alpha")
                if _draw_collapsible_header(active_box, scene, "image_camera_show_active_position", "Position"):
                    position_box = active_box.box()
                    position_box.prop(camera_object, "location")
                    position_box.prop(camera_object, "rotation_euler")
                if _draw_collapsible_header(active_box, scene, "image_camera_show_active_settings", "Settings"):
                    settings_box = active_box.box()
                    settings_box.prop(camera_object.data, "sensor_fit", text="Sensor Fit")
                    settings_box.prop(camera_object.data, "sensor_width", text="Sensor Width")
                    settings_box.prop(camera_object.data, "sensor_height", text="Sensor Height")
                    settings_box.prop(camera_object.data.dof, "use_dof", text="Depth of Field")
                    settings_box.prop(camera_object.data.dof, "focus_distance", text="Focus Distance")
                    settings_box.prop(camera_object.data.dof, "aperture_fstop", text="F-Stop")
            else:
                active_box.label(text="No active camera selected")

        layout.separator()

        if _draw_collapsible_header(layout, scene, "image_camera_show_sync", "Sync Render Resolution"):
            sync_box = layout.box()
            if _draw_collapsible_header(sync_box, scene, "image_camera_show_sync_settings", "Settings"):
                settings_box = sync_box.box()
                settings_box.prop(scene, "image_camera_sync_mode")
                if scene.image_camera_sync_mode == "LONG_EDGE":
                    settings_box.prop(scene, "image_camera_sync_long_edge")
            sync_box.operator(
                IMAGECAMERA_OT_sync_render_resolution.bl_idname,
                text="Sync Render Resolution",
                icon="OUTPUT",
            )

        layout.separator()

        if _draw_collapsible_header(layout, scene, "image_camera_show_batch", "Batch Render"):
            batch_box = layout.box()
            if _draw_collapsible_header(batch_box, scene, "image_camera_show_batch_settings", "Settings"):
                settings_box = batch_box.box()
                settings_box.prop(scene, "image_camera_batch_collection", text="Collection")
                settings_box.prop(scene, "image_camera_batch_output_dir", text="Output")
                settings_box.prop(scene, "image_camera_sync_mode")
                if scene.image_camera_sync_mode == "LONG_EDGE":
                    settings_box.prop(scene, "image_camera_sync_long_edge")
                settings_box.prop(scene, "image_camera_batch_conflict_mode")
            row = batch_box.row()
            row.enabled = bool(scene.image_camera_batch_output_dir)
            row.operator(
                IMAGECAMERA_OT_batch_render_cameras.bl_idname,
                text="Batch Render PNG",
                icon="RENDER_STILL",
            )
            row = batch_box.row()
            row.enabled = bool(scene.image_camera_batch_output_dir)
            row.operator(
                IMAGECAMERA_OT_render_active_camera.bl_idname,
                text="Render Active Camera",
                icon="RENDER_STILL",
            )

        layout.separator()

        if _draw_collapsible_header(layout, scene, "image_camera_show_delete", "Delete"):
            delete_box = layout.box()
            delete_box.operator(
                IMAGECAMERA_OT_purge_unused_datablocks.bl_idname,
                text="Purge Unused Data",
                icon="TRASH",
            )


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_IMAGE_OT_create_camera.bl_idname,
        text="Image and Create Camera",
    )


classes = (
    IMPORT_IMAGE_OT_create_camera,
    IMAGECAMERA_OT_create_from_panel,
    IMAGECAMERA_OT_render_active_camera,
    IMAGECAMERA_OT_purge_unused_datablocks,
    IMAGECAMERA_OT_sync_render_resolution,
    IMAGECAMERA_OT_batch_render_cameras,
    VIEW3D_PT_image_camera,
)


def _register_properties():
    bpy.types.Scene.image_camera_filepath = StringProperty(
        name="Image File",
        subtype="FILE_PATH",
        description="Image file used to create the camera",
        default="",
    )
    bpy.types.Scene.image_camera_show_create = BoolProperty(
        name="Show Create Camera",
        default=True,
    )
    bpy.types.Scene.image_camera_show_create_settings = BoolProperty(
        name="Show Create Camera Settings",
        default=True,
    )
    bpy.types.Scene.image_camera_show_active = BoolProperty(
        name="Show Active Camera",
        default=True,
    )
    bpy.types.Scene.image_camera_camera_to_view = BoolProperty(
        name="Camera to View",
        description="Lock the current 3D View to the active camera",
        default=True,
        update=_update_camera_to_view,
    )
    bpy.types.Scene.image_camera_bg_opacity = FloatProperty(
        name="BG Opacity",
        description="Opacity of the active camera reference image",
        subtype="FACTOR",
        min=0.0,
        max=1.0,
        get=_get_scene_active_camera_bg_opacity,
        set=_set_scene_active_camera_bg_opacity,
    )
    bpy.types.Scene.image_camera_passepartout = BoolProperty(
        name="Passepartout",
        description="Darken the view outside the active camera frame",
        default=False,
        get=_get_scene_active_camera_passepartout,
        set=_set_scene_active_camera_passepartout,
    )
    bpy.types.Scene.image_camera_passepartout_alpha = FloatProperty(
        name="Alpha",
        description="Opacity of the camera frame overlay",
        subtype="FACTOR",
        min=0.0,
        max=1.0,
        get=_get_scene_active_camera_passepartout_alpha,
        set=_set_scene_active_camera_passepartout_alpha,
    )
    bpy.types.Scene.image_camera_show_active_position = BoolProperty(
        name="Show Active Camera Position",
        default=True,
    )
    bpy.types.Scene.image_camera_show_active_settings = BoolProperty(
        name="Show Active Camera Settings",
        default=True,
    )
    bpy.types.Scene.image_camera_show_sync = BoolProperty(
        name="Show Sync Render Resolution",
        default=True,
    )
    bpy.types.Scene.image_camera_show_sync_settings = BoolProperty(
        name="Show Sync Render Resolution Settings",
        default=True,
    )
    bpy.types.Scene.image_camera_show_batch = BoolProperty(
        name="Show Batch Render",
        default=True,
    )
    bpy.types.Scene.image_camera_show_batch_settings = BoolProperty(
        name="Show Batch Render Settings",
        default=True,
    )
    bpy.types.Scene.image_camera_show_delete = BoolProperty(
        name="Show Delete",
        default=True,
    )
    bpy.types.Scene.image_camera_target_collection = PointerProperty(
        name="Collection",
        description="Collection where the new camera will be linked",
        type=bpy.types.Collection,
    )
    bpy.types.Scene.image_camera_batch_collection = PointerProperty(
        name="Batch Collection",
        description="Collection containing cameras to batch render",
        type=bpy.types.Collection,
    )
    bpy.types.Scene.image_camera_batch_output_dir = StringProperty(
        name="Output Directory",
        subtype="DIR_PATH",
        description="Directory where rendered PNG files will be saved",
        default="",
    )
    bpy.types.Scene.image_camera_batch_conflict_mode = EnumProperty(
        name="Conflict Action",
        description="How to handle output files that already exist",
        items=(
            ("SKIP", "Skip", "Skip cameras whose output file already exists"),
            ("OVERWRITE", "Overwrite", "Overwrite existing output files"),
            ("EXTRA_NAME", "Extra Naming", "Save as _001, _002, etc"),
        ),
        default="EXTRA_NAME",
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
    bpy.types.Scene.image_camera_sync_mode = EnumProperty(
        name="Sync Mode",
        description="How render resolution is synchronized to the current camera",
        items=(
            ("BACKGROUND_RATIO", "Background Ratio", "Match the attached background image aspect ratio"),
            ("LONG_EDGE", "Long Edge", "Set the longer output side to a fixed size"),
        ),
        default="BACKGROUND_RATIO",
    )
    bpy.types.Scene.image_camera_sync_long_edge = IntProperty(
        name="Long Edge",
        description="Target size for the longer side of the render resolution",
        default=3000,
        min=1,
        soft_min=1,
    )


def _unregister_properties():
    del bpy.types.Scene.image_camera_filepath
    del bpy.types.Scene.image_camera_show_create
    del bpy.types.Scene.image_camera_show_create_settings
    del bpy.types.Scene.image_camera_show_active
    del bpy.types.Scene.image_camera_camera_to_view
    del bpy.types.Scene.image_camera_bg_opacity
    del bpy.types.Scene.image_camera_passepartout
    del bpy.types.Scene.image_camera_passepartout_alpha
    del bpy.types.Scene.image_camera_show_active_position
    del bpy.types.Scene.image_camera_show_active_settings
    del bpy.types.Scene.image_camera_show_sync
    del bpy.types.Scene.image_camera_show_sync_settings
    del bpy.types.Scene.image_camera_show_batch
    del bpy.types.Scene.image_camera_show_batch_settings
    del bpy.types.Scene.image_camera_show_delete
    del bpy.types.Scene.image_camera_target_collection
    del bpy.types.Scene.image_camera_batch_collection
    del bpy.types.Scene.image_camera_batch_output_dir
    del bpy.types.Scene.image_camera_batch_conflict_mode
    del bpy.types.Scene.image_camera_set_active_camera
    del bpy.types.Scene.image_camera_mode
    del bpy.types.Scene.image_camera_frame_method
    del bpy.types.Scene.image_camera_auto_orientation
    del bpy.types.Scene.image_camera_copy_position
    del bpy.types.Scene.image_camera_copy_focal_length
    del bpy.types.Scene.image_camera_copy_depth_of_field
    del bpy.types.Scene.image_camera_sync_mode
    del bpy.types.Scene.image_camera_sync_long_edge


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
