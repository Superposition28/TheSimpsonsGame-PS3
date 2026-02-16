using System;
using System.IO;

namespace RWReader.Sections
{
	public class Clump : Section
	{
		public Clump()
		{
			Name = "Clump";
			Header.ClumpID = 0x00000010;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int AtomicNumber;
		public int LightNumber;
		public int CameraNumber;

		public override void Deserialize(BinaryReader reader)
		{
			AtomicNumber = reader.ReadInt32();

			if (Header.LibraryID.Version > 0x33000)
			{
				LightNumber = reader.ReadInt32();
				CameraNumber = reader.ReadInt32();
			}
		}
	}
}