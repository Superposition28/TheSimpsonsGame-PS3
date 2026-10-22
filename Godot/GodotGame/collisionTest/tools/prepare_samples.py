"""Copy a small, reproducible local sample set; never copies fonttest/.godot.

Original game assets and generated GLBs stay in ignored samples/. This tool
does not modify the source data. Rerun it after moving or cleaning the sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


SAMPLES = {
    'raw/zone01.hkt.PS3': 'L01_LandOfChocolate/loc/zone01str/assetsEnvirons/export/collision/collisionmodel1_cfeaf1.hkt.PS3',
    'models/zone01.glb': 'L01_LandOfChocolate/loc/zone01str/assetsEnvirons/export/terrain/lodmodel1_6850eb.rws.PS3.glb',
    'raw/cake.hkt.PS3': 'L01_LandOfChocolate/locStr/assets/props/epsLandOfChocolate/cakebreakawayGeo/exportCakebreakawayDes/collisionmodel1_c3621a.hkt.PS3',
    'models/cake.glb': 'L01_LandOfChocolate/locStr/assets/props/epsLandOfChocolate/cakebreakawayGeo/exportCakebreakawayDes/model1_3bcb4a.rws.PS3.glb',
    'raw/zone03.hkt.PS3': 'L01_LandOfChocolate/loc/zone03str/assetsEnvirons/export/collision/collisionmodel1_71b6f9.hkt.PS3',
    'models/zone03.glb': 'L01_LandOfChocolate/loc/zone03str/assetsEnvirons/export/terrain/lodmodel1_817701.rws.PS3.glb',
    'raw/shared_character.hko.PS3': 'A2_Characters/globalFolder/chars/margeMm0h0str/assets/shared/collision/char_collision_spheres_7959dc.hko.PS3',
    'raw/bunny.acs.PS3': 'L01_LandOfChocolate/loc/challengeModeDesignStr/assets/shared/collision/npc_bunny_94c523.acs.PS3',
    'raw/npc_default.bbn.PS3': 'L01_LandOfChocolate/loc/challengeModeDesignStr/assets/shared/bonebindings/npc_default_8d2f91.bbn.PS3',
    'raw/bunny.preinstanced': 'L01_LandOfChocolate/loc/challengeModeDesignStr/assets/chars/bunnyDark/boundExport/lod5_model_f960ed.dff.PS3.preinstanced',
    'models/bunny.glb': 'L01_LandOfChocolate/loc/challengeModeDesignStr/assets/chars/bunnyDark/boundExport/lod5_model_f960ed.dff.PS3.glb',
    'raw/weapon.acs.PS3': 'L02_BartmanBegins/brt/storyModeDesignStr/assets/shared/collision/weapons/weapon_baton_b3eaf7.acs.PS3',
    'raw/baton.preinstanced': 'L02_BartmanBegins/brt/storyModeDesignStr/assets/weapons/baton/boundExport/baton_1c9034.dff.PS3.preinstanced',
    'models/baton.glb': 'L02_BartmanBegins/brt/storyModeDesignStr/assets/weapons/baton/boundExport/baton_1c9034.dff.PS3.glb',
    'raw/homer.acs.PS3': 'A2_Characters/globalFolder/chars/homerFh0gh0hh0h0str/assets/shared/collision/homer_847125.acs.PS3',
    'raw/player_default.bbn.PS3': 'A2_Characters/globalFolder/chars/homerFh0gh0hh0h0str/assets/shared/bonebindings/player_default_e2c561.bbn.PS3',
}


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    module = project.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=module / 'GameFiles/PS3-EU-FullFlattened-audio_reorg-isRenamed')
    args = parser.parse_args()
    source = args.source.resolve()
    # Resolve every source before copying so a stale alias cannot create a partial set.
    missing = [relative for relative in SAMPLES.values() if not (source / relative).is_file()]
    if missing:
        raise SystemExit('Missing source samples:\n' + '\n'.join(missing))
    rows = []
    for target, relative in SAMPLES.items():
        original = source / relative
        dest = project / 'samples' / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, dest)
        data = dest.read_bytes()
        rows.append({'local': 'res://samples/' + target, 'source_id': 'ps3-eu-flattened',
                     'source_relative_path': relative, 'size': len(data),
                     'sha256': hashlib.sha256(data).hexdigest(),
                     'generated_export': dest.suffix.lower() == '.glb'})
    gdignore = project / 'samples/raw/.gdignore'
    if gdignore.exists():
        gdignore.unlink()
    (project / 'samples/manifest.json').write_text(json.dumps({'files': rows}, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(rows)} files ({sum(row["size"] for row in rows):,} bytes) in ignored samples/.')


if __name__ == '__main__':
    main()
