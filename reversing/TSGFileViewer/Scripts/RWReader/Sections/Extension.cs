using System;

namespace RWReader.Sections
{
	public class Extension : Struct
	{
		public Extension()
		{
			Name = "Extension";
			Header.ClumpID = 0x00000003;
			DataStorageType = SectionDataStorage.NoData;
			CanHaveChildren = true;
		}
	}
}