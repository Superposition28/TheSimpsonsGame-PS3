many .tscn files need to be recreated as they have been generated incorrectly and are now containing thousands of lines of redundnent data that should only exist in child scene files.
simply rename the file with a .old.ignore.tscn extension, then in godot recreate the scene file and reimport its components/scene files, and create anything else it contained directly
when complete delete the old broken file
