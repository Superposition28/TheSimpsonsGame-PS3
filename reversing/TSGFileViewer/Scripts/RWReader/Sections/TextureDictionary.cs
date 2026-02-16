using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	public class TextureDictionary : Section
	{
		public TextureDictionary()
		{
			Name = "Texture Dictionary";
			Header.ClumpID = 0x00000016;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int TextureCount;

		/*
		 * 1 - D3D8
		 * 2 - D3D9
		 * 6 - PS2
		 * 8 - XBOX
		 * 10 - PS3?
		 */
		public short DeviceID;

		public override void Deserialize(BinaryReader reader)
		{
			if (Header.LibraryID.Version >= 0x36000)
			{
				TextureCount = reader.ReadInt16();
				DeviceID = reader.ReadInt16();
			}
			else
			{
				TextureCount = reader.ReadInt32();
			}
		}
	}
}