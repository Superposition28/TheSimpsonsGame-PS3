using System;

namespace RWReader
{
	[Serializable]
	public struct LibraryID
	{
		public int RWVersion;
		public int MajorRevision;
		public int MinorRevision;
		public int BinaryRevision;
		public int LibraryBuild;

		public int Version;

		public LibraryID(int libId)
		{
			if ((libId & 0xFFFF0000) != 0)
			{
				LibraryBuild = libId & 0xFFFF;
				Version = (libId >> 14 & 0x3FF00) + 0x30000 | (libId >> 16 & 0x3F);
			}
			else
			{
				// Old version, does not subtract 0x3000 and does not store library build
				LibraryBuild = 0;
				Version = libId << 8;
			}

			RWVersion = (Version & 0b1100_0000_0000_0000_00) >> 16;
			MajorRevision = (Version & 0b0011_1100_0000_0000_00) >> 12;
			MinorRevision = (Version & 0b0000_0011_1100_0000_00) >> 8;
			BinaryRevision = (Version & 0b0000_0000_0011_1111_11);
		}
	}
}