using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	public class GeometryList : Section
	{
		public GeometryList()
		{
			Name = "Geometry List";
			Header.ClumpID = 0x0000001A;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int GeometryCount;

		public override void Deserialize(BinaryReader reader)
		{
			GeometryCount = reader.ReadInt32();
		}
	}
}