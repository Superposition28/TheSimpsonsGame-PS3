import os

def asset_pattern_stats(root_dir):
    rws_notexpected = rws_total = rws_matched = rws_ps3 = 0
    dff_notexpected = dff_total = dff_matched = dff_ps3 = 0

    for dirpath, _, filenames in os.walk(root_dir):
        # Normalize filenames to lowercase for consistent matching
        files_lower = [f.lower() for f in filenames]

        has_hkt = any(f.endswith(".hkt.ps3") for f in files_lower)
        has_hko = any(f.endswith(".hko.ps3") for f in files_lower)
        has_ps3 = any(f.endswith(".ps3") for f in files_lower)


        for original_filename in filenames:
            filename = original_filename.lower()
            if filename.endswith(".rws.ps3.preinstanced"):
                rws_total += 1
                if has_hkt:
                    rws_matched += 1
                if has_hko:
                    rws_notexpected += 1
                if has_ps3:
                    rws_ps3 += 1
            elif filename.endswith(".dff.ps3.preinstanced"):
                dff_total += 1
                if has_hko:
                    dff_matched += 1
                if has_hkt:
                    dff_notexpected += 1
                if has_ps3:
                    dff_ps3 += 1

    print("RWS Assets:")
    print(f"  Total              : {rws_total}")
    print(f"  Matched (.hkt)     : {rws_matched}")
    print(f"  Not Expected (.hko): {rws_notexpected}")
    print(f"  PS3               : {rws_ps3}")
    print(f"  Missing (.hkt)     : {rws_total - rws_matched}")

    print("\nDFF Assets:")
    print(f"  Total              : {dff_total}")
    print(f"  Matched (.hko)     : {dff_matched}")
    print(f"  Not Expected (.hkt): {dff_notexpected}")
    print(f"  PS3               : {dff_ps3}")
    print(f"  Missing (.hko)     : {dff_total - dff_matched}")



# Example usage
asset_pattern_stats(r"A:\Dev\Games\TheSimpsonsGame\PAL\Modules\Extract\GameFiles\quickbms_out")
