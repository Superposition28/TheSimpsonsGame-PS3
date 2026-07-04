## Pipeline TODO

Add `Convert Music (.mus -> .snr/.sns -> .wav)` after those conversion steps by running QuickBMS with `operations/mus.bms` to extract paired `.snr` and `.sns` files from each `.mus` archive.
Decode the extracted `.snr` files with vgmstream while keeping the matching `.sns` files beside them so the music streams resolve correctly.
Model the future `.mus` step as a QuickBMS-backed archive extraction stage in the pipeline, then follow it with vgmstream conversion for the extracted music streams.
may be better to create a mus.lua script to do this all at once, and output all music streams into a folder for each mus file, and then clean the snr/sns files after vgmstream .wav conversion is complete, to avoid many additional steps in the pipeline.

