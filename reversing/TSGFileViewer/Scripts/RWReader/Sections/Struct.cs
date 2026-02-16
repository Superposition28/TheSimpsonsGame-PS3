using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	public class Struct : Section
	{
		public Struct()
		{
			Name = "Struct";
			Header.ClumpID = 0x00000001;
			DataStorageType = SectionDataStorage.NoData;
			CanHaveChildren = false;
		}

		public override void Deserialize(BinaryReader reader)
		{
			Raw = reader.ReadBytes(Header.Size);
		}
	}
}