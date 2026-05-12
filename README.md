# Import Image and Create Camera

Blender add-on features:

- Open from `File > Import > Image and Create Camera`
- Open from the 3D View sidebar `N` panel under `Image Camera`
- The sidebar panel uses collapsible sections for Create Camera, Active Camera, Sync Render Resolution, and Batch Render
- Each section has a secondary collapsible Settings group
- The sidebar panel includes an active camera section with live focal length editing and a Position submenu
- The active camera section includes a `Camera to View` safety toggle that auto-disables after rendering
- Pick an image file
- Import the image
- Create a camera with the same base name
- Attach the image to the camera as a background or foreground reference
- Choose camera frame method: Stretch, Fit, or Crop
- Optionally auto-match the camera orientation to portrait or landscape
- Optional toggles to copy the current camera position, focal length, and depth of field
- Choose the target collection for the new camera
- Optionally set the new camera as the active scene camera
- Sync the render output resolution to the current background image ratio
- Optionally sync with a fixed long edge, such as 3000
- Render only the current active camera
- Batch render cameras from a selected collection to PNG files

## Install

1. Zip the folder, or use the `__init__.py` file directly
2. In Blender, open `Edit > Preferences > Add-ons`
3. Click `Install...` and select the zip or script
4. Enable the add-on
5. Open the 3D View sidebar with `N`
6. Use the `Image Camera` tab to set options and create the camera

## Naming

The camera and imported image are renamed to the image file base name.
If a name already exists, Blender-style numeric suffixes are added automatically.

## Notes

The image is added to `Camera.background_images`, so it is a camera-view reference image.
It is not part of the final render output.

`Auto Orientation` is enabled by default and sets camera fit mode from the image aspect ratio.

The copy toggles use the current scene camera if available, or the active camera object.

The `Collection` selector controls where the new camera object is linked in the scene.

The file browser import operator uses an `Accept and Create` confirmation button.

The `Active Camera` section edits the current camera data directly, so focal length and other settings update live.
The `Position` submenu edits camera `location` and `rotation` directly.
The `Render Active Camera` button is placed under the Batch Render section and uses the same output directory as batch rendering.
`Camera to View` locks the viewport to the active camera while rendering, then turns itself off after the render finishes.

`Sync Render Resolution` updates `Render Properties > Dimensions` to match the current camera's attached background image aspect ratio.
When `Sync Mode` is set to `Long Edge`, the add-on checks whether the attached background image is portrait or landscape.
The longer render side is set to `Long Edge`, and the shorter side is calculated from the current camera sensor ratio.
If no background image is attached, it falls back to the camera sensor orientation.

`Batch Render` renders every camera in the selected collection and saves each result as a PNG named after the camera.
The output directory must be set before running it.
If a PNG with the same name already exists, the add-on prompts for `Skip`, `Overwrite`, or `Extra Naming`.
The batch conflict mode is also available in the Batch Render settings section.
Both batch render and active camera render use the same output path.
