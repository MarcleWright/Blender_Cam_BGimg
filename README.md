# Import Image and Create Camera

Blender add-on features:

- Open from `File > Import > Image and Create Camera`
- Open from the 3D View sidebar `N` panel under `Image Camera`
- Pick an image file
- Import the image
- Create a camera with the same base name
- Attach the image to the camera as a background or foreground reference
- Choose camera frame method: Stretch, Fit, or Crop
- Optionally auto-match the camera orientation to portrait or landscape
- Optional toggles to copy the current camera position, focal length, and depth of field
- Choose the target collection for the new camera
- Optionally set the new camera as the active scene camera
- Sync the render output resolution to the current camera sensor ratio

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

`Sync Render Resolution` updates `Render Properties > Dimensions` to match the current camera's sensor aspect ratio.
