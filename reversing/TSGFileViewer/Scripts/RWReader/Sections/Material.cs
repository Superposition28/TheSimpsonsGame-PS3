using System;
using System.IO;
using UnityEngine;

namespace RWReader.Sections
{
	[Serializable]
	public class Material : Section
	{
		public Material()
		{
			Name = "Material";
			Header.ClumpID = 0x00000007;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int Flags;
		public Color Color;
		public int Unused;
		public bool IsTextured;

		public float Ambient;
		public float Specular;
		public float Diffuse;

		public override void Deserialize(BinaryReader reader)
		{
			Flags = reader.ReadInt32();
			Color = reader.ReadRwRGBA();
			Unused = reader.ReadInt32();
			IsTextured = reader.ReadBool32();

			if (Header.LibraryID.Version > 0x30400)
			{
				Ambient = reader.ReadSingle();
				Specular = reader.ReadSingle();
				Diffuse = reader.ReadSingle();
			}
		}
	}
}