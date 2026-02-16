using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	public class UnknownSection : Section
	{
		public UnknownSection()
		{
			Name = "Unknown";
			CanHaveChildren = false;
		}

		public override void Deserialize(BinaryReader reader)
		{

		}
	}
}