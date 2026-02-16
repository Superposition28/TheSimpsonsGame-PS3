using System;
using System.Collections.Generic;
using RWReader.Sections;
using String = RWReader.Sections.String;

namespace RWReader
{
	public class SectionManager
	{
		public Dictionary<int, Type> SectionMap = new();

		public SectionManager()
		{
			SectionMap = new Dictionary<int, Type>()
			{
				{ 0x00000001, typeof(Struct) },
				{ 0x00000002, typeof(String) },
				{ 0x00000003, typeof(Extension) },
				{ 0x00000006, typeof(Texture) },
				{ 0x00000007, typeof(Material) },
				{ 0x00000008, typeof(MaterialList) },
				{ 0x0000000E, typeof(FrameList) },
				{ 0x0000000F, typeof(Geometry) },
				{ 0x00000010, typeof(Clump) },
				{ 0x00000014, typeof(Atomic) },
				{ 0x00000015, typeof(TextureNative) },
				{ 0x00000016, typeof(TextureDictionary) },
				{ 0x0000001A, typeof(GeometryList) },
				{ 0x0000001F, typeof(RightToRender) },
				{ 0x00000116, typeof(SkinPLG) },
				{ 0x0000011E, typeof(HAnimPLG) },
				{ 0x00000120, typeof(MaterialEffectsPLG) },
				{ 0x0000050E, typeof(BinMeshPLG) },
				{ 0x0000EA2F, typeof(EARSTexturePlugin) },
				{ 0x0000EA33, typeof(EARSMesh) },
			};
		}

		private int _sectionID = 0;

		public Section GetSection(SectionHeader header)
		{
			Type sectionType;
			if (!SectionMap.ContainsKey(header.ClumpID))
			{
				sectionType = typeof(UnknownSection);
			}
			else
			{
				sectionType = SectionMap[header.ClumpID];
			}

			var instance = (Section)Activator.CreateInstance(sectionType);
			instance.Header = header;
			instance.ID = _sectionID++;
			return instance;
		}
	}
}
