using System;

namespace RWReader
{
	[Serializable]
	public struct SectionHeader
	{
		public int ClumpID;
		public int Size;
		public LibraryID LibraryID;
	}
}
