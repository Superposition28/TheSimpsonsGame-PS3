using System;
using System.IO;

namespace RWReader.Sections
{
	public class Atomic : Section
	{
		public Atomic()
		{
			Name = "Atomic";
			Header.ClumpID = 0x00000014;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int FrameIndex;
		public int GeometryIndex;
		public int Flags;
		public int Unused;

		public override void Deserialize(BinaryReader reader)
		{
			FrameIndex = reader.ReadInt32();
			GeometryIndex = reader.ReadInt32();
			Flags = reader.ReadInt32();
			Unused = reader.ReadInt32();
		}
	}
}
