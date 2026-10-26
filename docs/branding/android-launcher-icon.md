# Android launcher icon

The official IERCS artwork is kept at `assets/branding/iercs_app_icon.png` (1254 × 1254 PNG). Android's legacy density resources are generated from this master at 48, 72, 96, 144, and 192 pixels for mdpi through xxxhdpi; round resources use the same square artwork and rely on the launcher mask. Flutter and React both use the master; the React favicon variants at 32, 192, and 512 pixels are copies resized from that source.

The source is a flattened illustration, so its background and foreground cannot be separated cleanly without changing the approved artwork. Adaptive launcher resources therefore use the artwork as the background bitmap and a transparent foreground layer. Android themed monochrome icons are omitted until an approved monochrome variant exists. The splash screen uses the generated 72 dp launcher image.

No icon-generation package or application dependency was added. The Android raster variants were resized from the master with macOS `sips`; retain the master when regenerating them.
