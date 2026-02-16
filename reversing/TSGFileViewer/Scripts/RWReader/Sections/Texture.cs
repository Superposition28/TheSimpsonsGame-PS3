using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	public class Texture : Section
	{
		public Texture()
		{
			Name = "Texture";
			Header.ClumpID = 0x00000006;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public FilteringMode TexFilteringMode;
		public AddressingMode UAddressing;
		public AddressingMode VAddressing;
		public bool UseMipMaps;

		public override void Deserialize(BinaryReader reader)
		{
			// 8 bits - texture filtering
			// 4 bits - u addressing
			// 4 bits - v addressing
			// 1 bit - uses mip levels(?)
			// 15 bits - padding(?)

			TexFilteringMode = (FilteringMode)reader.ReadByte();
			var uvAddressing = reader.ReadByte();
			UAddressing = (AddressingMode)((uvAddressing & 0xF0) >> 4);
			VAddressing = (AddressingMode)(uvAddressing & 0x0F);
			var mipmapByte = reader.ReadByte();
			UseMipMaps = (mipmapByte & 0b10000000) == 1;
			reader.ReadBytes(3); // TODO : is this really unused?
		}

		public string GetTextureName() => GetChildren<String>()[0].Value;
		public string GetAlphaName() => GetChildren<String>()[1].Value;

		public enum FilteringMode
		{
			None,
			Nearest,
			Linear,
			MipNearest,
			MipLinear,
			LinearMipNearest,
			LinearMipLinear
		}

		public enum AddressingMode
		{
			None,
			Wrap,
			Mirror,
			Clamp,
			Border
		}
	}
}