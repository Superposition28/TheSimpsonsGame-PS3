using System;
using System.IO;

namespace RWReader.Sections
{
	public class EARSTexturePlugin : Section
	{
		public EARSTexturePlugin()
		{
			Name = "EARS Texture Plugin";
			Header.ClumpID = 0x0000EA2F;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public uint TextureNameHash;
		public uint FQPathHash;

		public override void Deserialize(BinaryReader reader)
		{
			TextureNameHash = reader.ReadUInt32BigEndian();
			FQPathHash = reader.ReadUInt32BigEndian();
		}
	}
}
