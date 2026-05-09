# Import Image and Create Camera

Blender add-on features:

- Open from `File > Import > Image and Create Camera`
- Pick an image file
- Import the image
- Create a camera with the same base name
- Attach the image to the camera as a background or foreground reference
- Optionally set the new camera as the active scene camera

## Install

1. Zip the folder, or use the `__init__.py` file directly
2. In Blender, open `Edit > Preferences > Add-ons`
3. Click `Install...` and select the zip or script
4. Enable the add-on

## Naming

The camera and imported image are renamed to the image file base name.
If a name already exists, Blender-style numeric suffixes are added automatically.

## Notes

The image is added to `Camera.background_images`, so it is a camera-view reference image.
It is not part of the final render output.
