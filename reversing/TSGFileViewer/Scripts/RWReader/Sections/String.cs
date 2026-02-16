using System;
using System.IO;
using System.Text;

namespace RWReader.Sections
{
	[Serializable]
	public class String : Section
	{
		public String()
		{
			Name = "String";
			Header.ClumpID = 0x00000002;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public string Value;

		public override void Deserialize(BinaryReader reader)
		{
			var builder = new StringBuilder();

			var currentByte = reader.ReadByte();
			while (currentByte != 0x00)
			{
				builder.Append(Encoding.ASCII.GetString(new[] { currentByte })); // this seems dumb, better way?
				currentByte = reader.ReadByte();
			}

			Value = builder.ToString();
		}
	}
}